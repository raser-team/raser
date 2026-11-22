# Energy Deposition and Ionization (`core/deposit`)

`src/raser/core/deposit/` takes the device dimensions and material from the [device model](device.md) and the setup script, radioactive source or beam, and laser definitions from [energy deposition components](../components/deposit.md). It uses Geant4 or a straight-line toy MIP model to compute particle deposition steps in the device (when the setup provides `devices`, it computes each device's deposit steps for multiple devices in one run), converts the deposited energy of each step into electron-hole pairs, and writes `deposit.h5`; for lasers, it directly produces carrier groups according to the absorption coefficient and likewise writes `deposit.h5`. The deposit file is passed to [carrier drift and induced current](current.md) for drift simulation, the earliest deposition time of each event is passed to [statistical analysis](analysis.md) as `truth`, and the [telescope](../bench/telescope.md) also reads this file. For commands and settings in the `deposit` section, see the [energy deposition stage](../stages/deposit.md).

## Physics

### Ionization Energy and Electron-Hole Pairs

When a charged particle loses energy in a semiconductor, on average one electron-hole pair is created per $\varepsilon$ of energy deposited. The fluctuation in the number of pairs is smaller than Poisson fluctuations, with a variance equal to $F$ times the mean (the Fano factor). The mean and sampled numbers of pairs for each deposition step are:

$$\bar{N} = \frac{E}{\varepsilon \times 10^{-6}} \tag{1}$$

$$N = \max\bigl(0,\ X\bigr), \qquad X \sim \mathcal{N}\bigl(\bar{N},\ F\bar{N}\bigr) \tag{2}$$

where:

- $E$: deposited energy in the step, $\text{MeV}$;
- $\varepsilon$: mean ionization energy of the material, $\text{eV}$ (`PAIR_ENERGY_EV`, with $10^{-6}$ converting it to $\text{MeV}$);
- $\bar{N}$: mean number of electron-hole pairs, pairs;
- $F$: Fano factor, dimensionless (`FANO_FACTOR`);
- $\mathcal{N}(\mu, \sigma^2)$: Gaussian distribution with mean $\mu$ and variance $\sigma^2$;
- $N$: number of pairs written to the file, pairs.

Both equations are implemented by `ionized_pairs(event, material, fano)`. When `fano=True`, sampling follows Eq. (2); otherwise $N = \bar{N}$, and the material does not need a Fano factor. Values for each material:

| Material | `PAIR_ENERGY_EV` ($\text{eV}$) | `FANO_FACTOR` | Source |
| --- | --- | --- | --- |
| `"Si"` | `3.6` | `0.115` | Ionization energy is an approximation to the $3.65\ \text{eV}$ given in PDG Sec. 35.8, Table 35.10 [8]; Fano factor takes the asymptotic value $0.115$ [9], measured as $0.1161$ [10] |
| `"SiC"` | `7.83` | `0.128` | Electron-hole pair creation energy of 4H-SiC $(7.83 \pm 0.02)\ \text{eV}$ [11]; Fano factor $0.128$ [12] |
| `"Diamond"` | `13.1` | `0.382` | Measured on CVD diamond with $5.486\ \text{MeV}$ α particles from Am-241; Fano factor is $0.382 \pm 0.007$ [2] |

For Fano fluctuations, see Ref. [1].

### Energy Loss in Geant4

The two source kinds `beam` and `decay_source` are transported by Geant4 [3, 4]. The physics list is `FTFP_BERT` plus `G4StepLimiterPhysics`; when the source contains `nuclides`, `G4RadioactiveDecayPhysics` [5] is also added, and the radioactive decay time threshold is set to $10^{60}$ years so that nuclides of any lifetime decay. Production cuts keep the defaults of the physics list. Each device's logical volume (`"Device"` for a single device, or the slot name for multiple devices) carries a `G4UserLimits` whose maximum step length is the setup's `maxstep`. Geant4 also truncates steps at volume boundaries and physics processes. Each step whose pre-step point lies inside a device logical volume is recorded as a deposition step of that device:

$$E_k = \texttt{GetTotalEnergyDeposit}, \qquad \mathbf{r}_k = \tfrac{1}{2}\bigl(\mathbf{r}_k^{\text{pre}} + \mathbf{r}_k^{\text{post}}\bigr), \qquad \ell_k \le s_{\max} \tag{3}$$

where:

- $E_k$: total deposited energy of step $k$ inside the device, $\text{MeV}$;
- $\mathbf{r}_k^{\text{pre}}, \mathbf{r}_k^{\text{post}}$: pre-step and post-step points of the step, $\mu\text{m}$;
- $\mathbf{r}_k$: position of the deposition step, taken at the step midpoint, $\mu\text{m}$ (code comment notes: when the step endpoints lie on the device surface, rounding error may place an endpoint outside the device);
- $\ell_k$: step length, $\mu\text{m}$; $s_{\max}$: the setup's `maxstep`, $\mu\text{m}$.

The device material in Geant4 is built according to `material`: `"Si"` uses NIST `G4_Si`; `"Diamond"` uses `G4_C` with the density changed to $3.52\ \text{g/cm}^3$ (code comment: NIST `G4_C` is graphite at $2.0\ \text{g/cm}^3$); `"SiC"` is a compound of equal atomic fractions of Si and C with density $3.21\ \text{g/cm}^3$. The diamond density is taken from the PDG table of atomic and nuclear properties [8], and the 4H-SiC density is taken from Ref. [13].

### Toy MIP Track

A toy MIP is a straight track passing through the device with fixed mean energy loss per unit length; after segmentation, each segment can fluctuate according to a Landau distribution [6]. The mean energy loss per unit length and the energy of each segment are:

$$\frac{dE}{dx} = n_{\text{MIP}}\,\varepsilon \times 10^{-6} \tag{4}$$

$$E_k = \begin{cases} \max\bigl(0,\ Y\bigr),\quad Y \sim \text{Landau}\Bigl(\dfrac{dE}{dx}\,\Delta l,\ w\,\Delta l\Bigr), & \texttt{landau\_sampling} = \texttt{true} \\[2ex] \dfrac{dE}{dx}\,\Delta l, & \texttt{landau\_sampling} = \texttt{false} \end{cases} \tag{5}$$

$$p(Y) = \frac{1}{\pi \sigma}\int_0^\infty e^{-t \ln t - \lambda t}\sin(\pi t)\,dt, \qquad \lambda = \frac{Y - \mu}{\sigma} \tag{6}$$

where:

- $n_{\text{MIP}}$: mean number of pairs per $\mu\text{m}$ of track, $\mu\text{m}^{-1}$ (`PAIRS_PER_UM`);
- $\varepsilon$: mean ionization energy from Eq. (1), $\text{eV}$;
- $dE/dx$: mean energy loss per unit length, $\text{MeV}/\mu\text{m}$;
- $\Delta l = L / n$: length of each segment, $\mu\text{m}$, where $L$ is the track length and $n$ is the number of segments;
- $w$: Landau width, $\text{MeV}/\mu\text{m}$ (`LANDAU_WIDTH_MEV_PER_UM`);
- $\mu = (dE/dx)\,\Delta l$, $\sigma = w\,\Delta l$: location and scale parameters passed to ROOT's `TRandom::Landau`, $\text{MeV}$;
- $E_k$: deposited energy of segment $k$, $\text{MeV}$.

This is implemented by `mip_deposits`. The number of pairs in each segment is then obtained via `ionized_pairs` according to Eqs. (1) and (2), so when `landau_sampling` is `false` and `fano` is `false`, there are exactly $n_{\text{MIP}}$ pairs per $\mu\text{m}$. Only two materials are supported:

| Material | `PAIRS_PER_UM` ($\mu\text{m}^{-1}$) | $dE/dx$ ($\text{MeV}/\mu\text{m}$) | `LANDAU_WIDTH_MEV_PER_UM` ($\text{MeV}/\mu\text{m}$) |
| --- | --- | --- | --- |
| `"Si"` | `80.0` | `2.88e-4` | `1.78e-5` |
| `"SiC"` | `55.0` | `4.31e-4` | `2.46e-5` |

Si yields about $80$ pairs per $\mu\text{m}$: the most probable charge in $300\ \mu\text{m}$ of silicon is about $23\,000\ e$, i.e. about $77\ e/\mu\text{m}$ [8, 14]. SiC yields about $55$ pairs$/\mu\text{m}$, converted from $7.83\ \text{eV}$ and MIP energy loss. The Landau width follows PDG Ch. 34 [8]:

$$w = \frac{K}{2}\left\langle\frac{Z}{A}\right\rangle\frac{\rho}{\beta^2} \times 10^{-4} \tag{4a}$$

with $\beta = 1$, where $K/2 = 0.1535\ \text{MeV cm}^2/\text{g}$, $\rho$ is the density ($\text{g/cm}^3$), and $10^{-4}$ converts per $\text{cm}$ to per $\mu\text{m}$: $1.78\times10^{-5}\ \text{MeV}/\mu\text{m}$ for Si ($\langle Z/A\rangle = 0.4985$, $\rho = 2.329$), and $2.46\times10^{-5}\ \text{MeV}/\mu\text{m}$ for 4H-SiC ($\langle Z/A\rangle = 0.4988$, $\rho = 3.21$).

### Single-Photon and Two-Photon Absorption of Lasers

A laser pulse generates carriers in the device via optical absorption. In single-photon absorption (SPA), each absorbed photon produces one electron-hole pair, and the intensity attenuates along the beam path according to the Beer–Lambert law as $e^{-\alpha s}$. In two-photon absorption (TPA), following $dI/dz = -\alpha I - \beta_2 I^2$ [15], the generation rate is proportional to the square of the intensity and is concentrated near the focus. The beam is Gaussian, with a transverse radius that expands with distance from the focus.

When `alpha` is not given in the laser file, the absorption coefficient $\alpha$ is looked up by `absorption_coefficient`:

$$\alpha(\lambda) = 100\,\exp\Bigl[\operatorname{interp}\bigl(10^{3}\lambda;\ \lambda_i,\ \ln \alpha_i\bigr)\Bigr] \tag{7}$$

The photon energy, photon count, and Gaussian beam radius are:

$$h\nu = \frac{h c}{\lambda \times 10^{-6}}, \qquad N_\gamma = \frac{E_p}{h\nu} \tag{8}$$

$$w_0 = \frac{\text{FWHM}_s}{\sqrt{2\ln 2}}, \qquad z_R = \frac{\pi w_0^2 n}{\lambda}, \qquad w^2(s) = w_0^2\left[1 + \left(\frac{s - s_f}{z_R}\right)^2\right] \tag{9}$$

The number of pairs generated per unit path length (integrated over the transverse cross section) is:

$$\left.\frac{dN}{ds}\right|_{\text{SPA}} = \alpha\, N_\gamma\, e^{-\alpha s \times 10^{-6}} \tag{10}$$

$$\left.\frac{dN}{ds}\right|_{\text{TPA}} = \frac{\beta_2\, E_p^2\, e^{-2\alpha s \times 10^{-6}}}{2\,h\nu\,\pi\, w^2(s) \times 10^{-12}} \cdot \frac{\sqrt{2\ln 2}}{\sqrt{\pi}\,\tau} \tag{11}$$

The transverse distribution and the generation-time distribution are:

$$\frac{dN}{dA} \propto \exp\!\left(-\frac{k\, r^2}{w^2(s)}\right), \qquad k = \begin{cases} 2, & \text{SPA} \\ 4, & \text{TPA} \end{cases} \tag{12}$$

$$P(t) = \frac{2\sqrt{2\ln 2}}{\sqrt{2\pi}\,\tau}\exp\!\left(-\frac{4\ln 2\; t^2}{\tau^2}\right) \tag{13}$$

where:

- $\lambda$: wavelength, $\mu\text{m}$ (`wavelength` in the laser file is given in $\text{nm}$ and multiplied by $10^{-3}$);
- $\lambda_i, \alpha_i$: wavelengths ($\text{nm}$) and absorption coefficients ($\text{cm}^{-1}$) in the absorption-coefficient table, with `interp` denoting linear interpolation between adjacent rows and $100$ converting $\text{cm}^{-1}$ to $\text{m}^{-1}$;
- $\alpha$: absorption coefficient, $\text{m}^{-1}$;
- $h = 6.626\times10^{-34}\ \text{J}\cdot\text{s}$, $c = 2.998\times10^{8}\ \text{m/s}$; $h\nu$: photon energy, $\text{J}$;
- $E_p$: pulse energy `pulse_energy`, $\text{J}$; $N_\gamma$: number of photons in the pulse;
- $\text{FWHM}_s$: spatial full width at half maximum of the beam spot at the focus `spacial_FWHM`, $\mu\text{m}$; $w_0$: beam waist radius, $\mu\text{m}$;
- $n$: refractive index `refractionIndex`; $z_R$: Rayleigh length, $\mu\text{m}$ (if `l_Rayleigh` is given in the laser file, the given value is used);
- $s$: distance along the beam path from the entrance face, $\mu\text{m}$; $s_f$: focal position along the beam path, $\mu\text{m}$; $w(s)$: beam radius at $s$, $\mu\text{m}$;
- $\beta_2$: two-photon absorption coefficient `beta_2`, $\text{m/W}$;
- $\tau$: temporal full width at half maximum of the pulse `temporal_FWHM`, $\text{s}$;
- $dN/ds$: number of pairs generated per meter of beam path, $\text{m}^{-1}$ ($10^{-6}$ and $10^{-12}$ convert $\mu\text{m}$ and $\mu\text{m}^2$ to $\text{m}$ and $\text{m}^2$);
- $r$: distance from the optical axis, $\mu\text{m}$;
- $P(t)$: normalized temporal distribution at offset $t$ ($\text{s}$) from the pulse center, $\text{s}^{-1}$ (`timePulse`).

The second factor in Eq. (11) is the integral of the squared Gaussian temporal pulse distribution. Beam intensity along the path attenuates only according to $\alpha$. When $\alpha \ne 0$, SPA carrier groups are added according to Eq. (10); when `tech` is `"TPA"`, TPA carrier groups are additionally added according to Eq. (11); for a two-photon laser, $\alpha$ represents defect absorption of sub-bandgap photons (code comment). The generation time of each group is broadened around `central_time` with FWHM $\tau$ for SPA groups and $\tau/\sqrt{2}$ for TPA groups, because $P^2(t)$ is a Gaussian narrower by a factor of $\sqrt{2}$. This is implemented by `LaserInjection`. The absorption-coefficient table `Si.txt` is taken from Ref. [7].

### Radioactive Decay Sources

Each event of a radioactive source is a single decay of a nuclide at rest. A nuclide is drawn with equal probability from `nuclides`, and its position is uniformly distributed on a disk perpendicular to the emission axis. The initial time of decay products is reset to zero and the daughter nucleus left by the decay is killed there, so one event corresponds to one decay. When `par_cone` is given, the directions of decay products are resampled isotropically inside a cone around the emission axis:

$$\hat{\mathbf{a}} = \frac{\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}}{|\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}|}, \qquad |\mathbf{r}_0 - \mathbf{r}_{\text{in}}| \le R, \quad (\mathbf{r}_0 - \mathbf{r}_{\text{in}}) \perp \hat{\mathbf{a}} \tag{14}$$

