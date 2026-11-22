# Hydrogen–Boron Fusion (`apps/hbf`)

`hbf` (Hydrogen–Boron Fusion, $\text{p}\text{–}{}^{11}\text{B}$, in the `raser_app` package) is a dedicated application for $\alpha$-particle diagnostics in laser- or accelerator-driven hydrogen–boron fusion. Centered on a SiC AC-LGAD (silicon carbide AC-coupled low-gain avalanche detector) pixel device, it reads [detector components (`components/device`)](../components/device.md), [energy deposition components (`components/deposit`)](../components/deposit.md), [front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), and [trigger components (`components/trigger`)](../components/trigger.md), and executes all eight stages in sequence—[`field`](../stages/field.md), [`deposit`](../stages/deposit.md), [`current`](../stages/current.md), [`readout`](../stages/readout.md), [`digitizer`](../stages/digitizer.md), [`trigger`](../stages/trigger.md), [`reconstruction`](../stages/reconstruction.md), and [`analysis`](../stages/analysis.md)—outputting the hit-time and flux distributions of fusion $\alpha$ particles across the pixel array.

## Setup and Standard Practice

In laser- or proton-beam-driven aneutronic hydrogen–boron fusion ($\text{p} + {}^{11}\text{B} \to 3\alpha + 8.68\ \text{MeV}$) experiments, wide-bandgap silicon carbide (4H-SiC) detectors—resistant to strong electromagnetic pulses, radiation-hard, and visible-blind—are arranged around the target chamber. Using the time-of-flight (ToF) method together with pixelated spatial readout, they simultaneously measure the arrival times and angular flux distributions of multi-$\text{MeV}$ fusion $\alpha$ particles to characterize fusion yield and energy spectra.

In RASER's `hbf` design, $\alpha$ particles produced by the fusion reaction (with main-peak kinetic energies of roughly $2.9\ \text{MeV}$ to $4.0\ \text{MeV}$) travel from the fusion target source toward a SiC AC-LGAD pixel device at distance $L_{\text{ToF}}$. The $\alpha$-particle hit time $t_{\text{hit}}$ and the particle flux $\Phi_{i_x, i_y}(t)$ within time bin $[t, t + \Delta t]$ measured by pixel $(i_x, i_y)$ are:

$$\text{p} + {}^{11}\text{B} \longrightarrow 3\,{}^{4}\text{He} + 8.68\ \text{MeV}, \qquad t_{\text{hit}} = t_{0} + L_{\text{ToF}}\sqrt{\frac{m_{\alpha}}{2 E_{\alpha}}}, \qquad \Phi_{i_x, i_y}(t) = \frac{N_{i_x, i_y}(t,\, t + \Delta t)}{p_x p_y \times 10^{-8}\,\Delta t} \tag{1}$$

where:

- $t_0$: fusion reaction time, $\text{s}$; $L_{\text{ToF}}$ is the flight distance from the target source to the entrance surface of the pixel device, $\text{m}$;
- $m_{\alpha}$, $E_{\alpha}$: rest mass and kinetic energy of the $\alpha$ particle, in $\text{kg}$ and $\text{J}$ after converting to SI units (kinetic energy is specified in $\text{MeV}$ in source configurations);
- $t_{\text{hit}}$: arrival hit time of the $\alpha$ particle at the pixel device extracted from the reconstructed waveform (`ToA` or `CFD`), $\text{s}$;
- $N_{i_x, i_y}(t, t + \Delta t)$: number of $\alpha$-particle hits recorded in pixel $(i_x, i_y)$ during the time interval $[t, t + \Delta t]$ (at high flux, converted from the pixel collected charge divided by the mean single-particle multiplied charge), count;
- $p_x, p_y$: SiC AC-LGAD pixel pitches in the $x$ and $y$ directions, $\mu\text{m}$ (multiplied by $10^{-8}\ \text{cm}^2/\mu\text{m}^2$ to obtain single-pixel area in $\text{cm}^2$);
- $\Delta t$: time-bin width for flux statistics, $\text{s}$;
- $\Phi_{i_x, i_y}(t)$: $\alpha$-particle flux measured by pixel $(i_x, i_y)$ at time $t$, $\text{cm}^{-2}\cdot\text{s}^{-1}$.

Avalanche multiplication in the SiC AC-LGAD device is calculated by `CalCurrentGain` in [`core/current`](../core/current.md) (with the 4H-SiC `"Hatakeyama"` impact ionization model), and the charge-sharing network of the resistive layer and dielectric coupling layer is built by `device_grid` in [`core/field/circuit_parameters.py`](../core/field.md). Standard experimental methods for $\alpha$-particle generation and time-of-flight diagnostics in hydrogen–boron fusion are described in Ref. [1] (L. Giuffrida et al., “High-current stream of energetic $\alpha$ particles from laser-driven proton-boron fusion”, *Phys. Rev. E* 101 (2020) 013204, doi:10.1103/PhysRevE.101.013204).

## Stages and Components Used

### Stages

