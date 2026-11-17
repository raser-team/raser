"""One formula for both the drift and the field solver.

A formula is written once, in the expression language of devsim
(`pow`, `exp`, `log`, `tanh`, `abs`, `ifelse(condition, a, b)`), in terms of
named variables (the electric field `E` in V/cm, the temperature `T` in K)
and named parameters. `value` evaluates it in Python, for the drift;
`devsim` gives the text the solver takes, each variable replaced by the
solver's expression for it. The solver takes the derivatives itself, with
devsim's `diff`.
"""

import math
import re

_FUNCTIONS = {
    "abs": abs,
    "exp": math.exp,
    "log": math.log,
    "pow": math.pow,
    "sqrt": math.sqrt,
    "tanh": math.tanh,
}


def _substitute(text, values):
    """`text` with each whole word in `values` replaced by its value in parentheses."""
    for name, value in values.items():
        text = re.sub(rf"(?<![\w.@]){re.escape(name)}(?![\w@])", f"({value})", text)
    return text


def _closing(text, start):
    """Index of the parenthesis closing the one at `start`, and of the commas at its level."""
    depth, commas = 0, []
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i, commas
        elif text[i] == "," and depth == 1:
            commas.append(i)
    raise ValueError(f"unbalanced parentheses in {text!r}")


def _python(text):
    """The Python expression of a devsim expression: `ifelse` evaluates only the branch taken."""
    match = re.search(r"(?<!\w)ifelse\(", text)
    if match is None:
        return text.replace("^", "**")
    opening = match.end() - 1
    closing, commas = _closing(text, opening)
    if len(commas) != 2:
        raise ValueError(f"ifelse takes three arguments in {text!r}")
    condition, if_true, if_false = (
        _python(text[a + 1 : b])
        for a, b in zip([opening, *commas], [*commas, closing])
    )
    return (
        _python(text[: match.start()])
        + f"(({if_true}) if ({condition}) else ({if_false}))"
        + _python(text[closing + 1 :])
    )


class Formula:
    """A formula of `variables`, its parameters put in as numbers.

    A parameter is a number or a text in the same language; a text may use
    the variables and the parameters given after it.
    """

    def __init__(self, text, variables, **parameters):
        self.variables = tuple(variables)
        self.text = _substitute(text, parameters)
        self._code = compile(_python(self.text), "<formula>", "eval")

    def value(self, **variables):
        """The formula at these values of its variables."""
        if set(variables) != set(self.variables):
            raise ValueError(f"the formula takes {self.variables}, not {tuple(variables)}")
        return eval(self._code, {"__builtins__": {}, **_FUNCTIONS}, variables)

    def devsim(self, **variables):
        """The text for devsim, each variable replaced by the solver's expression."""
        if set(variables) != set(self.variables):
            raise ValueError(f"the formula takes {self.variables}, not {tuple(variables)}")
        return _substitute(self.text, variables)
