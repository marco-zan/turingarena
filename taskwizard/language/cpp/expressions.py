from taskwizard.generation.expressions import AbstractExpressionGenerator


class ExpressionGenerator(AbstractExpressionGenerator):
    pass


def generate_expression(expression):
    return ExpressionGenerator().visit(expression)