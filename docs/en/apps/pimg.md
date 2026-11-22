# Proton Imaging (`apps/pimg`)

`pimg` (Proton Imaging, in the `raser_app` package) is a dedicated application for proton radiography and computed tomography. Its detector layout resembles [`telescope`](../bench/telescope.md), placing a human head phantom (starting from a simplified geometric toy model and replaceable by a detailed anatomical phantom) between upstream and downstream tracking pixel detector layers. It reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—outputting proton track positions, energy loss, and 2D water-equivalent path length (WEPL) images after traversing the head phantom.

## Setup and Standard Practice

In single-particle tracking proton imaging (Proton Radiography / Proton CT), the standard setup mirrors a beam telescope: front and rear position-sensitive tracking detectors (front/rear trackers) followed by a downstream residual energy/range detector, with the imaged object (such as a human head phantom) placed between the front and rear tracking arms. When a high-energy proton beam (typically $150\ \text{MeV}$ to $250\ \text{MeV}$ kinetic energy) passes through the head phantom, the upstream tracking layers measure each proton's entrance position $\mathbf{r}_{\text{in}}$ and direction, the downstream tracking layers measure its exit position $\mathbf{r}_{\text{out}}$ and scattering angle to estimate the most likely path (MLP), and the residual energy detector measures the exit kinetic energy $E_{\text{out}}$. Integrating the energy loss along the path reconstructs the water-equivalent path length (WEPL) of the object on the projection plane $(x, y)$:

$$\Delta E = E_{\text{in}} - E_{\text{out}}, \qquad \text{WEPL}(x, y) = \int_{\text{MLP}} \rho_{s}(\mathbf{r})\,dl = \int_{E_{\text{out}}}^{E_{\text{in}}} \frac{dE}{S_{\text{water}}(E)} \tag{1}$$

where:

- $E_{\text{in}}$, $E_{\text{out}}$: proton kinetic energy upon entering and exiting the head phantom, $\text{MeV}$; $\Delta E$ is the energy lost by the proton traversing the phantom, $\text{MeV}$;
- $\rho_{s}(\mathbf{r}) = S(\mathbf{r}, E) / S_{\text{water}}(E)$: relative stopping power (RSP) of the tissue material at position $\mathbf{r}$ relative to liquid water (dimensionless);
- $S_{\text{water}}(E) = -(dE/dl)_{\text{water}}$: mass or linear stopping power of protons in liquid water, $\text{MeV/mm}$;
- $\text{WEPL}(x, y)$: water-equivalent path length integrated along the proton path at projection coordinates $(x, y)$ (in $\mu\text{m}$ or $\text{mm}$), $\text{mm}$.

In RASER's `pimg` design, the Geant4 setup follows the multi-layer pixel tracking plane arrangement of [`telescope`](../bench/telescope.md) (such as several upstream and downstream `TAICHU3` or SiC pixel layers), placing a human head phantom in the central region of the telescope (by default a simplified `toy` model of skull plus brain tissue formed from concentric spherical shells or ellipsoids, with support for importing detailed head geometries or medical phantoms via `gdml_import`). This enables evaluating the effects of tracker spatial resolution, multiple Coulomb scattering, and energy resolution on image quality within a single simulation chain. The physical paradigm and detector system design of proton radiography and tomography are reviewed in Ref. [1] (R. P. Johnson, “Review of medical radiography and tomography with proton beams”, *Rep. Prog. Phys.* 81 (2018) 016701, doi:10.1088/1361-6633/aa8b1d).

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the shared fields of the tracking layers and energy detector at their operating biases, stored under `work/<device>/field/`.
- [`deposit`](../stages/deposit.md): uses Geant4 to simulate energy deposition steps of the proton beam passing successively through the upstream tracking layers, the central head phantom (`toy` geometry or imported detailed model), the downstream tracking layers, and the terminal energy detector.
- [`current`](../stages/current.md): computes carrier collected charge and induced current in each pixel tracking layer and the energy detector.
- [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md): solves front-end amplifier waveforms, digitization sampling/quantization, and coincidence triggering for each detector layer.
- [`reconstruction`](../stages/reconstruction.md): performs hit clustering on the upstream and downstream pixel tracking layers to reconstruct single-proton entrance and exit tracks.
- [`analysis`](../stages/analysis.md): aggregates all proton tracks under `work/pimg/analysis/`, computes the mean energy loss $\Delta E$ and scattering-angle distributions on the projection grid, and generates the 2D WEPL image of the head phantom.

