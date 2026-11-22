# Energy Deposition and Ionization (`core/deposit`)

`src/raser/core/deposit/` takes the device dimensions and material from the [device model](device.md) and the setup script, radioactive source or beam, and laser definitions from [energy deposition components](../components/deposit.md). It uses Geant4 or a straight-line toy MIP model to compute particle deposition steps in the device (when the setup provides multiple slots via `along_beam`, it computes each device's deposit steps for multiple devices in one run), converts the deposited energy of each step into electron-hole pairs, and writes `deposit.h5`; for lasers, it directly produces carrier groups according to the absorption coefficient and likewise writes `deposit.h5`. The deposit file is passed to [carrier drift and induced current](current.md) for drift simulation, the earliest deposition time of each event is passed to [statistical analysis](analysis.md) as `truth`, and the [telescope](../bench/telescope.md) also reads this file. For commands and settings in the `deposit` section, see the [energy deposition stage](../stages/deposit.md).

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

When `alpha` is not given in the laser file, the absorption coefficient $\alpha$ is provided by `absorption_coefficient` according to the device material. Silicon uses table lookup:

$$\alpha(\lambda) = 100\,\exp\Bigl[\operatorname{interp}\bigl(10^{3}\lambda;\ \lambda_i,\ \ln \alpha_i\bigr)\Bigr] \tag{7}$$

4H-SiC has an indirect band gap, so absorption near the band edge requires phonon participation. It is computed from a semi-empirical model of phonon-assisted indirect transitions [16], taking the device temperature $T$:

$$\alpha(\lambda, T) = 100 \sum_{p=1}^{7} \sum_{\pm} \Bigl(n_p + \tfrac{1}{2} \pm \tfrac{1}{2}\Bigr) \Bigl\{ A_p \bigl[\hbar\omega - (E_{GX} \pm \hbar\Omega_p)\bigr]_+^{1/2} + B A_p \bigl[\hbar\omega - (E_{GX} \pm \hbar\Omega_p + E_{\text{ex}})\bigr]_+^{2} \Bigr\} \tag{7a}$$

$$\hbar\omega = \frac{h c}{e\,\lambda \times 10^{-6}}, \qquad n_p = \frac{1}{\exp(\hbar\Omega_p / k_B T) - 1}, \qquad E_{GX}(T) = E_{GX}(0) - \frac{\varepsilon\,\Theta}{2}\left[\bigl(1 + (2T/\Theta)^{q}\bigr)^{1/q} - 1\right] \tag{7b}$$

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
- $\hbar\omega$: photon energy, $\text{eV}$ ($e$ is the elementary charge); $T$: `temperature` from the device file, $\text{K}$; $k_B = 8.617\times10^{-5}\ \text{eV/K}$;
- $\hbar\Omega_p$, $A_p$: energy ($\text{eV}$) and transition coefficient ($\text{eV}^{-1/2}\,\text{cm}^{-1}$) of the $p$-th phonon, taken from Ref. [16], Table I ($E \perp c$, where $E$ is the optical electric field): $\hbar\Omega_p$ = 32.4, 45.7, 50.8, 67.8, 76.3, 95.8, 106.2 meV, $A_p$ = 0.5, 4, 7, 3.5, 23, 23, 40.5;
- $\pm$: upper sign for phonon emission, lower sign for phonon absorption; $n_p$: Bose occupation number of the phonon; $[x]_+ = \max(x, 0)$;
- $B = 60\ \text{eV}^{-3/2}$: ratio of continuum to exciton ground-state transition coefficients; $E_{\text{ex}} = 20\ \text{meV}$: exciton binding energy;
- $E_{GX}(T)$: exciton band gap, $\text{eV}$; $E_{GX}(0) = 3.267\ \text{eV}$, $\varepsilon = 3\times10^{-4}\ \text{eV/K}$, $\Theta = 450\ \text{K}$, $q = 2.9$ (Ref. [16], Eq. (5)), giving $E_{GX} = 3.233\ \text{eV}$ at $300\ \text{K}$;
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

Eq. (7a) differs from Eq. (3) of Ref. [16] by one factor: the original paper divides by $\hbar\omega$ outside the sum, which with the original parameters yields an absorption lower than Fig. 4 ($75\ \text{K}$) of that paper by $\hbar\omega \approx 3.3$; removing this divisor agrees with Fig. 4, and compared with the $300\ \text{K}$ measurements in Ref. [17], agrees within $10\%$ across $353$–$364\ \text{nm}$ ($225$ vs. $210\ \text{cm}^{-1}$ at $355\ \text{nm}$), is $21\%$ higher at $336\ \text{nm}$, and $26\%$ lower at $369\ \text{nm}$; at longer wavelengths, Ref. [17] stops at its measurement floor of about $13\ \text{cm}^{-1}$, whereas Ref. [16] measures down to $0.02\ \text{cm}^{-1}$. The original parameters are fitted only up to $\hbar\omega = 3.8\ \text{eV}$, so for wavelengths shorter than $326\ \text{nm}$, `absorption_coefficient` raises an error and requires `alpha` to be given in the laser file. At $300\ \text{K}$ and $375\ \text{nm}$, $\alpha = 9.05\ \text{cm}^{-1}$; the lowest threshold is $E_{GX} - \hbar\Omega_7 = 3.126\ \text{eV}$ (about $397\ \text{nm}$), beyond which there is no interband absorption and $\alpha = 0$, so defect absorption must be specified via `alpha` in the laser file.

Limitations: only the parameter set for $E \perp c$ is used, which applies to top or bottom incidence on $c$-plane wafers; for edge incidence, polarization may be parallel to the $c$-axis, and the parameter set in Ref. [16], Table II is not wired in. Doping effects on the band edge are neglected; Ref. [16] measured nominally undoped epitaxial layers.

### Radioactive Decay Sources

Each event of a radioactive source is a single decay of a nuclide at rest. A nuclide is drawn with equal probability from `nuclides`, and its position is uniformly distributed on a disk perpendicular to the emission axis. The initial time of decay products is reset to zero and the daughter nucleus left by the decay is killed there, so one event corresponds to one decay. When `par_cone` is given, the directions of decay products are resampled isotropically inside a cone around the emission axis:

$$\hat{\mathbf{a}} = \frac{\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}}{|\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}|}, \qquad |\mathbf{r}_0 - \mathbf{r}_{\text{in}}| \le R, \quad (\mathbf{r}_0 - \mathbf{r}_{\text{in}}) \perp \hat{\mathbf{a}} \tag{14}$$

