// Example Pyra files shown in the editor's "Examples" menu.
const PYRA_EXAMPLES = {
  "Linear system (miniF2F style)": `from pyra import prove, Real


@prove
def mathd_algebra_example(x: Real, y: Real, h0: "x + y == 7", h1: "3 * x + y == 45"):
    assert x == 19                    # a proof step: Pyra finds the reasoning
    assert x ** 2 - y ** 2 == 217     # the conclusion
`,
  "Triangle inequality": `"""|x + y| <= |x| + |y| over the reals, step by step."""
from pyra import prove, Real


@prove
def triangle_inequality(x: Real, y: Real):
    assert x <= abs(x)
    assert y <= abs(y)
    assert -abs(x) <= x
    assert -abs(y) <= y
    assert abs(x + y) <= abs(x) + abs(y)
`,
  "Squares are non-negative (SMT)": `from pyra import prove, Real


@prove
def square_nonneg(x: Real, y: Real):
    assert x * x >= 0
    assert x * x + y * y >= 2 * x * y
`,
  "A false step (shows Unproved)": `from pyra import prove, Real


@prove
def partly_wrong(x: Real):
    assert x * x >= 0
    assert x + 1 > x + 2              # false: never accepted
    assert x * x + 1 > 0
`,
  "Number theory (miniF2F mathd_numbertheory_236)": `from pyra import prove


@prove
def mathd_numbertheory_236():
    assert 1999 % 5 == 4
    assert 1999 ** 2000 % 5 == 1
`,
  "Logarithms and powers (loads a Mathlib supplement)": `import math
import pyra
from pyra import prove, Real

pyra.require(modules=["Mathlib.Analysis.SpecialFunctions.Pow.Real"])


@prove(hints=["Real.log_rpow", "Real.log_pos"])
def mathd_algebra_59(b: Real, h0: "Real(4) ** b + Real(2) ** 3 == 12"):
    assert Real(4) ** b == 4
    assert math.log(Real(4) ** b) == math.log(Real(4))
    assert math.log(Real(4) ** b) == b * math.log(Real(4))
    assert math.log(Real(4)) > 0
    assert b * math.log(Real(4)) == math.log(Real(4))
    assert b == 1
`,
};