### Components

- [Detector components (`components/device`)](../components/device.md): provides upstream and downstream pixel tracking detectors (such as `TAICHU3.json`) as well as the tested/energy detector definitions.
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides broad-beam proton source components and Geant4 setup scripts placing a human head phantom (`toy` head model or GDML detailed head model) in the middle of the telescope.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), [trigger components (`components/trigger`)](../components/trigger.md): provides readout amplifier chains, digitization sampling, and trigger configurations.

## Usage and Configuration

Following the top-level design ([Command-Line Interface](../cli.md#commands)), run the `pimg` application directly, or use `--set` and `--scan` to scan tracking-layer device parameters:

```bash
raser pimg
```

Experiment configuration is written in `work/pimg/config.json`, sectioned by stage. This scenario requires two energy deposition components—a proton beam source and a setup placing a head phantom between upstream and downstream telescope layers—selected in the `deposit` section; the default tracking-layer device is `TAICHU3`.

The user-configurable keys under this design are listed below:

| Section.Key | Default (Design) | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `bias.voltage` from the device file | $\text{V}$ | Detector bias voltage |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain |
| `reconstruction.threshold`, `reconstruction.amplitude_threshold` | `10.0`, `10.0` | $\text{mV}$ | Pixel threshold-crossing level and cluster-seed amplitude threshold |

All other underlying physical and numerical parameters (material mean ionization energy and Fano factor, pixel thermal diffusion step `50e-12 s`, clustering neighborhood distance tolerance `1e-7 um^2`, and `200` reconstruction baseline sample points) are hardcoded in the source code.

## Outputs

Following the design in [Architecture Overview](../architecture.md#results), outputs are stored under `work/pimg/`: per-stage nodes are stored by input fingerprint under `work/pimg/nodes/<stage>/<node>/` (each carrying a `node.json`), symlink views named by scan point are placed at `work/pimg/points/<point>/<stage>`, the parameter table is written to `work/pimg/points.json`, shared fields of the devices used are stored under `work/<device>/field/`, and imaging results and cross-point comparison plots are stored under `work/pimg/analysis/`.

The designed output data files and plots are listed below:

| Filename | Writer Stage | Content | Unit |
| --- | --- | --- | --- |
| `deposit_<job>.h5`, `current.<layer>_<job>.h5`, `reconstruction_<job>.h5` | `deposit` through `reconstruction` | Per-layer pixel energy deposition steps, pixel collected charge/induced current, and per-proton entrance/exit cluster position reconstruction tables | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, charge $\text{C}$ |
| `analysis/[<point>/]result.json` and per-proton tracks | [`analysis`](../stages/analysis.md) | Statistical summaries on the imaging-plane grid (spatial resolution, contrast-to-noise ratio) and per-proton track and WEPL datasets | Coordinates $\text{mm}$, energy $\text{MeV}$, WEPL $\text{mm}$ |
| WEPL plot | [`analysis`](../stages/analysis.md) | 2D water-equivalent path length (WEPL) or mean energy loss $\Delta E$ proton radiograph of the head phantom on the projection plane $(x, y)$ | Horizontal and vertical spatial coordinates $\text{mm}$, color scale WEPL $\text{mm}$ (or $\Delta E$ $\text{MeV}$) |
