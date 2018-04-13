import ast
import os
import re

import pytest
from _pytest.assertion.rewrite import rewrite_asserts
from pytest import approx

from turingarena.loader import make_dummy_package, split_module, find_package_path
from turingarena.problem.python import HostPythonEvaluator


class EvaluationAssertionError(Exception):
    pass


class ProblemSolutionTestItem(pytest.Item):
    def __init__(self, parent, evaluator_name, source_name):
        super().__init__("test_solution", parent)
        self.evaluator_name = evaluator_name
        self.source_name = source_name

    def runtest(self):
        assertions = self.load_assertion_in_source()

        result = HostPythonEvaluator(
            self.evaluator_name,
            interface_name=self.evaluator_name,
        ).evaluate(self.source_name)

        for condition in assertions:
            mode = "exec"
            tree = ast.parse(f"assert {condition}\n", mode=mode)
            rewrite_asserts(tree)
            co = compile(tree, filename="<evaluation_assert>", mode=mode, dont_inherit=True)
            try:
                exec(co, dict(approx=approx), result._asdict())
            except AssertionError as e:
                raise EvaluationAssertionError(condition) from e
            except Exception as e:
                raise AssertionError(f"exception while checking: {condition}") from e

    def load_assertion_in_source(self):
        mod, rel_path = split_module(self.source_name, default_arg="interface.txt")
        with open(find_package_path(mod, rel_path)) as f:
            source_text = f.read()
        return re.findall(r"evaluation_assert\s+(.+)", source_text)

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, EvaluationAssertionError):
            [condition] = excinfo.value.args
            return "\n".join([
                excinfo.value.__cause__.args[0],
                "",
                f"Failed evaluation assert: {condition}",
            ])
        return super().repr_failure(excinfo)


class ProblemSolutionTestFile(pytest.File):
    def __init__(self, fspath, parent, evaluator_name, source_name):
        super().__init__(fspath=fspath, parent=parent)
        self.evaluator_name = evaluator_name
        self.source_name = source_name

    def collect(self):
        yield ProblemSolutionTestItem(self, self.evaluator_name, self.source_name)


def pytest_collect_file(path, parent):
    solutions_dir, source_filename = os.path.split(path)
    problem_dir, solutions_dirname = os.path.split(solutions_dir)

    if solutions_dirname != "solutions": return

    module_name = "__turingarena_current_test__"
    make_dummy_package(module_name, [problem_dir])

    return ProblemSolutionTestFile(
        fspath=path,
        parent=parent,
        evaluator_name=f"{module_name}",
        source_name=f"{module_name}:{path}",
    )
