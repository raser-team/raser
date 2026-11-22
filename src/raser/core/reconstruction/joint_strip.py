"""Two-parameter strip response with independently calibrated joint regions."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from .response import (
    StripResponse,
    _minimum,
    _sublevel_projection,
    conformal_quantile,
    merge_intervals,
)

JOINT_LEVELS = (0.68, 0.95)


@dataclass
class JointStripResponse:
    response: StripResponse
    projection: np.ndarray
    offset: np.ndarray
    metadata: dict
    cuts: dict = field(default_factory=dict)
    response_cut: float | None = None

    @classmethod
    def fit(cls, features, labels, *, floors, metadata, usable):
        x, y, f = (np.asarray(v, dtype=float) for v in (features, labels, floors))
        good = np.asarray(usable, dtype=bool)
        n = len(metadata["channels"])
        prefix, samples = 9 * n, int(metadata["feature_config"]["shape_samples"])
        if (
            n not in (2, 3)
            or x.ndim != 2
            or x.shape[1] != prefix + n * samples
            or y.shape != (len(x), 2)
            or f.shape != (x.shape[1],)
            or good.shape != (len(x),)
            or good.sum() < 16
            or not all(np.isfinite(v).all() for v in (x, y, f))
            or np.any(f <= 0)
        ):
            raise ValueError(
                "Joint fitting needs complete readout features and (slope, entrance um) labels"
            )
        # The response domain is a true product, rather than a coupled track locus.
        qs, us = np.unique(y[:, 0]), np.unique(y[:, 1])
        if len(qs) < 3 or len(us) < 3 or len(np.unique(y, axis=0)) != len(qs) * len(us):
            raise ValueError(
                "Training must independently cross at least three slopes and three entrance positions"
            )
        shape = x[good, prefix:]
        offset = np.zeros(x.shape[1])
        offset[prefix:] = shape.mean(axis=0)
        _, singular, axes = np.linalg.svd(shape - offset[prefix:], full_matrices=False)
        count = min(24, len(axes))
        projection = np.zeros((x.shape[1], prefix + count))
        projection[:prefix, :prefix] = np.eye(prefix)
        projection[prefix:, prefix:] = axes[:count].T
        values = (x - offset) @ projection
        transformed_floors = np.sqrt(f * f @ (projection * projection))
        response = StripResponse.fit(
            values,
            y,
            floors=transformed_floors,
            metadata={"method": "charge-waveform-position"},
            usable=good,
        )
        info = dict(
            metadata,
            schema="raser-joint-strip-v1",
            estimator="joint-position",
            target_coordinates=["signed dx/dz", "entrance x in um"],
            feature_projection={
                "kind": "training-only pulse PCA",
                "components": count,
                "retained_variance": float(
                    np.sum(singular[:count] ** 2) / np.sum(singular**2)
                )
                if np.any(singular)
                else 1.0,
            },
            retained_hypotheses=len(response.parameters),
            excluded_training_hypotheses=response.metadata[
                "excluded_training_hypotheses"
            ],
            training_usable=int(good.sum()),
            uncertainty_scope="Split-conformal joint slope/entrance regions for independent exchangeable eligible in-domain events; projections retain simultaneous coverage; selection-conditional coverage evaluated separately.",
        )
        return cls(response, projection, offset, info)

    def project(self, features):
        x = np.asarray(features, dtype=float)
        if x.shape != self.offset.shape or not np.isfinite(x).all():
            raise ValueError("Joint readout feature contract differs")
        return (x - self.offset) @ self.projection

    def best_fit(self, features):
        result = self.response.best_fit(self.project(features))
        return {
            "slope": result["slope"],
            "entrance_um": result["impact_um"],
            "distance": result["distance"],
        }

    def loss_at(self, features, target):
        p = np.asarray(target, dtype=float)
        if p.shape != (2,) or not np.isfinite(p).all():
            raise ValueError("Finite (slope, entrance um) target required")
        residual = self.response._residual(self.project(features))
        for cell in self.response.simplices:
            parameters = self.response.parameters[cell]
            c = np.linalg.solve((parameters[1:] - parameters[0]).T, p - parameters[0])
            if min(c) >= -1e-9 and c.sum() <= 1 + 1e-9:
                r = residual[cell[0]] + c @ (residual[cell[1:]] - residual[cell[0]])
                return float(r @ r)
        return None

    def calibrate(self, features, labels, *, usable, event_ids):
        if self.cuts:
            raise ValueError("Joint interval calibration is immutable")
        y = np.asarray(labels, dtype=float)
        if (
            y.shape != (len(features), 2)
            or len(usable) != len(y)
            or len(event_ids) != len(y)
        ):
            raise ValueError(
                "Calibration features, two-coordinate labels and IDs must match"
            )
        if len(set(event_ids)) != len(event_ids) or set(event_ids) & set(
            self.metadata.get("training_event_ids", [])
        ):
            raise ValueError("Joint calibration must be independent of training")
        scores, distances, used, excluded = [], [], [], []
        for x, p, ok, event_id in zip(features, y, usable, event_ids):
            at_truth = self.loss_at(x, p) if ok else None
            if at_truth is None:
                excluded.append(
                    {
                        "event_id": event_id,
                        "reason": "feature_ineligible"
                        if not ok
                        else "truth_outside_response_domain",
                    }
                )
                continue
            best = self.best_fit(x)
            scores.append(max(0.0, at_truth - best["distance"]))
            distances.append(best["distance"])
            used.append(event_id)
        self.cuts = {
            str(level): conformal_quantile(scores, level) for level in JOINT_LEVELS
        }
        self.response_cut = conformal_quantile(distances, 0.99)
        self.metadata.update(
            interval_used=len(used),
            interval_used_event_ids=used,
            interval_excluded=excluded,
            interval_joint_scores=scores,
            interval_fit_distances=distances,
            confidence_levels=list(JOINT_LEVELS),
        )

    def confidence_set(self, features, level):
        if str(level) not in self.cuts:
            raise ValueError("Independent joint interval calibration required")
        x = self.project(features)
        residual = self.response._residual(x)
        best = self.response.best_fit(x)
        limit = best["distance"] + self.cuts[str(level)]
        selected, q_intervals, u_intervals = [], [], []
        for index, cell in enumerate(self.response.simplices):
            p, r = self.response.parameters[cell], residual[cell]
            q = _sublevel_projection(p, r, limit)
            u = _sublevel_projection(p[:, ::-1], r, limit)
            if q is not None and u is not None:
                selected.append(index)
                q_intervals.append(q)
                u_intervals.append(u)
        # Connected components use actual shared-edge sublevel intersections.
        parent = {i: i for i in selected}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        owners: dict[tuple[int, ...], int] = {}
        for index in selected:
            vertices = self.response.simplices[index]
            for count in (1, 2):
                for shared in combinations(sorted(vertices), count):
                    key = tuple(int(v) for v in shared)
                    v = np.array(key, dtype=int)
                    if (
                        _minimum(self.response.parameters[v], residual[v])[1]
                        <= limit + 1e-9
                    ):
                        if key in owners:
                            parent[find(index)] = find(owners[key])
                        else:
                            owners[key] = index
        components = len({find(i) for i in selected})
        qs, us = merge_intervals(q_intervals), merge_intervals(u_intervals)
        angles = [
            [math.degrees(math.atan(a)), math.degrees(math.atan(b))] for a, b in qs
        ]
        low, high = (
            self.response.parameters.min(axis=0),
            self.response.parameters.max(axis=0),
        )
        limited = any(
            abs(a - low[d]) < 1e-8 or abs(b - high[d]) < 1e-8
            for d, intervals in enumerate([qs, us])
            for a, b in intervals
        )
        return {
            "level": level,
            "slope_intervals": qs,
            "angle_intervals_deg": angles,
            "entrance_intervals_um": us,
            "total_angle_width_deg": sum(b - a for a, b in angles),
            "total_entrance_width_um": sum(b - a for a, b in us),
            "components": components,
            "multimodal": components > 1,
            "support_limited": limited,
            "joint_loss_limit": limit,
            "joint_cell_indices": selected,
            "representation": "Response simplices intersected with the recorded quadratic loss sublevel; coordinate intervals are projections, not a rectangular joint set.",
        }

    def predict(self, features, *, usable=True, reason="ok"):
        if not self.cuts or self.response_cut is None:
            raise ValueError("Independent joint interval calibration required")
        if not usable:
            return {
                "accepted": False,
                "status": reason,
                "best_fit": None,
                "confidence_sets": {},
            }
        best = self.best_fit(features)
        sets = {
            str(level): self.confidence_set(features, level) for level in JOINT_LEVELS
        }
        region = sets["0.95"]
        status = (
            "outside_response_support"
            if best["distance"] > self.response_cut
            else "multiple_joint_solutions"
            if region["multimodal"]
            else "support_limited_joint_region"
            if region["support_limited"]
            else "ok"
        )
        return {
            "accepted": status == "ok",
            "status": status,
            "best_fit": best,
            "best_angle_deg": math.degrees(math.atan(best["slope"])),
            "confidence_sets": sets,
            "response_distance_cut": self.response_cut,
        }

    def save(self, path):
        if not self.cuts or self.response_cut is None:
            raise ValueError("Only independently calibrated joint models may be saved")
        with open(path, "xb") as stream:
            np.savez_compressed(
                stream,
                parameters=self.response.parameters,
                means=self.response.means,
                simplices=self.response.simplices,
                precision=self.response.precision,
                projection=self.projection,
                offset=self.offset,
                metadata=np.array(json.dumps(self.metadata, allow_nan=False)),
                calibration=np.array(
                    json.dumps(
                        {"cuts": self.cuts, "response_cut": self.response_cut},
                        allow_nan=False,
                    )
                ),
            )

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as d:
            metadata = json.loads(str(d["metadata"]))
            calibration = json.loads(str(d["calibration"]))
            if metadata.get("schema") != "raser-joint-strip-v1":
                raise ValueError("Unsupported joint strip model schema")
            response = StripResponse(
                d["parameters"],
                d["means"],
                d["simplices"],
                d["precision"],
                {"estimator": "continuous"},
            )
            model = cls(response, d["projection"], d["offset"], metadata, **calibration)
        n, k = len(response.parameters), response.means.shape[1]
        if (
            response.parameters.shape != (n, 2)
            or response.precision.shape != (k, k)
            or response.simplices.ndim != 2
            or response.simplices.shape[1] != 3
            or np.any(response.simplices < 0)
            or np.any(response.simplices >= n)
            or model.projection.shape != (len(model.offset), k)
            or len(metadata.get("channels", [])) not in (2, 3)
            or not all(
                np.isfinite(v).all()
                for v in [
                    response.parameters,
                    response.means,
                    response.precision,
                    model.projection,
                    model.offset,
                ]
            )
            or model.response_cut is None
            or not math.isfinite(model.response_cut)
            or model.response_cut < 0
            or any(
                not math.isfinite(model.cuts.get(str(level), float("nan")))
                or model.cuts[str(level)] < 0
                for level in JOINT_LEVELS
            )
        ):
            raise ValueError("Invalid joint strip model arrays or calibration")
        np.linalg.cholesky(response.precision)
        return model