$$\cos\theta = 1 - u_1\,(1 - \cos\theta_c), \qquad \varphi = 2\pi u_2, \qquad \hat{\mathbf{d}} = \cos\theta\,\hat{\mathbf{a}} + \sin\theta\,(\cos\varphi\,\hat{\mathbf{e}}_1 + \sin\varphi\,\hat{\mathbf{e}}_2) \tag{15}$$

$$f = \frac{1 - \cos\theta_c}{2} \tag{16}$$

where:

- $\mathbf{r}_{\text{in}}, \mathbf{r}_{\text{out}}$: source position and aiming point along the emission axis (the world coordinate origin is on the source; when unrotated, $\mathbf{r}_{\text{in}} = (0, 0, 0)$ and the emission axis $\hat{\mathbf{a}}$ points downstream along $+z$), $\mu\text{m}$; $\hat{\mathbf{a}}$: unit vector along the emission axis;
- $\mathbf{r}_0$: nuclide position, $\mu\text{m}$; $R$: disk radius `par_radius`, $\mu\text{m}$ (point source when $R = 0$);
- $\hat{\mathbf{e}}_1, \hat{\mathbf{e}}_2$: unit vectors orthogonal to $\hat{\mathbf{a}}$;
- $\theta_c$: half-cone angle `par_cone`, degrees; $u_1, u_2$: uniform random numbers on $[0, 1)$;
- $\hat{\mathbf{d}}$: emission direction of the decay product;
- $f$: fraction of the full solid angle covered by the cone, written to the file attribute `generated_fraction`.

Nuclides are generated by `NuclideGeneratorAction` (`G4GeneralParticleSource`, kinetic energy $0$), while time zeroing, daughter killing, and cone direction resampling are performed by `DecayStackingAction`, identifying decay tracks by the creator process subtype `RADIOACTIVE_DECAY = 210`. A code comment notes that Geant4's built-in `/process/had/rdm/decayHalfAngle` only works around the $z$ axis, so this is implemented directly. For radioactive decay in Geant4, see Ref. [5].

### Line Along the Beam

The setup uses `along_beam` to describe a line of geometry along the beam direction: the first item must be `"source"`, with the world coordinate origin $(0, 0, 0)$ on the source and the $z$ axis pointing downstream along the beam. Subsequent items in the line are gaps `{"gap": d}` ($d \ge 0$, $\mu\text{m}$), objects from `object` (`"<object name>"` or `{"object": "<object name>", "offset": [o_x, o_y]}`, occupying `side_z` along $z$), device slots `{"slot": "<slot name>", ...}` (occupying the total thickness $l_z + t$ of all layers of the device geometry along $z$; see [Detector Components](../components/device.md), with $t = 0$ when there are no layers outside the active layer), or a side-by-side list `[item, item, ...]` whose front faces align at the same $z$ and whose items are staggered laterally by their `offset` (occupying the thickness of the thickest item along $z$). Adjacent items with no `gap` between them are flush against each other; the source has thickness $0$, the front-face position $z_i$ of item $i$ equals the sum of thicknesses and gaps of all preceding items, and the slot front-surface center $\mathbf{P} = (P_x, P_y, P_z)$ and transformation from device coordinates $(x, y, z)$ (origin at a corner of the device front surface, with the active layer spanning $[0, l_x] \times [0, l_y] \times [0, l_z]$) to Geant4 world coordinates $\mathbf{r}_{\text{G4}}$ are:

$$z_i = \sum_{j < i} d_j, \qquad \mathbf{P} = \begin{cases} \bigl(o_x,\ o_y,\ z_i\bigr), & \texttt{facing} = \texttt{"upstream"} \\ \bigl(o_x,\ o_y,\ z_i + l_z + t\bigr), & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{17}$$

$$\mathbf{r}_{\text{G4}} = \begin{cases} \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} x - l_x/2 \\ y - l_y/2 \\ z \end{pmatrix}, & \texttt{facing} = \texttt{"upstream"} \\[4ex] \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} -(x - l_x/2) \\ y - l_y/2 \\ -z \end{pmatrix}, & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{18}$$

where:

- $d_j$: thickness or gap occupied by item $j$ along the $z$ axis ($0$ for `"source"`, $d$ for `{"gap": d}`, `side_z` for an object, $l_z + t$ for a slot, and the maximum thickness among items in a side-by-side list), $\mu\text{m}$; $z_i$: world $z$ coordinate of the front face of item $i$, $\mu\text{m}$;
- $o_x, o_y$: the slot's `offset` (default `[0, 0]`), $\mu\text{m}$;
- $l_z$: active-layer thickness of the device in that slot, $\mu\text{m}$; $t$: total thickness of layers outside the active layer, $\mu\text{m}$ ($t = 0$ when there are no such layers);
- $\mathbf{P} = (P_x, P_y, P_z)$: world coordinates of the center of the device front surface (the $z = 0$ plane in device coordinates), $\mu\text{m}$;
- $\phi$: the slot's `rotation_z`, degrees, restricted to `0`, `90`, `180`, `270`; $l_x, l_y$: transverse dimensions of the device in that slot, $\mu\text{m}$.

