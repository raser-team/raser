# Carrier Drift and Induced Current (`core/current`)

`src/raser/core/current/` takes electron-hole pairs together with their creation coordinates and times from [energy deposition](deposit.md), and the electric field, doping, conductive flag, trapping rates, and weighting potential from [device field](field.md). This package simulates drift, diffusion, trapping, and avalanche multiplication of carrier clusters, computes the time-domain induced current and net induced charge on each readout electrode, and writes `current_<job>.h5` files (it also provides interfaces for laser pulse convolution and diffusion-only collection in field-free pixels). The output current waveforms are passed to [electronics readout](readout.md), and net induced charges and initial pair counts are passed to [statistical analysis](analysis.md).

## Physics

### Drift

Under an electric field in a semiconductor, electrons and holes acquire a mean drift velocity collinear with the electric field: holes move along the field direction and electrons move opposite to it. In code, the mobility is evaluated from local electric field magnitude, temperature, and net doping concentration, giving the drift velocity:

$$\mathbf{v}(\mathbf{r}) = \pm \mu\bigl(T,\, N_{\text{eff}}(\mathbf{r}),\, E(\mathbf{r})\bigr)\,\mathbf{E}(\mathbf{r}) \tag{1}$$

where:

- $\mathbf{v}$: carrier drift velocity, $\text{cm/s}$ (multiplied by the conversion factor $10^4\ \mu\text{m/cm}$ when advancing position $\mathbf{r}$ [$\mu\text{m}$]);
- plus sign corresponds to holes, minus sign to electrons;
- $\mathbf{E}(\mathbf{r})$: electric field vector at position $\mathbf{r}=(x, y, z)$ ($\mu\text{m}$), $\text{V/cm}$, with magnitude $E = |\mathbf{E}|$;
- $T$: device temperature, $\text{K}$;
- $N_{\text{eff}}(\mathbf{r})$: effective net doping concentration at position $\mathbf{r}$, $\text{cm}^{-3}$;
- $\mu$: carrier mobility, $\text{cm}^2/(\text{V}\cdot\text{s})$.

Mobility is computed by `Material(material).cal_mobility`; see [model.md](model.md) for parameterizations. `core/current` uses each material's default mobility model: `"Selberherr"` for Si, `"Das"` for SiC (4H-SiC), and `"Reggiani_diamond"` for Diamond. The mobility model depends solely on `material`: there is no device-file key to select a mobility model, and `CalCurrent` passes no model name when constructing `Material(material)`. Carrier drift transport in semiconductors is covered in Ref. [1].

### Diffusion

Carriers undergo random scattering through lattice thermal motion, spreading spatially by diffusion. Under non-degenerate conditions the diffusion coefficient is given by the Einstein relation, and the displacement along each coordinate axis over time interval $\Delta t$ follows a zero-mean Gaussian distribution:

$$D = \frac{\mu k_B T}{e} \tag{2}$$

$$\sigma = 10^{4}\sqrt{2 D \Delta t} \tag{3}$$

where:

- $D$: diffusion coefficient, $\text{cm}^2/\text{s}$;
- $\mu$: carrier mobility, $\text{cm}^2/(\text{V}\cdot\text{s})$ (at the current electric field for drift in a field; zero-field electron mobility $\mu_n(T, N_{\text{eff}}, 0)$ for field-free diffusion-only collection);
- $k_B/e$: ratio of the Boltzmann constant to the elementary charge, taken in code as constant `kboltz` (`BOLTZMANN`) = $8.617385\times 10^{-5}\ \text{eV/K}$ (numerically equal to $k_B/e$ in $\text{V/K}$);
- $T$: device temperature, $\text{K}$;
- $\Delta t$: time step, $\text{s}$;
- $\sigma$: standard deviation of the Gaussian random displacement along each coordinate axis in one step, $\mu\text{m}$ ($10^4$ is the $\mu\text{m/cm}$ conversion factor).

Limitation: in both field drift (`drift.py`) and field-free diffusion (`diffusion.py`), an entire carrier cluster receives a single random displacement as if it were one carrier, without expanding the internal spread of the cluster. The Einstein relation is from Ref. [2].

### Trapping

