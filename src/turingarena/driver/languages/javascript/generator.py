from turingarena.driver.generator import InterfaceCodeGen, SkeletonCodeGen


class JavaScriptCodeGen(InterfaceCodeGen):
    @classmethod
    def build_callable_declarator(cls, callable):
        arguments = ", ".join(cls.build_parameter(p) for p in callable.parameters)
        return f"{callable.name}({arguments})"

    @classmethod
    def build_parameter(cls, parameter):
        return f"{parameter.name}"


class JavaScriptSkeletonCodeGen(JavaScriptCodeGen, SkeletonCodeGen):
    def generate(self):
        yield "async function init() {}"
        yield from self.visit(self.interface.body)

    def var_statement(self, statement):
        names = ", ".join(v.name for v in statement.variables)
        yield f"let {names};"

    def callback_statement(self, statement):
        callback = statement.callback
        yield f"function {build_callable_declarator(callback)}" + "{"
        with self.indent():
            yield from self.visit(callback.body)
        yield "}"
        yield

    def main_statement(self, statement):
        yield
        yield "async function main() {"
        with self.indent():
            yield "__load_source__(); // load user source file"
            yield from self.visit(statement.body)
        yield "}"

    def any_statement(self, statement):
        generators = {
            "checkpoint": lambda: ["print(0);"],
            "flush": lambda: ["flush();"],
            "exit": lambda: ["exit(0);"],
            "continue": lambda: ["continue;"],
            "break": lambda: ["break;"],
            "return": lambda: [f"return {self.visit(statement.value)};"],
            "function": lambda: [],
        }
        return generators[statement.statement_type]()

    def visit_Call(self, statement):
        method_name = statement.method.name
        parameters = ", ".join(self.visit(p) for p in statement.parameters)
        if statement.return_value is not None:
            return_value = self.visit(statement.return_value)
            yield f"{return_value} = {method_name}({parameters});"
        else:
            yield f"{method_name}({parameters});"

    def alloc_statement(self, statement):
        for argument in statement.arguments:
            arg = self.visit(argument)
            size = self.visit(statement.size)
            yield f"{arg} = Array({size});"

    def visit_Print(self, statement):
        args = ", ".join(self.visit(v) for v in statement.arguments)
        yield f"print({args});"

    def visit_Read(self, statement):
        args = ", ".join(self.visit(arg) for arg in statement.arguments)
        yield f"[{args}] = await readIntegers();"

    def visit_If(self, statement):
        condition = self.visit(statement.condition)
        yield f"if ({condition})" " {"
        with self.indent():
            yield from self.visit(statement.then_body)
        if statement.else_body is not None:
            yield "} else {"
            with self.indent():
                yield from self.visit(statement.else_body)
        yield "}"

    def visit_For(self, statement):
        index_name = statement.index.variable.name
        size = self.visit(statement.index.range)
        yield f"for (let {index_name} = 0; {index_name} < {size}; {index_name}++)" " {"
        with self.indent():
            yield from self.visit(statement.body)
        yield "}"

    def visit_Loop(self, loop_statement):
        yield "while (true) {"
        with self.indent():
            yield from self.visit(loop_statement.body)
        yield "}"

    def build_switch_condition(self, variable, labels):
        variable = self.visit(variable)
        result = f"{variable} == {self.visit(labels[0])}"
        for label in labels[1:]:
            result += f" || {variable} == {self.visit(label)}"
        return result

    def visit_Switch(self, switch_statement):
        cases = [case for case in switch_statement.cases]
        yield f"if ({self.build_switch_condition(switch_statement.variable, cases[0].labels)}) " "{"
        with self.indent():
            yield from self.visit(cases[0].body)
        for case in cases[1:]:
            yield "}" f" else if ({self.build_switch_condition(switch_statement.variable, case.labels)}) " "{"
            with self.indent():
                yield from self.visit(case.body)
        if switch_statement.default:
            yield "} else {"
            with self.indent():
                yield from self.visit(switch_statement.default)
        yield "}"


class JavaScriptTemplateCodeGen(JavaScriptCodeGen):
    def visit_MethodPrototype(self, m):
        yield
        yield f"function {self.build_callable_declarator(m.function)}" + "{"
        with self.indent():
            yield "// TODO"
        yield "}"
