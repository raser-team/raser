import math

import pytest

from raser.core.model.formula import Formula


def test_ifelse_evaluates_only_the_branch_taken() -> None:
    # At E = 0 the other branch divides by zero.
    formula = Formula("ifelse(E > 0, 1/E, ifelse(E < 0, -1/E, 0))", ["E"])

    assert formula.value(E=0.0) == 0.0
    assert formula.value(E=-4.0) == 0.25


def test_parameters_replace_whole_words_and_may_use_later_ones() -> None:
    # `h` must not be replaced inside `tanh`; `h` refers to `b`, given after it.
    formula = Formula("tanh(x)*h", ["x"], h="2*b", b=3)

    assert formula.value(x=1.0) == pytest.approx(6 * math.tanh(1.0))


def test_the_solver_text_is_the_same_formula_of_the_solver_variable() -> None:
    formula = Formula("ifelse(E > 1e5, a*exp(-b/E), 0)", ["E"], a=7.03e5, b=1.232e6)
    solver_text = formula.devsim(E="abs(ElectricField)")

    of_solver_variable = Formula(solver_text, ["ElectricField"])

    for field in (5e4, 3e5):
        assert of_solver_variable.value(ElectricField=-field) == formula.value(E=field)
    assert formula.value(E=3e5) > 0