Deep-level defects in irradiated semiconductors trap free carriers during transport, causing the surviving number of carriers still contributing to signal induction in a cluster to decay exponentially. Integrating the local trapping rate along the drift trajectory $\mathbf{r}(t')$, the surviving carrier count at time $t$ is:

$$N(t) = N_0 \exp\!\left(-\int_{t_0}^{t} \Gamma\bigl(\mathbf{r}(t')\bigr)\,dt'\right) \tag{4}$$

where:

- $N(t)$: signed number of untrapped carriers remaining in the cluster at time $t$ ($\text{s}$) (dimensionless);
- $N_0$: initial signed carrier count at time $t_0$ ($\text{s}$) (dimensionless);
- $\Gamma(\mathbf{r})$: carrier trapping rate at position $\mathbf{r}$ ($\mu\text{m}$), $\text{s}^{-1}$, provided by `DevsimField.get_trap_e` (electrons) and `DevsimField.get_trap_h` (holes) in [field.md](field.md).

Trapping decay is evaluated only when the device has a non-`None` `irradiation_model`; otherwise trapping is omitted (equivalent to $\Gamma = 0$). Deep-level defect trapping kinetics are from Ref. [3], and the effective trapping rate and exponential survival model in irradiated silicon detectors are from Ref. [4].

### Shockley-Ramo Induction

The instantaneous current induced on any readout electrode by a moving charge is given by the Shockley-Ramo theorem. The dimensionless electrostatic solution obtained by setting the target electrode to $1$, all other electrodes to $0$, and removing space charge is the electrode's weighting potential $\phi_w(\mathbf{r})$, with weighting electric field $\mathbf{E}_w = -\nabla \phi_w$; the instantaneous induced current and the charge induced over a step are:

$$i(t) = -q\,\mathbf{v}(t)\cdot\mathbf{E}_w\bigl(\mathbf{r}(t)\bigr) \tag{5}$$

$$\Delta Q = \int_{t_1}^{t_2} i(t)\,dt = q\,\bigl[\phi_w(\mathbf{r}_2) - \phi_w(\mathbf{r}_1)\bigr] \tag{6}$$

where:

- $i(t)$: instantaneous induced current on the electrode, $\text{A}$;
- $q = N e_0$: charge carried by the cluster, $\text{C}$ ($N$ is the signed carrier count, positive for holes and negative for electrons; elementary charge $e_0 = 1.60217733\times 10^{-19}\ \text{C}$);
- $\mathbf{v}(t)$: carrier velocity, $\text{cm/s}$;
- $\mathbf{E}_w(\mathbf{r})$: weighting electric field, $\text{cm}^{-1}$;
- $\phi_w(\mathbf{r})$: dimensionless weighting potential (also written $U_w$ in code comments), returned by `DevsimField.get_w_p` and clamped to $[0, 1]$;
- $\Delta Q$: charge induced on that electrode while the cluster moves from $\mathbf{r}_1$ to $\mathbf{r}_2$ ($\mu\text{m}$) during $[t_1, t_2]$ ($\text{s}$), $\text{C}$.

The code uses the potential-difference form Eq. (6) to accumulate induced charge step by step. The Shockley-Ramo theorem is from Refs. [5, 6].

### Impact Ionization Multiplication

In high-field regions, carriers gain sufficient kinetic energy to create secondary electron-hole pairs by impact ionization. The carrier-count growth rate per unit path length along the drift direction is governed by the local impact ionization coefficient:

$$\frac{dN}{ds} = \alpha(E, T)\,N \tag{7}$$

where:

- $N$: carrier count (dimensionless);
- $s$: distance traveled by the carrier along the electric-field drift direction, $\text{cm}$ (position in $\mu\text{m}$ multiplied by $10^{-4}\ \text{cm}/\mu\text{m}$);
- $\alpha(E, T)$: impact ionization coefficient, $\text{cm}^{-1}$ ($\alpha_n$ for electrons, $\alpha_p$ for holes);
- $E$: local electric field magnitude, $\text{V/cm}$; $T$: device temperature, $\text{K}$.

Multi-dimensional fields (`local_path`) integrate Eq. (7) directly along primary carrier drift paths. One-dimensional planar devices (`planar_integral`) account for bidirectional ionization feedback of both electrons and holes. Taking the electron-exiting face as origin $b$ (front surface $z_0$ if $E_z > 0$ at peak field, back surface $z_M$ if $E_z < 0$) and depth coordinate $z \in [0, W]$ ($\text{cm}$, where $W$ is the mesh depth span) directed from $b$ toward the opposite face, the steady-state multiplication factor $M(z)$ and net added pair count (net gain) $G(z)$ for an electron-hole pair created at depth $z$ are:

$$K(z) = \exp\!\left(\int_{0}^{z} \bigl[\alpha_n(z') - \alpha_p(z')\bigr]\,dz'\right) \tag{8}$$

$$G(z) = M(z) - 1 = \frac{K(z)}{1 - \int_{0}^{W} \alpha_p(z')\,K(z')\,dz'} - 1 \tag{9}$$

where:

- $K(z)$: dimensionless depth factor;
- $\alpha_n(z'), \alpha_p(z')$: electron and hole impact ionization coefficients at depth $z'$, $\text{cm}^{-1}$;
- $\int_{0}^{W} \alpha_p(z')\,K(z')\,dz'$: breakdown integral (dimensionless); when $\ge 1$, the device undergoes avalanche breakdown;
- $M(z)$: total multiplication factor (dimensionless), and $G(z)$ is the number of extra secondary pairs per primary electron-hole pair (value returned by `planar_gain_at`).

The 1D steady-state two-carrier multiplication integral is from Ref. [7]. Impact ionization coefficients are supplied by `Material(material, avalanche_model=avalanche_model).cal_coefficient` (see [model.md](model.md) for formulas and parameters), supporting three models:

- `"vanOverstraeten"` (default for Si): van Overstraeten–de Man piecewise Chynoweth law, set to zero below $1.75\times 10^5\ \text{V/cm}$ [8]; citation for the temperature factor introduced via the optical phonon energy in code is to be added.
- `"Okuto"` (Si): Okuto–Crowell model, set to zero for fields not exceeding $1.0\times 10^5\ \text{V/cm}$ [9].
- `"Hatakeyama"` (default for 4H-SiC): Hatakeyama anisotropic model evaluated at a $4^\circ$ off-axis angle from $\langle 0001\rangle$ toward $\langle 11\bar{2}0\rangle$, set to zero for fields not exceeding $10^4\ \text{V/cm}$ [10, 11]; citation for the temperature factor introduced via the optical phonon energy in code is to be added.

## Algorithms

### Built-in Constants

The table below lists all built-in physical constants and numerical step parameters in `drift.py`, `cal_current.py`, and `diffusion.py`. They are module constants with no corresponding keys in the device file; the time window, step size, and `max_drift_time` are selected from the table by device dimension:

| Constant | 1D (or `is_plugin()` true) | 2D / 3D | Unit | Location and Meaning |
| --- | --- | --- | --- | --- |
| `t_bin` | `5e-12` | `50e-12` | $\text{s}$ | Output time step of current: induced-current time-bin width (file attribute `dt`) |
| `t_start` (relative) | `-1.25e-9` | `-12.5e-9` | $\text{s}$ | Start offset relative to the event's earliest creation time (`-0.25 * t_end`) |
| `t_end` (relative) | `5e-9` | `50e-9` | $\text{s}$ | Minimum end offset relative to the event's latest creation time |
| `delta_t` | `2e-12` | `20e-12` | $\text{s}$ | Single-step carrier drift time step $\Delta t$ |
| `min_intensity` | `1` | `1` | $\text{V/cm}$ | Minimum electric-field threshold for stopping drift (`"low_field"`) |
| `max_drift_time` | `100e-9` | `100e-9` | $\text{s}$ | Upper cap on single-cluster drift duration (`"time_out"`) |
| `kboltz` | `8.617385e-5` | `8.617385e-5` | $\text{eV/K}$ | Boltzmann constant for thermal diffusion in `drift.py` (numerically equal to $k_B/e$ [$\text{V/K}$]) |
| `e0` | `1.60217733e-19` | `1.60217733e-19` | $\text{C}$ | Elementary charge for Shockley-Ramo induced charge in `drift.py` |
| `edge_sampling` | `0.05` | `0.05` | $\mu\text{m}$ | Default sampling spacing in `split_at_conductor_edges` for locating conductive boundaries |
| `edge_tolerance` | `1e-4` | `1e-4` | $\mu\text{m}$ | Default bisection tolerance in `split_at_conductor_edges` for locating conductive boundaries |
| `BOLTZMANN` | `8.617385e-5` | `8.617385e-5` | $\text{eV/K}$ | Boltzmann constant for diffusion-only collection in `diffusion.py` |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | `1.602176634e-19` | $\text{C}$ | Elementary charge converting current and charge in `diffusion.py` |

### Time Window, Time Bins, and Initial Cluster Filtering

When an event enters `CalCurrent`, it initializes in the following steps:

1. **Select profile**: if `my_d.is_plugin()` is true, use `t_bin[1]`, `t_end[1]`, `t_start[1]`, and `delta_t[1]`; otherwise select the profile by `my_d.dimension`.
2. **Determine time window and bin count**: find the minimum $t_{\min}$ and maximum $t_{\max}$ of all input deposition creation times $t_m$ ($\text{s}$) (both $0.0$ if there are no inputs). Set the left edge of the first time bin to $t_{\text{start}} = t_{\min} + \text{relative\_start}$ and the initial bin count to $n_{\text{bin}} = \lceil (t_{\max} + \text{relative\_end} - t_{\text{start}}) / t_{\text{bin}} \rceil$. If floating-point rounding causes $t_{\text{start}} + n_{\text{bin}} t_{\text{bin}} < t_{\max} + \text{relative\_end}$, increment $n_{\text{bin}}$ until coverage is satisfied, and finally set $t_{\text{end}} = t_{\text{start}} + n_{\text{bin}} t_{\text{bin}}$.
3. **Determine readout electrode names**: call `electrode_names(read_out_contact, read_ele_num)`. If `len(read_out_contact) == read_ele_num`, take each entry's `"name"`; if length is `1`, generate `"<name>1"` through `"<name><read_ele_num>"`; otherwise raise `ValueError`.
4. **Total pair count and spatial filtering**: sum all input `ionized_pairs` into `pairs`. Retain only deposition steps $(x, y, z, t)$ satisfying both:
   - inside the device bounds: $0 \le x \le l_x$, $0 \le y \le l_y$, $0 \le z \le l_z$;
   - inside the projection of the centered electrode array: for each of $x$ and $y$, let the left edge of the first electrode be $u_{\text{first}} = (l_u - N_u p_u)/2$ and electrode index $i_u = \lfloor (u - u_{\text{first}})/p_u \rfloor$ (with right edge $u = u_{\text{first}} + N_u p_u$ assigned to $N_u - 1$), requiring $0 \le i_x < N_x$ and $0 \le i_y < N_y$.
5. **Sensitive pair count and drift launch**: among the retained deposition steps, sum the pairs satisfying `not my_f.get_conductive(x, y, z)` into `sensitive_pairs`. Create electron and hole clusters from the retained steps with `-n_pairs` and `+n_pairs`, drifting all electron clusters to completion one by one first, and then all hole clusters to completion one by one (fixing the random-stream draw order).

For particle steps straddling a conductive/depleted boundary, the module also provides helper `split_at_conductor_edges(start, middle, pairs, conducts, spacing, tolerance)`: it reconstructs the step endpoint $\mathbf{r}_{\text{end}} = 2\mathbf{r}_{\text{mid}} - \mathbf{r}_{\text{start}}$, samples `conducts(x, y, z)` at spacing no larger than `spacing` (default `0.05` $\mu\text{m}$), bisects each adjacent sampling interval where the conductive state changes down to width $\le$ `tolerance` (default `1e-4` $\mu\text{m}$), splits the step into sub-segments, and allocates pairs proportionally to segment length at each sub-segment's midpoint. Limitation: conductive layers thinner than `spacing` may be missed by the initial sampling.

### Single-Step Advance and Stop Conditions

Starting from $(\mathbf{r}_0, t_0)$, a single cluster repeatedly calls `advance` inside the `drift` loop until `reason` is non-empty. Each step executes in the following strict order:

1. **Timeout check (`"time_out"`)**: if $t - t_0 \ge \text{max\_drift\_time}$, stop immediately and record `reason = "time_out"`.
2. **Conductive region check (`"collected"`)**: if `my_f.get_conductive(x, y, z)` is true, stop immediately and record `reason = "collected"`. What counts as conductive is classified by the field module at that bias: all nodes of the enclosing mesh element must be conductive, see [field.md](field.md).
3. **Missing field check (`"no_field"`)**: call `my_f.get_e_field_cached(x, y, z)` to obtain $\mathbf{E} = (E_x, E_y, E_z)$ ($\text{V/cm}$). If `ValueError` is raised, stop immediately and record `reason = "no_field"`; if any component is non-finite (`NaN` or `Inf`), raise `ValueError`.
4. **Low field check (`"low_field"`)**: compute field magnitude $E = \sqrt{E_x^2 + E_y^2 + E_z^2}$. If $E \le \text{min\_intensity}$, stop immediately and record `reason = "low_field"`.
5. **Compute drift step**: read local doping $N_{\text{eff}} = \text{my\_f.get\_doping\_cached}(x, y, z)$ ($\text{cm}^{-3}$), call `mobility(T, N_eff, carriers, E)` for $\mu$ ($\text{cm}^2/(\text{V}\cdot\text{s})$), set polarity sign $s = +1$ (`carriers > 0`) or $-1$, and compute the drift displacement for fixed step $\Delta t$:
   $$\Delta \mathbf{r} = s\,\mu\,\mathbf{E}\,\Delta t \times 10^4 \quad [\mu\text{m}]$$
6. **Add Gaussian thermal diffusion step**: if `diffusion=True`, compute per-axis standard deviation $\sigma$ ($\mu\text{m}$) from Eq. (3) and draw three independent $\mathcal{N}(0, \sigma^2)$ samples for $x, y, z$ from the dedicated random stream `stream("drift")`, adding them to $\Delta \mathbf{r}$. If `diffusion=False`, the random stream is not queried. `diffusion` is a constructor argument of `CalCurrent` with no corresponding device-file key: `write_induced_currents` always uses the default `True`, and `write_laser_currents` always passes `False`.
7. **Clip on exiting a device face (`"left_device"`)**: initialize the retained step fraction $f = 1.0$. For each axis $u \in \{x, y, z\}$ (device size $L_u$):
   - if $u + \Delta u < 0$, update $f \leftarrow \min(f, -u / \Delta u)$;
   - if $u + \Delta u > L_u$, update $f \leftarrow \min(f, (L_u - u) / \Delta u)$.

   If $f > 0$, update $\mathbf{r} \leftarrow \mathbf{r} + f\,\Delta\mathbf{r}$, $t \leftarrow t + f\,\Delta t$, and append $(\mathbf{r}, t)$ to `path`. If $f < 1$, stop and record `reason = "left_device"`.

### Surviving Carrier Count under Trapping

After all clusters of one polarity finish drifting, `drift_all` computes surviving counts under trapping in one pass. When `my_d.irradiation_model is None`, trapping is skipped and `remaining` is set to `None`. Otherwise, for each path $\{(\mathbf{r}_k, t_k)\}_{k=0}^{M-1}$ of $M$ points ($M - 1$ steps):

1. Select `my_f.get_trap_h_cached` (holes) or `my_f.get_trap_e_cached` (electrons) by carrier charge sign, read trapping rate $\Gamma_k$ ($\text{s}^{-1}$, $k = 0, \dots, M - 2$) at the **start** position $\mathbf{r}_k$ of each step, and treat it as constant over $[t_k, t_{k+1}]$.
2. Compute step decay $d_k = \Gamma_k (t_{k+1} - t_k)$.
3. Evaluate the surviving carrier count at each **step midpoint** (`surviving`) for induced-charge and local-avalanche calculations:
   $$N_{k + 1/2} = N_0 \exp\!\left(-\sum_{j=0}^{k-1} d_j - \frac{1}{2} d_k\right)$$
4. When the surviving count at an arbitrary fraction $\eta \in [0, 1]$ within a step is needed (`surviving_at`, used for gain-layer crossing in 1D planar gain), evaluate:
   $$N_{k + \eta} = N_0 \exp\!\left(-\sum_{j=0}^{k-1} d_j - \eta\, d_k\right)$$

When `count_ends` tallies carrier counts by stop reason, it takes unsigned values: if trapping is enabled and the path took at least one step, it takes the last step's midpoint surviving count $|N_{M - 3/2}|$, otherwise the initial count $|N_0|$.

### Induced Charge Binning

`CalCurrent.binned` allocates a floating-point array `bins` ($\text{A}$) of length $n_{\text{bin}} + 2$ per electrode: index `0` is the underflow bin ($t < t_{\text{start}}$), indices `1` through `n_bin` are the in-window bins, and index `n_bin + 1` is the overflow bin ($t \ge t_{\text{end}}$). For each path with $\ge 2$ points:

1. **Identify electrodes and weighting-potential shifts (`electrodes_near`)**:
   - If `len(read_out_contact) != 1`, evaluate all readout electrodes with weighting-potential shift $(0, 0)$.
   - If `len(read_out_contact) == 1` (single repeated electrode), determine the starting electrode indices $(i_x, i_y)$ from $(x_0, y_0)$ and evaluate only neighboring electrodes $i \in [\max(i_x - s_x, 0),\, \min(i_x + s_x, N_x - 1)]$, $j \in [\max(i_y - s_y, 0),\, \min(i_y + s_y, N_y - 1)]$, where $s_x = \text{my\_f.cells\_either\_side}$ and $s_y = \text{read\_out\_contact}[0].\text{get}(\text{"y\_span"}, 0)$. Electrode index is $i \cdot N_y + j$, querying weighting potential `0` in the field with shift:
     $$\Delta x_{\text{off}} = x_{\text{first}} + (i - s_x)\,p_x, \qquad \Delta y_{\text{off}} = y_{\text{first}} + (j - s_y)\,p_y$$
     Electrodes outside this neighborhood are neglected as zero.
2. **Compute per-step induced charge (`induced_charges`)**: for each target electrode, query $\phi_{w,k} = \text{my\_f.get\_w\_p}(x_k - \Delta x_{\text{off}},\, y_k - \Delta y_{\text{off}},\, z_k,\, e_{\text{field}})$ along the path and compute step $k$'s induced charge $\Delta Q_k = N_k e_0 (\phi_{w,k+1} - \phi_{w,k})$ ($\text{C}$), where $N_k = N_0$ without trapping and $N_k = N_{k + 1/2}$ with trapping.
3. **Distribute across bins by time overlap (`spread_over_bins`)**: let bin width $\Delta t_{\text{bin}} = (t_{\text{end}} - t_{\text{start}}) / n_{\text{bin}}$ (equal to $t_{\text{bin}}$ by construction in step 2) and equivalent single-bin current $v_k = \Delta Q_k / t_{\text{bin}}$. Compute the range of logical bin indices covered by $[t_k, t_{k+1}]$: $m_{\text{first}} = \lfloor (t_k - t_{\text{start}}) / \Delta t_{\text{bin}} \rfloor$ to $m_{\text{last}} = \lfloor (t_{k+1} - t_{\text{start}}) / \Delta t_{\text{bin}} \rfloor$. For each $m \in [m_{\text{first}}, m_{\text{last}}]$:
   - overlap interval $[a_m, b_m] = \bigl[\max(t_k,\, t_{\text{start}} + m\,\Delta t_{\text{bin}}),\, \min(t_{k+1},\, t_{\text{start}} + (m + 1)\,\Delta t_{\text{bin}})\bigr]$;
   - time fraction $w_m = \max(b_m - a_m,\, 0) / (t_{k+1} - t_k)$;
   - accumulate $v_k w_m$ into `bins[e, clamp(m + 1, 0, n_bin + 1)]`, placing all $m < 0$ into underflow bin `0` and all $m \ge n_{\text{bin}}$ into overflow bin `n_bin + 1`.
4. **Total current and net charge**: sum primary hole bins and primary electron bins (plus gain hole and gain electron bins when avalanche is enabled) elementwise into `sum_bins`. The in-window electrode current is the slice `[:, 1:-1]`, whereas net induced charge `charge = sum_bins.sum(axis=1) * t_bin` ($\text{C}$) includes all charge in the underflow and overflow bins.

### Avalanche Multiplication Algorithms

When `my_d.has_avalanche` is true, `CalCurrent` builds `CalCurrentGain`. `gain_algorithm(my_f)` selects the algorithm by the number of field axes: 1D fields (`len(my_f.axes) == 1`) use `"planar_integral"`, while multi-dimensional fields use `"local_path"` (which forces `keep_drift_paths = True`). Each algorithm generates starting positions and pair counts for gain electron-hole pairs, calls `drift_all` to drift them and `binned` to bin them, and merges the results into total current, `ends`, and `without_field`.

Limitation: `"local_path"` computes gain only once along primary carrier paths; gain clusters only drift and do not multiply further. Eq. (9) in `"planar_integral"` already includes mutual feedback between electrons and holes and does not have this limitation.

#### One-Dimensional Planar Integral (`planar_integral`)

1. **One-time profile integration (`DevsimField._integrate_planar_gain`, cached after first call)**:
   - Verifies `"z"` is in `my_f.axes`, raising `ValueError` otherwise. Extracts unique depth nodes $z_0 < z_1 < \dots < z_M$ ($\text{cm}$) of the potential mesh along the device centerline $(x, y) = (0.5 l_x, 0.5 l_y)$ and queries potential $U_m$ ($\text{V}$) at each node.
   - Takes a piecewise-constant electric field $E_m = -(U_{m+1} - U_m) / \Delta z_m$ ($\text{V/cm}$) on each interval $[z_m, z_{m+1}]$ ($\Delta z_m = z_{m+1} - z_m$) and calls `cal_coefficient(|E_m|, ±1, T)` to obtain $\alpha_{n,m}$ and $\alpha_{p,m}$ ($\text{cm}^{-1}$).
   - Finds the interval $m^*$ with largest $|E_m|$ and sets the gain-layer center depth to $z_{\text{gain}} = 0.5(z_{m^*} + z_{m^*+1})\times 10^4$ ($\mu\text{m}$). Uses $E_{m^*} > 0$ to determine whether electrons drift toward front face $z_0$ and $z_{m^*} + z_{m^*+1} \le z_0 + z_M$ to determine whether the gain layer lies in the front half, yielding the polarity `planar_gain_carrier` of carriers drifting from the bulk into the gain layer (`-1` for electrons, `+1` for holes).
   - Sets $r_m = \alpha_{n,m} - \alpha_{p,m}$. Accumulates $\ln K(z_m) = \sum r_m \Delta z_m$ starting from the electron-exiting face, and computes the breakdown integral analytically over the piecewise-constant intervals:
     $$I_{\text{bd}} = \sum_{m=0}^{M-1} \alpha_{p,m}\,K_{\text{near},m} \cdot \begin{cases} \Delta z_m, & r_m = 0 \\ \dfrac{e^{r_m \Delta z_m} - 1}{r_m}, & r_m \ne 0 \end{cases}$$
     where $K_{\text{near},m}$ is the value of $K$ at the end of the interval closer to the electron-exiting face. Raises `ValueError` if $I_{\text{bd}} \ge 1$.
   - For any creation depth $z$ ($\mu\text{m}$), `planar_gain_at(my_d, z)` linearly interpolates $\ln K$ at $z \times 10^{-4}$ on the mesh nodes and returns net gain $G(z) = \exp(\ln K) / (1 - I_{\text{bd}}) - 1$. `planar_gain(my_d)` returns the net gain at the far bulk face.
2. **Generating gain clusters (`_build_planar_gain_carriers`)**:
   - Takes the primary carrier system matching `planar_gain_carrier` as `source_system`.
   - For each path in `source_system` with $\ge 2$ points, computes depth offsets relative to the gain layer $d_k = z_k - z_{\text{gain}}$:
     - if $d_k d_{k+1} \le 0$ for some step (crossing the gain layer), takes the first crossing step $k$, interpolates $\eta = d_k / (d_k - d_{k+1})$ ($0$ if $d_k = d_{k+1}$), and evaluates the surviving carrier count at crossing $N_{\text{arr}}$ using `surviving_at` ($N_0$ without trapping);
     - if the path never crosses and $|d_{\text{end}}| < |d_0|$ (moving toward the gain layer without reaching it), skips with no multiplication;
     - if the path never crosses and $|d_{\text{end}}| \ge |d_0|$ (born on the near side of the gain layer and drifting away, so the opposite-polarity carrier immediately crosses the gain layer), takes the full initial count $N_{\text{arr}} = N_0$.
   - Spawns a pair of gain electron and hole clusters at $(x_{\text{end}}, y_{\text{end}}, z_{\text{gain}}, t_{\text{end}})$—where $x_{\text{end}}, y_{\text{end}}, t_{\text{end}}$ are the lateral position and time when the primary cluster stops drifting (not when it crosses the gain layer)—with pair count $|N_{\text{arr}}| \cdot G(z_0)$, where $z_0$ is the primary cluster's starting depth.

#### Multi-Dimensional Local Path Integral (`local_path`)

1. Read configuration parameters: `min_pairs = max(gain_pair_threshold, 0.0)` (default `0.05`), `max_carriers = gain_max_carriers` (default `50000`), `emit_slices = max(1, local_gain_emit_slices)` (default `1`), and `samples = max(1, local_gain_integration_steps)` (default `3`).
2. Iterate over every path with $\ge 2$ points in both primary electron and hole systems. Initialize untrapped cumulative active carrier count $N_{\text{act}} = |N_0|$, pending pair count $N_{\text{pend}} = 0$, and pending segment list `pending = []`. On step $k$, the untrapped fraction is $u_k = 1$ (no trapping) or $u_k = N_{k + 1/2} / N_0$ (with trapping).
3. For each step $(\mathbf{r}_k, t_k) \to (\mathbf{r}_{k+1}, t_{k+1})$ along the path (skipping zero spatial displacement):
   - Sample `samples` equally spaced midpoints $\mathbf{r}_{k,s} = \mathbf{r}_k + \frac{s + 0.5}{\text{samples}}(\mathbf{r}_{k+1} - \mathbf{r}_k)$ ($s = 0, \dots, \text{samples}-1$) along the step, querying $\mathbf{E}(\mathbf{r}_{k,s})$ and magnitude $E$ (on query exception, increment warning count and skip that sample; skip if $E \le 0$).
   - Project displacement along the carrier's drift direction: $\Delta s_{\mu\text{m}} = \text{sign} \cdot (\Delta\mathbf{r} \cdot \mathbf{E}) / E$; only when $\Delta s_{\mu\text{m}} > 0$, evaluate $\alpha = \max(\text{cal\_coefficient}(E, \text{sign}, T), 0)$ ($0$ if non-finite) and accumulate the step exponent:
     $$\eta_{\text{step}} = \sum_{s} \alpha_s \cdot \frac{\Delta s_{\mu\text{m}}}{\text{samples}} \times 10^{-4}$$
   - Clamp $\eta_{\text{step}}$ to upper bound `50.0` and compute untrapped growth $\Delta N_{\text{grow}} = N_{\text{act}}(\exp(\eta_{\text{step}}) - 1)$ and trapped-scaled new pairs $\Delta N_{\text{new}} = \Delta N_{\text{grow}} \cdot u_k$.
   - If $\Delta N_{\text{new}} \le 0$: if $N_{\text{pend}} > 0$, emit immediately and clear `pending`, then proceed to the next step.
   - Otherwise update $N_{\text{act}} \leftarrow N_{\text{act}} + \Delta N_{\text{grow}}$, $N_{\text{pend}} \leftarrow N_{\text{pend}} + \Delta N_{\text{new}}$, and append the current segment and $\Delta N_{\text{new}}$ to `pending`; as soon as $N_{\text{pend}} \ge \text{min\_pairs}$, emit immediately and clear `pending`.
4. At the end of the path, if $N_{\text{pend}} > 0$ remains, emit once more.
5. **Emission rule**: if `pending` holds a single step segment, the emission interval is that segment itself; if it spans multiple segments, compute the $\Delta N_{\text{new}}$-weighted centroid of the segment space-time midpoints $(x, y, z, t)$ as a single-point emission interval. Spawn `emit_slices` gain-pair origins at fractional positions $\frac{m + 0.5}{\text{emit\_slices}}$ along the emission interval, each carrying $N_{\text{pend}} / \text{emit\_slices}$ pairs. If `max_carriers > 0` and total emitted gain clusters exceed `max_carriers`, raise `ValueError`.

### Laser Temporal Pulse Convolution

`CalCurrentLaser` convolves the time-domain induced currents calculated under instantaneous generation with the laser temporal pulse shape $P(t)$ ($\text{s}^{-1}$, normalized to $\int P(t)\,dt = 1$):

1. Calls parent class `CalCurrent` to drift, multiply, and bin the initial electron-hole pairs produced by laser injection `my_l` (`CalCurrentLaser` defaults to `diffusion=True`, while `write_laser_currents` explicitly passes `diffusion=False`).
2. Calls `pulse_in_bins(my_l.timePulse, my_l.temporal_FWHM, n_bin, bin_width)` to compute discrete pulse weights at integer bin offsets $k \in [-(n_{\text{bin}} - 1),\, n_{\text{bin}} - 1]$:
   - Choose per-bin midpoint sample count $S = \max\!\left(1,\, \lceil 20\,\Delta t_{\text{bin}} / \text{FWHM} \rceil\right)$ (sampling spacing at most $\text{FWHM}/20$);
   - Integrate by the midpoint rectangle rule:
     $$p_k = \frac{\Delta t_{\text{bin}}}{S} \sum_{s=0}^{S-1} P\!\left(\left(k + \frac{s + 0.5}{S} - 0.5\right)\Delta t_{\text{bin}}\right)$$
3. Construct the $n_{\text{bin}} \times n_{\text{bin}}$ matrix $M_{a,b} = p_{a - b}$ and right-multiply the in-window arrays `hole_current`, `electron_current`, and `current` (plus `gain_current.hole_bins[:, 1:-1]` and `gain_current.electron_bins[:, 1:-1]` when avalanche is enabled):
   $$I^{\text{conv}}_{e, b} = \sum_{a=0}^{n_{\text{bin}}-1} I_{e, a}\,p_{a - b}$$
4. Pad both ends of the convolved waveforms with zero (zeroing underflow and overflow bins) and refill the corresponding ROOT histograms.

### Diffusion-Only Collection

`collect_by_diffusion(my_d, pairs, positions, window, step)` (`diffusion.py`, called by [../bench/telescope.md](../bench/telescope.md)) simulates pure diffusion collection of electrons in low-bias, field-free pixel sensors:

1. **Validation and geometry precomputation**: requires `my_d.is_pixel` to be true and `e_width_x`, `e_width_y` ($\mu\text{m}$) to be defined on the device. Computes intra-pixel margins `low_x = (p_x - e_width_x)/2`, `low_y = (p_y - e_width_y)/2`, and the centered pixel-array origin `first_x = (l_x - x_ele_num * p_x)/2`, `first_y = (l_y - y_ele_num * p_y)/2`.
2. **Zero-field mobility and step standard deviation**: takes effective doping $N_{\text{eff}} = \text{Donors} - \text{Acceptors}$ ($\text{cm}^{-3}$), calls `Material(material).cal_mobility(T, N_eff, -1, 0)` for zero-field electron mobility $\mu_n(0)$, and computes the Gaussian displacement standard deviation $\sigma$ ($\mu\text{m}$) for time step `step` ($\text{s}$) using Eq. (3).
3. **Time binning**: sets step cap $K = \text{round}(\text{window} / \text{step})$, first-bin left edge $t_0 = \min_m t_m$, and latest creation time $t_{\max} = \max_m t_m$ ($0.0$ if no deposits). Helper `time_bin(t, t0, step)` computes $k = \lfloor q \rfloor$ for $q = (t - t_0)/\text{step}$, adding $1$ when $q - k > 1 - 10^{-9}$ to eliminate floating-point boundary error at integer steps. Total bin count is $n_{\text{bin}} = \text{time\_bin}(t_{\max}, t_0, \text{step}) + K + 1$.
4. **2D random walk**: draws random numbers from dedicated random stream `stream("diffusion")` and iterates over each deposit cluster $(x, y, z, t, n_{\text{pairs}})$ satisfying $0 \le z \le l_z$, with starting bin $k_0 = \text{time\_bin}(t, t_0, \text{step})$, looping $k = 0, 1, \dots, K$:
   - if $0 < x < l_x$ and $0 < y < l_y$ does not hold, the cluster exits through a side face and terminates;
   - compute pixel indices $i = \lfloor (x - \text{first\_x}) / p_x \rfloor$, $j = \lfloor (y - \text{first\_y}) / p_y \rfloor$ and check whether the position falls strictly inside the pixel's central rectangular collection zone ($\text{low\_x} < x - \text{first\_x} - i p_x < p_x - \text{low\_x}$, similarly in $y$, with $0 \le i < N_x$ and $0 \le j < N_y$); on hit, add $n_{\text{pairs}}$ to bin $k_0 + k$ of pixel $i N_y + j$ and terminate;
   - otherwise update $x \leftarrow x + \mathcal{N}(0, \sigma^2)$, $y \leftarrow y + \mathcal{N}(0, \sigma^2)$.
5. **Return current and net charge**: net pixel charge `charge = -e * electrons.sum(axis=1)` ($\text{C}$) and mean bin current `current = -e * electrons / step` ($\text{A}$), negative for electrons.

Limitation: this model omits junction electric fields and drift, $z$-direction motion, carrier recombination, and hole contributions, and does not compute current induced prior to arrival at the collection zone—currents are derived solely from charge arriving in each time bin.

## Software Implementation

### Module and Function Responsibilities

- `drift.py`: implements single-cluster transport and per-step physics. `advance` performs one step advance and stop checks, and `drift` loops a cluster until stopped; `induced_charges` computes Shockley-Ramo induced charges per step on a specified electrode; `surviving` and `surviving_at` compute surviving carrier counts under trapping.
- `cal_current.py`: implements event-level transport orchestration, binning, avalanche multiplication, laser convolution, and batch output. `CalCurrent` handles time-window setup, spatial filtering, carrier drift, and binning; `CalCurrentGain` subclasses `CalCurrent` to execute `"planar_integral"` or `"local_path"` multiplication selected by `gain_algorithm`; `CalCurrentG4P` wraps `CarrierListFromG4P` inputs; `CalCurrentLaser` performs laser pulse convolution using `pulse_in_bins`; `spread_over_bins`, `fill_histogram`, `electrode_names`, `split_at_conductor_edges`, `deposits_in`, and `log_ends` are helper functions; `write_induced_currents` and `write_laser_currents` write event results to HDF5 files and trigger plotting.
- `diffusion.py`: provides `time_bin` and `collect_by_diffusion` for 2D diffusion-only collection in field-free pixel sensors.
- `currents.py`: defines `EventCurrents`, `Currents`, `append_currents`, and `read_currents` for sparse per-event appending to `current_<job>.h5` and full-electrode restoration on read.
- `draw.py` and `draw_drift_path.py`: use PyROOT to plot induced-current waveforms (`draw_currents`), strip/pixel collected charge (`charge_collection_strip`, `charge_collection_pixel`), and 3D/$x$-$z$ drift paths (`draw_drift_path`).

### Core Data Structures

- `Cluster` (`drift.py`): represents a single drifting carrier cluster, holding signed carrier count `carriers`, current coordinates `position` ($\mu\text{m}$), current time `t` ($\text{s}$), start time `start` ($\text{s}$), trajectory point list `path`, and stop reason `reason` (`None` while drifting), constructed via `Cluster.starting(x, y, z, t, carriers)`.
- `Drifted` (`drift.py`): holds the drift results for all clusters of one polarity in four equal-length lists: `carriers` (initial signed carrier counts), `paths` (per-cluster `(x, y, z, t)` arrays of shape `(points, 4)`), `reasons` (stop reasons), and `remaining` (per-step midpoint signed surviving counts, `None` without trapping); when `keep_drift_paths=False`, `paths` and `remaining` are cleared after computation to free memory.
- `EventCurrents` (`currents.py`): single-event current output record containing event ID `event`, left edge of first bin `t0` ($\text{s}$), time-domain current matrix `current` (shape `(electrodes, bins)`, $\text{A}$), net electrode charges `charge` (shape `(electrodes,)`, $\text{C}$), initial pair count `pairs`, and optional fields `sensitive_pairs` and `carriers_without_field` written when drifting in a solved field. `read_currents` returns `Currents(electrodes, dt, events)` wrapping the entire file.

## Interface

See [../stages/current.md](../stages/current.md) for the command-line entry point and slice scheduling options, and [field.md](field.md) for bias, irradiation fluence, and 3D interpolation settings used to construct `DevsimField`.

### Keys Read from the Device File

Users can configure only the keys listed in the table below. All other parameters on this page (mobility model, time window, step sizes, diffusion switch) are hardcoded.

| Key or Derived Attribute | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `default_dimension`, `field_dimension`, `mesh.plugin` | see [device.md](device.md) (`mesh.plugin` defaults to `False`) | None | Map to `dimension` and `is_plugin()`, selecting the time-window and step-size profile |
| `l_x`, `l_y`, `l_z` | None (required) | $\mu\text{m}$ | Device bounds $[0, l_x] \times [0, l_y] \times [0, l_z]$ |
| `electrodes`, `p_x`, `p_y`, `x_ele_num`, `y_ele_num`, `read_ele_num` | see [device.md](device.md) | $\mu\text{m}$ / count | Layout, pitch, and counts of the centered readout electrode array; `electrodes` (`"strip"`/`"pixel"`) also determines the charge-collection plot type, and `"pixel"` is required for `collect_by_diffusion` |
| `read_out_contact` | None (required) | None | List of readout electrode dicts, each containing `"name"`; for a single repeated electrode, optional `"y_span"` (default `0`) sets neighbor span along `y` (`x` span comes from `cells_either_side` of the field object) |
| `det_name`, `det_model` | `det_name` defaults to filename stem; `det_model` has no default (required for plotting) | None | Device name (used in error messages) and model identifier (used in `<det_model>_drift_path` filenames) |
| `material`, `temperature` | None (required) | None, $\text{K}$ | Material name (passed to `Material` in [model.md](model.md)) and device temperature $T$ |
| `irradiation.irradiation_model` | `None` if no `irradiation` block | None | Maps to `irradiation_model`; enables carrier trapping decay when non-`None` |
| `enable_gain`, `avalanche_model` | `False`, `None` | None | When both are active, `has_avalanche` is true and enables `CalCurrentGain`; supports `"vanOverstraeten"`, `"Okuto"`, `"Hatakeyama"` |
| `gain_pair_threshold` | `0.05` | pairs | Minimum accumulated pairs to trigger emission of a new gain cluster in `"local_path"` mode (negative values clamped to `0.0`) |
| `gain_max_carriers` | `50000` | clusters | Maximum gain clusters allowed per event in `"local_path"` mode; unlimited when $\le 0$ |
| `local_gain_emit_slices` | `1` | clusters | Number of sub-clusters evenly split along the step per emission in `"local_path"` mode (at least `1`) |
| `local_gain_integration_steps` | `3` | steps | Number of sampling points integrating the ionization coefficient within one drift step in `"local_path"` mode (at least `1`) |
| `fano_sampling`, `fano_factor` | `False`, `0.0` | None | Fano sampling switch and factor passed only by `CalCurrentG4P` to `CarrierListFromG4P` |
| `e_width_x`, `e_width_y` | None (required for `collect_by_diffusion`) | $\mu\text{m}$ | Dimensions of the central rectangular collection zone in each pixel for diffusion-only collection |
| `doping.Donors`, `doping.Acceptors` | None (required for `collect_by_diffusion`) | $\text{cm}^{-3}$ | Numeric donor and acceptor concentrations used to compute zero-field electron mobility in diffusion-only collection |

### `current_<job>.h5` File Format

Written event by event via `append_currents`, storing only electrodes whose current array is not identically zero; `read_currents` restores unstored electrodes as all-zero arrays.

**File Attributes**

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `electrodes` | string array | None | List of readout electrode names, ordered identically to columns of `charge` |
| `dt` | `float64` | $\text{s}$ | Time-bin width (equal to `t_bin`) |

**Datasets**

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(events,)`, `int64` | None | Event ID (`0` when written by `write_laser_currents`) |
| `t0` | `(events,)`, `float64` | $\text{s}$ | Left edge of the event's first time bin (equal to `t_start`) |
| `count` | `(events,)`, `int64` | bins | Number of time bins for the event (equal to `n_bin`) |
| `pairs` | `(events,)`, `float64` | pairs | Total input electron-hole pairs for the event (before avalanche multiplication) |
| `sensitive_pairs` | `(events,)`, `float64` (optional) | pairs | Electron-hole pairs born inside the device, above the electrode array, and in a non-conductive region (present when written by drifting in a solved field) |
| `carriers_without_field` | `(events,)`, `float64` (optional) | count | Total untrapped carriers remaining at stop time in clusters (including gain clusters) that stopped with `"no_field"` (present when written by drifting in a solved field) |
| `charge` | `(events, len(electrodes))`, `float64` (gzip) | $\text{C}$ | Signed net induced charge on each readout electrode (including underflow and overflow bins before/after the time window) |
| `stored` | `(events,)`, `int64` | count | Number of electrodes in the event with non-all-zero current arrays stored in `current` |
| `index` | `(sum(stored),)`, `int64` | None | `0`-based index in `electrodes` of each stored electrode, partitioned per event by `stored` |
| `current` | `(sum(stored * count),)`, `float64` (gzip) | $\text{A}$ | Mean induced current across `count` time bins for each stored electrode, concatenated sequentially by event and stored electrode |

### Plot Outputs

`write_induced_currents(deposits_path, currents_path, my_d, my_f, plots=0, plot_path=None, detector=None)` reads the deposit file at `deposits_path` and writes currents to `currents_path`; with the default `plots=0`, no plots are drawn and `plot_path` need not be given. When `plots > 0`, drift-path plots, current-waveform plots, and (for strip/pixel layouts) collected-charge plots are generated under `<plot_path>/event_<event>/` for the first `plots` events, where the stage passes `current.plots` as `plots` and places `plot_path` inside the `current` node itself; `write_laser_currents` draws only current-waveform plots when `plot_path` is provided.

| Filename | Content | Unit |
| --- | --- | --- |
| `<det_model>_drift_path.pdf`, `.root` | Top panel: 3D device bounding box with deposition points (black), hole (red), electron (blue), gain hole (magenta), and gain electron (light blue) paths; bottom panel: $x$-$z$ plane projection | spatial axes $\mu\text{m}$ |
| `<tag>No_<k>electrode_basic_infor.pdf`, `.root` | Drawn only for the $k$-th electrode (`1`-based) having non-zero current components, showing `electron`, `hole`, `total` (plus `electron gain` and `hole gain` when avalanche is enabled); `tag` defaults to empty | `Time [s]`, `Current [A]` |
| `cce.pdf`, `.root` | Line graph of collected charge per strip (`TGraph`) when `is_strip` is true; 2D pixel distribution (`TH2I`) when `is_pixel` is true; values are in electron counts (converted by `charge / 1.6e-19`), though the axis title in code is still labeled `charge[Coulomb]` | electron count |

## References

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] A. Einstein, “Über die von der molekularkinetischen Theorie der Wärme geforderte Bewegung von in ruhenden Flüssigkeiten suspendierten Teilchen”, Ann. Phys. 322 (1905) 549, doi:10.1002/andp.19053220806
- [3] W. Shockley, W. T. Read, Jr., “Statistics of the Recombinations of Holes and Electrons”, Phys. Rev. 87 (1952) 835, doi:10.1103/PhysRev.87.835
- [4] G. Kramberger, V. Cindro, I. Mandić, M. Mikuž, M. Zavrtanik, “Effective trapping time of electrons and holes in different silicon materials irradiated with neutrons, protons and pions”, Nucl. Instrum. Methods Phys. Res. A 481 (2002) 297, doi:10.1016/S0168-9002(01)01263-3
- [5] W. Shockley, “Currents to Conductors Induced by a Moving Point Charge”, J. Appl. Phys. 9 (1938) 635, doi:10.1063/1.1710367
- [6] S. Ramo, “Currents Induced by Electron Motion”, Proc. IRE 27 (1939) 584, doi:10.1109/JRPROC.1939.228757
- [7] R. J. McIntyre, “Multiplication Noise in Uniform Avalanche Diodes”, IEEE Trans. Electron Devices 13 (1966) 164, doi:10.1109/T-ED.1966.15651
- [8] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [9] Y. Okuto, C. R. Crowell, “Threshold energy effect on avalanche breakdown voltage in semiconductor junctions”, Solid-State Electronics 18 (1975) 161, doi:10.1016/0038-1101(75)90099-4
- [10] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [11] T. Hatakeyama, J. Nishio, C. Ota, T. Shinohe, “Physical modeling and scaling properties of 4H-SiC power devices”, Proc. Int. Conf. Simulation of Semiconductor Processes and Devices (SISPAD) (2005) 171, doi:10.1109/SISPAD.2005.201500
