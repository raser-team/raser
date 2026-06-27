import pytest


pytestmark = pytest.mark.root


def test_vector_arithmetic_and_length():
    from raser.supports.math import Vector

    a = Vector(1, 2, 3)
    b = Vector(4, 5, 6)

    assert a.add(b).components == [5, 7, 9]
    assert b.sub(a).components == [3, 3, 3]
    assert a.mul(3).components == [3, 6, 9]
    assert a.cross(b).components == [-3, 6, -3]
    assert a.get_length() == pytest.approx(14**0.5)


def test_calculate_gradient_uses_finite_difference():
    from raser.supports.math import calculate_gradient

    def plane(x, y, z):
        return 2 * x - 3 * y + 4 * z

    assert calculate_gradient(plane, [], [1.0, 2.0, 3.0]) == pytest.approx(
        [2.0, -3.0, 4.0]
    )


@pytest.mark.parametrize("value", ["1", "-2.5", "四"])
def test_is_number_accepts_numeric_strings(value):
    from raser.supports.math import is_number

    assert is_number(value)


@pytest.mark.parametrize("value", ["abc", object()])
def test_is_number_rejects_non_numeric_values(value):
    from raser.supports.math import is_number

    assert not is_number(value)