$$\cos\theta = 1 - u_1\,(1 - \cos\theta_c), \qquad \varphi = 2\pi u_2, \qquad \hat{\mathbf{d}} = \cos\theta\,\hat{\mathbf{a}} + \sin\theta\,(\cos\varphi\,\hat{\mathbf{e}}_1 + \sin\varphi\,\hat{\mathbf{e}}_2) \tag{15}$$

$$f = \frac{1 - \cos\theta_c}{2} \tag{16}$$

where:

- $\mathbf{r}_{\text{in}}, \mathbf{r}_{\text{out}}$: source position and aiming point (the setup's `source.at` and `source.towards`), $\mu\text{m}$; $\hat{\mathbf{a}}$: unit vector along the emission axis;
- $\mathbf{r}_0$: nuclide position, $\mu\text{m}$; $R$: disk radius `par_radius`, $\mu\text{m}$ (point source when $R = 0$);
- $\hat{\mathbf{e}}_1, \hat{\mathbf{e}}_2$: unit vectors orthogonal to $\hat{\mathbf{a}}$;
- $\theta_c$: half-cone angle `par_cone`, degrees; $u_1, u_2$: uniform random numbers on $[0, 1)$;
- $\hat{\mathbf{d}}$: emission direction of the decay product;
- $f$: fraction of the full solid angle covered by the cone, written to the file attribute `generated_fraction`.

Nuclides are generated by `NuclideGeneratorAction` (`G4GeneralParticleSource`, kinetic energy $0$), while time zeroing, daughter killing, and cone direction resampling are performed by `DecayStackingAction`, identifying decay tracks by the creator process subtype `RADIOACTIVE_DECAY = 210`. A code comment notes that Geant4's built-in `/process/had/rdm/decayHalfAngle` only works around the $z$ axis, so this is implemented directly. For radioactive decay in Geant4, see Ref. [5].

### Placement of Multiple Devices

The setup's `devices` specifies a set of slots, each holding one device whose board is perpendicular to the $z$ axis and may be rotated about the $z$ axis by $0^\circ$, $90^\circ$, $180^\circ$, or $270^\circ$. The slot's device coordinates $(x, y, z)$ (with origin at a corner of the device's front surface, identical to the device coordinates for a single device) relate to the Geant4 coordinates $\mathbf{r}_{\text{G4}}$ by:

$$\mathbf{r}_{\text{G4}} = \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} x - l_x/2 \\ y - l_y/2 \\ z \end{pmatrix} \tag{17}$$

where:

- $\mathbf{P}$: the slot's `position`, Geant4 coordinates of the center of the device front surface (the $z = 0$ plane in device coordinates), $\mu\text{m}$;
- $\phi$: the slot's `rotation_z`, degrees, restricted to `0`, `90`, `180`, `270`;
- $l_x, l_y$: dimensions of the device in that slot, $\mu\text{m}$.

When $\mathbf{P} = 0$ and $\phi = 0$, this reduces to the placement of a single device.

## Algorithm

### Built-in Constants

| Constant | Value | Unit | Location and Meaning | Key in File |
| --- | --- | --- | --- | --- |
| `PAIR_ENERGY_EV` | Si `3.6`, SiC `7.83`, Diamond `13.1` | $\text{eV}$ | `ionization.py`, $\varepsilon$ in Eq. (1) | none |
| `FANO_FACTOR` | Si `0.115`, SiC `0.128`, Diamond `0.382` | dimensionless | `ionization.py`, $F$ in Eq. (2) | none (the switch `deposit.fano` is a stage setting) |
| `PAIRS_PER_UM` | Si `80.0`, SiC `55.0` | $\mu\text{m}^{-1}$ | `mip_track.py`, $n_{\text{MIP}}$ in Eq. (4) | none |
| `LANDAU_WIDTH_MEV_PER_UM` | Si `1.78e-5`, SiC `2.46e-5` | $\text{MeV}/\mu\text{m}$ | `mip_track.py`, $w$ in Eq. (5) | none |
| `GENERATED_LIMIT` | `10_000_000` | events | `generation.py`, maximum number of generated events when running by recorded count | none (stage setting `deposit.generated_limit`) |
| `DEVICE_ALONE` | see "Setup" below | — | `simulate_deposits.py`, setup used when none is given | replaced as a whole by `deposit.g4setup` |
| `WORLD_HALF_SIDE` | `25000` | $\mu\text{m}$ | `simulate_deposits.py`, default half-side length of the world cube | `world_half_size_um` under `gdml_import` |
| Physics list | `FTFP_BERT` + `G4StepLimiterPhysics` | — | `geant4/interaction.py` | none |
| Radioactive decay time threshold | `1.0e60` | years | `geant4/interaction.py` | none |
| Random engine | `CLHEP::RanecuEngine`, seeded by the `deposit` stage's seed (derived from the job's seed) | — | `geant4/interaction.py` | none |
| Device density | Diamond `3.52`, SiC `3.21` (Si:C atomic ratio `50:50`) | $\text{g/cm}^3$ | `geant4/detector_construction.py` | none |
| `RADIOACTIVE_DECAY` | `210` | — | `geant4/nuclide_source.py`, process subtype for radioactive decay | none |
| $h$, $c$ | `6.626e-34`, `2.998e8` | $\text{J}\cdot\text{s}$, $\text{m/s}$ | `laser.py`, Eq. (8) | none |
| Number of rings, number of sectors | `4`, `8` | count | `laser.py`, division of the laser cross section | none |
| Beam-path sampling density | `50` points per finest scale | — | `laser.py`, see "Laser Carrier Groups" | none |

