"""Continuous strip response fits and independently calibrated confidence sets."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
from scipy.spatial import Delaunay

LEVELS = (0.68, 0.84, 0.95, 0.975)


def conformal_quantile(scores, level):
    """Finite-sample split-conformal rank; insufficient samples are an error."""
    x = np.sort(np.asarray(scores, dtype=float))
    if x.ndim != 1 or not len(x) or not np.isfinite(x).all() or not 0 < level < 1:
        raise ValueError(
            "Finite nonempty calibration scores and level in (0,1) required"
        )
    rank = math.ceil((len(x) + 1) * level)
    if rank > len(x):
        raise ValueError(f"Need more independent interval events for level {level}")
    return float(x[rank - 1])


def _minimum(parameters, residual):
    """Global quadratic minimum on a line segment or triangle."""
    candidates = [(parameters[0], residual[0])]
    if len(parameters) == 3:
        basis = residual[1:] - residual[0]
        c = np.linalg.lstsq(basis.T, -residual[0], rcond=None)[0]
        if np.min(c) >= 0 and c.sum() <= 1:
            candidates.append(
                (
                    parameters[0] + c @ (parameters[1:] - parameters[0]),
                    residual[0] + c @ basis,
                )
            )
    for i, j in combinations(range(len(parameters)), 2):
        delta = residual[j] - residual[i]
        norm = float(delta @ delta)
        a = float(np.clip(-residual[i] @ delta / norm, 0, 1)) if norm > 0 else 0.0
        candidates.append(
            (
                parameters[i] + a * (parameters[j] - parameters[i]),
                residual[i] + a * delta,
            )
        )
    p, r = min(candidates, key=lambda item: float(item[1] @ item[1]))
    return p, float(r @ r)


def _sublevel_projection(parameters, residual, limit):
    """Exact projection of a quadratic sublevel intersected with one simplex."""
    bounds = []
    tolerance = 1e-10 * max(1.0, abs(limit))
    for i, j in combinations(range(len(parameters)), 2):
        delta = residual[j] - residual[i]
        a, b, c = (
            float(delta @ delta),
            float(2 * residual[i] @ delta),
            float(residual[i] @ residual[i] - limit),
        )
        if a < 1e-24:
            if c <= tolerance:
                bounds.extend([parameters[i, 0], parameters[j, 0]])
            continue
        discriminant = b * b - 4 * a * c
        if discriminant < -tolerance:
            continue
        radius = math.sqrt(max(0.0, discriminant))
        lo, hi = max(0.0, (-b - radius) / (2 * a)), min(1.0, (-b + radius) / (2 * a))
        if lo <= hi + 1e-12:
            bounds.extend(
                parameters[i, 0]
                + np.array([lo, hi]) * (parameters[j, 0] - parameters[i, 0])
            )
    if len(parameters) == 3:
        basis = residual[1:] - residual[0]
        information = basis @ basis.T
        if np.linalg.eigvalsh(information).min() > 1e-12 * max(
            1.0, float(np.linalg.norm(information))
        ):
            inverse = np.linalg.inv(information)
            centre = -inverse @ basis @ residual[0]
            r = residual[0] + centre @ basis
            remaining = limit - float(r @ r)
            direction = parameters[1:, 0] - parameters[0, 0]
            variance = float(direction @ inverse @ direction)
            if remaining >= -tolerance and variance > 0:
                offset = inverse @ direction * math.sqrt(max(0.0, remaining) / variance)
                for c in (centre - offset, centre + offset):
                    if np.min(c) >= -1e-10 and c.sum() <= 1 + 1e-10:
                        bounds.append(parameters[0, 0] + c @ direction)
    return [float(min(bounds)), float(max(bounds))] if bounds else None


def merge_intervals(intervals):
    merged: list[list[float]] = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(hi, merged[-1][1])
        else:
            merged.append([float(lo), float(hi)])
    return merged


@dataclass
class StripResponse:
    parameters: np.ndarray
    means: np.ndarray
    simplices: np.ndarray
    precision: np.ndarray
    metadata: dict
    cuts: dict = field(default_factory=dict)
    response_cut: float | None = None
    projection: np.ndarray | None = None
    offset: np.ndarray | None = None

    @classmethod
    def fit(
        cls, features, labels, *, floors, metadata, estimator="continuous", usable=None
    ):
        x, y, floors = (
            np.asarray(features, dtype=float),
            np.asarray(labels, dtype=float),
            np.asarray(floors, dtype=float),
        )
        if x.ndim != 2 or y.shape != (len(x), 2) or floors.shape != (x.shape[1],):
            raise ValueError(
                "Strip response needs feature rows and (signed slope, impact um) labels"
            )
        if not all(np.isfinite(a).all() for a in (x, y, floors)) or np.any(floors <= 0):
            raise ValueError(
                "Response training values and positive floors must be finite"
            )
        good = (
            np.ones(len(x), dtype=bool)
            if usable is None
            else np.asarray(usable, dtype=bool)
        )
        if good.shape != (len(x),) or estimator not in {
            "continuous",
            "timing-baseline",
        }:
            raise ValueError("Invalid strip training mask or estimator")
        raw_count = x.shape[1]
        projection = np.eye(raw_count)
        offset = np.zeros(raw_count)
        projection_info: dict = {"kind": "identity"}
        if estimator == "continuous" and metadata.get("method") == "joint":
            prefix = 21
            if (
                raw_count != prefix + 3 * metadata["feature_config"]["shape_samples"]
                or good.sum() < 2
            ):
                raise ValueError(
                    "Joint strip input requires compact observables and three complete pulse shapes"
                )
            shape = x[good, prefix:]
            offset[prefix:] = shape.mean(axis=0)
            _, singular, axes = np.linalg.svd(
                shape - offset[prefix:], full_matrices=False
            )
            count = min(16, len(axes))
            projection = np.zeros((raw_count, prefix + count))
            projection[:prefix, :prefix] = np.eye(prefix)
            projection[prefix:, prefix:] = axes[:count].T
            variance = (
                float(np.sum(singular[:count] ** 2) / np.sum(singular**2))
                if np.any(singular)
                else 1.0
            )
            projection_info = {
                "kind": "training_only_pulse_shape_pca",
                "compact_prefix": prefix,
                "shape_components": count,
                "retained_training_shape_variance": variance,
            }
            x = (x - offset) @ projection
            floors = np.sqrt(floors**2 @ projection**2)
        point_rows, means, cell_rows, residuals, excluded = [], [], [], [], []
        if estimator == "continuous":
            for point in np.unique(y, axis=0):
                indices = np.flatnonzero(np.all(y == point, axis=1) & good)
                if len(indices) < 8:
                    excluded.append(
                        {"parameters": point.tolist(), "usable": len(indices)}
                    )
                    continue
                mean = x[indices].mean(axis=0)
                point_rows.append(point)
                means.append(mean)
                residuals.extend(x[indices] - mean)
            points = np.asarray(point_rows)
            if (
                len(points) < 6
                or np.linalg.matrix_rank(points - points.mean(axis=0)) != 2
            ):
                raise ValueError(
                    "Need at least six non-collinear slope/impact hypotheses with eight usable replicates each"
                )
            cells = Delaunay(points / np.ptp(points, axis=0)).simplices
        else:
            # Forward timing law: adjacent CFD differences = intercept + coefficient / q.
            # Separate signs retain the leading-electrode change and exclude q=0.
            for sign in (-1, 1):
                indices = np.flatnonzero(good & (sign * y[:, 0] > 1e-8))
                if len(indices) < 8 or len(np.unique(y[indices, 0])) < 3:
                    raise ValueError(
                        "Timing baseline needs three nonzero slopes and eight usable events per sign"
                    )
                inverse_q = 1 / y[indices, 0]
                design = np.column_stack([np.ones(len(indices)), inverse_q])
                coefficients = np.linalg.lstsq(design, x[indices], rcond=None)[0]
                start = len(point_rows)
                for r in (float(inverse_q.min()), float(inverse_q.max())):
                    point_rows.append([r])
                    means.append(np.array([1.0, r]) @ coefficients)
                cell_rows.append([start, start + 1])
                residuals.extend(x[indices] - design @ coefficients)
            points = np.asarray(point_rows)
            cells = np.asarray(cell_rows, dtype=int)
        residual = np.asarray(residuals)
        if len(residual) <= len(points):
            raise ValueError("Insufficient independent response residuals")
        covariance = residual.T @ residual / (len(residual) - len(points))
        covariance = (
            0.8 * covariance + 0.2 * np.diag(np.diag(covariance)) + np.diag(floors**2)
        )
        info = {
            **metadata,
            "schema": "raser-strip-response-v3",
            "estimator": estimator,
            "target_dimensions": 1,
            "kind": "strip",
            "retained_hypotheses": len(points),
            "excluded_training_hypotheses": excluded,
            "training_usable": int(good.sum()),
            "feature_count": x.shape[1],
            "raw_feature_count": raw_count,
            "feature_projection": projection_info,
            "parameter_coordinates": "slope_impact"
            if estimator == "continuous"
            else "inverse_slope",
            "estimate_scope": "continuous interpolation within the recorded response domain",
            "uncertainty_scope": "split-conformal profile sets; marginal coverage for exchangeable eligible in-domain events; selection-conditional coverage requires separate evaluation",
        }
        return cls(
            points,
            np.asarray(means),
            np.asarray(cells, dtype=int),
            np.linalg.inv(covariance),
            info,
            projection=projection,
            offset=offset,
        )

    @property
    def slope_bounds(self):
        q = self.parameters[:, 0]
        if self.metadata["estimator"] == "timing-baseline":
            return [sorted((1 / q[a], 1 / q[b])) for a, b in self.simplices]
        return [[float(q.min()), float(q.max())]]

    def _residual(self, features):
        x = np.asarray(features, dtype=float)
        if self.projection is not None:
            if x.shape != (self.projection.shape[0],) or not np.isfinite(x).all():
                raise ValueError(
                    "Features differ from the continuous response contract"
                )
            x = (x - self.offset) @ self.projection
        if x.shape != self.means.shape[1:] or not np.isfinite(x).all():
            raise ValueError("Features differ from the continuous response contract")
        return (self.means - x) @ np.linalg.cholesky(self.precision)

    def best_fit(self, features):
        residual = self._residual(features)
        candidates = [
            _minimum(self.parameters[cell], residual[cell]) for cell in self.simplices
        ]
        p, loss = min(candidates, key=lambda item: item[1])
        q = float(1 / p[0] if self.metadata["estimator"] == "timing-baseline" else p[0])
        return {
            "slope": q,
            "impact_um": float(p[1]) if len(p) == 2 else None,
            "distance": loss,
        }

    def profile(self, features, slope):
        if not math.isfinite(slope):
            raise ValueError("Profile slope must be finite")
        residual, losses = self._residual(features), []
        baseline = self.metadata["estimator"] == "timing-baseline"
        if baseline and slope == 0:
            return None
        coordinate = 1 / slope if baseline else slope
        for cell in self.simplices:
            p, w = self.parameters[cell], residual[cell]
            intersections = []
            for i, j in combinations(range(len(cell)), 2):
                a, b = p[i, 0], p[j, 0]
                if a == b:
                    if abs(coordinate - a) <= 1e-12:
                        intersections.extend([(p[i], w[i]), (p[j], w[j])])
                elif min(a, b) - 1e-12 <= coordinate <= max(a, b) + 1e-12:
                    f = np.clip((coordinate - a) / (b - a), 0, 1)
                    intersections.append(
                        (p[i] + f * (p[j] - p[i]), w[i] + f * (w[j] - w[i]))
                    )
            if intersections:
                if len(intersections) == 1:
                    losses.append(float(intersections[0][1] @ intersections[0][1]))
                else:
                    a, b = (
                        min(intersections, key=lambda t: t[0][-1]),
                        max(intersections, key=lambda t: t[0][-1]),
                    )
                    losses.append(
                        _minimum(np.asarray([a[0], b[0]]), np.asarray([a[1], b[1]]))[1]
                    )
        return min(losses) if losses else None

    def calibrate_intervals(self, features, slopes, *, usable, event_ids):
        if self.cuts:
            raise ValueError("Interval calibration is immutable; fit a fresh response")
        statistics = self.interval_statistics(
            features, slopes, usable=usable, event_ids=event_ids
        )
        self.cuts, self.response_cut = statistics["cuts"], statistics["response_cut"]
        self.metadata.update(
            interval_used=statistics["used"],
            interval_excluded=statistics["excluded"],
            interval_used_event_ids=statistics["used_ids"],
            interval_profile_scores=statistics["profile_scores"],
            interval_fit_distances=statistics["fit_distances"],
            confidence_levels=list(LEVELS),
            response_support_level=0.99,
        )

    def interval_statistics(self, features, slopes, *, usable, event_ids):
        if (
            len(features) != len(slopes)
            or len(features) != len(usable)
            or len(features) != len(event_ids)
        ):
            raise ValueError("Interval records, labels and masks must match")
        if len(set(event_ids)) != len(event_ids) or set(event_ids).intersection(
            self.metadata.get("training_event_ids", [])
        ):
            raise ValueError(
                "Interval calibration IDs must be independent of response training"
            )
        scores, distances, excluded, used_ids = [], [], [], []
        for x, q, ok, event_id in zip(features, slopes, usable, event_ids):
            if not ok:
                excluded.append({"event_id": event_id, "reason": "feature_ineligible"})
                continue
            at_truth = self.profile(x, float(q))
            if at_truth is None:
                excluded.append(
                    {"event_id": event_id, "reason": "truth_outside_calibrated_domain"}
                )
                continue
            best = self.best_fit(x)
            scores.append(max(0.0, at_truth - best["distance"]))
            distances.append(best["distance"])
            used_ids.append(event_id)
        # 99% response support also uses independent records, never fitting residuals.
        response_cut = conformal_quantile(distances, 0.99)
        cuts = {str(level): conformal_quantile(scores, level) for level in LEVELS}
        return {
            "cuts": cuts,
            "response_cut": response_cut,
            "used": len(scores),
            "excluded": excluded,
            "used_ids": used_ids,
            "profile_scores": scores,
            "fit_distances": distances,
        }

    def confidence_set(self, features, level, *, cut=None):
        if cut is None and str(level) not in self.cuts:
            raise ValueError(
                "Requested confidence level has no independent calibration"
            )
        threshold = self.cuts[str(level)] if cut is None else float(cut)
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("Profile confidence cut must be finite and nonnegative")
        best = self.best_fit(features)
        residual = self._residual(features)
        limit = best["distance"] + threshold
        intervals = []
        for cell in self.simplices:
            interval = _sublevel_projection(
                self.parameters[cell], residual[cell], limit
            )
            if interval is not None:
                if self.metadata["estimator"] == "timing-baseline":
                    interval = sorted([1 / interval[0], 1 / interval[1]])
                intervals.append(interval)
        intervals = merge_intervals(intervals)
        angles = [
            [math.degrees(math.atan(q)) for q in interval] for interval in intervals
        ]
        edges = [float(q) for pair in self.slope_bounds for q in pair]
        limited = any(
            abs(q - edge) < 1e-8
            for interval in intervals
            for q in interval
            for edge in edges
        )
        return {
            "level": level,
            "slope_intervals": intervals,
            "angle_intervals_deg": angles,
            "total_width_deg": sum(hi - lo for lo, hi in angles),
            "support_limited": limited,
            "multimodal": len(intervals) > 1,
        }

    def predict(
        self, features, *, usable=True, reason="ok", cuts=None, response_cut=None
    ):
        if not self.cuts or self.response_cut is None:
            raise ValueError(
                "Independent interval calibration is required before prediction"
            )
        if not usable:
            return {
                "accepted": False,
                "status": reason,
                "best_fit": None,
                "confidence_sets": {},
            }
        cuts = self.cuts if cuts is None else cuts
        response_cut = self.response_cut if response_cut is None else response_cut
        best = self.best_fit(features)
        sets = {
            str(level): self.confidence_set(features, level, cut=cuts[str(level)])
            for level in LEVELS
        }
        selected = sets["0.95"]
        status = (
            "outside_response_support"
            if best["distance"] > response_cut
            else "multimodal_angle"
            if selected["multimodal"]
            else "support_limited_interval"
            if selected["support_limited"]
            else "ok"
        )
        return {
            "accepted": status == "ok",
            "status": status,
            "best_fit": best,
            "confidence_sets": sets,
            "response_distance_cut": response_cut,
        }

    def save(self, path):
        with open(path, "xb") as stream:
            np.savez_compressed(
                stream,
                parameters=self.parameters,
                means=self.means,
                simplices=self.simplices,
                precision=self.precision,
                metadata=np.array(json.dumps(self.metadata, allow_nan=False)),
                projection=self.projection
                if self.projection is not None
                else np.eye(self.means.shape[1]),
                offset=self.offset
                if self.offset is not None
                else np.zeros(self.means.shape[1]),
                calibration=np.array(
                    json.dumps(
                        {"cuts": self.cuts, "response_cut": self.response_cut},
                        allow_nan=False,
                    )
                ),
            )

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as data:
            calibration = json.loads(str(data["calibration"]))
            model = cls(
                data["parameters"],
                data["means"],
                data["simplices"],
                data["precision"],
                json.loads(str(data["metadata"])),
                **calibration,
                projection=data["projection"],
                offset=data["offset"],
            )
        d = 2 if model.metadata.get("estimator") == "continuous" else 1
        if (
            model.metadata.get("schema") != "raser-strip-response-v3"
            or model.metadata.get("estimator") not in {"continuous", "timing-baseline"}
            or model.parameters.ndim != 2
            or model.parameters.shape[1] != d
            or model.means.ndim != 2
            or len(model.means) != len(model.parameters)
            or model.simplices.ndim != 2
            or model.simplices.shape[1] != d + 1
            or not len(model.simplices)
            or not np.issubdtype(model.simplices.dtype, np.integer)
            or model.simplices.min() < 0
            or model.simplices.max() >= len(model.parameters)
            or model.precision.shape != (model.means.shape[1], model.means.shape[1])
            or model.projection is None
            or model.offset is None
            or model.projection.ndim != 2
            or model.projection.shape[1] != model.means.shape[1]
            or model.offset.shape != (model.projection.shape[0],)
            or not np.isfinite(model.projection).all()
            or not np.isfinite(model.offset).all()
            or not all(
                np.isfinite(a).all()
                for a in (model.parameters, model.means, model.precision)
            )
            or not np.allclose(model.precision, model.precision.T)
            or np.linalg.eigvalsh(model.precision).min() <= 0
            or any(not math.isfinite(c) or c < 0 for c in model.cuts.values())
            or set(model.cuts) != {str(level) for level in LEVELS}
            or model.response_cut is None
            or not math.isfinite(model.response_cut)
            or model.response_cut < 0
        ):
            raise ValueError("Invalid continuous strip response model")
        if d == 1 and any(
            np.prod(model.parameters[cell, 0]) <= 0 for cell in model.simplices
        ):
            raise ValueError("Inverse-slope branches must stay away from zero")
        if any(
            np.linalg.matrix_rank(
                model.parameters[cell][1:] - model.parameters[cell][0]
            )
            != d
            for cell in model.simplices
        ):
            raise ValueError("Response cells must span their parameter coordinates")
        return model
