"""The gradient of a quantity that is known between the ends of its mesh."""

STEP = 1.0e-5  # cm, the distance the difference is taken over


def gradient(function, point, ranges):
    """The gradient of `function` at `point`, per unit of its coordinates.

    `ranges` gives for every coordinate the two ends between which the
    function is known. The difference is taken over STEP centred on the
    point; where that would reach beyond an end of the range it stops at the
    end, which makes it one-sided there. A point outside the ranges is an error.
    """
    point = [float(value) for value in point]
    components = []
    for axis, (low, high) in enumerate(ranges):
        if not low <= point[axis] <= high:
            raise ValueError(
                f"{point[axis]} is outside the mesh, which runs from {low} to {high}"
            )
        below, above = point[axis] - STEP / 2, point[axis] + STEP / 2
        width = STEP
        if below < low or above > high:
            below, above = max(below, low), min(above, high)
            width = above - below
        lower, upper = list(point), list(point)
        lower[axis], upper[axis] = below, above
        components.append((float(function(*upper)) - float(function(*lower))) / width)
    return tuple(components)
