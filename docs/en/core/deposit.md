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

The device material in Geant4 is built according to `material`: `"Si"` uses NIST `G4_Si`; `"Diamond"` uses `G4_C` with the density changed to $3.52\ \text{g/cm}^3$ (code comment: NIST `G4_C` is graphite at $2.0\ \text{g/cm}^3$); `"SiC"` is a compound of equal atomic fractions of Si and C with density $3.21\ \text{g/cm}^3$. The diamond density is taken from the PDG table of atomic and nuclear properties [8], and the 4H-SiC density is taken from Ref. [13]. The device's `material` takes only `"Si"`, `"SiC"`, or `"Diamond"` (the three materials with ionization energy and Fano factor); names defined in `G4SETUP["materials"]` and Geant4 NIST material names starting with `"G4_"` are used only for `material` in `objects`.

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

A radioactive source together with its encapsulation and collimator forms a single component whose external output consists of the particles emerging from the collimator exit; this emission distribution depends solely on the nuclides, encapsulation, and collimator, independent of which downstream devices are placed or what coincidence condition is applied, and the source component contains no emission angle tuned for a particular experiment. Each event is a single decay of a nuclide at rest: a nuclide is drawn with equal probability from `nuclides`, and its position is uniformly distributed on a disk perpendicular to the emission (bore) axis (radius `par_radius`; point source on axis when $R = 0$). The initial time of decay products is reset to zero and the daughter nucleus left by the decay is killed there, so one event corresponds to one decay. When `activity` (in $\text{Bq}$) is given, it specifies the decays per second of each nuclide; $^{90}\text{Sr}$ and $^{90}\text{Y}$ are in secular equilibrium, so each nuclide decays at `activity`.

A radioactive source without `collimator` emits isotropically over full $4\pi$ space. When `collimator` (containing `material`, `length`, `radius`, `outer_side`) is given, the nuclide disk lies on the collimator entrance face ($z = -L$) centered on the bore axis; the center of the collimator exit plane lies at the world origin $(0, 0, 0)$, the $z$ axis points downstream along the bore axis, and the collimator body lies on $z \in [-L, 0]$ (the $z < 0$ side). The setup does not place the collimator as an object.

For an emission point $\mathbf{r}_0$ on the disk and an emission direction $\hat{\mathbf{d}}$, let $\ell(\mathbf{r}_0, \hat{\mathbf{d}})$ denote the straight-line path length traveled through the collimator material between the emission point and the exit plane $z = 0$ ($\ell = 0$ when the ray stays entirely inside the bore; backward-hemisphere directions $\hat{\mathbf{d}}\cdot\hat{\mathbf{z}} \le 0$ are not emitted). Only directions satisfying $\ell(\mathbf{r}_0, \hat{\mathbf{d}}) \le R_{\text{CSDA}}(E_{\max})$ are emitted, where $E_{\max}$ is the largest $\beta$-spectrum endpoint energy among the nuclides in the source and $R_{\text{CSDA}}(E_{\max})$ is the continuous-slowing-down approximation (CSDA) range in the collimator material for electrons at kinetic energy $E_{\max}$, obtained from Geant4's `G4EmCalculator`. The fraction $f$ of full $4\pi$ space covered by the emitted directions is computed numerically over emission points and directions and written as `generated_fraction`:

$$f = \frac{1}{\pi R^2}\int_{|\mathbf{r}_0 - \mathbf{r}_c| \le R} d^2\mathbf{r}_0 \cdot \frac{1}{4\pi}\int_{\hat{\mathbf{d}}\cdot\hat{\mathbf{z}} > 0} \mathbb{I}\bigl[\ell(\mathbf{r}_0, \hat{\mathbf{d}}) \le R_{\text{CSDA}}(E_{\max})\bigr]\,d\Omega \tag{21}$$

For a point source on the axis ($R = 0$) with bore radius $r$ and length $L$, the fraction whose straight line stays entirely inside the bore is:

$$f_{\text{hole}} = \frac{1 - \cos\theta_c}{2}, \qquad \theta_c = \arctan\frac{r}{L} \tag{22}$$

Taking `decay/Sr90` from the library ($r = 500\ \mu\text{m}$, $L = 3000\ \mu\text{m}$) as an example, $\theta_c = 9.46^\circ$, and this straight-through bore fraction is $0.68\%$. Emission is not restricted solely to the geometric opening angle $\theta_c$ because electrons entering the bore wall at larger angles can scatter out through the bore: in a control simulation emitting within a $12^\circ$ cone, about $7\%$ of the events selected by the downstream device come from outside the geometric opening angle as electrons scattered off the collimator wall.

Electrons inside the collimator material undergo range rejection: if $R_{\text{CSDA}}(E)$ at an electron's current kinetic energy is smaller than its distance $d_{\min}(\mathbf{r})$ to the nearest bore wall surface or exit plane, the track is terminated and its energy is deposited locally:

$$R_{\text{CSDA}}(E) < d_{\min}(\mathbf{r}) \tag{23}$$

Bremsstrahlung photons produced by the electron are unaffected and continue to be transported normally.

Particles crossing the exit plane ($z = 0$, spanning the entire world) are recorded (species, position, direction, kinetic energy, time; neutrinos omitted) and terminated there. For each block of the emission distribution, the number of decays actually sent into Geant4 (those falling within the emitted directions) is fixed at `EMISSION_BLOCK_DECAYS = 1_000_000`, corresponding to the full-space decay count `decays = EMISSION_BLOCK_DECAYS / generated_fraction`, and with exit-plane crossing decay count `emitted`, the single-block emission probability $\varepsilon$ (when a job uses multiple blocks, `emission_probability` takes `sum(emitted) / sum(decays)` across the blocks used) and the emission rate $\dot{N}_{\text{emit}}$ when `activity` is given are:

$$\varepsilon = \frac{\texttt{emitted}}{\texttt{decays}}, \qquad \dot{N}_{\text{emit}} = n_{\text{nuclides}} \cdot \texttt{activity} \cdot \varepsilon \tag{24}$$

where:

- $\mathbf{r}_0$: nuclide emission point on the entrance face $z = -L$, $\mu\text{m}$; $\mathbf{r}_c = (0, 0, -L)$: center of the collimator entrance face, $\mu\text{m}$; $R$: disk radius `par_radius`, $\mu\text{m}$ (reduces to a point on axis $\mathbf{r}_c$ when $R = 0$, with Eq. (21) averaging only over solid angle);
- $\hat{\mathbf{d}}$: unit vector of decay-product emission direction; $\hat{\mathbf{z}}$: unit vector pointing downstream along the bore axis; $\ell(\mathbf{r}_0, \hat{\mathbf{d}})$: straight-line path length in collimator material from $\mathbf{r}_0$ to $z = 0$, $\mu\text{m}$;
- $R_{\text{CSDA}}(E)$: CSDA range of an electron with kinetic energy $E$ ($\text{MeV}$) in the collimator material, $\mu\text{m}$; $E_{\max}$: largest $\beta$-spectrum endpoint energy among the nuclides in the source, $\text{MeV}$;
- $f$: fraction of full $4\pi$ solid angle covered by emitted directions, written to attribute `generated_fraction` of `emission.h5`;
- $r, L$: collimator bore `radius` and `length`, $\mu\text{m}$; $\theta_c$: geometric half-opening angle from an on-axis point source to the exit aperture; $f_{\text{hole}}$: fraction of $4\pi$ whose straight rays stay inside the bore;
- $d_{\min}(\mathbf{r})$: distance from the electron's current position $\mathbf{r}$ to the nearest bore wall surface or exit plane, $\mu\text{m}$;
- `emitted`: number of decays crossing the exit plane, decays; `decays`: corresponding full-space decay count of the block (`EMISSION_BLOCK_DECAYS / generated_fraction`), decays;
- $\varepsilon$: emission probability, written to attribute `emission_probability` of `deposit.h5` (when multiple blocks are used, `sum(emitted) / sum(decays)` across the blocks used);
- $n_{\text{nuclides}}$: number of nuclides in `nuclides`; `activity`: activity of each nuclide, $\text{Bq}$; $\dot{N}_{\text{emit}}$: emission rate at the collimator exit plane, $\text{s}^{-1}$.

