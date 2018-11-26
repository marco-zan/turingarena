import logging
from collections import namedtuple
from functools import partial
from typing import Optional

from turingarena.driver.interface.diagnostics import Diagnostic
from turingarena.driver.interface.expressions import IntLiteral, VariableReference
from turingarena.driver.interface.requests import RequestSignature, CallRequestSignature
from turingarena.driver.interface.statements.call import AcceptCallbacks, CallReturn
from turingarena.driver.interface.statements.callback import CallbackStart
from turingarena.driver.interface.statements.for_loop import For
from turingarena.driver.interface.statements.io import Read, Checkpoint
from turingarena.driver.interface.statements.loop import Loop
from turingarena.driver.interface.variables import Variable, Reference, \
    VariableDeclaration, ReferenceDirection, VariableAllocation, ReferenceDeclaration, ReferenceResolution
from turingarena.util.visitor import visitormethod

logger = logging.getLogger(__name__)


class InterfaceContext(namedtuple("InterfaceContext", [
    "methods",
    "constants",
])):
    @property
    def methods_by_name(self):
        return {m.name: m for m in self.methods}

    @property
    def main_block_context(self):
        return self.initial_context.with_reference_actions(
            a(c.variable.as_reference())
            for c in self.constants
            for a in [
                partial(ReferenceDeclaration, dimensions=0),
                ReferenceResolution,
            ]
        )

    @property
    def initial_context(self):
        return INITIAL_CONTEXT._replace(global_context=self)