### Branches of `simulate_deposits`

`simulate_deposits(devices, source, g4setup, events, g4_seed, edep_min, edep_max, fano, generated, generated_limit, picture, drawn)` executes in the following order. `devices` is an ordered dictionary mapping slot names to devices. When the setup has no `devices` key, it is equivalent to `"devices": {"Device": {"position": [0, 0, 0]}}`, i.e. a single-device experiment has slot name `"Device"` and passes `{"Device": my_d}`. The slot names in the setup and in the `devices` argument must match one-to-one (their order may differ); any extra or missing slot raises `ValueError` (`the g4setup places <setup slots>, the devices are <given slots>`).

1. **Check source kind**: If `source["kind"]` is not one of `"toy_mip"`, `"beam"`, or `"decay_source"`, raise `ValueError` (`no simulation of deposits for a source of kind ...`).
2. **Check event counts**: `asked(events, generated, generated_limit)` requires that exactly one of `events` (number of events to record) and `generated` (number of events to generate) be given, raising `ValueError` otherwise; if the given number or `generated_limit` is less than `1`, raise `ValueError` (`the <name> asked for are <number>: at least 1`).
3. **Toy MIP branch** (`kind == "toy_mip"`): Read `g4setup["maxstep"]` (or `DEVICE_ALONE["maxstep"] = 2` when `g4setup` is `None`) and call `mip_deposits(devices, source, g4setup, ...)`; see the next section. This branch runs in Python, drawing random numbers from the stream `stream("toy_mip")`.
4. **Geant4 branch** (`kind` is `"beam"` or `"decay_source"`):
   1. Import `geant4.interaction`. If `g4ppyy` is missing, raise `MissingDependency` (`Geant4's Python bindings, g4ppyy, are not installed in this Python`).
   2. `g4_configuration` builds the run configuration: if `par_in`, `par_out`, or `par_angle` appears in the source or in its `particles`, raise `ValueError` (source placement belongs to the setup); take a deep copy of `g4setup` (or `DEVICE_ALONE` if `None`) and pop `"source"`, raising `ValueError` if absent (`the g4setup ... does not place the source`); overwrite same-named setup keys with keys from the source and remove `name`, `kind`, and `description`; set `par_in = source.at`, `par_out = source.towards`, and `par_angle = source.angle` (default `0`). When `particles` is present, each item inherits `par_randx`, `par_randy`, `par_type`, and `par_energy` from the configuration, overrides them with its own keys, and adds `offset` (default `[0, 0, 0]` $\mu\text{m}$) to both the emission point and the aiming point. Finally write `recorded_events = events`, `total_events = generated` (or `generated_limit` when running by recorded count), `edep_min`, and `edep_max`.
   3. `tilted` rotates the source by the incidence angle: unchanged when `par_angle` is `0`. If the setup has `devices` while `par_angle` is nonzero, raise `ValueError` (`a g4setup with devices tilts no source`). Otherwise write $\mathbf{r}_{\text{in}} = (x_0, y_0, z_0)$ and $\mathbf{r}_{\text{out}} = (x_1, y_1, z_1)$; if $0 \le z_0 \le l_z$ or $z_1 = z_0$, raise `ValueError` (the source line does not enter the device through either face). Take the entrance face $z_f = l_z$ (for $z_0 > l_z$) or $z_f = 0$, with rotation axis parallel to the $y$ axis passing through $x_p = x_0 + \frac{z_f - z_0}{z_1 - z_0}(x_1 - x_0)$, and transform `par_in` and `par_out` in both the top-level configuration and each entry of `particles` by
      $$x' = (x - x_p)\cos\vartheta + (z - z_f)\sin\vartheta + x_p, \qquad z' = -(x - x_p)\sin\vartheta + (z - z_f)\cos\vartheta + z_f$$
      where $\vartheta$ is `par_angle` (degrees). For $\vartheta > 0$, a source above the top face rotates toward the $-x$ side so particles travel with a $+x$ component toward the entrance point. $y$, `par_randx`, and `par_randy` are unchanged, and objects in the setup do not move.
   4. Build the geometry (`GeneralDetectorConstruction`; or `GDMLDetectorConstruction` when `geant4_model == "gdml_import"`). The world is a cube of material `world` centered at the midpoint of the device's $z = 0$ face, with half-side length given by `world_half_side`: let $\rho = \max\bigl(l_x/2,\ l_y/2,\ l_z,\ \max_{\text{object},u}(|p_u| + a_u/2),\ \max_{\text{source},u}(|r_{\text{in},u}| + R)\bigr)$, where $p_u$ and $a_u$ are `position_<u>` and `side_<u>` of each object and $R$ is `par_radius`; take `25000` when $\rho \le 25000\ \mu\text{m}$, and $2\rho$ otherwise. The device is a box of dimensions $l_x \times l_y \times l_z$ centered at $(0, 0, l_z/2)$, occupying $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]$. When the setup has `devices`, the world is centered at the Geant4 origin and the device term in $\rho$ is replaced across slots by $\max\bigl(|P_x| + \tfrac{1}{2}\max(l_x, l_y),\ |P_y| + \tfrac{1}{2}\max(l_x, l_y),\ |P_z| + l_z\bigr)$; for each slot, a box logical volume named after the slot with material taken from that slot device's `material` is built and placed according to Eq. (17), with its front-surface center at `position` $\mathbf{P}$ and rotated by `rotation_z` about the $z$ axis. Surrounding objects are then built from `object`. If two binary compounds share the same `compound_name` with conflicting composition or density, raise `ValueError` (`Conflicting Geant4 material definition for ...`). Binary compounds convert atomic fractions to mass fractions via $m_i = n_i A_i / (n_1 A_1 + n_2 A_2)$.
   5. Configure the random engine, physics list, and user actions. If the source contains `nuclides`, use `NuclideGeneratorAction` and `DecayStackingAction`; otherwise use `GeneralPrimaryGeneratorAction`. For each event and each particle, the latter draws $\delta_x \sim U(-\texttt{par\_randx}, \texttt{par\_randx})$ and $\delta_y \sim U(-\texttt{par\_randy}, \texttt{par\_randy})$ from `stream("source")` and emits from $\mathbf{r}_{\text{in}}$ in direction $\mathbf{d} = \mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}} + (\delta_x, \delta_y, 0)$; when `par_type` is a list, it also draws an index with equal probability. If `par_type` and `par_energy` are lists of different lengths, raise `ValueError`.
   6. Execute `/run/initialize`; if `picture` is given and `drawn > 0`, enable off-screen visualization (see "Plots"); run `BeamOn(total_events)`.
   7. Event recording (see `require` and per-slot energy windows for recording conditions with multiple devices): at the end of an event, if total deposited energy in the device satisfies $E_{\text{tot}} > 0$ and $E_{\text{tot}} \ge$ `edep_min` and $E_{\text{tot}} \le$ `edep_max` (unprovided bounds are not checked), record the event. When running by recorded count, call `AbortRun` once the recorded count reaches `recorded_events`, and set `generated_events` to the number of completed events. When running by generated count, `generated_events = total_events`.
   8. `deposits()`: if running by recorded count and fewer than `recorded_events` events were recorded, raise `RuntimeError` (`... events asked for were recorded when the limit of ... generated events was reached ...`). Otherwise convert step positions from Geant4 coordinates to the device coordinates of their respective devices: $\mathbf{r}_{\text{dev}} = \mathbf{r}_{\text{G4}} + (l_x/2,\ l_y/2,\ 0)$ for a single device, or the inverse of Eq. (17) for multiple devices; call `deposits_of_steps(<slot name>, ...)` for each device to drop steps with $E_k \le 0$, concatenate the deposit steps across devices in the order of `devices` for each event, and drop events with no remaining steps. Event IDs are Geant4's `eventID`.
   9. Regardless of whether an error occurred, call `close()` at the end to release Geant4 objects.
