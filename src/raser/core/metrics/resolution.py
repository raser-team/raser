"""Width of the core of a distribution, as a resolution."""

import math

import numpy as np
from scipy.optimize import minimize

ROUNDS = 6
MINIMUM_EVENTS = 20


def truncated_gaussian(values, low, high):
    """Unbinned maximum likelihood of a Gaussian seen only inside [low, high]:
    the density is the Gaussian over the part of it inside the window, so the
    values inside the window alone give the width of the whole Gaussian.

    values : (events,), all inside the window

    Returns (mean, mean_error, sigma, sigma_error) in the unit of the values.
    """
    scale = float(np.std(values))
    if scale == 0:
        raise ValueError("all values in the window are equal")
    # in units of their spread the values, the steps and the widths are near 1
    x = np.asarray(values, dtype="float64") / scale
    a, b = low / scale, high / scale
    n = len(x)

    def negative_log_likelihood(parameters):
        mean, sigma = parameters[0], math.exp(parameters[1])
        z = (x - mean) / sigma
        inside = 0.5 * (
            math.erf((b - mean) / (sigma * math.sqrt(2)))
            - math.erf((a - mean) / (sigma * math.sqrt(2)))
        )
        return float(0.5 * np.dot(z, z) + n * (parameters[1] + math.log(inside)))

    # the mean stays inside the window, or the fit runs off to a tail
    fit = minimize(
        negative_log_likelihood,
        [float(x.mean()), 0.0],
        method="L-BFGS-B",
        bounds=[(a, b), (None, None)],
    )
    if not fit.success:
        raise ArithmeticError(f"the fit in [{low}, {high}] did not converge: {fit.message}")
    # the errors are from the curvature of the likelihood at its minimum
    step = 1e-4
    curvature = np.empty((2, 2))
    for i, j in ((0, 0), (0, 1), (1, 1)):
        di, dj = step * np.eye(2)[i], step * np.eye(2)[j]
        curvature[i, j] = curvature[j, i] = (
            negative_log_likelihood(fit.x + di + dj)
            - negative_log_likelihood(fit.x + di - dj)
            - negative_log_likelihood(fit.x - di + dj)
            + negative_log_likelihood(fit.x - di - dj)
        ) / (4 * step**2)
    mean_error, ln_sigma_error = np.sqrt(np.diag(np.linalg.inv(curvature)))
    mean, sigma = fit.x[0], math.exp(fit.x[1])
    return (
        mean * scale,
        mean_error * scale,
        sigma * scale,
        sigma * ln_sigma_error * scale,
    )


def core_width(values, window=None):
    """Width of the core of the values.

    The window starts at the median +- 8 median absolute deviations, or at
    the given one, and is narrowed to mean +- 2 sigma of a Gaussian fitted
    inside it, at most ROUNDS times; it stops when sigma changes by less
    than 0.5 % or the window no longer shrinks.

    values : (events,)
    window : (low, high) of the first round, in the unit of the values

    Returns a dict in the unit of the values:
      events        number of values
      window        (low, high) of the last fit
      window_events number of values inside it
      rounds        number of fits
      mean, mean_error, sigma, sigma_error   of the last fit
      sigma68       half of the 16 % to 84 % interval of the values inside
                    the window; equal to sigma for a Gaussian
    """
    values = np.asarray(values, dtype="float64")
    if values.ndim != 1:
        raise ValueError(f"values have shape {values.shape}, expected (events,)")
    if len(values) < MINIMUM_EVENTS:
        raise ValueError(f"{len(values)} values, fewer than {MINIMUM_EVENTS}")
    if window is None:
        median = np.median(values)
        deviation = np.median(np.abs(values - median))
        low = max(median - 8 * deviation, values.min())
        high = min(median + 8 * deviation, values.max())
    else:
        low, high = window
    if not low < high:
        raise ValueError(f"the window [{low}, {high}] is empty")

    fit = None
    for round_ in range(1, ROUNDS + 1):
        inside = values[(values >= low) & (values <= high)]
        if len(inside) < MINIMUM_EVENTS:
            if fit is None:
                raise ValueError(
                    f"{len(inside)} of {len(values)} values are inside "
                    f"[{low}, {high}], fewer than {MINIMUM_EVENTS}"
                )
            break
        previous = fit
        mean, mean_error, sigma, sigma_error = truncated_gaussian(inside, low, high)
        fit = {
            "events": len(values),
            "window": (float(low), float(high)),
            "window_events": len(inside),
            "rounds": round_,
            "mean": mean,
            "mean_error": mean_error,
            "sigma": sigma,
            "sigma_error": sigma_error,
            "sigma68": float(np.diff(np.quantile(inside, [0.16, 0.84]))[0] / 2),
        }
        if previous is not None and abs(sigma - previous["sigma"]) <= 5e-3 * previous["sigma"]:
            break
        new_low, new_high = mean - 2 * sigma, mean + 2 * sigma
        if new_low < low or new_high > high:
            break
        if (high - low) - (new_high - new_low) <= 1e-3 * (high - low):
            break
        low, high = new_low, new_high
    assert fit is not None
    return fit
