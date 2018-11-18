import logging
from abc import abstractmethod
from functools import partial

from turingarena.driver.interface.analysis.references import ReferenceActionAnalyzer
from turingarena.driver.interface.common import AbstractSyntaxNodeWrapper, memoize
from turingarena.driver.interface.seq import SequenceNode
from turingarena.driver.interface.step import Step

logger = logging.getLogger(__name__)


class AbstractBlock(SequenceNode):
    @property
    @memoize
    def flat_inner_nodes(self):
        return tuple(self._generate_flat_inner_nodes())

    @abstractmethod
    def _generate_flat_inner_nodes(self):
        pass

    def validate(self):
        for node in self.children:
            # TODO: analysis of unreachable code
            yield from node.validate()

    @property
    @memoize
    def children(self):
        return tuple(self._generate_children())

    def _generate_children(self):
        from turingarena.driver.interface.stmtanalysis import StatementAnalyzer
        group = []
        for node in self.flat_inner_nodes:
            can_be_grouped = StatementAnalyzer().can_be_grouped(node)

            if can_be_grouped and len(self._group_directions(group + [node])) <= 1:
                group.append(node)
                continue

            if group:
                yield Step(tuple(group))
                group.clear()

            if not can_be_grouped:
                yield node
            else:
                group.append(node)

        if group:
            yield Step(tuple(group))

    def _group_directions(self, group):
        from turingarena.driver.interface.stmtanalysis import StatementAnalyzer
        return {d for n in group for d in StatementAnalyzer().declaration_directions(n)}

    def _describe_node(self):
        yield "block"
        for n in self.children:
            yield from self._indent_all(n.node_description)


class AbstractContextBlock(AbstractBlock):
    __slots__ = []

    def _generate_flat_inner_nodes(self):
        inner_context = self.context._replace(main_block=False)
        for b in self._get_flat_children_builders():
            node = b(inner_context)
            if not node.is_relevant:
                continue
            yield node
            inner_context = inner_context.with_reference_actions(node.reference_actions)

    @abstractmethod
    def _get_flat_children_builders(self):
        pass


class Block(AbstractContextBlock, AbstractSyntaxNodeWrapper):
    __slots__ = []

    def _get_flat_children_builders(self):
        for ast in self.ast.statements:
            from turingarena.driver.interface.statements.statements import statement_classes
            for cls in statement_classes[ast.statement_type]:
                yield partial(cls, ast)