5. **Write source emission fraction**: `generated_fraction(source)` evaluates to Eq. (16) when the source contains `nuclides` and `par_cone` is not `None`, and `1.0` otherwise.
6. **Ionization**: Call `ionized_pairs(event, material, fano)` for each event, taking each step's `material` from the `material` of its slot's device. Raise `ValueError` if the material is not in `PAIR_ENERGY_EV`, or if `fano=True` and the material is not in `FANO_FACTOR`. Each event draws from its own stream `stream(f"ionization/{event.event}")`, so an event's pair counts are independent of which events were recorded before it.

`write_simulated_deposits` calls `simulate_deposits`, writes the file via `write_deposits`, and returns the number of recorded events.

In GDML import mode, the device logical volume `"Device"` is built according to `material` for `"Si"` (`G4_Si`) and `"SiC"` (equal atomic fractions of Si and C, $3.21\ \text{g/cm}^3$).

### Slicing Energy-Loss Tracks into Deposition Steps

**Geant4**: Step length is determined by Geant4, capped at `maxstep` inside the device (Eq. (3)). For every step whose pre-step logical volume is named `"Device"` (or a slot name for multiple devices), `GeneralSteppingAction` calls `RecordDevice`: it records separately by logical volume name, accumulates $E_{\text{tot}}$, and records the step midpoint $\frac{1}{2}(\mathbf{r}^{\text{pre}} + \mathbf{r}^{\text{post}}) \times 1000$ (converting Geant4's $\text{mm}$ to $\mu\text{m}$), the pre-step point $\mathbf{r}^{\text{pre}} \times 1000$ (written as `x_start`, etc.), the deposited energy ($\text{MeV}$), and the global time of the pre-step point ($\text{s}$).

**toy MIP** (`mip_deposits`):

1. Raise `ValueError` if the source contains keys outside `_SOURCE_KEYS` (`name`, `kind`, `description`, `start`, `end`, `position_range_um`, `direction_sigma_mrad`, `packets`, `landau_sampling`), if `landau_sampling` is missing, or if the material is not in `PAIRS_PER_UM`.
2. `generation(events, generated, generated_limit, recorded)` yields event IDs $0, 1, \dots$: `generated` events when running by generated count; or generating until the recorded count equals `events` when running by recorded count, raising `RuntimeError` if `generated_limit` is reached without enough recorded events. All draws use the single stream `stream("toy_mip")`.
3. Track endpoints for each event (`_track_ends`): default start $(l_x/2, l_y/2, 0)$ and default end $(l_x/2, l_y/2, l_z)$. When `position_range_um` is given, draw $x_s \sim U(x_{\text{lo}}, x_{\text{hi}})$ and $y_s \sim U(y_{\text{lo}}, y_{\text{hi}})$ in order (both `"x"` and `"y"` must be provided). When `direction_sigma_mrad` is given, draw slope $k_u \sim \mathcal{N}(0, (10^{-3}\sigma_u)^2)$ for each of `"x"` and `"y"` with $\sigma > 0$. Whenever the start point or slope is drawn, the end transverse coordinates become $u_e = u_s + k_u (z_e - z_s)$.
4. Number of segments $n$: `int(packets)` if `packets` is provided, otherwise $n = \lceil L / \texttt{maxstep} \rceil$, where $L$ is the distance from start to end ($\mu\text{m}$). Each segment has length $\Delta l = L/n$, and segment energies are drawn sequentially according to Eq. (5).
5. Events whose total energy $\sum_k E_k$ is less than `edep_min` or greater than `edep_max` are not recorded. Toy MIP retains segments with energy $0$.
6. Segment $k$ ($k = 0, \dots, n-1$) has position at the segment midpoint $\mathbf{r}_s + \frac{k + 0.5}{n}(\mathbf{r}_e - \mathbf{r}_s)$, start point $\mathbf{r}_s + \frac{k}{n}(\mathbf{r}_e - \mathbf{r}_s)$, time $0.0\ \text{s}$, and detector name `"Device"`.
7. Return `Deposits(generated_events = last_event_id + 1, ...)`.

When the setup has `devices`, the track traverses all slots in Geant4 coordinates; steps 3, 4, and 6 are replaced by the following, with the rest unchanged:

- Raise `ValueError` if the source contains `start`, `end`, or `position_range_um` (for multiple devices, the track start point is given by the setup's `source`).
- Take the start point $\mathbf{r}_s$ from the setup's `source.at` and direction from `source.towards - source.at`; when `direction_sigma_mrad` is given, draw slopes as in step 3 and add them to $dx/dz$ and $dy/dz$ of the direction. Raise `ValueError` if the $z$ component of the direction is not positive.
- For each slot in `devices`, take the track segment within $z \in [P_z, P_z + l_z]$, split its length $L$ according to step 4, transform each segment's midpoint and start point to that slot's device coordinates via the inverse of Eq. (17), discard segments whose transverse coordinates fall outside $[0, l_x] \times [0, l_y]$, and assign the slot name as detector name and `0.0 s` as time. Segments across slots are concatenated end-to-end in the order of `devices`.
- See `require` and per-slot energy windows for the recording conditions in step 5.

### Laser Carrier Groups

`LaserInjection(my_d, laser_dic)` reads the laser keys (see "Interface"). If `alpha` is not given, it looks up the table using Eq. (7): raise `ValueError` if `deposit/absorption/<material>.txt` does not exist in the components or if $10^3\lambda$ is shorter than the shortest wavelength in the table; set $\alpha = 0$ if it is longer than the longest wavelength. It then adds SPA groups with $k = 2$ and broadening $\tau$ when $\alpha \ne 0$, and subsequently adds TPA groups with $k = 4$ and broadening $\tau/\sqrt{2}$ when `tech == "TPA"`. If `tech` is neither `"SPA"` nor `"TPA"`, `NameError(tech)` is raised after adding any SPA groups. Each call to `_add_groups` proceeds as follows:

1. **Beam-path coordinates** (`_beam_frame`): `"top"` enters from $z = 0$ along $+z$, path length $l_z$, focus $s_f = f_z l_z$, transverse coordinates $(u, v) = (x, y)$, center $(f_x l_x, f_y l_y)$; `"bottom"` enters from $z = l_z$ along $-z$, path length $l_z$, $s_f = l_z - f_z l_z$, $z = l_z - s$; `"edge"` enters from $x = 0$ along $+x$, path length $l_x$, $s_f = f_x l_x$, $(u, v) = (y, z)$, center $(f_y l_y, f_z l_z)$. Here $f_x, f_y, f_z$ are `fx_rel`, `fy_rel`, `fz_rel`. Any other `direction` raises `NameError(direction)`.
2. **Beam-path sampling**: Let the finest length scale be $d = \min\bigl(L_{\text{beam}},\ z_R,\ 10^{6}/\alpha\bigr)$ (taking the third term as $L_{\text{beam}}$ when $\alpha = 0$). Place $\lceil 50 L_{\text{beam}}/d \rceil + 1$ equidistant points on $[0, L_{\text{beam}}]$, compute $dN/ds$ via Eq. (10) or (11), and accumulate via the trapezoidal rule (multiplied by $10^{-6}$ to convert to per $\mu\text{m}$) to obtain $M(s)$, with total pairs $N_{\text{tot}} = M(L_{\text{beam}})$.
3. **Grouping**: Divide the cross section into $4$ rings $\times$ $8$ sectors, and divide the beam path into $n_s = \bigl\lceil \max(N_{\text{tot}}/\texttt{pairs\_per\_group},\ \texttt{groups}) / 32 \bigr\rceil$ slices. The position $s_i$ of slice $i$ is obtained by inverting $M(s_i) = \frac{i + 0.5}{n_s} N_{\text{tot}}$ via interpolation; the relative radius of ring $j$ is $\rho_j = \sqrt{-\ln\bigl(1 - \frac{j + 0.5}{4}\bigr)/k}$; the azimuth of sector $m$ is $\varphi_m = \frac{m + 0.5}{8}\,2\pi$. Each group sits at $r = \rho_j\,w(s_i)$, $u = u_c + r\cos\varphi_m$, $v = v_c + r\sin\varphi_m$, and receives an equal share of pairs $N_{\text{tot}}/(32 n_s)$.
4. **Discard groups outside the device**: Keep only groups with $0 \le u \le$ transverse extent and $0 \le v \le$ transverse extent. Approximation: light outside the device does not pass through the device (code comment), and the pairs carried by discarded groups are dropped with them.
5. For each group, record its position and time `central_time` (stored in `track_position`), pair count (`ionized_pairs`), and temporal broadening (`time_FWHM`).

`laser_deposits(my_d, laser_dic)` writes these groups as a single event with event ID `0`: detector name `"Device"`, pair counts equal to the above mean values, energies $N \cdot \varepsilon \times 10^{-6}$ ($\text{MeV}$, converted from pairs via the ionization energy), start points equal to positions, and `t_fwhm` taken from `time_FWHM`; `generated_events = 1`, and if there are no groups the event list is empty.

### Writing and Reading Deposit Files

`write_deposits(path, deposits)` validates first and writes afterward:

1. If an optional column (`x_start`, `y_start`, `z_start`, `t_fwhm`) is present on some events and absent on others, raise `ValueError` (`some events have <name> and some do not`). An optional column is written only when present on all events.
2. If any event has `pairs` equal to `None`, raise `ValueError` (only deposits with sampled ionization are written).
3. If any event's `detector`, `x`, `y`, `z`, `t`, `e`, `pairs`, or any optional column to be written has a length not equal to the number of deposition steps, raise `ValueError`.
4. Once all checks pass, open the file with `"w"` (overwriting any existing file) and write attributes and datasets; steps of all events are concatenated end-to-end and split by `count`. If a check fails, any existing file is left untouched.

`read_deposits(path)` splits each column back into events using `count`, reads optional columns only if present, and returns a `Deposits` instance.

### Geometry Viewing

`view_geometry(my_d, source, g4setup, events, g4_seed, driver, output)` does not write a deposit file:

1. Let `tsg` be whether `driver.upper()` is in `{"TSG", "TSG_FILE", "TSG_OFFSCREEN"}`. If `output` is given while the driver is neither TSG nor starts with `"OGL"`, raise `ValueError`.
2. If the driver is not in `DAWNFILE`, `HEPREPFILE`, `K3DJUPYTER`, `MPLJUPYTER`, `TSG`, `TSG_FILE`, `TSG_OFFSCREEN`, `VRML2FILE`, first create a `G4UIExecutive` session.
3. Build and rotate the configuration with `generated = events` and no energy window, and construct the same geometry and actions as in the "Geant4 branch".
4. Open the driver (`register_driver` registers `TSG_OFFSCREEN`, `TSG_QT_GLES`, `OGL`, `VRML2FILE`, and `ATREE` for g4ppyy). When using TSG with `output` given, configure PNG output to `<output>.png`. Run the component macro `deposit/vis_pcb.mac` for `gdml_import`, or `deposit/init_vis.mac` and `deposit/vis.mac` otherwise; raise `FileNotFoundError` if a macro is not found in the component paths. When using OGL with `output` given, set a white background, vector printing, size `2000 × 2000`, and filename `output`.
5. Run `BeamOn(events)`, then refresh the viewer and export the image. If an interactive session was created, enter it and return after the window is closed. If any Geant4 command returns a nonzero status, raise `RuntimeError` (`Geant4 refused the command ...`).

## Software Implementation

### Role of Each File

- `simulate_deposits.py`: stage entry points `simulate_deposits` and `write_simulated_deposits`, default setup `DEVICE_ALONE`, configuration builder `g4_configuration`, incidence-angle rotation `tilted`, world sizing `world_half_side`, and emission fraction `generated_fraction`.
- `generation.py`: event-count validation `asked`, generation loop `generation`, `GENERATED_LIMIT`, and insufficient-event error `too_few`.
- `mip_track.py`: toy MIP tracks and segmentation `mip_deposits`.
- `ionization.py`: `PAIR_ENERGY_EV`, `FANO_FACTOR`, and `ionized_pairs`.
- `deposits.py`: data structures `EventDeposits` and `Deposits`, along with `deposits_of_steps`, `write_deposits`, and `read_deposits`.
- `laser.py`: `absorption_coefficient`, `LaserInjection` (carrier groups, `timePulse`, and two group-distribution plots), and `laser_deposits`.
- `view_geometry.py`: `view_geometry`.
- `geant4/interaction.py`: `GeneralG4Interaction`, setting up, running, recording, and tearing down a Geant4 run.
- `geant4/detector_construction.py`, `geant4/g4_gdml_import.py`: geometry and materials; the latter imports external GDML.
- `geant4/action_initialization.py`, `primary_generator_action.py`, `nuclide_source.py`, `event_action.py`, `stepping_action.py`, `run_action.py`: Geant4 user actions handling respectively action assembly, beam emission, nuclides and decay products, event recording, step recording, and run setup.
- `geant4/drivers.py`: registers visualization drivers for g4ppyy. `geant4/g4ppyy_runtime.py`: imports g4ppyy and releases the visualization manager before the run manager on process exit.
- `toy_mip.py`: `ToyMIPLineSource` and `ToyMIPInteraction`, straight-line toy MIP carrier packets for algorithm testing. `energy_loss.py`: Fano sampling `sample_fano_pairs` and Landau sampling `sample_landau_energy_loss`. `carrier_list.py`: `CarrierListFromG4P` and `PixelCarrierListFromG4P`, converting Geant4 steps into carrier lists for `CalCurrentG4P` in [carrier drift and induced current](current.md).

### Core Data Structures

- `EventDeposits`: deposits for a single event. `event` (event ID); per-step lists `detector` (detector name), `x`, `y`, `z` (step midpoint in device coordinates, $\mu\text{m}$), `t` ($\text{s}$), `e` ($\text{MeV}$); `pairs` (pairs, `None` prior to ionization sampling); `x_start`, `y_start`, `z_start` (step start point, $\mu\text{m}$, `None` when unknown); `t_fwhm` (Gaussian FWHM broadening of generation time around `t`, $\text{s}$, with `None` meaning all generated at `t`).
- `Deposits`: deposits for a job. `generated_events` (number of events generated by the source), `edep_min`, `edep_max` ($\text{MeV}$, may be `None`), `events` (list of `EventDeposits`), `generated_fraction` (default `1.0`).
- `LaserInjection`: `track_position` (`[x, y, z, t]` per group, $\mu\text{m}$ and $\text{s}$), `ionized_pairs` (pairs per group), `time_FWHM` (temporal broadening per group, $\text{s}$), as well as `temporal_FWHM`, `timePulse`, and other attributes used for current convolution.

## Interface

Users can configure the keys in device files, setup scripts, radioactive source and beam files, and laser files listed in the tables below; all other parameters on this page are hard-coded. Event counts, energy window, `deposit.fano`, and plotted event count `deposit.plots` are settings in the `deposit` section; see the [energy deposition stage](../stages/deposit.md).

### Keys Read from Device Files

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `l_x`, `l_y`, `l_z` | none (required) | $\mu\text{m}$ | Device dimensions; see [device model](device.md) |
| `material` | none (required) | none | `"Si"`, `"SiC"`, or `"Diamond"`; determines Geant4 material, ionization energy, and Fano factor; toy MIP supports only `"Si"` and `"SiC"` |

### Setup

A setup is the dictionary `G4SETUP` inside a `<name>.py` script under `components/deposit/`; when no setup is given, `DEVICE_ALONE` is used (identical to `device_alone.py` except for `name` and `description`).

#### Top-Level Keys of `G4SETUP`

| Key | Default (`DEVICE_ALONE`) | Unit | Meaning |
| --- | --- | --- | --- |
| `name`, `description` | none (optional) | none | Setup name and description; `name` appears only in error messages |
| `geant4_model` | `"device"` | none | Required for Geant4 sources; `"gdml_import"` imports an external GDML file, while other values serve only as labels |
| `world` | `"G4_Galactic"` | none | Required for Geant4 sources; NIST material name of the world volume |
| `maxstep` | `2` | $\mu\text{m}$ | Required; maximum Geant4 step length inside the device, and also the segment-length upper bound for toy MIP when `packets` is not given |
| `source` | `{"at": [0, 0, -17000], "towards": [0, 0, 0], "angle": 0}` | $\mu\text{m}$, degrees | Required for Geant4 sources; `at` is the source position, `towards` is the aiming point (in Geant4 coordinates), and `angle` is the incidence angle (default `0`), rotated according to step 4.3 of "Branches of `simulate_deposits`" when nonzero |
| `object` | `{}` | none | Required for Geant4 sources; surrounding objects, which may contain the two categories `"elemental"` and `"binary_compounds"` |
| `par_type`, `par_energy`, `par_randx`, `par_randy` | none | see sources | Optional; the setup may provide these beam keys, and same-named keys in the source override them |
| `devices` | none (optional) | none | Device slots, see the table below; each slot places one device according to Eq. (17). When omitted, this is equivalent to a single slot `"Device"` with `position` `[0, 0, 0]` |

In Geant4 coordinates, the device occupies $x \in [-l_x/2, l_x/2]$, $y \in [-l_y/2, l_y/2]$, $z \in [0, l_z]$, with $z < 0$ above the top face $z = 0$.

#### Keys for `devices`

`devices` maps each slot name to a dictionary with the keys below. The slot name serves as both the Geant4 logical volume name and the detector name in the deposit file; it may use only characters in `[A-Za-z0-9_-]` and must not be `"Device"`, a name appearing in `object`, or a configuration key of the [energy deposition stage](../stages/deposit.md) (slot names appear in addresses such as `deposit.<slot>.<key>`), otherwise `ValueError` is raised. Which device is placed in each slot is not specified by the setup, but passed via the caller's `devices` argument (see "Branches of `simulate_deposits`").

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `position` | none (required) | $\mu\text{m}$ | Geant4 coordinates `[x, y, z]` of the device front-surface center, $\mathbf{P}$ in Eq. (17) |
| `rotation_z` | `0` | degrees | Rotation angle about the $z$ axis, restricted to `0`, `90`, `180`, `270`; any other value raises `ValueError` |
| `colour` | `[1, 0.1, 0.8]` | none | Visualization RGB color (`0` to `1`) |

If two slots overlap in $z$ and also overlap transversely, raise `ValueError` (`the devices <A> and <B> overlap`).

#### Geometry Keys for the Two Categories of `object`

Both `object["elemental"]` and `object["binary_compounds"]` are dictionaries keyed by volume name, where each entry is a box: the former uses a Geant4 NIST material and the latter is a compound of two elements. For example, an aluminum layer above the top face of the device:

```python
"object": {
    "elemental": {
        "Al": {
            "name": "Al",
            "material": "G4_Al",
            "side_x": 5000,
            "side_y": 5000,
            "side_z": 0.08,
            "colour": [1, 0.1, 0.8],
            "position_x": 0,
            "position_y": 0,
            "position_z": -89.3,
        },
    },
},
```

This is a $5\ \text{mm} \times 5\ \text{mm} \times 0.08\ \mu\text{m}$ aluminum foil centered $89.3\ \mu\text{m}$ above the device top face. `position_x`, `position_y`, and `position_z` give the center of the box; to place the bottom face at distance $d$ above the device top face, write `position_z = -(d + side_z / 2)`.

Every key in the table below is required for its applicable category, except `tub` under `elemental`, which may be omitted.

| Key | Applicable Category | Unit | Meaning |
| --- | --- | --- | --- |
| `name` | both | none | Volume name |
| `material` | `elemental` | none | Geant4 NIST material name, such as `"G4_Al"`, `"G4_Ni"`, `"G4_Ti"`, `"G4_Si"`, `"G4_BRASS"` |
| `material_1`, `material_2` | `binary_compounds` | none | Symbols of the two elements, such as `"Si"`, `"C"`, `"N"`, `"O"` |
| `compound_name` | `binary_compounds` | none | Compound material name; compounds with the same name must have identical composition and density |
| `density` | `binary_compounds` | $\text{g/cm}^3$ | Compound density |
| `natoms_1`, `natoms_2` | `binary_compounds` | none | Atomic-number shares of the two elements, converted to mass fractions using atomic weights |
| `side_x`, `side_y`, `side_z` | both | $\mu\text{m}$ | Full dimensions of the box along $x$, $y$, and $z$ |
| `position_x`, `position_y`, `position_z` | both | $\mu\text{m}$ | Position of the box center in Geant4 coordinates |
| `colour` | both | none | Visualization RGB color `[r, g, b]` |
| `tub` | optional for `elemental`, required for `binary_compounds` (use `{}` if no hole) | $\mu\text{m}$ | Cylindrical hole subtracted along the $z$ axis through the box center, containing radius `"tub_radius"` and half-length `"tub_depth"` |

#### Additional Keys for `"gdml_import"`

When the GDML file contains the string `RASER_GDML_WRAPPER_WORLD`, the GDML world volume is used directly as the Geant4 world volume, and the world size, material, and placement of the imported geometry are all supplied by the GDML file; the keys in the table below that take effect are `gdml.file`, `gdml.validate`, and `visualization`.

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `world_half_size_um` | computed by `world_half_side` | $\mu\text{m}$ | Overrides the half-side length of the world cube |
| `gdml.file` | none (required) | none | Path to the GDML file; searched in order as an absolute path, relative to each component root, under `deposit/<file>` of each component root, and under `src/raser/<file>`; raises `ValueError` if empty and `FileNotFoundError` if not found |
| `gdml.top_volume` | `None` | none | Name of the logical volume to place; if absent from the file or omitted, the GDML world volume is placed |
| `gdml.validate` | `False` | none | Whether to validate the GDML schema while reading |
| `gdml.auto_center` | `True` | none | Whether to subtract the center of the bounding box of all `<position>` coordinates in the GDML file |
| `gdml.position_um` | `[0.0, 0.0, 0.0]` | $\mu\text{m}$ | Translation of the imported geometry; treated as zero if its length is not `3` |
| `gdml.rotation_xyz` | `[0.0, 0.0, 0.0]` | degrees | Successive rotation angles around the $x$, $y$, and $z$ axes |
| `gdml.placement_name` | `"ImportedGDML"` | none | Physical volume name of the imported geometry |
| `visualization` | `{}` | none | Visualization style: `imported_visible` (`True`), `imported_force_wireframe` (`True`), `imported_force_solid` (opposite of wireframe), `imported_colour_rgba` (`[0.20, 0.85, 0.85, 1.00]`), `device_visible` (`True`), `hide_device` (`False`), `device_force_wireframe` (`False`), `device_force_solid` (opposite of wireframe), `device_colour_rgba` (`[1.00, 0.10, 0.10, 0.35]`) |

#### Built-in Setups

| Component | Location | Description |
| --- | --- | --- |
| `device_alone` | `raser/components/deposit/` | Device placed alone in vacuum, source $17\ \text{mm}$ above the top face |
| `Sr90_collimator` | `src/raser_bench/signal/components/deposit/` | Brass collimator in air (see [signal](../bench/signal.md)) |
| `pcb_readout_gdml` | `src/raser_bench/signal/components/deposit/` | PCB readout board imported from `pcb_readout.gdml` (see [signal](../bench/signal.md)) |
| `time_resolution` | `src/raser_bench/timeres/components/deposit/` | Reference silicon device and two apertured PCB boards (see [time resolution](../bench/timeres.md)) |
| `telescope` | `src/raser_bench/telescope/components/deposit/` | 8 slots arranged along $z$ in vacuum, defaulting to 3 + 2 + 3 (see [beam telescope](../bench/telescope.md)) |

### Radioactive Sources and Beams

#### Common Keys

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `name` | none (optional) | none | Source name |
| `kind` | none (required) | none | `"beam"`, `"decay_source"`, or `"toy_mip"` |
| `description` | none (optional) | none | Text description |

A source must not contain `par_in`, `par_out`, or `par_angle`: source position and direction are given by the setup's `source`.

#### Keys for `beam` and `decay_source`

`"beam"` and `"decay_source"` take the same Geant4 branch; whether nuclide decay is used depends solely on whether `nuclides` is present in the source.

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `par_type` | none (required when `nuclides` is absent) | none | Geant4 particle name (e.g. `"e-"`, `"proton"`, `"alpha"`), or a list of particle names drawn with equal probability |
| `par_energy` | none (required when `nuclides` is absent) | $\text{MeV}$ | Particle kinetic energy, or a list of the same length as `par_type` |
| `par_randx`, `par_randy` | `0`, `0` | $\mu\text{m}$ | Half-width of uniform random offsets added to the $x$ and $y$ components of the emission direction `towards - at` |
| `particles` | none (optional) | none | List of particles emitted simultaneously per event; each item may override `par_type`, `par_energy`, `par_randx`, `par_randy`, and shift both the emission point and aiming point by `offset` (default `[0, 0, 0]`, $\mu\text{m}$) |
| `nuclides` | none (optional) | none | Nuclides at rest `[[Z, A], ...]`; when given, one species is chosen with equal probability per event for a single decay, and emitted particles come from the decay |
| `par_radius` | `0` | $\mu\text{m}$ | Radius of the disk containing the nuclides, perpendicular to the emission axis |
| `par_cone` | `None` | degrees | Half-cone angle for isotropic emission of decay products around the emission axis; effective only when `nuclides` is present |

#### Keys for `toy_mip`

A `toy_mip` source may contain only the keys in the table below and the common keys.

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `landau_sampling` | none (required) | none | When `true`, each segment energy is sampled from the Landau distribution in Eq. (5); when `false`, the mean energy loss is used |
| `start` | `[l_x / 2, l_y / 2, 0.0]` | $\mu\text{m}$ | Track start point in device coordinates |
| `end` | `[l_x / 2, l_y / 2, l_z]` | $\mu\text{m}$ | Track end point in device coordinates |
| `position_range_um` | none (optional) | $\mu\text{m}$ | Uniform sampling ranges for the start transverse coordinates `{"x": [lo, hi], "y": [lo, hi]}`; both entries must be provided |
| `direction_sigma_mrad` | none (optional) | mrad | Gaussian sampling standard deviations for slopes $dx/dz$ and $dy/dz$, `{"x": sigma_x, "y": sigma_y}`; both entries must be provided |
| `packets` | $\lceil L / \texttt{maxstep} \rceil$ | segments | Number of deposition segments into which a track is sliced |

#### Built-in Radioactive Sources and Beams

| Component | Kind | Description |
| --- | --- | --- |
| `beam/electron`, `beam/muon`, `beam/pion`, `beam/proton` | `beam` | `e-`, `mu-`, `pi-`, `proton`, $1000\ \text{MeV}$ |
| `beam/proton_3GeV_spread` | `beam` | $3000\ \text{MeV}$ protons, `par_randx = par_randy = 728.6` $\mu\text{m}$ |
| `decay/Sr90` | `decay_source` | Nuclides Sr-90 and Y-90 with equal probability, `par_radius = 2500` $\mu\text{m}$, `par_cone = 15` degrees |
| `decay/Am241` | `decay_source` | Emits $5.54\ \text{MeV}$ `alpha` via `par_type` and `par_energy` |
| `toy/MIP` | `toy_mip` | Default track, `landau_sampling = true` |
| `toy/MIP_pixel_edge`, `toy/MIP_pixel_edge_fast` | `toy_mip` | From $(600, 450, 0)$ to $(600, 450, 300)$ $\mu\text{m}$, `packets` equal to `50` and `5`, the latter without Landau sampling |
| `toy/MIP_strip_edge` | `toy_mip` | Start $x$ sampled uniformly in $[150, 270]$ $\mu\text{m}$, standard deviation of $dx/dz$ equal to $10$ mrad |
| `bunch` (`src/raser_app/bmos/components/deposit/`) | `beam` | Three $80\ \text{MeV}$ protons emitted simultaneously side by side (see [`bmos`](../apps/bmos.md)) |

### Lasers

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `description` | none (optional) | none | Laser model and parameter description |
| `tech` | none (required) | none | `"SPA"` (single-photon absorption) or `"TPA"` (two-photon absorption) |
| `direction` | none (required) | none | `"top"` (from $z = 0$ along $+z$), `"bottom"` (from $z = l_z$ along $-z$), or `"edge"` (from $x = 0$ along $+x$) |
| `refractionIndex` | none (required) | none | Refractive index $n$ of the device material at this wavelength |
| `wavelength` | none (required) | $\text{nm}$ | Laser wavelength |
| `alpha` | looked up via Eq. (7) | $\text{m}^{-1}$ | Absorption coefficient; setting `0` disables single-photon absorption, leaving only TPA groups for a `"TPA"` laser |
| `beta_2` | none (required for `"TPA"`) | $\text{m/W}$ | Two-photon absorption coefficient |
| `temporal_FWHM` | none (required) | $\text{s}$ | Temporal full width at half maximum $\tau$ of the pulse |
| `pulse_energy` | none (required) | $\text{J}$ | Pulse energy $E_p$ |
| `spacial_FWHM` | none (required) | $\mu\text{m}$ | Spatial full width at half maximum of the beam spot at the focus |
| `l_Rayleigh` | computed by Eq. (9) | $\mu\text{m}$ | Rayleigh length inside the device |
| `central_time` | none (required) | $\text{s}$ | Central time of the pulse |
| `pairs_per_group` | none (required) | pairs | Upper bound on the number of pairs per carrier group |
| `groups` | none (required) | groups | Minimum number of groups created per absorption mechanism (before discarding groups outside the device) |
| `fx_rel`, `fy_rel`, `fz_rel` | none (required) | none | Relative coordinates of the focus, giving absolute position $(f_x l_x,\ f_y l_y,\ f_z l_z)$ |

#### Absorption Coefficient Table (`deposit/absorption/<material>.txt`)

A whitespace-separated two-column text file with `#` comment lines: the first column is wavelength ($\text{nm}$) and the second column is the interband absorption coefficient at $300\ \text{K}$ ($\text{cm}^{-1}$), sorted in ascending order of wavelength. Only `Si.txt` is included in the library, covering $250$ to $1450\ \text{nm}$, taken from Ref. [7].

#### Built-in Lasers

| Component | `tech` | Description |
| --- | --- | --- |
| `LA01IR_top_Si`, `LA01IR_edge_Si` | `"SPA"` | $1064\ \text{nm}$, silicon, $\alpha$ looked up from table |
| `LA01R_top_Si`, `LA01R_bottom_Si` | `"SPA"` | $660\ \text{nm}$, silicon, $\alpha$ looked up from table |
| `PIL037_top_SiC`, `PIL037_edge_SiC` | `"SPA"` | $375\ \text{nm}$, silicon carbide, `alpha` equal to `1000` and `21000` $\text{m}^{-1}$ respectively |
| `TPA1550_top_Si`, `TPA1550_edge_Si` | `"TPA"` | $1550\ \text{nm}$, silicon, longer than the table upper limit, $\alpha = 0$, TPA groups only |

### `deposit.h5` File Format

#### File Attributes

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `generated_events` | `int` | events | Number of events generated by the source |
| `recorded_events` | `int` | events | Number of events stored in the file |
| `generated_fraction` | `float` | none | Fraction of source emissions generated; Eq. (16) for nuclide sources with `par_cone`, `1.0` otherwise |
| `edep_min`, `edep_max` | `float` | $\text{MeV}$ | Lower and upper bounds of the total deposited energy window in the device; written only when given |

The fraction of generated events that are recorded is `recorded_events / generated_events`; the number of recorded events per source emission is `recorded_events / generated_events * generated_fraction`.

#### Datasets

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(recorded_events,)`, `int64` | none | Event ID: Geant4 `eventID`, toy MIP generation index, or `0` for lasers |
| `count` | `(recorded_events,)`, `int64` | steps | Number of deposition steps in each event |
| `detector` | `(sum(count),)`, variable-length `str` | none | Name of the detector where the step occurs: `"Device"` for a single device, or the slot name for multiple devices |
| `x`, `y`, `z` | `(sum(count),)`, `float64` | $\mu\text{m}$ | Step midpoint in the device coordinates of its device |
| `t` | `(sum(count),)`, `float64` | $\text{s}$ | Time since primary particle creation; global time of the pre-step point for Geant4, `0.0` for toy MIP, `central_time` for lasers |
| `e` | `(sum(count),)`, `float64` | $\text{MeV}$ | Deposited energy; for lasers, pair count multiplied by ionization energy |
| `pairs` | `(sum(count),)`, `float64` | pairs | Number of electron-hole pairs |
| `x_start`, `y_start`, `z_start` | `(sum(count),)`, `float64` (optional) | $\mu\text{m}$ | Step start point, written when present on all events; step end point is `2 * (x, y, z) - start` |
| `t_fwhm` | `(sum(count),)`, `float64` (optional) | $\text{s}$ | Gaussian FWHM broadening of generation time around `t`, written when present on all events (`laser_deposits`) |

### Plots

| File | Writer | Content | Coordinate Units |
| --- | --- | --- | --- |
| `<picture>.png` | `simulate_deposits` (`picture` non-empty and `drawn > 0`, Geant4 sources only) | Geometry rendered by `TSG_OFFSCREEN` (`vis.mac`: volumes, axes, tracks colored by charge, and step points) together with the first `drawn` recorded events; written by the stage as `g4_geometry.png` inside the `deposit` node | Geant4 coordinates |
| `<output>.png` | `view_geometry` (TSG drivers) | Geometry and tracks of generated events | Geant4 coordinates |
| `<output>` vector image | `view_geometry` (OGL drivers) | Same as above, `2000 × 2000`, white background | Geant4 coordinates |
| `nocarrier_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier3D` | `TH3D` of carrier groups weighted by pair count, $50^3$ bins spanning the bounding box of the groups; axis titles `Depth`, `Width`, `Thick` (i.e., $x$, $y$, $z$); relative coordinates in the filename formatted to 5 decimal places | $\mu\text{m}$ |
| `nocarrier2D_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier2D` | `TH2D` (`COLZ`) in the $x$-$z$ plane, $50 \times 50$ bins, color representing pair count (`Carriers`) | $\mu\text{m}$ |

## References

- [1] U. Fano, “Ionization Yield of Radiations. II. The Fluctuations of the Number of Ions”, Phys. Rev. 72 (1947) 26, doi:10.1103/PhysRev.72.26
- [2] T. Shimaoka et al., “Fano factor evaluation of diamond detectors for alpha particles”, Phys. Status Solidi A 213 (2016) 2629, doi:10.1002/pssa.201600195
- [3] S. Agostinelli et al. (GEANT4 Collaboration), “GEANT4—a simulation toolkit”, Nucl. Instrum. Methods Phys. Res. A 506 (2003) 250, doi:10.1016/S0168-9002(03)01368-8
- [4] J. Allison et al., “Recent developments in Geant4”, Nucl. Instrum. Methods Phys. Res. A 835 (2016) 186, doi:10.1016/j.nima.2016.06.125
- [5] S. Hauf et al., “Radioactive Decays in Geant4”, IEEE Trans. Nucl. Sci. 60 (2013) 2966, doi:10.1109/TNS.2013.2270894
- [6] L. Landau, “On the energy loss of fast particles by ionization”, J. Phys. (USSR) 8 (1944) 201
- [7] M. A. Green, “Self-consistent optical parameters of intrinsic silicon at 300 K including temperature coefficients”, Sol. Energy Mater. Sol. Cells 92 (2008) 1305, doi:10.1016/j.solmat.2008.06.009
- [8] S. Navas et al. (Particle Data Group), “Review of Particle Physics”, Phys. Rev. D 110 (2024) 030001, doi:10.1103/PhysRevD.110.030001
- [9] K. Ramanathan, N. Kurinsky, “Ionization yield in silicon for eV-scale electron-recoil processes”, Phys. Rev. D 102 (2020) 063026, doi:10.1103/PhysRevD.102.063026
- [10] B. G. Lowe, “Measurements of Fano factors in silicon and germanium in the low-energy X-ray region”, Nucl. Instrum. Methods Phys. Res. A 399 (1997) 354, doi:10.1016/S0168-9002(97)00965-0
- [11] A. Gsponer et al., Nucl. Instrum. Methods Phys. Res. A 1064 (2024) 169412, doi:10.1016/j.nima.2024.169412
- [12] S. K. Chaudhuri, K. J. Zavalla, K. C. Mandal, Appl. Phys. Lett. 102 (2013) 031109, doi:10.1063/1.4776703
- [13] M. E. Levinshtein, S. L. Rumyantsev, M. S. Shur (eds.), *Properties of Advanced Semiconductor Materials*, Wiley (2001)
- [14] H. Bichsel, “Straggling in thin silicon detectors”, Rev. Mod. Phys. 60 (1988) 663, doi:10.1103/RevModPhys.60.663
- [15] R. W. Boyd, *Nonlinear Optics*, 3rd ed., Academic Press (2008)