Nuclides are generated by `NuclideGeneratorAction` (`G4GeneralParticleSource`, kinetic energy $0$), while time zeroing and daughter killing are performed by `DecayStackingAction`, identifying decay tracks by the creator process subtype `RADIOACTIVE_DECAY = 210`. When generating block `0` of an emission distribution, a control run using only the source itself relaxes the direction restriction to the entire forward hemisphere (with range rejection active as usual) and writes the ratio of the two emission probabilities with its statistical error and the comparison of emitted electron kinetic-energy spectra to `emission_check` in `node.json`. For radioactive decay in Geant4, see Ref. [5].

### Line Along the Beam

The setup uses `along_beam` to describe a line of geometry along the beam direction: the first item must be `"source"`; without a collimator the world coordinate origin $(0, 0, 0)$ lies on the source, and with a collimator it lies at the center of the collimator exit plane with the collimator body on the $z < 0$ side (the setup does not place the collimator as an object), all `gap`s in the setup are measured from the collimator exit plane, and the $z$ axis points downstream along the beam (bore axis). Subsequent items in the line are gaps `{"gap": d}` ($d \ge 0$, $\mu\text{m}$), objects from `objects` (`"<object name>"` or `{"object": "<object name>", "offset": [o_x, o_y]}`, occupying the object's thickness along $z$: `size[2]` for `"box"`, `length` for `"tube"`), device slots `{"slot": "<slot name>", ...}` (occupying the total thickness $l_z + t$ of all layers of the device geometry along $z$; see [Detector Components](../components/device.md), with $t = 0$ when there are no layers outside the active layer), or a side-by-side list `[item, item, ...]` whose front faces align at the same $z$ and whose items are staggered laterally by their `offset` (occupying the thickness of the thickest item along $z$). Adjacent items with no `gap` between them are flush against each other; the source has thickness $0$, the front-face position $z_i$ of item $i$ equals the sum of thicknesses and gaps of all preceding items, and the slot front-surface center $\mathbf{P} = (P_x, P_y, P_z)$ and transformation from device coordinates $(x, y, z)$ (origin at a corner of the device front surface, with the active layer spanning $[0, l_x] \times [0, l_y] \times [0, l_z]$) to Geant4 world coordinates $\mathbf{r}_{\text{G4}}$ are:

$$z_i = \sum_{j < i} d_j, \qquad \mathbf{P} = \begin{cases} \bigl(o_x,\ o_y,\ z_i\bigr), & \texttt{facing} = \texttt{"upstream"} \\ \bigl(o_x,\ o_y,\ z_i + l_z + t\bigr), & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{17}$$

$$\mathbf{r}_{\text{G4}} = \begin{cases} \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} x - l_x/2 \\ y - l_y/2 \\ z \end{pmatrix}, & \texttt{facing} = \texttt{"upstream"} \\[4ex] \mathbf{P} + \begin{pmatrix} \cos\phi & -\sin\phi & 0 \\ \sin\phi & \cos\phi & 0 \\ 0 & 0 & 1 \end{pmatrix} \begin{pmatrix} -(x - l_x/2) \\ y - l_y/2 \\ -z \end{pmatrix}, & \texttt{facing} = \texttt{"downstream"} \end{cases} \tag{18}$$

where:

- $d_j$: thickness or gap occupied by item $j$ along the $z$ axis ($0$ for `"source"`, $d$ for `{"gap": d}`, object thickness—`size[2]` for `"box"` or `length` for `"tube"`—for an object, $l_z + t$ for a slot, and the maximum thickness among items in a side-by-side list), $\mu\text{m}$; $z_i$: world $z$ coordinate of the front face of item $i$, $\mu\text{m}$;
- $o_x, o_y$: the slot's `offset` (default `[0, 0]`), $\mu\text{m}$;
- $l_z$: active-layer thickness of the device in that slot, $\mu\text{m}$; $t$: total thickness of layers outside the active layer, $\mu\text{m}$ ($t = 0$ when there are no such layers);
- $\mathbf{P} = (P_x, P_y, P_z)$: world coordinates of the center of the device front surface (the $z = 0$ plane in device coordinates), $\mu\text{m}$;
- $\phi$: the slot's `rotation_z`, degrees, restricted to `0`, `90`, `180`, `270`; $l_x, l_y$: transverse dimensions of the device in that slot, $\mu\text{m}$.

When `facing` is `"upstream"` (the default), the active layer occupies $[z_i,\ z_i + l_z]$, layers outside the active layer occupy $[z_i + l_z,\ z_i + l_z + t]$, the device front surface faces the source at $P_z = z_i$, and the device $z$ axis points along $+z$; placing a slot immediately before a board with no gap mounts the device's substrate and other outer layers against the side of the board facing the source with the active layer on the outside. When `facing` is `"downstream"`, the device is flipped $180^\circ$ about the $y$ axis (for $\phi = 0$, $x_{\text{G4}} = P_x - (x - l_x/2)$, $y_{\text{G4}} = P_y + (y - l_y/2)$, $z_{\text{G4}} = P_z - z$), layers outside the active layer occupy $[z_i,\ z_i + t]$, the active layer occupies $[z_i + t,\ z_i + t + l_z]$, and the device front surface faces downstream at $P_z = z_i + l_z + t$; placing a slot after a board with `"facing": "downstream"` mounts the substrate against the side of the board facing away from the source with the active layer on the outside. When two devices are mounted on the facing sides of two boards (a `"downstream"` slot after the first board, an `"upstream"` slot before the second board, separated by `{"gap": g}`), their active layers face each other and the spacing between them is the `gap`. The world cube is centered at the midpoint of this line, with half-side length taken as `25000` $\mu\text{m}$ when $\rho \le 25000\ \mu\text{m}$ and $2\rho$ otherwise, where $\rho$ is the maximum among half the total length of the line, each item's transverse half-size plus offset, and the source disk radius.

### Recording Conditions for Multiple Devices