class StatementContext(namedtuple("StatementContext", [
    "global_context",
    "prev_reference_actions",
    "index_variables",
    "main_block",
    "in_loop",
])):
    def with_reference_actions(self, actions):
        actions = tuple(actions)
        assert all(
            a.reference is not None
            for a in actions
        )
        return self._replace(
            prev_reference_actions=self.prev_reference_actions + actions
        )

    def get_resolved_references(self):
        return {
            a.reference
            for a in self.prev_reference_actions
            if isinstance(a, ReferenceResolution)
        }

    @property
    def declared_variables(self):
        return {
            a.reference.variable
            for a in self.prev_reference_actions
            if isinstance(a, ReferenceDeclaration)
        }

    @property
    def variable_mapping(self):
        return {v.name: v for v in self.declared_variables}

    def with_index_variable(self, variable):
        return self._replace(
            index_variables=self.index_variables + (variable,),
        )

    def with_loop(self):
        return self._replace(in_loop=True)

    def expression(self, **kwargs):
        options = dict(
            index_count=0,
            declaring=False,
            reference=False,
            resolved=False,
        )
        options.update(kwargs)
        return ExpressionContext(
            statement_context=self,
            **options,
        )

    @visitormethod
    def validate(self, n):
        return []

    def validate_InterfaceDefinition(self, n):
        for method in n.methods:
            yield from self.validate(method)
        yield from self.validate(n.main_block)

    def validate_Read(self, n):
        for exp in n.arguments:
            yield from self.validate_reference_declaration(exp)

    def validate_Write(self, n):
        for exp in n.arguments:
            yield from self.validate(exp)

    def validate_Switch(self, n):
        yield from self.validate(n.value)

        if len(n.cases) == 0:
            yield Diagnostic(Diagnostic.Messages.EMPTY_SWITCH_BODY, parseinfo=n.ast.parseinfo)

        labels = []
        for case in n.cases:
            for label in case.labels:
                if label in labels:
                    yield Diagnostic(Diagnostic.Messages.DUPLICATED_CASE_LABEL, label, parseinfo=n.ast.parseinfo)
                labels.append(label)
            yield from self.validate(case)

    def validate_Case(self, n):
        for l in n.labels:
            if not isinstance(l, IntLiteral):
                yield Diagnostic(
                    Diagnostic.Messages.SWITCH_LABEL_NOT_LITERAL,
                    parseinfo=n.ast.labels.parseinfo,
                )
        yield from self.validate(n.body)

    def validate_CallbackImplementation(self, n):
        yield from self.validate(n.prototype)

    def validate_Return(self, n):
        yield from self.validate_reference_declaration(n.value)

    def validate_SequenceNode(self, n):
        for child in n.children:
            yield from self.validate(child)

    def validate_MethodPrototype(self, n):
        for callback in n.callbacks:
            yield from self.validate(callback)

    def validate_CallbackPrototype(self, n):
        for callback in n.callbacks:
            yield Diagnostic(
                Diagnostic.Messages.UNEXPECTED_CALLBACK,
                callback.name,
                parseinfo=callback.ast.parseinfo,
            )
        for parameter in n.parameter_declarations:
            if parameter.variable.dimensions:
                yield Diagnostic(
                    Diagnostic.Messages.CALLBACK_PARAMETERS_MUST_BE_SCALARS,
                    parseinfo=parameter.ast.parseinfo,
                )

    def validate_For(self, n):
        yield from self.validate(n.index.range)
        yield from self.validate(n.body)

    def validate_Loop(self, n):
        yield from self.validate(n.body)

    def validate_Break(self, n):
        if not n.context.in_loop:
            yield Diagnostic(Diagnostic.Messages.UNEXPECTED_BREAK, parseinfo=n.ast.parseinfo)

    def validate_If(self, n):
        yield from self.validate(n.condition)
        for branch in n.branches:
            yield from self.validate(branch)

    def validate_Call(self, n):
        if n.method_name not in n.context.global_context.methods_by_name:
            yield Diagnostic(
                Diagnostic.Messages.METHOD_NOT_DECLARED,
                n.method_name,
                parseinfo=n.ast.parseinfo,
            )
            return

        method = n.method
        if method.has_return_value and n.return_value is None:
            yield Diagnostic(
                Diagnostic.Messages.CALL_NO_RETURN_EXPRESSION, method.name,
                parseinfo=n.ast.parseinfo,
            )
        if not method.has_return_value and n.return_value is not None:
            yield Diagnostic(
                Diagnostic.Messages.METHOD_DOES_NOT_RETURN_VALUE, method.name,
                parseinfo=n.ast.return_value.parseinfo,
            )

    def validate_CallArgumentsResolve(self, n):
        method = n.method
        if method is None:
            return

        if len(n.arguments) != len(method.parameters):
            yield Diagnostic(
                Diagnostic.Messages.CALL_WRONG_ARGS_NUMBER,
                method.name, len(method.parameters), len(n.arguments),
                parseinfo=n.ast.parseinfo,
            )
        for parameter, expression in zip(method.parameters, n.arguments):
            yield from self.validate(expression)
            dimensions = n.context.dimensions(expression)
            if dimensions != parameter.dimensions:
                yield Diagnostic(
                    Diagnostic.Messages.CALL_WRONG_ARGS_TYPE,
                    parameter.name, method.name, parameter.dimensions, dimensions,
                    parseinfo=expression.ast.parseinfo,
                )

    def validate_CallReturn(self, n):
        method = n.method
        if method is None:
            return

        if n.return_value is not None:
            yield from self.validate(n.return_value)

    def validate_IntermediateNode(self, n):
        return ()

    def validate_VariableReference(self, e):
        if not e.variable_name in self.variable_mapping:
            yield Diagnostic(
                Diagnostic.Messages.VARIABLE_NOT_DECLARED,
                e.variable_name,
                parseinfo=e.ast.parseinfo,
            )

    def validate_Subscript(self, e):
        yield from self.validate(e.array)
        yield from self.validate(e.index)

    def validate_IntLiteral(self, e):
        return ()

    def validate_reference_declaration(self, e, index_count=0):
        return self._validate_reference_declaration(e, index_count)

    @visitormethod
    def _validate_reference_declaration(self, e, index_count):
        pass

    def _validate_reference_declaration_VariableReference(self, e, index_count):
        if e.variable_name in self.variable_mapping:
            yield Diagnostic(
                Diagnostic.Messages.VARIABLE_REUSED,
                e.variable_name,
                parseinfo=e.ast.parseinfo,
            )

    def _validate_reference_declaration_Subscript(self, e, index_count):
        yield from self.validate_reference_declaration(e.array, index_count + 1)
        yield from self.validate(e.index)

        reversed_indexes = self.index_variables[::-1]
        try:
            expected_index = reversed_indexes[index_count]
        except IndexError:
            expected_index = None

        if expected_index is None:
            yield Diagnostic(
                Diagnostic.Messages.UNEXPECTED_ARRAY_INDEX,
                parseinfo=e.index.ast.parseinfo,
            )
            return

        if not isinstance(e.index, VariableReference) or e.index.variable_name != expected_index.variable.name:
            yield Diagnostic(
                Diagnostic.Messages.WRONG_ARRAY_INDEX,
                expected_index.variable.name,
                parseinfo=e.index.ast.parseinfo,
            )

    def _validate_reference_declaration_IntLiteral(self, e, index_count):
        yield "unexpected literal"  # TODO: make a Diagnostic

    def variable_declarations(self, n):
        return frozenset(self._get_variable_declarations(n))

    def _get_variable_declarations(self, n):
        types = [
            Read,
            CallReturn,
            For,
        ]

        if not any(isinstance(n, t) for t in types):
            return
        for a in self.reference_actions(n):
            if a.reference.index_count == 0 and isinstance(a, ReferenceDeclaration):
                yield VariableDeclaration(a.reference.variable, a.dimensions)

    def variable_allocations(self, n):
        return list(self._get_allocations(n))

    @visitormethod
    def _get_allocations(self, n):
        pass

    def _get_allocations_For(self, n):
        for a in self.reference_actions(n.body):
            if not isinstance(a, ReferenceDeclaration):
                continue
            if a.dimensions == 0:
                continue
            yield VariableAllocation(
                variable=a.reference.variable,
                indexes=self.index_variables[-a.reference.index_count + 1:],
                size=n.index.range,
                dimensions=a.dimensions - a.reference.index_count,
            )

    def _get_allocations_IntermediateNode(self, n):
        return []

    def comment(self, n):
        return self._get_comment(n)

    @visitormethod
    def _get_comment(self, n):
        pass

    def _get_comment_MainExit(self, n):
        return "terminate"

    def _get_comment_PrintCallbackRequest(self, n):
        return "requesting a callback"

    def _get_comment_PrintCallbackIndex(self, n):
        return f"index of this callback: {n.callback_index} = {n.implementation.name}"

    def _get_comment_PrintNoCallbacks(self, n):
        return "no more callbacks"

    def _get_comment_IntermediateNode(self, n):
        return None

    def is_relevant(self, n):
        "Whether this node should be kept in the parent block"
        return self._is_relevant(n)

    @visitormethod
    def _is_relevant(self, n):
        pass

    def _is_relevant_SwitchValueResolve(self, n):
        return not self.is_resolved(n.value)

    def _is_relevant_IfConditionResolve(self, n):
        return not self.is_resolved(n.condition)

    def _is_relevant_CallReturn(self, n):
        return n.return_value is not None

    def _is_relevant_PrintNoCallbacks(self, n):
        return n.method and n.method.callbacks

    def _is_relevant_AcceptCallbacks(self, n):
        return n.method and n.method.has_callbacks

    def _is_relevant_IntermediateNode(self, n):
        return True

    def reference_actions(self, n):
        return list(self._get_reference_actions(n))

    @visitormethod
    def _get_reference_actions(self, n):
        pass

    def _get_reference_actions_Read(self, n):
        for exp in n.arguments:
            yield self.reference_declaration(exp)

    def _get_reference_actions_Write(self, n):
        for exp in n.arguments:
            yield ReferenceResolution(self.reference(exp))

    def _get_reference_actions_Switch(self, n):
        for c in n.cases:
            yield from self.reference_actions(c.body)

    def _get_reference_actions_SwitchValueResolve(self, n):
        yield ReferenceResolution(self.reference(n.value))

    def _get_reference_actions_CallbackStart(self, n):
        for p in n.callback_implementation.parameters:
            yield ReferenceDeclaration(p.as_reference(), dimensions=0)

    def _get_reference_actions_Return(self, n):
        yield ReferenceResolution(self.reference(n.value))

    def _get_reference_actions_For(self, n):
        for a in self.reference_actions(n.body):
            r = a.reference
            if r.index_count > 0:
                yield a._replace(reference=r._replace(index_count=r.index_count - 1))

    def _get_reference_actions_CallArgumentsResolve(self, n):
        references = self.get_resolved_references()
        for p in n.arguments:
            if p.reference is not None and p.reference not in references:
                yield ReferenceResolution(p.reference)

    def _get_reference_actions_CallReturn(self, n):
        yield self.reference_declaration(n.return_value)

    def _get_reference_actions_SequenceNode(self, n):
        for child in n.children:
            if hasattr(child, 'context'):
                # FIXME: should strip context from nodes
                yield from child.context.reference_actions(child)
            else:
                yield from self.reference_actions(child)

    def _get_reference_actions_IntermediateNode(self, n):
        return []

    @visitormethod
    def can_be_grouped(self, n):
        pass

    def can_be_grouped_For(self, n):
        # no local references
        return all(
            a.reference.index_count > 0
            for a in self.reference_actions(n.body)
        ) and all(
            self.can_be_grouped(child)
            for child in n.body.children
        )

    NON_GROUPABLE = [
        Loop,
        AcceptCallbacks,
    ]

    def can_be_grouped_IntermediateNode(self, n):
        for t in self.NON_GROUPABLE:
            if isinstance(n, t):
                return False
        return True

    def declaration_directions(self, n):
        return frozenset(self._get_directions(n))

    DIRECTION_MAP = {
        ReferenceDirection.DOWNWARD: [
            Read,
        ],
        ReferenceDirection.UPWARD: [
            Checkpoint,
            CallbackStart,
            CallReturn,
        ],
    }

    @visitormethod
    def _get_directions(self, n):
        pass

    def _get_directions_SequenceNode(self, n):
        for child in n.children:
            yield from self.declaration_directions(child)

    def _get_directions_ControlStructure(self, n):
        for b in n.bodies:
            yield from self.declaration_directions(b)

    def _get_directions_AcceptCallbacks(self, n):
        for callback in n.callbacks:
            yield from self.declaration_directions(callback.body)

    def _get_directions_CallbackImplementation(self, n):
        return self.declaration_directions(n.body)

    def _get_directions_IntermediateNode(self, n):
        for d, ts in self.DIRECTION_MAP.items():
            for t in ts:
                if isinstance(n, t):
                    yield d

    def first_requests(self, n):
        logging.debug(f"first_requests({n.__class__.__name__}) -> {frozenset(self._get_first_requests(n))}")
        return frozenset(self._get_first_requests(n))

    @visitormethod
    def _get_first_requests(self, n):
        pass

    def _get_first_requests_Exit(self, n):
        yield RequestSignature("exit")

    def _get_first_requests_Call(self, n):
        yield CallRequestSignature("call", n.method_name)

    def _get_first_requests_SequenceNode(self, n):
        for child in n.children:
            logging.debug(f"first_requests_SequenceNode({n.__class__.__name__}) visiting {child.__class__.__name__}")
            for r in self.first_requests(child):
                if r is not None:
                    yield r
            if None not in self.first_requests(child):
                break
        else:
            yield None

    def _get_first_requests_For(self, n):
        yield None
        yield from self.first_requests(n.body)

    def _get_first_requests_Loop(self, n):
        yield None
        yield from self.first_requests(n.body)

    def _get_first_requests_Switch(self, n):
        for c in n.cases:
            yield from self.first_requests(c.body)

    def _get_first_requests_If(self, n):
        yield from self.first_requests(n.then_body)
        if n.else_body is not None:
            yield from self.first_requests(n.else_body)
        else:
            yield None

    def _get_first_requests_IntermediateNode(self, n):
        yield None

    @visitormethod
    def variable(self, e) -> Optional[Variable]:
        pass

    def variable_VariableReference(self, e):
        return self.variable_mapping.get(e.variable_name)

    def variable_Expression(self, e):
        return None

    @visitormethod
    def dimensions(self, e) -> int:
        pass

    def dimensions_Literal(self, e):
        return 0

    def dimensions_VariableReference(self, e):
        return self.variable(e).dimensions

    def dimensions_Subscript(self, e):
        array_dimensions = self.dimensions(e.array)
        if array_dimensions < 1:
            # not an array, fix
            return 0
        return array_dimensions - 1

    @visitormethod
    def reference(self, e) -> Optional[Reference]:
        pass

    def reference_VariableReference(self, e):
        variable = self.variable(e)
        if variable is not None:
            return variable.as_reference()

    def reference_Subscript(self, e):
        array_reference = self.reference(e.array)
        if array_reference is not None:
            return array_reference._replace(
                index_count=array_reference.index_count + 1,
            )

    def reference_Expression(self, e):
        return None

    def reference_declaration(self, e, dimensions=0) -> Optional[Reference]:
        return self._reference_declaration(e, dimensions)

    @visitormethod
    def _reference_declaration(self, e, dimensions):
        pass

    def _reference_declaration_VariableReference(self, e, dimensions):
        return ReferenceDeclaration(
            reference=Variable(name=e.variable_name, dimensions=dimensions).as_reference(),
            dimensions=dimensions,
        )

    def _reference_declaration_Subscript(self, e, dimensions):
        array_declaration = self.reference_declaration(e.array, dimensions + 1)
        if array_declaration is not None:
            return array_declaration._replace(
                reference=array_declaration.reference._replace(
                    index_count=array_declaration.reference.index_count + 1,
                ),
            )

    def _reference_declaration_Expression(self, e):
        return None

    @visitormethod
    def is_resolved(self, e) -> bool:
        pass

    def is_resolved_Reference(self, r):
        return r in self.get_resolved_references()

    def is_resolved_Literal(self, e):
        return True

    def is_resolved_VariableReference(self, e):
        return self.is_resolved(self.reference(e))

    def is_resolved_Subscript(self, e):
        return (
                self.is_resolved(self.reference(e))
                or self.is_resolved(e.array)
        )


INITIAL_CONTEXT = StatementContext(
    global_context=None,
    prev_reference_actions=(),
    index_variables=(),
    main_block=True,
    in_loop=False,
)


class ExpressionContext(namedtuple("ExpressionContext", [
    "statement_context",
    "declaring",
    "reference",
    "resolved",
    "index_count",
])):
    # TODO: wrap all options into an optional field of type ReferenceContext
    pass
