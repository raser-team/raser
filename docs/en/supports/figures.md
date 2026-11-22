# Figures (`supports/figures`)

Every figure drawn in RASER—regardless of which stage, experiment, or asset produces it, and whether drawn with matplotlib or ROOT—obtains its style and saves its files through `raser.supports.figures`. This page specifies figure formats, dimensions and fonts, axes, colors, filenames, and storage locations, and lists the minimum figures each stage must draw. For figure ownership and which node holds them, see [Architecture Overview](../architecture.md#results).

## Formats

Each figure is saved in two copies:

- `.png`: 200 dpi, for documentation and quick inspection;
- `.pdf`: vector graphics, for detailed inspection and inclusion in papers.

Figures drawn with ROOT save an extra `.root` copy containing the canvas itself, which can be reopened in ROOT to adjust axis ranges or extract data. Geometry and track plots drawn off-screen by Geant4 are saved only as `.png`.

## Dimensions and Fonts

- A single panel is 6 × 4 inches, and its `.png` is 1200 × 800 pixels; a ROOT canvas is likewise 1200 × 800 pixels. When multiple panels are arranged side by side, each panel remains 6 × 4 inches and the full figure is scaled by rows and columns.
- Sans-serif fonts: matplotlib uses the default DejaVu Sans, and ROOT uses Helvetica (font code 43, size in pixels). Axis titles are 12 pt; tick labels and legends are 10 pt.
- Figures carry no overall suptitle; what a figure shows is described by its filename and the caption in the documentation. When multiple panels are arranged side by side, each panel may have a one-line subtitle naming only the quantity distinguishing the panels, such as `CFD 30%`.
- Ticks point inward on all four sides; legends have no frame; ROOT does not draw statistics boxes.
- Two-dimensional distributions use the viridis colormap (`kViridis` in ROOT).

## Axes and Units

Axis titles are written in English as `Quantity [unit]`: the quantity name starts with a capital letter and uses full words; dimensionless quantities omit the brackets, such as `Charge collection efficiency`. The vertical axis of a histogram is labeled `Events`.

Convert data to the units in the table below when plotting: first convert data to SI units (field solvers output length in cm, electric field in V/cm, and doping in cm⁻³, which must first be converted to m, V/m, and m⁻³), then divide by `UNIT[<unit>]`. Common multipliers such as `×10⁻⁹` must not appear on tick labels; quantities spanning several orders of magnitude (leakage current, doping concentration, trapping rate) use logarithmic axes.

| Quantity | Unit | Example axis title |
| --- | --- | --- |
| Single-event waveform time | ns | `Time [ns]` |
| Time difference, time resolution | ps | `CFD 30% - truth [ps]` |
| Induced current | μA | `Current [μA]` |
| Leakage current | A, log axis | `Leakage current [A]` |
| Bias voltage | V, absolute value | `Reverse bias [V]` |
| Amplifier output, digitized voltage | mV | `Amplitude [mV]` |
| Position or depth inside device | μm | `Depth [μm]` |
| Setup dimensions | mm | `x [mm]` |
| Electric field | kV/cm | `Electric field [kV/cm]` |
| Potential, weighting potential | V; weighting potential is dimensionless | `Weighting potential` |
| Doping concentration | cm⁻³, log axis | `Doping [cm⁻³]` |
| Trapping rate | s⁻¹, log axis | `Trapping rate [s⁻¹]` |
| Capacitance | pF | `Capacitance [pF]` |
| Charge | fC | `Charge [fC]` |
| Deposited energy | keV | `Deposited energy [keV]` |

Write μ as the Unicode character `μ`, and as `#mu` in ROOT.

## Colors

The same species or element uses the same color across all figures:

| Plotted quantity | Color |
| --- | --- |
| Electrons | Blue `#1f6fb4` |
| Holes | Red `#d1352b` |
| Electrons from avalanche multiplication | Light blue `#5bb6e8` |
| Holes from avalanche multiplication | Orange `#f08a3c` |
| Total (total current, total charge) | Black |
| Initial deposition point | Gray `#808080` |
| Reference lines such as thresholds and means | Black dashed |
| Fit curve | Black solid |
| Histogram | Gray-blue `#6c8ebf` fill |

When plotting several curves of the same kind in one figure: ordered curves (such as scan-point bias voltages or CFD fractions) sample equidistantly from the viridis colormap; unordered curves (such as multiple devices or timing methods) take colors sequentially from the eight-color Okabe–Ito palette. ROOT uses the same colors, converted to ROOT color indices by `root_color`.

## Filenames

- Lowercase English words joined by `_` clearly stating what is plotted, such as `electric_field` and `drift_path`.
- Omit the device name, experiment name, and node ID: the node containing the figure already specifies them.
- Single-event figures append the event number after the figure name: `current_17` is the induced current of event 17. The event number matches `event` in the node's data file.
- Figures within the same node distinguished by bias voltage, electrode, etc. append the value with its unit or the index after the figure name: `electric_field_200V`, `current_17_electrode_2`. Numbers are written in shortest form: `200.0` is written `200`, `0.5` is written `0.5`, and negative numbers keep the minus sign: `electric_field_-200V`. Units keep their original letter case.

## Storage Locations

| Figure | Location |
| --- | --- |
| Stage figures | `plots/` inside the stage node: `<experiment>/nodes/<stage>/<node_id>/plots/` |
| Device field figures | `work/<device>/field/<node_id>/plots/` |
| Per-point statistical plots | `plots/` inside that point's `analysis` node |
| Cross-point trend plots | `<experiment>/analysis/` |
| Front-end circuit schematic and impulse response | Circuit asset `work/<circuit>/plots/` |
| Object-only figures from `raser <stage> --draw <object>` | `plots/` inside that object's folder, such as `work/<device>/plots/` |

When inspecting figures by scan point, enter through the view `<experiment>/points/<point>/<stage>/<job>/plots/`, which points to the corresponding node in the table above; `field` and `analysis` have only one node per point, with views `<experiment>/points/<point>/field/plots/` and `<experiment>/points/<point>/analysis/plots/`.

## Figures per Stage

Each stage draws at least the figures listed below. "Per-event" figures are drawn for the first `<stage>.plots` recorded events, with this option and its default value documented on each stage page; all other figures are drawn once per node. Figures specific to individual experiments and applications (`telescope`, `tct`, `bmos`, `cflm`, etc.) follow the same rules and are placed in the node of the stage they read and write.

| Stage | Figure name | What is plotted | Count |
| --- | --- | --- | --- |
| field | `doping` | Doping concentration profile along depth | One per node |
| field | `iv` | Leakage current versus reverse bias | One per node |
| field | `cv` | Left: capacitance versus reverse bias; right: $1/C^2$ versus reverse bias | One per node |
| field | `electric_field_<V>V`, `potential_<V>V` | Electric field and potential profiles along depth; 2D and 3D devices add a transverse profile and a 2D slice | One per bias |
| field | `weighting_potential_<electrode>` | Weighting potential profile along depth; same additions for 2D and 3D devices | One per readout electrode |
| field | `trapping_rate_<V>V` | Electron and hole trapping rate profiles along depth | One per bias when irradiated |
| field | `device_circuit_<V>V` | Device parameter circuit diagram: junction capacitance, coupling capacitance, and undepleted layer, labeled with values | One per bias |
| deposit | `geometry` | Geant4 setup geometry and tracks of the first few events, on a white background | One per node |
| deposit | `deposited_energy` | Deposited energy distribution in the device across all events in this node | One per node |
| current | `drift_path_<event>` | Top: 3D device boundaries and electron/hole drift trajectories; bottom: projection onto the $x$-$z$ plane | Per event |
| current | `current_<event>` | Induced currents of electrons, holes, avalanche-multiplied carriers, and total on the readout electrode; for multiple electrodes, one per electrode with `_electrode_<index>` appended | Per event |
| current | `charge_per_electrode_<event>` | Charge collected by each electrode in strip and pixel devices | Per event |
| current | `collected_charge` | Total collected charge distribution across all events in this node | One per node |
| readout | `waveform_<event>` | Top: input induced current; bottom: amplifier output voltage waveform (including noise) | Per event |
| readout | `schematic`, `impulse_response` | Front-end circuit schematic and impulse response, saved into the circuit asset | One per circuit |
| digitizer | `samples_<event>` | Analog waveform overlaid with digitized samples | Per event |
| trigger | `trigger_amplitude` | Amplitude distributions of recorded and discarded events, with the trigger threshold drawn | One per node |
| reconstruction | `features_<event>` | Digital waveform annotated with baseline, amplitude, ToA, and each CFD time | Per event |
| analysis | `efficiency` | Charge collection efficiency distribution, with a dashed line at the mean | One per scan point |
| analysis | `amplitude` | Amplitude distribution of recorded events, with a dashed line at the amplitude threshold | One per scan point |
| analysis | `time_difference` | Distribution and truncated-Gaussian fit of timestamp minus true time for each timing method, one panel per method | One per scan point |
| analysis | `resolution_of_fraction` | Time resolution versus CFD fraction | One per scan point |
| analysis | `trend` | Left: charge collection efficiency versus scan quantity; right: time resolution of each timing method versus scan quantity | One per experiment, drawn when scanning a single numeric quantity |

## Usage

```python
from raser.supports import figures

figure, axis = figures.new()                       # Single panel, 6 × 4 inches, style already configured
axis.step(time / figures.UNIT["ns"], current / figures.UNIT["uA"], color=figures.ELECTRON, label="electrons")
axis.set_xlabel(figures.label("Time", "ns"))       # "Time [ns]"
axis.set_ylabel(figures.label("Current", "uA"))    # "Current [μA]"
figures.save(figure, folder, "current", 17)        # folder/current_17.png, current_17.pdf
```

When plotting with ROOT:

```python
canvas = figures.canvas()                          # 1200 × 800 pixels, gStyle already configured
graph.SetLineColor(figures.root_color(figures.HOLE))
graph.GetXaxis().SetTitle(figures.label("Depth", "um", root=True))   # "Depth [#mum]"
figures.save_canvas(canvas, folder, "drift_path", 17)   # drift_path_17.png, .pdf, .root
```

| Name | Purpose |
| --- | --- |
| `new(rows=1, columns=1)` | Creates a new matplotlib figure, 6 × 4 inches per panel, returning the figure and axes (or an array of axes when multiple panels) |
| `canvas(columns=1, rows=1)` | Creates a new ROOT canvas, 1200 × 800 pixels per panel, and configures `gStyle` |
| `save(figure, folder, name, *suffixes)` | Saves `<name>.png` and `<name>.pdf` and returns the `.png` path; creates `folder` if it does not exist |
| `save_canvas(canvas, folder, name, *suffixes)` | Saves `.png`, `.pdf`, and `.root` copies and returns the `.png` path |
| `file_name(name, *suffixes)` | Builds the filename without extension according to the rules above. Suffixes may be numbers, lowercase words, or `(value, unit)` pairs: `file_name("electric_field", (200.0, "V"))` yields `electric_field_200V`, and `file_name("current", 17, "electrode", 2)` yields `current_17_electrode_2` |
| `label(quantity, unit=None, root=False)` | Builds an axis title: `label("Depth", "um")` yields `Depth [μm]`; omits the unit brackets when no unit is given |
| `UNIT` | Conversion factors from units to SI, e.g., `UNIT["ns"] == 1e-9`; divide SI data by this factor when plotting. Keys cover all units in the unit table above, written in ASCII: `ns`, `ps`, `uA`, `A`, `V`, `mV`, `um`, `mm`, `kV/cm`, `cm-3`, `s-1`, `pF`, `fC`, `keV` |
| `ELECTRON`, `HOLE`, `GAIN_ELECTRON`, `GAIN_HOLE`, `TOTAL`, `DEPOSIT`, `HISTOGRAM` | Colors from the color table above |
| `series(count, ordered)` | Colors for several curves of the same kind in one figure: equidistantly sampled from viridis when `ordered=True`, otherwise sequentially from Okabe–Ito |
| `root_color(color)` | Converts a color above to a ROOT color index |

On error:

- If the figure name or a suffix word contains uppercase letters, spaces, or symbols other than `_`, `file_name` raises `ValueError: figure name must be lowercase words joined by _: <name>`;
- If the unit is not in `UNIT`, `label` raises `ValueError: unknown unit: <unit>`.