When `facing` is `"upstream"` (the default), the active layer occupies $[z_i,\ z_i + l_z]$, layers outside the active layer occupy $[z_i + l_z,\ z_i + l_z + t]$, the device front surface faces the source at $P_z = z_i$, and the device $z$ axis points along $+z$; placing a slot immediately before a board with no gap mounts the device's substrate and other outer layers against the side of the board facing the source with the active layer on the outside. When `facing` is `"downstream"`, the device is flipped $180^\circ$ about the $y$ axis (for $\phi = 0$, $x_{\text{G4}} = P_x - (x - l_x/2)$, $y_{\text{G4}} = P_y + (y - l_y/2)$, $z_{\text{G4}} = P_z - z$), layers outside the active layer occupy $[z_i,\ z_i + t]$, the active layer occupies $[z_i + t,\ z_i + t + l_z]$, and the device front surface faces downstream at $P_z = z_i + l_z + t$; placing a slot after a board with `"facing": "downstream"` mounts the substrate against the side of the board facing away from the source with the active layer on the outside. When two devices are mounted on the facing sides of two boards (a `"downstream"` slot after the first board, an `"upstream"` slot before the second board, separated by `{"gap": g}`), their active layers face each other and the spacing between them is the `gap`. The world cube is centered at the midpoint of this line, with half-side length taken as `25000` $\mu\text{m}$ when $\rho \le 25000\ \mu\text{m}$ and $2\rho$ otherwise, where $\rho$ is the maximum among half the total length of the line, each item's transverse half-size plus offset, and the source disk radius.

### Recording Conditions for Multiple Devices

In multi-device experiments, particles do not necessarily hit all devices required for triggering. In the default `timeres` setup (Sr-90 source, DUT `HPK-Si-PiN`), each Geant4 decay takes about `0.18 ms`, whereas downstream drift, readout, and reconstruction take about `0.2 s` per recorded event; in roughly three-quarters of events with deposition in the DUT, the reference device has no deposition and would not trigger in a real measurement. Pre-filtering at the `deposit` stage under the coincidence condition therefore records only valid events satisfying the condition and avoids running expensive downstream stages on non-triggering events.

A slot $s$ is defined as "hit" in an event when the total deposited energy in its active layer satisfies $E_s > 0$ and falls within its energy window $[E_{s,\min},\ E_{s,\max}]$ (`None` disables checking on that side), with hit time $t_s$ taken as the global time of the earliest deposit step in that slot's active layer; the syntax and evaluation of the logical expression `require` are defined in [Coincidence Condition](../components/trigger.md#coincidence-condition)—operands are slot names, operators are `AND`, `OR`, and parentheses, and `"all"` and `"any"` are shorthand for `AND` and `OR` over all slots, with `deposit` using the energy criterion above as the hit predicate and `trigger` using amplitude threshold crossing. With a coincidence timing window `coincidence_window_ns` (denoted $W$), an event is recorded only if there exists some time $t_0$ such that the logical expression is true when counting only slots whose hit times fall within $[t_0,\ t_0 + W]$:

$$h_s = \mathbb{I}\bigl(E_s > 0,\ E_{s,\min} \le E_s \le E_{s,\max}\bigr), \qquad t_s = \min_{k \in \mathcal{K}_s} t_{s,k} \tag{19}$$

$$h_s(t_0) = h_s \cdot \mathbb{I}\bigl(t_0 \le t_s \le t_0 + W\bigr), \qquad \exists\, t_0 \in \mathbb{R}:\ \mathcal{F}\bigl(\{h_s(t_0)\}_{s \in \mathcal{S}}\bigr) = \texttt{true} \tag{20}$$

where:

- $s \in \mathcal{S}$: slot name, where $\mathcal{S}$ is the set of all slots in the setup;
- $\mathcal{K}_s$: set of deposit steps in the active layer of slot $s$, with total deposited energy $E_s = \sum_{k \in \mathcal{K}_s} E_{s,k}$, $\text{MeV}$;
- $E_{s,\min}, E_{s,\max}$: lower and upper bounds of slot $s$'s energy window, $\text{MeV}$ (unprovided bounds are not checked);
- $h_s \in \{0, 1\}$: hit flag of slot $s$ without the timing window;
- $t_{s,k}$: global time of the $k$-th deposit step in slot $s$, $\text{s}$; $t_s$: global time of the earliest deposit step in slot $s$, $\text{s}$;
- $W$: coincidence timing window `coincidence_window_ns`, input in $\text{ns}$ (converted to $W \times 10^{-9}\ \text{s}$ when compared against $t_s$; when `None`, no timing cut is applied and $h_s(t_0) = h_s$ directly);
- $t_0$: left endpoint of the timing window, $\text{s}$;
- $h_s(t_0) \in \{0, 1\}$: hit flag of slot $s$ within the timing window $[t_0,\ t_0 + W]$;
- $\mathcal{F}$: Boolean function parsed from `require`.

The `coincidence_window_ns` in `deposit` must not be narrower than the `trigger` coincidence window plus drift and shaping times, otherwise it will drop events that `trigger` would keep. For a single slot, the condition reduces to total deposited energy in the device $> 0$ and within the window. When a slot is not hit in an event, that slot has no deposit steps in that event, and downstream `current.<slot>` does not write that event for it.

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
| 4H-SiC absorption model parameters | see variable definitions of Eqs. (7a) and (7b) | — | `laser.py`, Ref. [16], Table I and Eq. (5) | none |
| Number of rings, number of sectors | `4`, `8` | count | `laser.py`, division of the laser cross section | none |
| Beam-path sampling density | `50` points per finest scale | — | `laser.py`, see "Laser Carrier Groups" | none |

### Branches of `simulate_deposits`

`simulate_deposits(devices, source, g4setup, events, g4_seed, windows, require, coincidence_window_ns, fano, generated, generated_limit, picture, drawn)` executes in the following order. `devices` is an ordered dictionary mapping slot names to devices; `windows` maps each slot name to `(lower, upper)` ($\text{MeV}$, with `None` disabling checking on that side); `require` is the coincidence-condition logical expression string; `coincidence_window_ns` is the coincidence timing window ($\text{ns}$, `None` for no timing cut). When no setup is provided, `DEVICE_ALONE` is used, equivalent to `"along_beam": ["source", {"gap": 17000}, {"slot": "Device"}]`; a setup with only one device names its slot `"Device"` and passes `{"Device": my_d}`. The slot names in the setup and in the `devices` argument must match one-to-one, and any extra or missing slot raises `ValueError` (`the g4setup places <setup slots>, the devices are <given slots>`); the order of slots in the output follows the `devices` argument.