`deposit` filters solely on information from deposition itself (total deposited energy in each slot's active layer and earliest deposition time), without using any downstream information; which devices' waveforms must cross threshold simultaneously and how triggering is defined are decided by the `trigger` stage using its own settings, which `deposit` neither reads nor references. The same batch of deposited events can therefore be evaluated under different trigger conditions to compare how triggering affects distributions.

`deposit` retains the three filters that depend only on deposition itself, all defined on this page:

- **Energy window**: a slot $s$ is "hit" in an event when the total deposited energy in its active layer satisfies $E_s > 0$ and falls within its energy window $[E_{s,\min},\ E_{s,\max}]$ (`None` disables checking on that side), with hit time $t_s$ taken as the global time of the earliest deposit step in that slot's active layer, Eq. (19).
- **Slot logical expression `require`**: operands are slot names, operators are `AND`, `OR`, and parentheses, with `AND` binding tighter than `OR`; `"any"` is shorthand for the `OR` of all slots, and `"all"` is shorthand for the `AND` of all slots. An error is raised if the expression contains a name that is not a slot name or leaves any slot unused.
- **Timing window `coincidence_window_ns`** (denoted $W$): an event is recorded only if there exists some time $t_0$ such that `require` evaluates to true when counting only slots whose hit times fall within $[t_0,\ t_0 + W]$, Eq. (20); when `None`, no timing cut is applied and $h_s(t_0) = h_s$ directly.

$$h_s = \mathbb{I}\bigl(E_s > 0,\ E_{s,\min} \le E_s \le E_{s,\max}\bigr), \qquad t_s = \min_{k \in \mathcal{K}_s} t_{s,k} \tag{19}$$

$$h_s(t_0) = h_s \cdot \mathbb{I}\bigl(t_0 \le t_s \le t_0 + W\bigr), \qquad \exists\, t_0 \in \mathbb{R}:\ \mathcal{F}\bigl(\{h_s(t_0)\}_{s \in \mathcal{S}}\bigr) = \texttt{true} \tag{20}$$

where:

- $s \in \mathcal{S}$: slot name, where $\mathcal{S}$ is the set of all slots in the setup;
- $\mathcal{K}_s$: set of deposit steps in the active layer of slot $s$, with total deposited energy $E_s = \sum_{k \in \mathcal{K}_s} E_{s,k}$, $\text{MeV}$;
- $E_{s,\min}, E_{s,\max}$: lower and upper bounds of slot $s$'s energy window, $\text{MeV}$ (unprovided bounds are not checked);
- $h_s \in \{0, 1\}$: hit flag of slot $s$ without the timing window;
- $t_{s,k}$: global time of the $k$-th deposit step in slot $s$, $\text{s}$; $t_s$: global time of the earliest deposit step in slot $s$, $\text{s}$;
- $W$: timing window `coincidence_window_ns`, input in $\text{ns}$ (converted to $W \times 10^{-9}\ \text{s}$ when compared against $t_s$; when `None`, no timing cut is applied and $h_s(t_0) = h_s$ directly);
- $t_0$: left endpoint of the timing window, $\text{s}$;
- $h_s(t_0) \in \{0, 1\}$: hit flag of slot $s$ within the timing window $[t_0,\ t_0 + W]$;
- $\mathcal{F}$: Boolean function parsed from `require`.

For a single slot, the condition reduces to total deposited energy in the device $> 0$ and within its energy window. A recorded event keeps the deposit steps of all slots. The examples all use `require = "any"` and `coincidence_window_ns = null`, dropping only events with no deposition in any slot's active layer; in the default `timeres` setup (Sr-90 source, DUT `HPK-Si-PiN`), downstream drift, readout, and reconstruction take about `0.2 s` per recorded event, and in roughly three-quarters of events with deposition in the DUT the reference device has no deposition, so when saving downstream computation is needed `require` can be set to `"ref AND dut"` to keep those events out of downstream stages, though they cannot be used to compare other trigger conditions.

## Algorithm

### Built-in Constants

| Constant | Value | Unit | Location and Meaning | Key in File |
| --- | --- | --- | --- | --- |
| `PAIR_ENERGY_EV` | Si `3.6`, SiC `7.83`, Diamond `13.1` | $\text{eV}$ | `ionization.py`, $\varepsilon$ in Eq. (1) | none |
| `FANO_FACTOR` | Si `0.115`, SiC `0.128`, Diamond `0.382` | dimensionless | `ionization.py`, $F$ in Eq. (2) | none (the switch `deposit.fano` is a stage setting) |
| `PAIRS_PER_UM` | Si `80.0`, SiC `55.0` | $\mu\text{m}^{-1}$ | `mip_track.py`, $n_{\text{MIP}}$ in Eq. (4) | none |
| `LANDAU_WIDTH_MEV_PER_UM` | Si `1.78e-5`, SiC `2.46e-5` | $\text{MeV}/\mu\text{m}$ | `mip_track.py`, $w$ in Eq. (5) | none |
| `GENERATED_LIMIT` | `10_000_000` | events | `generation.py`, maximum number of generated events when running by recorded count | none (stage setting `deposit.generated_limit`) |
| `EMISSION_BLOCK_DECAYS` | `1_000_000` | decays | number of decays per block actually sent into Geant4 (those falling within emitted directions) for source emission distributions | none |
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

`simulate_deposits(devices, source, g4setup, events, g4_seed, windows, require, coincidence_window_ns, fano, generated, generated_limit, picture, drawn, observers=None, primaries=None)` executes in the following order. `devices` is an ordered dictionary mapping slot names to devices; `windows` maps each slot name to `(lower, upper)` ($\text{MeV}$, with `None` disabling checking on that side); `require` is the slot logical expression string; `coincidence_window_ns` is the timing window ($\text{ns}$, `None` for no timing cut); `observers` and `primaries` are entry points for experiment scripts (see "Interface → Entry Points for Experiment Scripts"). `source` is the source component named by the setup's `source` block, together with the overriding keys (read and merged by the stage). When no setup is provided, `DEVICE_ALONE` is used; it supplies geometry only, equivalent to `"along_beam": ["source", {"gap": 17000}, {"slot": "Device"}]`, and the source is then the `source` argument as passed; a setup with only one device names its slot `"Device"` and passes `{"Device": my_d}`. The slot names in the setup and in the `devices` argument must match one-to-one, and any extra or missing slot raises `ValueError` (`the g4setup places <setup slots>, the devices are <given slots>`); the order of slots in the output follows the `devices` argument.

1. **Check source kind**: If `source["kind"]` is not one of `"toy_mip"`, `"beam"`, `"decay_source"`, or `"primaries"`, raise `ValueError` (`no simulation of deposits for a source of kind ...`); likewise raise `ValueError` if `source["kind"] == "primaries"` without providing `primaries`.
2. **Check event counts and recording conditions**:
   - `asked(events, generated, generated_limit)` requires that exactly one of `events` (number of events to record) and `generated` (number of events to generate) be given, raising `ValueError` otherwise; if the given number or `generated_limit` is less than `1`, raise `ValueError` (`the <name> asked for are <number>: at least 1`).
   - Validate the recording-condition parameters, raising `ValueError` on any invalid setting: slot names in `windows` do not match `devices` (`the energy windows are for <windows slots>, the devices are <given slots>`); a slot's lower bound exceeds its upper bound (`slot '<slot>' has edep_min (<lo> MeV) > edep_max (<hi> MeV)`); `require` has a syntax error, names an operand that is not a slot name, or leaves a slot unused (`invalid require expression '<require>'`, `require '<require>' names unknown slot '<operand>'`, or `require '<require>' does not use the slot '<slot>'`); `coincidence_window_ns` is not `None` and not greater than `0` (`coincidence_window_ns must be positive, got <value> ns`).
3. **Toy MIP branch** (`kind == "toy_mip"`): Read `g4setup["maxstep"]` (or `DEVICE_ALONE["maxstep"] = 2` when `g4setup` is `None`) and call `mip_deposits(devices, source, g4setup, ...)`; see the next section. This branch runs in Python, drawing random numbers from the stream `stream("toy_mip")`.
4. **Geant4 branch** (`kind` is `"beam"`, `"decay_source"`, or `"primaries"`):
   1. Import `geant4.interaction`. If `g4ppyy` is missing, raise `MissingDependency` (`Geant4's Python bindings, g4ppyy, are not installed in this Python`).
   2. `g4_configuration` builds the run configuration: if `par_in`, `par_out`, or `par_angle` appears in the source or in its `particles`, raise `ValueError` (source placement belongs to the setup); take a deep copy of `g4setup` (or `DEVICE_ALONE` if `None`) and extract `angle` from its `"source"` block (default `0`); the configuration takes the keys of the source as passed, with `name`, `kind`, and `description` removed; with the source at the world origin pointing downstream along $+z$, set `par_in = [0, 0, 0]`, `par_out` to the point on the axis at the $z$ of the front face of the first slot, `[0, 0, z_i]`, and `par_angle = source.get("angle", 0)`. When `particles` is present, each item inherits `par_randx`, `par_randy`, `par_type`, and `par_energy` from the configuration, overrides them with its own keys, and adds `offset` (default `[0, 0, 0]` $\mu\text{m}$) to both the emission point and the aiming point. Finally write `recorded_events = events`, `total_events = generated` (or `generated_limit` when running by recorded count), `windows`, `require`, and `coincidence_window_ns`.
   3. `tilted` rotates the source by the incidence angle: unchanged when `par_angle` is `0`. If `primaries` is given while the setup has nonzero `par_angle`, raise `ValueError` (`a setup with source.angle takes no primaries function`); if a multi-slot setup has nonzero `par_angle`, raise `ValueError` (`a multi-slot g4setup tilts no source`). Otherwise this applies only to single-slot setups: write $\mathbf{r}_{\text{in}} = (x_0, y_0, z_0)$ and $\mathbf{r}_{\text{out}} = (x_1, y_1, z_1)$; if $z_f \le z_0 \le z_f + l_z + t$ or $z_1 = z_0$, raise `ValueError` (the source line does not enter the device through a face). Take the rotation axis parallel to the $y$ axis passing through the single-slot device front-surface center $(x_p, P_y, z_f) = (P_x, P_y, P_z)$, and transform `par_in` and `par_out` in both the top-level configuration and each entry of `particles` by
      $$x' = (x - x_p)\cos\vartheta + (z - z_f)\sin\vartheta + x_p, \qquad z' = -(x - x_p)\sin\vartheta + (z - z_f)\cos\vartheta + z_f$$
      where $\vartheta$ is `par_angle` (degrees). For $\vartheta > 0$, the upstream source rotates toward the $-x$ side so particles travel with a $+x$ component toward the device front-surface center. $y$, `par_randx`, and `par_randy` are unchanged, and slots and objects in the setup do not move. For collimated sources, `source.angle` keeps the same meaning: the source together with its collimator rotates as a whole about the single slot's front-surface center $(x_p, P_y, z_f)$, and emitted particle positions (on the exit plane $(x, y, 0)$) and directions ($(dx, dy, dz)$) rotate by the same transformation.
   4. Build the geometry (`GeneralDetectorConstruction`; or `GDMLDetectorConstruction` when `geant4_model == "gdml_import"`, where the geometry is given by GDML rather than `along_beam`). First validate `along_beam`, `materials`, and `objects` (raising `ValueError` on any error): the first item is not `"source"` (`the first item of along_beam must be 'source'`); a `gap` is negative (`gap must be non-negative`); an object name is not in `objects` (`object '<object>' is not in objects`); the same object or slot appears twice (`duplicate '<name>' in along_beam`); `facing` is neither `"upstream"` nor `"downstream"` (`slot '<slot>' has facing <value>: expected 'upstream' or 'downstream'`); `rotation_z` is not `0`, `90`, `180`, or `270`; side-by-side items overlap transversely (`side-by-side items overlap`); the slot names do not match `devices` (`the g4setup places <setup slots>, the devices are <given slots>`); a `materials` entry conflicts with a NIST material name, names an element unrecognized by Geant4, or has non-positive density or share; or an `objects` entry has `shape` other than `"box"` or `"tube"`, misses a required dimension key, has a non-positive dimension, has `hole` not less than the box transverse half-sizes, has `inner_radius` not less than `outer_radius`, or names a `material` that is neither in `materials` nor a NIST material. The world is a cube of material `world` centered at the midpoint $(0, 0, L_{\text{col}}/2)$ of the `along_beam` line, with half-side length given by `world_half_side`: let $\rho = \max\bigl(L_{\text{col}}/2,\ \max_{\text{item}}(|o_x| + w_x/2,\ |o_y| + w_y/2),\ R\bigr)$, where $L_{\text{col}} = \sum_j d_j$ is the total length of the line, $w_x, w_y$ are the full transverse dimensions of each item (`size[0]`, `size[1]` for `"box"`, $2 \cdot \texttt{outer\_radius}$ for `"tube"`, or after rotation for a slot), $o_x, o_y$ are its `offset`, and $R$ is `par_radius`; take `25000` when $\rho \le 25000\ \mu\text{m}$, and $2\rho$ otherwise. Starting from `"source"` ($z = 0$; at the exit plane center when the source carries a `collimator`, without placing the collimator as an object in `along_beam` and measuring all `gap`s from the exit plane), compute the front-face position $z_i$ of each item via Eq. (17): for each slot, build an active-layer box logical volume ($l_x \times l_y \times l_z$) named after the slot with material taken from that slot device's `material` (only `"Si"`, `"SiC"`, or `"Diamond"`), and place it according to Eqs. (17)–(18). The thicknesses and materials of a device's layers are intrinsic properties written in the device file, and Geant4 uses that same geometry (see [Architecture Overview](../architecture.md#components)); the reference device's substrate lies in the beam path, and multiple scattering in it determines how many particles reach downstream devices. The device geometry is layered along depth, with layers outside the active layer (substrate, etc.) described in [Detector Components](../components/device.md); Geant4 builds all layers according to the device geometry, creating a separate logical volume for each layer outside the active layer whose energy deposition is not recorded, recording deposition only in the active layer. Each custom material in `materials` is built as a `G4Material` by converting atomic-count shares to mass fractions via Eq. (25); surrounding objects referenced in `along_beam` are then placed (laterally centered at `offset`, centered in $z$ at $z_i + d_i/2$, where $d_i$ is `size[2]` for `"box"` or `length` for `"tube"`).
   5. Configure the random engine, physics list, and user actions. When `observers` is provided, verify that every name in `watched` on observers with a `step` method belongs to an object or slot in the setup (raising `ValueError` otherwise). When `primaries` is provided (`kind == "primaries"`), each event calls `primaries(event, generator)` with random stream `stream(f"primaries/{event}")` as `generator` to obtain the primary particle list, and the returned particles are launched as-is without applying `source.angle` (raising `ValueError` on any invalid return value other than an empty list); otherwise emission follows the source kind: when the source contains `nuclides` and `collimator`, load or generate on demand the source's emission distribution as described in "Launching from Emission Distributions" below, and use a primary generator action that launches all emitted particles of each decay from the exit plane $z = 0$ per event; when the source contains `nuclides` without `collimator`, use `NuclideGeneratorAction` and `DecayStackingAction` to simulate each decay isotropically into full $4\pi$ space; otherwise (`beam` or `decay_source` without `nuclides`) use `GeneralPrimaryGeneratorAction`. For each event and each particle, the latter draws $\delta_x \sim U(-\texttt{par\_randx}, \texttt{par\_randx})$ and $\delta_y \sim U(-\texttt{par\_randy}, \texttt{par\_randy})$ from `stream("source")` and emits from $\mathbf{r}_{\text{in}}$ in direction $\mathbf{d} = \mathbf{r}_{\text{out}} - \mathbf{r}_{\text{in}} + (\delta_x, \delta_y, 0)$; when `par_type` is a list, it also draws an index with equal probability. If `par_type` and `par_energy` are lists of different lengths, raise `ValueError`. Before launching primary particles into Geant4 transport, observers implementing `primary(event, particles)` are called sequentially in the order of `observers`, each receiving the particle list left by the previous one (only dropping is allowed, with no additions or modifications, otherwise raising `ValueError`), and the total number of particles dropped across all observers is accumulated into `dropped_primaries`. During transport, every step whose pre-step point lies inside an object or slot listed in an observer's `watched` attribute triggers `step(event, volume, e, x, y, z, t)`.
   6. Execute `/run/initialize`; if `picture` is given and `drawn > 0`, enable off-screen visualization (see "Plots"); run `BeamOn(total_events)`.
   7. Event recording: at the end of an event, compute total deposited energy $E_s$ in the active layer for each slot $s$ according to Eq. (19): if $E_s > 0$ and `windows[s]` is satisfied (unprovided bounds are not checked), mark the slot as hit ($h_s = 1$) and take the global time of the earliest deposit step in that slot as $t_s$; otherwise mark it as not hit ($h_s = 0$). When no timing window is set (`coincidence_window_ns` is `None`), evaluate `require` directly on $\{h_s\}$; otherwise, try each hit slot's $t_s$ as the left endpoint $t_0$ in turn, count slots whose hit time falls within $[t_0, t_0 + W]$ as hit per Eq. (20), and evaluate `require` to check whether the recording condition holds for some $t_0$. Any observer implementing `event(event, energies, first_times)` is then called; if any returns `False`, the event is vetoed (not recorded, incrementing `vetoed_events`). A recorded event keeps the deposit steps of all slots. When running by recorded count, call `AbortRun` once the recorded count reaches `recorded_events`, and set `generated_events` to the total number of completed generated events (for collimated sources, the number of decays launched from the emission distribution). When running by generated count, `generated_events = total_events`.
   8. `deposits()`: if running by recorded count and fewer than `recorded_events` events were recorded, raise `RuntimeError` (`... events asked for were recorded when the limit of ... generated events was reached ...`). Otherwise convert step positions from Geant4 world coordinates to the device coordinates of their respective devices via the inverse of Eq. (18) for each slot; call `deposits_of_steps(<slot name>, ...)` for each device to drop steps with $E_k \le 0$, concatenate the deposit steps across devices in the order of `devices` for each event, and drop events with no remaining steps. Event IDs are Geant4's `eventID`.
   9. Regardless of whether an error occurred, call `close()` at the end to release Geant4 objects.
5. **Write emission probability and observer bookkeeping**: when the source contains `nuclides` and `collimator`, write the emission probability $\varepsilon$ (Eq. (24) for a single block; `sum(emitted) / sum(decays)` across the blocks used when a job spans multiple blocks) to `emission_probability`, and `1.0` otherwise; write `dropped_primaries` and `vetoed_events` to `Deposits` (both `0` when no observers are given).
6. **Ionization**: Call `ionized_pairs(event, material, fano)` for each event, taking each step's `material` from the `material` of its slot's device. Raise `ValueError` if the material is not in `PAIR_ENERGY_EV`, or if `fano=True` and the material is not in `FANO_FACTOR`. Each event draws from its own stream `stream(f"ionization/{event.event}")`, so an event's pair counts are independent of which events were recorded before it.

`write_simulated_deposits` takes the same parameters as `simulate_deposits` (`devices`, `source`, `g4setup`, `events`, `g4_seed`, `windows`, `require`, `coincidence_window_ns`, `observers`, `primaries`, etc.), calls `simulate_deposits`, writes the file via `write_deposits`, and returns the number of recorded events.

In GDML import mode, the device logical volume `"Device"` is built according to `material` for `"Si"` (`G4_Si`) and `"SiC"` (equal atomic fractions of Si and C, $3.21\ \text{g/cm}^3$).

### Generation of Emission Distributions

Nuclide decay sources carrying `collimator` generate and cache emission distribution assets block by block; sources without `collimator` and `beam` sources do not generate emission distributions:

1. **Node identity and storage path**: emission distributions are stored at `work/<source_name>/emission/<node_id>/emission.h5` and `node.json`. The node ID is computed from all keys of the source component, the world material `world`, the random seed `seed`, and the block index `block` (`0, 1, ...`); different world materials (such as vacuum vs. air) map to different nodes.
2. **Collimator geometry and emission restriction**: Geant4 builds the collimator over $z \in [-L, 0]$ (outer cross-section side `outer_side`, material `material`, centered cylindrical bore of radius `radius`) with the exit plane center at $(0, 0, 0)$. Numerical integration over the entrance disk ($z = -L$, radius `par_radius`) and directions yields `generated_fraction` (Eq. (21)) for the allowed set $\{\ell(\mathbf{r}_0, \hat{\mathbf{d}}) \le R_{\text{CSDA}}(E_{\max})\}$ (where $E_{\max}$ is the largest $\beta$-spectrum endpoint energy among the nuclides in the source), and decays emit only within that allowed set.
3. **Range rejection and exit-plane scoring**: electrons inside the collimator material satisfying Eq. (23) are immediately terminated and deposit their energy locally, while produced bremsstrahlung photons are unaffected and transported normally. Every non-neutrino particle crossing the exit plane $z = 0$ (spanning the entire world) has its species (PDG code), $(x, y)$, $(dx, dy, dz)$, kinetic energy `ekin`, and global time `t` recorded and is then terminated. The number of decays actually sent into Geant4 per block (those falling within emitted directions) is fixed at `EMISSION_BLOCK_DECAYS = 1_000_000`, recording the corresponding full-space decay count `decays = EMISSION_BLOCK_DECAYS / generated_fraction` as attribute `decays` and decays crossing the exit plane as attribute `emitted`.
4. **Source self-validation on block 0**: when generating `block = 0`, a separate control simulation using only the source itself relaxes the emission direction restriction to the entire forward hemisphere ($\hat{\mathbf{d}}\cdot\hat{\mathbf{z}} > 0$, with range rejection active as usual), compares the two emission probabilities and the emitted electron kinetic-energy spectra, and writes the decay counts on both sides, emitted counts on both sides, and the emission-probability ratio with its statistical error to `emission_check` in `node.json`. This check uses only the source itself and involves no experiment.

### Launching from Emission Distributions

When a downstream experiment's `deposit` run uses a radioactive source with `collimator`, it does not re-simulate decays and scattering inside the collimator, but reads `emission.h5` block by block:

1. **Decay-by-decay replay**: each entry in `emission.h5` is one decay that crossed the exit plane; each Geant4 event in the downstream run corresponds to one such decay and launches all `count` recorded particles simultaneously from $(x, y, 0)$ along $(dx, dy, dz)$ with kinetic energy `ekin` and start time `t`; once a block is exhausted, the next block (`block = 0, 1, ...`) is used.
2. **Event counts and emission probability**: `generated_events` in `deposit.h5` counts the decays launched from the emission distribution, and attribute `emission_probability` stores $\varepsilon = \texttt{emitted} / \texttt{decays}$ (Eq. (24); when a job uses multiple blocks, `sum(emitted) / sum(decays)` across the blocks used), so `recorded_events / generated_events * emission_probability` gives the number of recorded events per decay. The `generated_fraction` attribute belongs solely to `emission.h5`.
3. **Correlation across experiments and scan points**: different experiments and different scan points with the same source and seed share the exact same batch of emitted particles. When comparing them, statistical fluctuations from the upstream collimator emission cancel out, so those results are not independent.
4. **Sources without collimators and beam sources**: radioactive sources without `collimator`, `beam` sources, and `primaries` sources do not produce emission distributions; every event emits directly, and `emission_probability` in `deposit.h5` is `1.0`.

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
- In step 5, events are selected for recording according to Eqs. (19)–(20) using per-slot energy windows `windows`, `require`, and `coincidence_window_ns` (all hit slots have time `0.0 s`); segments of all slots are kept and concatenated end-to-end in the order of `devices`.

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

- `simulate_deposits.py`: stage entry points `simulate_deposits` and `write_simulated_deposits`, default setup `DEVICE_ALONE`, configuration builder `g4_configuration`, incidence-angle rotation `tilted`, world sizing `world_half_side`, emission probability `emission_probability` (plus block-by-block generation and reading of emission distribution assets), and the built-in observers `WatchedEnergy` and `PrimaryStart` for experiment scripts.
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
- `Deposits`: deposits for a job. `generated_events` (total number of generated events launched by the source or emission distribution), `windows` (dictionary mapping slot names to `(edep_min, edep_max)`, $\text{MeV}$, either bound may be `None`), `require` (slot logical expression string), `coincidence_window_ns` (timing window, $\text{ns}$, may be `None`), `events` (list of `EventDeposits`), `emission_probability` (default `1.0`), `dropped_primaries` (total number of primary particles dropped across all observers' `primary` methods, `0` without observers), `vetoed_events` (number of events vetoed by observers' `event` method, `0` without observers).
- `LaserInjection`: `track_position` (`[x, y, z, t]` per group, $\mu\text{m}$ and $\text{s}$), `ionized_pairs` (pairs per group), `time_FWHM` (temporal broadening per group, $\text{s}$), as well as `temporal_FWHM`, `timePulse`, and other attributes used for current convolution.

## Interface

Users can configure the keys in device files, setup scripts, radioactive source and beam files, and laser files listed in the tables below; all other parameters on this page are hard-coded. Event counts, energy window, `deposit.fano`, and plotted event count `deposit.plots` are settings in the `deposit` section; see the [energy deposition stage](../stages/deposit.md).

### Keys Read from Device Files

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `l_x`, `l_y`, `l_z` | none (required) | $\mu\text{m}$ | Active-layer dimensions of the device; see [device model](device.md) |
| `material` | none (required) | none | Only `"Si"`, `"SiC"`, or `"Diamond"` (the three materials with ionization energy and Fano factor); determines Geant4 material, ionization energy, and Fano factor; toy MIP supports only `"Si"` and `"SiC"` |
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
| `source` | `{"name": "decay/Sr90", "angle": 0}` | none; degrees | The source the setup uses: `name` is the source component name (see [Energy-deposition components](../components/deposit.md)); `angle` is the incidence angle (default `0`), used only for single-slot setups to rotate the source around the device front-surface center per step 4.3 of "Branches of `simulate_deposits`" (for collimated sources, the source together with its collimator rotates as a whole, and emitted particle positions and directions rotate accordingly); beam emission direction is $+z$; keys other than `name` and `angle` override same-named keys of the source component |
| `materials` | `{}` | $\text{g/cm}^3$ for density | Optional; custom materials dictionary mapping material name to `{"density": <g/cm3>, "elements": {<element symbol>: <atomic share>, ...}}`; used only for `material` in `objects`, as are Geant4 NIST material names starting with `"G4_"` |
| `objects` | `{}` | $\mu\text{m}$ | Required for Geant4 sources; surrounding objects dictionary mapping object name to shape (`"box"` or `"tube"`), dimensions, material, and optional `colour` without position, placed in `along_beam` |
| `along_beam` | `["source", {"gap": 17000}, {"slot": "Device"}]` | none | Required (except for `gdml_import`); a line starting from `"source"` and pointing downstream along $+z$, placing device slots and surrounding objects per Eqs. (17)–(18), see the table below |

In Geant4 world coordinates, the origin $(0, 0, 0)$ sits on the source (at the center of the collimator exit plane when carrying a collimator, with the collimator body on the $z < 0$ side and all `gap`s in the setup measured from the collimator exit plane) and $+z$ points downstream along the beam; the front-surface center $\mathbf{P}$ and the $z$-intervals occupied by the active layer and layers outside the active layer (see [Detector Components](../components/device.md)) of each slot are determined by its position in `along_beam` and its `facing` via Eqs. (17)–(18).

#### Items of `along_beam`

`along_beam` is a list starting from `"source"` and ordered along $+z$, with item kinds and keys listed below. The slot name serves as both the active-layer Geant4 logical volume name (each layer outside the active layer is built as a separate logical volume whose deposition is not recorded) and the detector name in the deposit file; it may use only characters in `[A-Za-z0-9_-]` and must not collide with any name in `objects` or any configuration key of the [energy deposition stage](../stages/deposit.md) (slot names appear in addresses such as `deposit.<slot>.<key>`); for a setup with only one device, the slot name is `"Device"`. Which device goes into each slot is not specified by the setup, but passed via the caller's `devices` argument, whose slot names must match the setup's slots one-to-one (see "Branches of `simulate_deposits`").

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
| `"source"` | none (string) | none (required first item) | none | Source; must be the first item of `along_beam`, has thickness `0`, and carries the world coordinate origin (at the center of the collimator exit plane when carrying a collimator, from which all `gap`s in the setup are measured) |
| `{"gap": d}` | `gap` | none | $\mu\text{m}$ | Gap of length $d \ge 0$ along $z$; adjacent items without a `gap` between them are flush |
| `"<object name>"` or `{"object": "<object name>", ...}` | `object`, `offset` | `offset` defaults to `[0, 0]` | $\mu\text{m}$ for `offset` | An object from `objects`, occupying its thickness along $z$ (`size[2]` for `"box"`, `length` for `"tube"`) and laterally centered at `offset`; shorthand `"<object name>"` equals `offset = [0, 0]` |
| `{"slot": "<slot name>", ...}` | `slot`, `facing`, `offset`, `rotation_z`, `colour` | `facing` defaults to `"upstream"`, `offset` to `[0, 0]`, `rotation_z` to `0`, `colour` to `[1, 0.1, 0.8]` | $\mu\text{m}$ for `offset`, degrees for `rotation_z` | A device occupying total thickness $l_z + t$ of all layers in its geometry along $z$; `facing` is `"upstream"` (front surface facing the source) or `"downstream"` (flipped $180^\circ$ about the $y$ axis, front surface facing downstream), and `rotation_z` is restricted to `0`, `90`, `180`, `270`, placed per Eqs. (17)–(18); `colour` is the visualization RGB color (`0` to `1`) |
| `[item, item, ...]` | items in list | none | none | Side-by-side items (objects or slots only) whose front faces align at the same $z$, occupying the thickness of the thickest item along $z$ and staggered laterally via each item's `offset` |

If the first item of `along_beam` is not `"source"`, if a `gap` is negative, if an object name is absent from `objects`, if the same object or slot appears twice, if `facing` is neither `"upstream"` nor `"downstream"`, if `rotation_z` is not in `{0, 90, 180, 270}`, if side-by-side items overlap transversely, or if the slot names do not match the device table, `ValueError` is raised.

#### Keys for `materials` and `objects`

Below is a `G4SETUP` example containing a custom material `SiO2`, a box aluminum foil `Al`, a board `pcb1` with a circular through-hole, and a tube `pipe`:

```python
G4SETUP = {
    "world": "G4_Galactic",
    "maxstep": 2,
    "materials": {
        "SiO2": {"density": 2.2, "elements": {"Si": 1, "O": 2}},
    },
    "objects": {
        "Al":   {"shape": "box", "size": [5000, 5000, 10], "material": "G4_Al"},
        "pcb1": {"shape": "box", "size": [20000, 20000, 1500], "hole": 500, "material": "SiO2"},
        "pipe": {"shape": "tube", "inner_radius": 10000, "outer_radius": 10500, "length": 200000, "material": "G4_Al"},
    },
    "along_beam": [...],
}
```

`materials` maps material names to `{"density": <g/cm3>, "elements": {<element symbol>: <atomic share>, ...}}` (unlimited number of elements), converting atomic-count shares to mass fractions using atomic weights:

$$m_i = \frac{n_i A_i}{\sum_j n_j A_j} \tag{25}$$

where:

- $n_i$: atomic-count share of element $i$ (dimensionless, value in the `elements` dictionary);
- $A_i$: atomic weight of element $i$ (supplied by Geant4 from the element symbol);
- $m_i$: mass fraction of element $i$ (dimensionless).

`material` in `objects` can use a name defined in `materials` or directly a Geant4 NIST material name (starting with `"G4_"`); these two kinds of names are used only for `objects`, while device `material` takes only `"Si"`, `"SiC"`, or `"Diamond"`. `objects` maps object names to shape, dimensions, material, and optional `colour`; objects do not specify position, which is given by `along_beam`. Along $z$, `"box"` occupies thickness `size[2]` and `"tube"` occupies thickness `length`.

| Key | Parent Dictionary / Applicable Shape | Default | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `density` | `materials.<material name>` | none (required) | $\text{g/cm}^3$ | Material density (must be positive) |
| `elements` | `materials.<material name>` | none (required) | none | Dictionary mapping element symbols to atomic-count shares `{<symbol>: <share>, ...}` (unlimited elements; shares must be positive) |
| `shape` | `objects.<object name>` | none (required) | none | `"box"` (rectangular box) or `"tube"` (cylinder along the $z$ axis) |
| `material` | `objects.<object name>` | none (required) | none | Material name, taken from `materials` or a Geant4 NIST material name starting with `"G4_"` |
| `size` | `objects.<object name>` (`"box"`) | none (required for `"box"`) | $\mu\text{m}$ | Full box dimensions `[x, y, z]` along $x$, $y$, and $z$ (thickness along $z$ is `size[2]`) |
| `hole` | `objects.<object name>` (`"box"`) | none (optional) | $\mu\text{m}$ | Radius of a centered circular through-hole along $z$ (must be $> 0$ and less than the box transverse half-sizes $\min(\texttt{size[0]}, \texttt{size[1]})/2$) |
| `outer_radius` | `objects.<object name>` (`"tube"`) | none (required for `"tube"`) | $\mu\text{m}$ | Outer radius of the cylinder (must be positive) |
| `length` | `objects.<object name>` (`"tube"`) | none (required for `"tube"`) | $\mu\text{m}$ | Length of the cylinder along $z$ (thickness along $z$ is `length`; must be positive) |
| `inner_radius` | `objects.<object name>` (`"tube"`) | `0` (optional) | $\mu\text{m}$ | Inner radius of the cylinder (default `0` for a solid cylinder; $> 0$ for a tube or ring; must satisfy $0 \le \texttt{inner\_radius} < \texttt{outer\_radius}$) |
| `colour` | `objects.<object name>` | none (optional) | none | Visualization RGB color `[r, g, b]` |

`ValueError` is raised on invalid material or object definitions:

- a name in `materials` conflicts with a NIST material name (`material '<name>' conflicts with a NIST material name`);
- an element symbol is not recognized by Geant4 (`unknown Geant4 element '<symbol>' in material '<name>'`);
- density or an element share is not positive (`density of material '<name>' must be positive`, `element share of '<symbol>' in material '<name>' must be positive`);
- `shape` is neither `"box"` nor `"tube"` (`object '<name>' has unknown shape '<shape>': expected 'box' or 'tube'`);
- a required dimension key is missing or a dimension is not positive (`object '<name>' is missing required key '<key>'`, `dimensions of object '<name>' must be positive`);
- `hole` is not less than the box transverse half-sizes (`hole radius (<hole> um) of object '<name>' must be less than half of x and y sizes`);
- `inner_radius` is not less than `outer_radius` (`inner_radius (<r_in> um) of object '<name>' must be less than outer_radius (<r_out> um)`);
- `material` is neither in `materials` nor a NIST material name (`unknown material '<material>' for object '<name>'`).

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
| `pcb_readout_gdml` | `src/raser_bench/signal/components/deposit/` | PCB readout board imported from `pcb_readout.gdml` (see [signal](../bench/signal.md)) |
| `time_resolution` | `src/raser_bench/timeres/components/deposit/` | Aluminum foil, reference silicon device, and two apertured PCB boards arranged along the beam (see [time resolution](../bench/timeres.md)) |
| `telescope` | `src/raser_bench/telescope/components/deposit/` | 8 slots arranged along the beam in vacuum, defaulting to 3 + 2 + 3 (see [beam telescope](../bench/telescope.md)) |

### Radioactive Sources and Beams

#### Common Keys

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `name` | none (optional) | none | Source name |
| `kind` | none (required) | none | `"beam"`, `"decay_source"`, `"toy_mip"`, or `"primaries"` (`{"kind": "primaries"}` is sufficient when a `primaries` callback replaces source emission) |
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
| `par_radius` | `0` | $\mu\text{m}$ | Radius of the disk containing the nuclides, perpendicular to the emission axis; with `collimator`, the disk lies on the collimator entrance face centered on the bore axis |
| `collimator` | none (optional) | $\mu\text{m}$ for `length`, `radius`, `outer_side` | Collimator dictionary `{"material": <Geant4 NIST material name>, "length": <µm>, "radius": <bore radius µm>, "outer_side": <outer side length µm>}`; exit plane center at world origin $z = 0$, collimator body on $z < 0$ side; when omitted, the source emits isotropically into full $4\pi$ space |
| `activity` | none (optional) | $\text{Bq}$ | Decays per second of each nuclide; $^{90}\text{Sr}$ and $^{90}\text{Y}$ are in secular equilibrium, so each nuclide decays at this activity |

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
| `decay/Sr90` | `decay_source` | Nuclides Sr-90 and Y-90 with equal probability, `par_radius = 0` $\mu\text{m}$, copper collimator `collimator = {"material": "G4_Cu", "length": 3000, "radius": 500, "outer_side": 8000}` (typical copper collimator dimensions; the actual source used should match the physical object) |
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

### `emission.h5` File Format

Stored at `work/<source_name>/emission/<node_id>/emission.h5` (`node.json` in the same directory additionally records `emission_check` for block `0`: decay counts on both sides, emitted counts on both sides, and the emission-probability ratio with its statistical error between the control and filtered runs).

#### File Attributes

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `decays` | `float` | decays | Corresponding full-space decay count of this block (`EMISSION_BLOCK_DECAYS / generated_fraction`) |
| `generated_fraction` | `float` | none | Fraction $f$ of full $4\pi$ space covered by emitted directions computed via Eq. (21) |
| `emitted` | `int` | decays | Number of decays with at least one non-neutrino particle crossing the exit plane $z = 0$ |
| `block` | `int` | none | Block index of the emission distribution (`0, 1, ...`) |
| `seed` | `int` | none | Random seed used to generate this emission block |

#### Datasets

| Dataset | Shape and Type | Unit | Meaning |
| --- | --- | --- | --- |
| `event` | `(emitted,)`, `int` | none | Event ID of each decay crossing the exit plane |
| `count` | `(emitted,)`, `int` | particles | Number of non-neutrino particles crossing the exit plane $z = 0$ in that decay |
| `particle` | `(sum(count),)`, `int` | none | Particle PDG code |
| `x`, `y` | `(sum(count),)`, `float` | $\mu\text{m}$ | Transverse position where the particle crosses the exit plane $z = 0$ |
| `dx`, `dy`, `dz` | `(sum(count),)`, `float` | none | Unit direction cosines at the exit plane |
| `ekin` | `(sum(count),)`, `float` | $\text{MeV}$ | Kinetic energy of the particle at the exit plane |
| `t` | `(sum(count),)`, `float` | $\text{s}$ | Global time when the particle reaches the exit plane |

### `deposit.h5` File Format

#### File Attributes

| Attribute | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `generated_events` | `int` | events | Number of events launched from the source or emission distribution (counted by emitted decays for collimated sources) |
| `recorded_events` | `int` | events | Number of events stored in the file |
| `emission_probability` | `float` | none | Emission probability $\varepsilon$ of the source (Eq. (24); `sum(emitted) / sum(decays)` across the blocks used when a job spans multiple blocks); `1.0` for sources without an emission distribution |
| `dropped_primaries` | `int` | particles | Total number of primary particles dropped across all observers' `primary` methods (`0` without observers) |
| `vetoed_events` | `int` | events | Number of events vetoed by observers' `event` method (`0` without observers) |
| `edep_min.<slot>`, `edep_max.<slot>` | `float` | $\text{MeV}$ | Lower and upper bounds of the total deposited energy window in that slot's active layer (slot name `"Device"` for a single device); written only when given |
| `require` | `str` | none | Slot logical expression |
| `coincidence_window_ns` | `float` | $\text{ns}$ | Timing window; written only when given |

The fraction of generated events that are recorded is `recorded_events / generated_events`; the number of recorded events per source decay is `recorded_events / generated_events * emission_probability` (`generated_fraction` belongs solely to the emission distribution file `emission.h5`).

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

### Entry Points for Experiment Scripts

Experiment scripts interact only with RASER's own data (event ID, particle species, position, direction, energy, time, slot or object name, and deposited energy), without access to transport-engine objects or the ability to invoke transport-engine commands; physics lists, production cuts, step limits, and random numbers are not exposed in these entry points. Switching to a different transport engine requires no changes to experiment scripts.

`simulate_deposits` provides optional keyword parameters `observers=None` and `primaries=None` (`write_simulated_deposits` accepts the same keyword parameters and forwards them):

#### `observers`

`observers` is a collection of objects, each of which may implement any subset of the following three methods (unimplemented methods are not called):

- **`primary(event, particles)`**: Called once per event after the event's primary particles are generated; `event` is the event ID and `particles` is a list of `(particle, x, y, z, dx, dy, dz, ekin, t)` tuples (respectively PDG code; world coordinates $x, y, z$ in $\mu\text{m}$; unit direction cosines $dx, dy, dz$; kinetic energy `ekin` in $\text{MeV}$; global time `t` in $\text{s}$). `primary` may only drop particles, never add or modify them: returning `None` launches the particles as generated; returning a list (which may be empty) launches only the remaining particles, and every item in the returned list must be one of the items passed into `particles` (otherwise `ValueError` is raised). When there are multiple observers, they are called sequentially in the order of `observers`, with each receiving the particle list left by the previous one.
- **`step(event, volume, e, x, y, z, t)`**: Called on every step taken inside an object or slot listed in the class attribute `watched`; `volume` is the object or slot name, `e` is the energy deposited in this step ($\text{MeV}$), $(x, y, z)$ is the step position in world coordinates ($\mu\text{m}$), and `t` is the global time of the pre-step point ($\text{s}$); returns nothing. An observer specifies the names to watch via the class attribute `watched = ("pcb1", "ref", ...)`.
- **`event(event, energies, first_times)`**: Called once at the end of each event; `energies` and `first_times` are dictionaries mapping slot names to total active-layer deposited energy ($\text{MeV}$) and earliest deposit time ($\text{s}$). Returning `False` vetoes recording the event (even if it satisfies the recording conditions), while returning `None` or `True` leaves the outcome unchanged.

Whatever an observer records remains on the observer instance itself for the experiment script to retrieve after simulation. Two built-in observers are provided in the library:

| Class Name | Usage and Recorded Data |
| --- | --- |
| `WatchedEnergy(names)` | Records for each recorded event the total deposited energy ($\text{MeV}$) and earliest deposition time ($\text{s}$) in each object or slot listed in `names` |
| `PrimaryStart()` | Records for each recorded event the initial primary-particle launch state `(particle, x, y, z, dx, dy, dz, ekin, t)` |

The total number of particles dropped across all observers' `primary` methods and the number of events vetoed by `event` are recorded in `Deposits` and in the `deposit.h5` attributes `dropped_primaries` and `vetoed_events` (both `0` when no observers are provided); `generated_events` still counts all generated events.

#### `primaries`

`primaries` is a callable `primaries(event, generator) -> list` (with list items in the same format as `particles` in `primary`) that replaces emission from the source component; `generator` is the random stream `stream(f"primaries/{event}")`. The returned particles are launched as-is, and the setup's `source.angle` does not act on them; if a setup has a nonzero `angle` while `primaries` is given, `ValueError` is raised. When `primaries` is given, `source` only needs `{"kind": "primaries"}`. Common use cases include:

- Launching a bunch of lost electrons read from a sample file;
- Launching $\alpha$ particles sampled from a given energy spectrum;
- Launching multiple protons simultaneously in a single event.

#### Validation and Errors

`ValueError` is raised in each of the following cases:

- The list returned by an observer's `primary` method contains an item that was not passed in `particles` (`observer returned a primary that it was not given`);
- `primaries` returns an invalid value other than an empty list (`primaries must return a sequence of 9-tuples`);
- A setup with nonzero `source.angle` is used together with `primaries` (`a setup with source.angle takes no primaries function`);
- A name in an observer's `watched` attribute is not an object or slot in the setup (`watched volume '<name>' is not in setup`).

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
