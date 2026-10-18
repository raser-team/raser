"""Figures for stereo strip placement and native six-channel waveforms."""

from __future__ import annotations

import math
from pathlib import Path


def draw_geometry(plan: dict, destination: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Arc, Polygon, Rectangle

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), layout="constrained")
    left, right = axes
    colors = ("#2c6896", "#b35131")
    for layer, color in zip(plan["layers"], colors):
        angle = math.radians(layer["rotation_z_deg"])
        matrix = np.array(
            [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
        )
        for center in (-20, 0, 20):
            polygon = (
                np.array(
                    [
                        [center - 9, -120],
                        [center + 9, -120],
                        [center + 9, 120],
                        [center - 9, 120],
                    ]
                )
                @ matrix.T
            )
            left.add_patch(
                Polygon(polygon, facecolor=color, alpha=0.3, edgecolor=color)
            )
            point = matrix @ np.array([center, 75])
            left.text(
                *point, f"{layer['name']}{center // 20 + 2}", ha="center", fontsize=9
            )
        z_center = layer["center_um"][2]
        thickness = layer["dimensions_um"][2]
        right.add_patch(
            Rectangle(
                (-40, z_center - thickness / 2),
                80,
                thickness,
                facecolor=color,
                alpha=0.22,
                edgecolor=color,
            )
        )
        right.plot([-40, 40], [z_center - thickness / 2] * 2, color=color, lw=3)
        right.text(
            46,
            z_center,
            f"{layer['name']}: {layer['rotation_z_deg']:+g} deg\n50 um Si\nfront 0 V / back -200 V",
            va="center",
            fontsize=10,
        )
        for depth in (4.0, 5.5):
            right.plot(
                [-40, 40], [z_center - thickness / 2 + depth] * 2, color=color, lw=0.8
            )
    half = plan["geometry"]["stereo_angle_deg"] / 2
    left.add_patch(
        Arc((0, 0), 100, 100, theta1=90 - half, theta2=90 + half, color="black")
    )
    left.text(0, 57, f"total {2 * half:g} deg", ha="center", fontsize=11)
    left.set(
        xlim=(-105, 105),
        ylim=(-105, 105),
        xlabel="global x (um)",
        ylabel="global y (um)",
        title="Top view: central region of 5 mm strips",
        aspect="equal",
    )
    left.text(-100, -96, "pitch 20 um | metal 18 um | gap 2 um", fontsize=9)
    separation = plan["geometry"]["center_separation_um"]
    right.annotate(
        "",
        (0, -plan["geometry"]["silicon_gap_um"] / 2),
        (0, plan["geometry"]["silicon_gap_um"] / 2),
        arrowprops={"arrowstyle": "<->"},
    )
    right.text(
        4, 0, f"gap {plan['geometry']['silicon_gap_um']:g} um", va="center", fontsize=10
    )
    right.set(
        xlim=(-60, 170),
        ylim=(separation / 2 + 45, -separation / 2 - 45),
        xlabel="schematic lateral direction",
        ylabel="global z (um)",
        title=f"Side view: center separation {separation:g} um",
    )
    right.set_xticks([])
    fig.suptitle(
        "strip_ayyouby_stack | two layers, six independent channels", fontsize=15
    )
    fig.savefig(destination, dpi=170, facecolor="white")
    plt.close(fig)


def draw_waveforms(plan: dict, root: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    with np.load(root / "waveforms.npz") as data:
        fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout="constrained")
        for row, layer in enumerate(plan["layers"]):
            for column in range(3):
                label = f"{layer['name']}_{column + 1}"
                ax = axes[row, column]
                ax.step(
                    data[f"time_s_{label}"] * 1e9,
                    data[f"current_A_{label}"] * 1e6,
                    where="mid",
                    color="#242424",
                    lw=1,
                )
                right = ax.twinx()
                right.step(
                    data[f"frontend_time_s_{label}"] * 1e9,
                    data[f"frontend_mV_{label}"],
                    where="mid",
                    color="#b35131",
                    lw=1,
                )
                ax.set(
                    xlim=(-0.5, 5),
                    xlabel="global time (ns)",
                    ylabel="current (uA)",
                    title=f"{layer['name']}/top{column + 1} | {layer['rotation_z_deg']:+g} deg",
                )
                right.set_ylabel("frontend (mV)", color="#b35131")
                ax.grid(axis="y", alpha=0.2)
        fig.suptitle(
            f"Stereo {plan['geometry']['stereo_angle_deg']:g} deg | one shared toy/MIP | slopes ({plan['truth']['slope_x']:g}, {plan['truth']['slope_y']:g})\nNative samples; separate y scales; no angular-resolution statistics",
            fontsize=13,
        )
        fig.savefig(root / "six_channel_waveforms_ns.png", dpi=160, facecolor="white")
        plt.close(fig)