1. **Check source kind**: If `source["kind"]` is not one of `"toy_mip"`, `"beam"`, or `"decay_source"`, raise `ValueError` (`no simulation of deposits for a source of kind ...`).
2. **Check event counts and recording conditions**:
   - `asked(events, generated, generated_limit)` requires that exactly one of `events` (number of events to record) and `generated` (number of events to generate) be given, raising `ValueError` otherwise; if the given number or `generated_limit` is less than `1`, raise `ValueError` (`the <name> asked for are <number>: at least 1`).
   - Validate the recording-condition parameters, raising `ValueError` on any invalid setting: slot names in `windows` do not match `devices` (`the energy windows are for <windows slots>, the devices are <given slots>`); a slot's lower bound exceeds its upper bound (`slot '<slot>' has edep_min (<lo> MeV) > edep_max (<hi> MeV)`); `require` has a syntax error or names an operand that is not a slot name (`invalid require expression '<require>'` or `require '<require>' names unknown slot '<operand>'`); `coincidence_window_ns` is not `None` and not greater than `0` (`coincidence_window_ns must be positive, got <value> ns`).
3. **Toy MIP branch** (`kind == "toy_mip"`): Read `g4setup["maxstep"]` (or `DEVICE_ALONE["maxstep"] = 2` when `g4setup` is `None`) and call `mip_deposits(devices, source, g4setup, ...)`; see the next section. This branch runs in Python, drawing random numbers from the stream `stream("toy_mip")`.
4. **Geant4 branch** (`kind` is `"beam"` or `"decay_source"`):
   1. Import `geant4.interaction`. If `g4ppyy` is missing, raise `MissingDependency` (`Geant4's Python bindings, g4ppyy, are not installed in this Python`).
   2. `g4_configuration` builds the run configuration: if `par_in`, `par_out`, or `par_angle` appears in the source or in its `particles`, raise `ValueError` (source placement belongs to the setup); take a deep copy of `g4setup` (or `DEVICE_ALONE` if `None`) and extract the optional `"source"` block (default `{}`); overwrite same-named setup keys with keys from the source and remove `name`, `kind`, and `description`; with the source at the world origin pointing downstream along $+z$, set `par_in = [0, 0, 0]`, `par_out` to the point on the axis at the $z$ of the front face of the first slot, `[0, 0, z_i]`, and `par_angle = source.get("angle", 0)`. When `particles` is present, each item inherits `par_randx`, `par_randy`, `par_type`, and `par_energy` from the configuration, overrides them with its own keys, and adds `offset` (default `[0, 0, 0]` $\mu\text{m}$) to both the emission point and the aiming point. Finally write `recorded_events = events`, `total_events = generated` (or `generated_limit` when running by recorded count), `windows`, `require`, and `coincidence_window_ns`.
   3. `tilted` rotates the source by the incidence angle: unchanged when `par_angle` is `0`. If a multi-slot setup has nonzero `par_angle`, raise `ValueError` (`a multi-slot g4setup tilts no source`). Otherwise this applies only to single-slot setups: write $\mathbf{r}_{\text{in}} = (x_0, y_0, z_0)$ and $\mathbf{r}_{\text{out}} = (x_1, y_1, z_1)$; if $z_f \le z_0 \le z_f + l_z + t$ or $z_1 = z_0$, raise `ValueError` (the source line does not enter the device through a face). Take the rotation axis parallel to the $y$ axis passing through the single-slot device front-surface center $(x_p, P_y, z_f) = (P_x, P_y, P_z)$, and transform `par_in` and `par_out` in both the top-level configuration and each entry of `particles` by
      $$x' = (x - x_p)\cos\vartheta + (z - z_f)\sin\vartheta + x_p, \qquad z' = -(x - x_p)\sin\vartheta + (z - z_f)\cos\vartheta + z_f$$
      where $\vartheta$ is `par_angle` (degrees). For $\vartheta > 0$, the upstream source rotates toward the $-x$ side so particles travel with a $+x$ component toward the device front-surface center. $y$, `par_randx`, and `par_randy` are unchanged, and slots and objects in the setup do not move.
   4. Build the geometry (`GeneralDetectorConstruction`; or `GDMLDetectorConstruction` when `geant4_model == "gdml_import"`, where the geometry is given by GDML rather than `along_beam`). First validate `along_beam` and `object` (raising `ValueError` on any error): the first item is not `"source"` (`the first item of along_beam must be 'source'`); a `gap` is negative (`gap must be non-negative`); an object name is not in `object` (`object '<object>' is not in object`); the same object or slot appears twice (`duplicate '<name>' in along_beam`); `facing` is neither `"upstream"` nor `"downstream"` (`slot '<slot>' has facing <value>: expected 'upstream' or 'downstream'`); `rotation_z` is not `0`, `90`, `180`, or `270`; side-by-side items overlap transversely (`side-by-side items overlap`); or the slot names do not match `devices` (`the g4setup places <setup slots>, the devices are <given slots>`). The world is a cube of material `world` centered at the midpoint $(0, 0, L_{\text{col}}/2)$ of the `along_beam` line, with half-side length given by `world_half_side`: let $\rho = \max\bigl(L_{\text{col}}/2,\ \max_{\text{item}}(|o_x| + w_x/2,\ |o_y| + w_y/2),\ R\bigr)$, where $L_{\text{col}} = \sum_j d_j$ is the total length of the line, $w_x, w_y$ are the full transverse dimensions of each item (after rotation for a slot), $o_x, o_y$ are its `offset`, and $R$ is `par_radius`; take `25000` when $\rho \le 25000\ \mu\text{m}$, and $2\rho$ otherwise. Starting from `"source"` ($z = 0$), compute the front-face position $z_i$ of each item via Eq. (17): for each slot, build an active-layer box logical volume ($l_x \times l_y \times l_z$) named after the slot with material taken from that slot device's `material`, and place it according to Eqs. (17)–(18). The thicknesses and materials of a device's layers are intrinsic properties written in the device file, and Geant4 uses that same geometry (see [Architecture Overview](../architecture.md#components)); the reference device's substrate lies in the beam path, and multiple scattering in it determines how many particles reach downstream devices. The device geometry is layered along depth, with layers outside the active layer (substrate, etc.) described in [Detector Components](../components/device.md); Geant4 builds all layers according to the device geometry, creating a separate logical volume for each layer outside the active layer whose energy deposition is not recorded, recording deposition only in the active layer. Surrounding objects referenced in `along_beam` are then placed (laterally centered at `offset`, centered in $z$ at $z_i + \texttt{side\_z}/2$). If two binary compounds share the same `compound_name` with conflicting composition or density, raise `ValueError` (`Conflicting Geant4 material definition for ...`). Binary compounds convert atomic fractions to mass fractions via $m_i = n_i A_i / (n_1 A_1 + n_2 A_2)$.
   5. Configure the random engine, physics list, and user actions. If the source contains `nuclides`, use `NuclideGeneratorAction` and `DecayStackingAction`; otherwise use `GeneralPrimaryGeneratorAction`. For each event and each particle, the latter draws $\delta_x \sim U(-\texttt{par\_randx}, \texttt{par\_randx})$ and $\delta_y \sim U(-\texttt{par\_randy}, \texttt{par\_randy})$ from `stream("source")` and emits from $\mathbf{r}_{\text{in}}$ in direction $\mathbf{d} = \mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}} + (\delta_x, \delta_y, 0)$; when `par_type` is a list, it also draws an index with equal probability. If `par_type` and `par_energy` are lists of different lengths, raise `ValueError`.
   6. Execute `/run/initialize`; if `picture` is given and `drawn > 0`, enable off-screen visualization (see "Plots"); run `BeamOn(total_events)`.
   7. Event recording: at the end of an event, compute total deposited energy $E_s$ in the active layer for each slot $s$ according to Eq. (19): if $E_s > 0$ and `windows[s]` is satisfied (unprovided bounds are not checked), mark the slot as hit ($h_s = 1$) and take the global time of the earliest deposit step in that slot as $t_s$; otherwise mark it as not hit ($h_s = 0$). When no timing window is set (`coincidence_window_ns` is `None`), evaluate `require` directly on $\{h_s\}$; otherwise, try each hit slot's $t_s$ as the left endpoint $t_0$ in turn, count slots whose hit time falls within $[t_0, t_0 + W]$ as hit per Eq. (20), and evaluate `require`, recording the event if any $t_0$ makes `require` true. Deposit steps of slots that are not hit in the event are not kept. When running by recorded count, call `AbortRun` once the recorded count reaches `recorded_events`, and set `generated_events` to the number of completed events. When running by generated count, `generated_events = total_events`.
   8. `deposits()`: if running by recorded count and fewer than `recorded_events` events were recorded, raise `RuntimeError` (`... events asked for were recorded when the limit of ... generated events was reached ...`). Otherwise convert step positions from Geant4 world coordinates to the device coordinates of their respective devices via the inverse of Eq. (18) for each slot; call `deposits_of_steps(<slot name>, ...)` for each device to drop steps with $E_k \le 0$ (a slot that is not hit has no deposit steps in that event), concatenate the deposit steps across devices in the order of `devices` for each event, and drop events with no remaining steps. Event IDs are Geant4's `eventID`.
   9. Regardless of whether an error occurred, call `close()` at the end to release Geant4 objects.
