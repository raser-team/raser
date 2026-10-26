import csv
import math
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Existing RASER simulation output
ROOT = Path(
    "/root/raser/work/AlGaN_GaN_HEMT_TRANSPORT_V1/field"
)

profiles = sorted(
    ROOT.glob("*/HEMT_TRANSPORT_final_profile.csv"),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

if not profiles:
    raise SystemExit("[ERROR] No HEMT profile CSV found.")

PROFILE_FILE = profiles[0]
OUT = PROFILE_FILE.parent

def read_csv(path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

profile_rows = read_csv(PROFILE_FILE)

required = {
    "region", "x_um", "y_nm", "electrons_cm3"
}
if not profile_rows or not required.issubset(profile_rows[0]):
    raise SystemExit("[ERROR] Unexpected profile CSV schema.")

data = []
for r in profile_rows:
    if r["region"] not in ("AlGaN_barrier", "GaN_buffer"):
        continue
    try:
        x = float(r["x_um"])
        y = float(r["y_nm"])
        n = float(r["electrons_cm3"])
    except (ValueError, TypeError):
        continue

    if all(math.isfinite(v) for v in (x, y, n)) and n > 0:
        data.append({
            "region": r["region"],
            "x": x, "y": y, "n": n
        })

if not data:
    raise SystemExit("[ERROR] No valid semiconductor data.")

# --------------------------------------------------
# 1. Two-dimensional electron concentration map
# --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5.5))

scatter = ax.scatter(
    [r["x"] for r in data],
    [r["y"] for r in data],
    c=[math.log10(r["n"]) for r in data],
    s=5,
    marker="s",
    linewidths=0,
    rasterized=True,
)

ax.axhline(
    20.0, linestyle="--", linewidth=1,
    label="AlGaN/GaN interface"
)
ax.set_xlabel("Lateral position x (um)")
ax.set_ylabel("Depth from top surface (nm)")
ax.set_title("RASER HEMT: 2D Electron Concentration")
ax.set_ylim(
    max(r["y"] for r in data),
    min(r["y"] for r in data)
)
ax.legend()
fig.colorbar(
    scatter, ax=ax,
    label="log10 Electron concentration (cm^-3)"
)
fig.tight_layout()

for ext in ("png", "pdf"):
    fig.savefig(
        OUT / f"HEMT_TRANSPORT_electron_density_2D.{ext}",
        dpi=300
    )
plt.close(fig)

# --------------------------------------------------
# 2. Vertical profile at the channel centre
# --------------------------------------------------
gan = [r for r in data if r["region"] == "GaN_buffer"]
xs = sorted(set(r["x"] for r in gan))

if not xs:
    raise SystemExit("[ERROR] No GaN buffer data.")

x0 = min(xs, key=lambda x: abs(x - 2.5))
cut = sorted(
    [r for r in gan if abs(r["x"] - x0) < 1e-8],
    key=lambda r: r["y"]
)

def plot_profile(filename, zoom=False):
    pts = [
        r for r in cut
        if not zoom or 20 <= r["y"] <= 120
    ]
    if len(pts) < 2:
        print("[WARN] Insufficient points for", filename)
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogy(
        [r["y"] for r in pts],
        [r["n"] for r in pts],
        "o-", markersize=3, linewidth=1.5
    )
    ax.axvline(
        20.0, linestyle="--", linewidth=1,
        label="AlGaN/GaN interface"
    )
    ax.set_xlabel("Depth from top surface (nm)")
    ax.set_ylabel("Electron concentration (cm^-3)")
    ax.set_title(
        "RASER HEMT Electron Density Profile"
        + (" - Interface Zoom" if zoom else "")
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()

    for ext in ("png", "pdf"):
        fig.savefig(
            OUT / f"{filename}.{ext}",
            dpi=300
        )
    plt.close(fig)

plot_profile("HEMT_TRANSPORT_2DEG_profile")
plot_profile("HEMT_TRANSPORT_2DEG_interface_zoom", zoom=True)

# --------------------------------------------------
# 3. Classical excess sheet-density estimate vs x
# Integrate max(n - background, 0) over y=20-80 nm
# --------------------------------------------------
def interp(points, target_y):
    for (y1, n1), (y2, n2) in zip(points, points[1:]):
        if y1 <= target_y <= y2:
            if y2 == y1:
                return n1
            t = (target_y - y1) / (y2 - y1)
            return n1 + t * (n2 - n1)
    raise ValueError("Interpolation target outside profile.")

sheet_rows = []

for x in xs:
    pts = sorted(
        [(r["y"], r["n"]) for r in gan
         if abs(r["x"] - x) < 1e-8],
        key=lambda p: p[0]
    )

    deep = [n for y, n in pts if y >= 500]
    if len(deep) == 0 or pts[0][0] > 20 or pts[-1][0] < 80:
        continue

    background = statistics.median(deep)
    ys = sorted(
        [20.0, 80.0] +
        [y for y, n in pts if 20 < y < 80]
    )

    try:
        excess = [
            max(interp(pts, y) - background, 0.0)
            for y in ys
        ]
    except ValueError:
        continue

    # Trapezoidal integral; nm -> cm uses 1e-7.
    ns = sum(
        (excess[i] + excess[i + 1]) * 0.5
        * (ys[i + 1] - ys[i]) * 1e-7
        for i in range(len(ys) - 1)
    )

    sheet_rows.append({
        "x_um": x,
        "background_cm3": background,
        "sheet_density_cm-2": ns
    })

if sheet_rows:
    with (OUT / "HEMT_TRANSPORT_2DEG_sheet_density.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(sheet_rows[0]))
        writer.writeheader()
        writer.writerows(sheet_rows)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(
        [r["x_um"] for r in sheet_rows],
        [r["sheet_density_cm-2"] for r in sheet_rows],
        "o-", markersize=3, linewidth=1.5
    )
    ax.set_xlabel("Lateral position x (um)")
    ax.set_ylabel("Estimated excess sheet density (cm^-2)")
    ax.set_title("RASER HEMT: Interface Sheet-Density Estimate")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    for ext in ("png", "pdf"):
        fig.savefig(
            OUT / f"HEMT_TRANSPORT_2DEG_sheet_density.{ext}",
            dpi=300
        )
    plt.close(fig)

# --------------------------------------------------
# 4. Replot Id-Vg directly from the actual RASER CSV
# --------------------------------------------------
idvg_file = OUT / "HEMT_TRANSPORT_IdVg.csv"

if idvg_file.exists():
    rows = read_csv(idvg_file)
    if rows and {"Vg_V", "Id_mA_per_mm"}.issubset(rows[0]):
        rows.sort(key=lambda r: float(r["Vg_V"]))

        fig, ax = plt.subplots(figsize=(7.2, 4.8))
        ax.plot(
            [float(r["Vg_V"]) for r in rows],
            [float(r["Id_mA_per_mm"]) for r in rows],
            "o-", markersize=3
        )
        ax.set_xlabel("Gate voltage Vg (V)")
        ax.set_ylabel("Drain current |Id| (mA/mm)")
        ax.set_title("AlGaN/GaN HEMT: RASER DC Transfer Curve")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        for ext in ("png", "pdf"):
            fig.savefig(
                OUT / f"HEMT_TRANSPORT_IdVg_from_CSV.{ext}",
                dpi=300
            )
        plt.close(fig)

print("\n[OK] RASER CSV post-processing completed.")
print("[SOURCE]", PROFILE_FILE)
print("[OUTPUT DIRECTORY]", OUT)

for p in sorted(OUT.glob("HEMT_TRANSPORT_*")):
    if p.suffix in (".png", ".pdf", ".csv"):
        print("[FILE]", p.name)