- [`field`](../stages/field.md): solves or reuses the electric field, gain-layer profile, and weighting field of the SiC AC-LGAD pixel device at the operating bias, stored under `work/<device>/field/`.
- [`deposit`](../stages/deposit.md): uses Geant4 to simulate energy deposition and electron-hole pair generation near the entrance surface of the SiC AC-LGAD pixel device by $\alpha$ particles emitted from the hydrogen–boron fusion source in the target-chamber geometry.
- [`current`](../stages/current.md): simulates electron and hole drift and `"Hatakeyama"` avalanche multiplication in the SiC multiplication field, computing the induced current in each cell.
- [`readout`](../stages/readout.md): feeds the induced currents into the 2D resistive-layer and AC-coupling capacitance grid (`device_grid`) of the AC-LGAD and the front-end amplifier chain to solve output voltage waveforms for each pixel channel.
- [`digitizer`](../stages/digitizer.md) and [`trigger`](../stages/trigger.md): performs digitization sampling/quantization and threshold-crossing trigger selection on each pixel channel's waveform.
- [`reconstruction`](../stages/reconstruction.md): extracts arrival time (`ToA`, `CFD`), amplitude, and pixel cluster position for each hit from the triggered pixel waveforms.
- [`analysis`](../stages/analysis.md): aggregates all events and computes and plots the $\alpha$-particle hit-time spectrum and 2D pixel flux distribution under `work/hbf/analysis/`.

### Components

- [Detector components (`components/device`)](../components/device.md): provides a SiC AC-LGAD pixel device definition configured with `"material": "SiC"`, `"electrodes": "pixel"`, `"enable_gain": true`, `"avalanche_model": "Hatakeyama"`, and `"resistive_layer"` (including the `"coupling"` dielectric layer).
- [Energy deposition components (`components/deposit`)](../components/deposit.md): provides the hydrogen–boron fusion $\alpha$-particle source and the time-of-flight target-chamber Geant4 setup definitions.
- [Front-end readout circuit components (`components/readout`)](../components/readout.md), [digitizer components (`components/digitizer`)](../components/digitizer.md), [trigger components (`components/trigger`)](../components/trigger.md): provides multi-channel front-end amplifier chains, digitization sampling, and trigger threshold configurations.

## Usage and Configuration

Following the top-level design ([Command-Line Interface](../cli.md#commands)), run the `hbf` application directly, or use `--set` and `--scan` to scan device bias voltage and resistive-layer sheet resistance:

```bash
raser hbf
raser hbf --scan field.voltage=400,500
```

Experiment configuration is written in `work/hbf/config.json`, sectioned by stage. This scenario requires three types of components: a SiC AC-LGAD pixel device (detector component), a fusion α-particle source, and a target-chamber-to-device flight-distance setup (both energy deposition components, selected in the `deposit` section).

The user-configurable keys under this design are listed below:

| Section.Key | Default (Design) | Unit | Meaning |
| --- | --- | --- | --- |
| `field.voltage` | `bias.voltage` from the device file | $\text{V}$ | Reverse bias voltage of the SiC AC-LGAD pixel device |
| `field.irradiation` | `None` | $\text{neq/cm}^2$ | Device irradiation fluence |
| `readout.amplifier` | `"SantaCruz+Gali52+Termination50"` | None | Front-end amplifier and termination load component chain joined by `+` |
| `readout.sheet_resistance` | `None` (`resistive_layer.sheet_resistance` from the device file) | $\Omega$ | Overrides the sheet resistance of the AC-LGAD resistive charge-sharing layer |
| `reconstruction.threshold`, `reconstruction.amplitude_threshold` | `10.0`, `10.0` | $\text{mV}$ | Threshold-crossing timing threshold and cluster-seed amplitude threshold for pixel waveforms |

All other underlying physical and numerical parameters (silicon carbide mean ionization energy `8.4 eV` and Fano factor `0.128`, default `"Das"` mobility model, drift time-window and time-step profiles, `ngspice` noise-analysis lower frequency bound `1e3 Hz` and temperature `27 °C`, and `200` reconstruction baseline sample points) are hardcoded in the `core` modules.

## Outputs

Following the design in [Architecture Overview](../architecture.md#results), outputs are stored under `work/hbf/`: per-stage nodes are stored by input fingerprint under `work/hbf/nodes/<stage>/<node>/` (each carrying a `node.json`), symlink views named by scan point are placed at `work/hbf/points/<point>/<stage>`, the parameter table is written to `work/hbf/points.json`, the device shared field is stored under `work/<device>/field/`, and statistical summaries and trend plots are stored under `work/hbf/analysis/`.

The designed output data files and plots are listed below:

| Filename | Writer Stage | Content | Unit |
| --- | --- | --- | --- |
| `deposit_<job>.h5`, `current_<job>.h5`, `readout_<job>.h5`, `reconstruction_<job>.h5` | `deposit` through `reconstruction` | Per-job $\alpha$-particle deposition steps, induced currents per AC-LGAD pixel, coupled readout voltage waveforms, and per-event pixel timing/amplitude reconstruction tables | Coordinates $\mu\text{m}$, time $\text{s}$, energy $\text{MeV}$, current $\text{A}$, voltage $\text{V}$ |
| `analysis/[<point>/]result.json`, `events.h5` | [`analysis`](../stages/analysis.md) | Aggregated $\alpha$-particle hit-time statistics, total counts, mean flux across pixel channels, and per-event hit-time and pixel-coordinate tables | Time $\text{s}$, flux $\text{cm}^{-2}\cdot\text{s}^{-1}$ |
| Hit-time distribution plot | [`analysis`](../stages/analysis.md) | Hit-time (ToF) distribution of fusion $\alpha$ particles on the SiC AC-LGAD pixel device | Horizontal axis hit time $\text{ns}$ or $\text{ps}$, vertical axis events |
| Flux distribution plot | [`analysis`](../stages/analysis.md) | 2D spatial distribution of $\alpha$-particle flux across the pixel array | Horizontal and vertical axes pixel coordinates ($\mu\text{m}$ or pixel indices), color scale flux $\text{cm}^{-2}\cdot\text{s}^{-1}$ |