5. **Write source emission fraction**: `generated_fraction(source)` evaluates to Eq. (16) when the source contains `nuclides` and `par_cone` is not `None`, and `1.0` otherwise.
6. **Ionization**: Call `ionized_pairs(event, material, fano)` for each event, taking each step's `material` from the `material` of its slot's device. Raise `ValueError` if the material is not in `PAIR_ENERGY_EV`, or if `fano=True` and the material is not in `FANO_FACTOR`. Each event draws from its own stream `stream(f"ionization/{event.event}")`, so an event's pair counts are independent of which events were recorded before it.

`write_simulated_deposits` takes the same parameters as `simulate_deposits` (`devices`, `source`, `g4setup`, `events`, `g4_seed`, `windows`, `require`, `coincidence_window_ns`, etc.), calls `simulate_deposits`, writes the file via `write_deposits`, and returns the number of recorded events.

In GDML import mode, the device logical volume `"Device"` is built according to `material` for `"Si"` (`G4_Si`) and `"SiC"` (equal atomic fractions of Si and C, $3.21\ \text{g/cm}^3$).

### Slicing Energy-Loss Tracks into Deposition Steps

**Geant4**: Step length is determined by Geant4, capped at `maxstep` inside the device (Eq. (3)). For every step whose pre-step logical volume is named after a slot (`"Device"` for a single device), `GeneralSteppingAction` calls `RecordDevice`: it records separately by logical volume name, accumulates $E_{\text{tot}}$, and records the step midpoint $\frac{1}{2}(\mathbf{r}^{\text{pre}} + \mathbf{r}^{\text{post}}) \times 1000$ (converting Geant4's $\text{mm}$ to $\mu\text{m}$), the pre-step point $\mathbf{r}^{\text{pre}} \times 1000$ (written as `x_start`, etc.), the deposited energy ($\text{MeV}$), and the global time of the pre-step point ($\text{s}$).

**toy MIP** (`mip_deposits`):

1. Raise `ValueError` if the source contains keys outside `_SOURCE_KEYS` (`name`, `kind`, `description`, `start`, `end`, `position_range_um`, `direction_sigma_mrad`, `packets`, `landau_sampling`), if `landau_sampling` is missing, or if the material is not in `PAIRS_PER_UM`.
2. `generation(events, generated, generated_limit, recorded)` yields event IDs $0, 1, \dots$: `generated` events when running by generated count; or generating until the recorded count equals `events` when running by recorded count, raising `RuntimeError` if `generated_limit` is reached without enough recorded events. All draws use the single stream `stream("toy_mip")`.
3. Track endpoints for each event (`_track_ends`): default start $(l_x/2, l_y/2, 0)$ and default end $(l_x/2, l_y/2, l_z)$. When `position_range_um` is given, draw $x_s \sim U(x_{\text{lo}}, x_{\text{hi}})$ and $y_s \sim U(y_{\text{lo}}, y_{\text{hi}})$ in order (both `"x"` and `"y"` must be provided). When `direction_sigma_mrad` is given, draw slope $k_u \sim \mathcal{N}(0, (10^{-3}\sigma_u)^2)$ for each of `"x"` and `"y"` with $\sigma > 0$. Whenever the start point or slope is drawn, the end transverse coordinates become $u_e = u_s + k_u (z_e - z_s)$.
4. Number of segments $n$: `int(packets)` if `packets` is provided, otherwise $n = \lceil L / \texttt{maxstep} \rceil$, where $L$ is the distance from start to end ($\mu\text{m}$). Each segment has length $\Delta l = L/n$, and segment energies are drawn sequentially according to Eq. (5).
5. Events whose total energy $\sum_k E_k$ is not greater than `0` or falls outside `windows["Device"]` are not recorded. Toy MIP retains segments with energy $0$.
6. Segment $k$ ($k = 0, \dots, n-1$) has position at the segment midpoint $\mathbf{r}_s + \frac{k + 0.5}{n}(\mathbf{r}_e - \mathbf{r}_s)$, start point $\mathbf{r}_s + \frac{k}{n}(\mathbf{r}_e - \mathbf{r}_s)$, time $0.0\ \text{s}$, and detector name `"Device"`.
7. Return `Deposits(generated_events = last_event_id + 1, ...)`.

For a multi-slot setup, the track traverses all slots in Geant4 world coordinates; steps 3, 4, and 6 are replaced by the following, with the rest unchanged:

- Raise `ValueError` if the source contains `start`, `end`, or `position_range_um` (for multiple slots, the track starts from the setup's source).
- Take the start point $\mathbf{r}_s$ at the world origin $(0, 0, 0)$ where the source sits, and the direction along $+z$ (`[0, 0, 1]`); when `direction_sigma_mrad` is given, draw slopes as in step 3 as $dx/dz$ and $dy/dz$ of the direction (direction vector $(k_x, k_y, 1)$).
- For each slot in `devices`, take the track segment within the slot active layer's $z$-interval ($[P_z,\ P_z + l_z]$ for `"upstream"`, and $[P_z - l_z,\ P_z]$ for `"downstream"`), split its length $L$ according to step 4, transform each segment's midpoint and start point to that slot's device coordinates via the inverse of Eq. (18), discard segments whose transverse coordinates fall outside $[0, l_x] \times [0, l_y]$, and assign the slot name as detector name and `0.0 s` as time.
- In step 5, events are selected for recording according to Eqs. (19)–(20) using per-slot energy windows `windows`, `require`, and `coincidence_window_ns` (all hit slots have time `0.0 s`); only segments of hit slots are kept and concatenated end-to-end in the order of `devices`, and a slot that is not hit has no deposit steps in that event.

### Laser Carrier Groups

`LaserInjection(my_d, laser_dic)` reads the laser keys (see "Interface"). If `alpha` is not given: when the device material is `"SiC"`, it computes $\alpha$ from Eqs. (7a) and (7b) using the device's `temperature`, raising `ValueError` if $\hbar\omega > 3.8\ \text{eV}$; for other materials, it looks up the table using Eq. (7), raising `ValueError` if `deposit/absorption/<material>.txt` does not exist in the components or if $10^3\lambda$ is shorter than the shortest wavelength in the table, and setting $\alpha = 0$ if it is longer than the longest wavelength. It then adds SPA groups with $k = 2$ and broadening $\tau$ when $\alpha \ne 0$, and subsequently adds TPA groups with $k = 4$ and broadening $\tau/\sqrt{2}$ when `tech == "TPA"`. If `tech` is neither `"SPA"` nor `"TPA"`, `NameError(tech)` is raised after adding any SPA groups. Each call to `_add_groups` proceeds as follows:

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
- `Deposits`: deposits for a job. `generated_events` (number of events generated by the source), `windows` (dictionary mapping slot names to `(edep_min, edep_max)`, $\text{MeV}$, either bound may be `None`), `require` (coincidence-condition logical expression string), `coincidence_window_ns` (coincidence timing window, $\text{ns}$, may be `None`), `events` (list of `EventDeposits`), `generated_fraction` (default `1.0`).
- `LaserInjection`: `track_position` (`[x, y, z, t]` per group, $\mu\text{m}$ and $\text{s}$), `ionized_pairs` (pairs per group), `time_FWHM` (temporal broadening per group, $\text{s}$), as well as `temporal_FWHM`, `timePulse`, and other attributes used for current convolution.

## Interface

Users can configure the keys in device files, setup scripts, radioactive source and beam files, and laser files listed in the tables below; all other parameters on this page are hard-coded. Event counts, energy window, `deposit.fano`, and plotted event count `deposit.plots` are settings in the `deposit` section; see the [energy deposition stage](../stages/deposit.md).

### Keys Read from Device Files

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `l_x`, `l_y`, `l_z` | none (required) | $\mu\text{m}$ | Active-layer dimensions of the device; see [device model](device.md) |
| `material` | none (required) | none | `"Si"`, `"SiC"`, or `"Diamond"`; determines Geant4 material, ionization energy, and Fano factor; toy MIP supports only `"Si"` and `"SiC"` |
| `temperature` | none (required when a laser for a `"SiC"` device omits `alpha`) | $\text{K}$ | $T$ in Eq. (7b) |

The device geometry is layered along depth, with layers outside the active layer (substrate, etc.) described in [Detector Components](../components/device.md); Geant4 builds all layers according to the device geometry and records energy deposition only in the active layer.

### Setup

A setup is the dictionary `G4SETUP` inside a `<name>.py` script under `components/deposit/`; when no setup is given, `DEVICE_ALONE` is used (identical to `device_alone.py` except for `name` and `description`).

#### Top-Level Keys of `G4SETUP`

| Key | Default (`DEVICE_ALONE`) | Unit | Meaning |
| --- | --- | --- | --- |
| `name`, `description` | none (optional) | none | Setup name and description; `name` appears only in error messages |
| `geant4_model` | `"device"` | none | Required for Geant4 sources; `"gdml_import"` imports an external GDML file, while other values serve only as labels |
| `world` | `"G4_Galactic"` | none | Required for Geant4 sources; NIST material name of the world volume |
| `maxstep` | `2` | $\mu\text{m}$ | Required; maximum Geant4 step length inside the device, and also the segment-length upper bound for toy MIP when `packets` is not given |
| `source` | `{"angle": 0}` | degrees | Optional; keeps only `angle` (incidence angle, default `0`), used only for single-slot setups to rotate the source around the device front-surface center per step 4.3 of "Branches of `simulate_deposits`"; beam emission direction is $+z$ |
| `object` | `{}` | none | Required for Geant4 sources; surrounding objects, which may contain `"elemental"` and `"binary_compounds"` categories, each defining only material, dimensions, hole, and color, placed in `along_beam` |
| `par_type`, `par_energy`, `par_randx`, `par_randy` | none | see sources | Optional; the setup may provide these beam keys, and same-named keys in the source override them |
| `along_beam` | `["source", {"gap": 17000}, {"slot": "Device"}]` | none | Required (except for `gdml_import`); a line starting from `"source"` and pointing downstream along $+z$, placing device slots and surrounding objects per Eqs. (17)–(18), see the table below |

In Geant4 world coordinates, the origin $(0, 0, 0)$ sits on the source and $+z$ points downstream along the beam; the front-surface center $\mathbf{P}$ and the $z$-intervals occupied by the active layer and layers outside the active layer (see [Detector Components](../components/device.md)) of each slot are determined by its position in `along_beam` and its `facing` via Eqs. (17)–(18).

#### Items of `along_beam`

`along_beam` is a list starting from `"source"` and ordered along $+z$, with item kinds and keys listed below. The slot name serves as both the active-layer Geant4 logical volume name (each layer outside the active layer is built as a separate logical volume whose deposition is not recorded) and the detector name in the deposit file; it may use only characters in `[A-Za-z0-9_-]` and must not collide with any name in `object` or any configuration key of the [energy deposition stage](../stages/deposit.md) (slot names appear in addresses such as `deposit.<slot>.<key>`); for a setup with only one device, the slot name is `"Device"`. Which device goes into each slot is not specified by the setup, but passed via the caller's `devices` argument, whose slot names must match the setup's slots one-to-one (see "Branches of `simulate_deposits`").

```python
"along_beam": [
    "source",
    {"gap": 1995}, "Al",
    {"gap": 4978.5},
    {"slot": "ref"}, "pcb1",
    {"gap": 8183.5},
    {"slot": "dut"}, "pcb2",
]
```

| Item Kind | Keys | Default | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `"source"` | none (string) | none (required first item) | none | Source; must be the first item of `along_beam`, has thickness `0`, and carries the world coordinate origin |
| `{"gap": d}` | `gap` | none | $\mu\text{m}$ | Gap of length $d \ge 0$ along $z$; adjacent items without a `gap` between them are flush |
| `"<object name>"` or `{"object": "<object name>", ...}` | `object`, `offset` | `offset` defaults to `[0, 0]` | $\mu\text{m}$ for `offset` | An object from `object`, occupying its thickness `side_z` along $z$ and laterally centered at `offset`; shorthand `"<object name>"` equals `offset = [0, 0]` |
| `{"slot": "<slot name>", ...}` | `slot`, `facing`, `offset`, `rotation_z`, `colour` | `facing` defaults to `"upstream"`, `offset` to `[0, 0]`, `rotation_z` to `0`, `colour` to `[1, 0.1, 0.8]` | $\mu\text{m}$ for `offset`, degrees for `rotation_z` | A device occupying total thickness $l_z + t$ of all layers in its geometry along $z$; `facing` is `"upstream"` (front surface facing the source) or `"downstream"` (flipped $180^\circ$ about the $y$ axis, front surface facing downstream), and `rotation_z` is restricted to `0`, `90`, `180`, `270`, placed per Eqs. (17)–(18); `colour` is the visualization RGB color (`0` to `1`) |
| `[item, item, ...]` | items in list | none | none | Side-by-side items (objects or slots only) whose front faces align at the same $z$, occupying the thickness of the thickest item along $z$ and staggered laterally via each item's `offset` |

If the first item of `along_beam` is not `"source"`, if a `gap` is negative, if an object name is absent from `object`, if the same object or slot appears twice, if `facing` is neither `"upstream"` nor `"downstream"`, if `rotation_z` is not in `{0, 90, 180, 270}`, if side-by-side items overlap transversely, or if the slot names do not match the device table, `ValueError` is raised.

#### Geometry Keys for the Two Categories of `object`

Both `object["elemental"]` and `object["binary_compounds"]` are dictionaries keyed by volume name, where each entry is a box: the former uses a Geant4 NIST material and the latter is a compound of two elements. For example, an aluminum layer between the source and the device:

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
        },
    },
},
```

This is a $5\ \text{mm} \times 5\ \text{mm} \times 0.08\ \mu\text{m}$ aluminum foil; to place its bottom face at distance $d$ from the device front surface, write `"Al"` before the slot in `along_beam` separated by `{"gap": d}`.

Every key in the table below is required for its applicable category, except `tub` under `elemental`, which may be omitted.

| Key | Applicable Category | Unit | Meaning |
| --- | --- | --- | --- |
| `name` | both | none | Volume name |
| `material` | `elemental` | none | Geant4 NIST material name, such as `"G4_Al"`, `"G4_Ni"`, `"G4_Ti"`, `"G4_Si"`, `"G4_BRASS"` |
| `material_1`, `material_2` | `binary_compounds` | none | Symbols of the two elements, such as `"Si"`, `"C"`, `"N"`, `"O"` |
| `compound_name` | `binary_compounds` | none | Compound material name; compounds with the same name must have identical composition and density |
| `density` | `binary_compounds` | $\text{g/cm}^3$ | Compound density |
| `natoms_1`, `natoms_2` | `binary_compounds` | none | Atomic-number shares of the two elements, converted to mass fractions using atomic weights |
| `side_x`, `side_y`, `side_z` | both | $\mu\text{m}$ | Full dimensions of the box along $x$, $y$, and $z$ (`side_z` is thickness) |
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
| `device_alone` | `raser/components/deposit/` | Device placed alone in vacuum, `17 mm` from the source to the device front surface |
| `Sr90_collimator` | `src/raser_bench/signal/components/deposit/` | Brass collimator between the source and device in air (see [signal](../bench/signal.md)) |
| `pcb_readout_gdml` | `src/raser_bench/signal/components/deposit/` | PCB readout board imported from `pcb_readout.gdml` (see [signal](../bench/signal.md)) |
| `time_resolution` | `src/raser_bench/timeres/components/deposit/` | Aluminum foil, reference silicon device, and two apertured PCB boards arranged along the beam (see [time resolution](../bench/timeres.md)) |
| `telescope` | `src/raser_bench/telescope/components/deposit/` | 8 slots arranged along the beam in vacuum, defaulting to 3 + 2 + 3 (see [beam telescope](../bench/telescope.md)) |

### Radioactive Sources and Beams

#### Common Keys

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `name` | none (optional) | none | Source name |
| `kind` | none (required) | none | `"beam"`, `"decay_source"`, or `"toy_mip"` |
| `description` | none (optional) | none | Text description |

A source must not contain `par_in`, `par_out`, or `par_angle`: the source emits along $+z$ from the world origin, and the incidence angle is given by the setup's `source.angle`.

#### Keys for `beam` and `decay_source`

`"beam"` and `"decay_source"` take the same Geant4 branch; whether nuclide decay is used depends solely on whether `nuclides` is present in the source.

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `par_type` | none (required when `nuclides` is absent) | none | Geant4 particle name (e.g. `"e-"`, `"proton"`, `"alpha"`), or a list of particle names drawn with equal probability |
| `par_energy` | none (required when `nuclides` is absent) | $\text{MeV}$ | Particle kinetic energy, or a list of the same length as `par_type` |
| `par_randx`, `par_randy` | `0`, `0` | $\mu\text{m}$ | Half-width of uniform random offsets added to the $x$ and $y$ components of the emission direction vector ($\mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}}$) |
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
| `alpha` | looked up via Eq. (7) for silicon, calculated via Eq. (7a) for silicon carbide | $\text{m}^{-1}$ | Absorption coefficient; setting `0` disables single-photon absorption, leaving only TPA groups for a `"TPA"` laser |
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
| `PIL037_top_SiC`, `PIL037_edge_SiC` | `"SPA"` | $375\ \text{nm}$, silicon carbide, $\alpha$ calculated via Eq. (7a) ($9.05\ \text{cm}^{-1}$ at $300\ \text{K}$) |
| `TPA1550_top_Si`, `TPA1550_edge_Si` | `"TPA"` | $1550\ \text{nm}$, silicon, longer than the table upper limit, $\alpha = 0$, TPA groups only |

### `deposit.h5` File Format

#### File Attributes

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `generated_events` | `int` | events | Number of events generated by the source |
| `recorded_events` | `int` | events | Number of events stored in the file |
| `generated_fraction` | `float` | none | Fraction of source emissions generated; Eq. (16) for nuclide sources with `par_cone`, `1.0` otherwise |
| `edep_min.<slot>`, `edep_max.<slot>` | `float` | $\text{MeV}$ | Lower and upper bounds of the total deposited energy window in that slot's active layer (slot name `"Device"` for a single device); written only when given |
| `require` | `str` | none | Coincidence condition logical expression |
| `coincidence_window_ns` | `float` | $\text{ns}$ | Coincidence timing window; written only when given |

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
| `nocarrier2D_<fx>_<fy>_<fz>.pdf` | `LaserInjection.draw_nocarrier2D` | Volume density of electron-hole pairs on the $y = f_y l_y$ $x$-$z$ plane (which passes through the optical axis for all three incidence directions), `TH2D` (`COLZ`), evaluated directly on a $200 \times 200$ grid by multiplying $dN/ds$ from Eqs. (10) and (11) by the transverse profile $\frac{k}{\pi w^2}\exp(-k r^2/w^2)$, with color representing pairs per $\mu\text{m}^3$ (`Pairs [μm⁻³]`); plotted along the beam path from the entrance face to where the cumulative pair count $M(s)$ reaches $0.99\,N_{\text{tot}}$, and transversely out to $2 w_{\max}$ on both sides of the optical axis ($w_{\max}$ is the maximum beam radius along this path segment, clipped at the device boundaries) | $\mu\text{m}$ |

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
- [16] P. Grivickas, V. Grivickas, J. Linnros, A. Galeckas, “Fundamental band edge absorption in nominally undoped and doped 4H-SiC”, J. Appl. Phys. 101 (2007) 123521, doi:10.1063/1.2749335
- [17] S. G. Sridhara, R. P. Devaty, W. J. Choyke, “Absorption coefficient of 4H silicon carbide from 3900 to 3250 Å”, J. Appl. Phys. 84 (1998) 2963, doi:10.1063/1.368403
