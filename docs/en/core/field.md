# Device Field (`core/field`)

`src/raser/core/field/` obtains geometry, doping, bias, and irradiation settings from [device definition](device.md), selects the mesh according to the `field` section settings, and obtains band structure, permittivity, recombination lifetimes, and impact ionization coefficients from [material models](model.md). It uses DEVSIM to solve for the electric potential, carrier concentrations, trapping rates, and conductive regions of a device at a given bias voltage and irradiation fluence, then computes the weighting potential of each readout electrode, mutual capacitance per unit strip length, IV/CV/noise curves, and undepleted bulk parameters of 1D devices; it can also import fields from Sentaurus TDR files. Results are written to the field node `field/<node_id>/`, one field node per bias voltage, with the node record stored in `node.json`; [carrier transport](current.md) reads interpolated electric field, doping, trapping rates, conductive flags, weighting potential, and planar avalanche gain through `DevsimField`, and [electronics readout](readout.md) obtains the device equivalent SPICE circuit through `field_circuit` and `device_circuit`. See [../stages/field.md](../stages/field.md) for the command-line entry point.

## Physics

### Poisson and Drift-Diffusion Equations

DEVSIM solves simultaneously for the electric potential and the electron and hole concentrations on the device mesh. Space charge consists of free carriers, net doping, and charged irradiation defects; current consists of drift and diffusion; the continuity equations of the two carrier types are coupled through recombination and impact ionization. The steady-state system solved by the code is:

$$\nabla\cdot\bigl(\varepsilon\,\nabla\psi\bigr) = -q\,\bigl(p - n + N_{\text{net}} + N_t^{+} - N_t^{-}\bigr) \tag{1}$$

$$\nabla\cdot\mathbf{J}_n = q\,(U - G_{\text{ii}}), \qquad \nabla\cdot\mathbf{J}_p = -q\,(U - G_{\text{ii}}) \tag{2}$$

$$U = U_{\text{SRH}} + U_{\text{const}} + U_r + R_{\text{TAT}} \tag{3}$$

where:

- $\psi$: electrostatic potential, $\text{V}$;
- $\varepsilon = \varepsilon_r \varepsilon_0$: permittivity, $\text{F/cm}$ ($\varepsilon_0 = 8.8541878128\times10^{-14}\ \text{F/cm}$, $\varepsilon_r$ taken from `RELATIVE_PERMITTIVITY` in [model.md](model.md): Si `11.9`, SiC `9.76`, Diamond `5.7`);
- $q = 1.602176634\times10^{-19}\ \text{C}$: elementary charge (`ElectronCharge`);
- $n$, $p$: electron and hole concentrations, $\text{cm}^{-3}$;
- $N_{\text{net}} = N_D - N_A$: net doping (`NetDoping = Donors - Acceptors`), $\text{cm}^{-3}$;
- $N_t^{+}$, $N_t^{-}$: concentrations of positively charged donor defects and negatively charged acceptor defects (`TrappedHoles`, `TrappedElectrons`), $\text{cm}^{-3}$, see Eq. (12); zero when no irradiation model is active;
- $\mathbf{J}_n$, $\mathbf{J}_p$: electron and hole current densities, $\text{A/cm}^2$;
- $U$: net recombination rate, $\text{cm}^{-3}\,\text{s}^{-1}$; $U_{\text{const}}$ is the additional recombination rate given by `U_const` in the device file (a number or a DEVSIM expression, default `0`); $U_r$ is the recombination rate from irradiation defects, see Eq. (13); $R_{\text{TAT}}$ is the trap-assisted tunneling term for SiC when the avalanche term is enabled, see Eq. (8);
- $G_{\text{ii}}$: impact ionization generation rate, $\text{cm}^{-3}\,\text{s}^{-1}$, see Eq. (7); zero when the avalanche term is not enabled.

Currents are written on mesh edges using the Scharfetter-Gummel discretization [1]:

$$J_n = \frac{q\,\mu_n V_T}{L}\Bigl[n_1 B(-\Delta) - n_0 B(\Delta)\Bigr], \qquad J_p = -\frac{q\,\mu_p V_T}{L}\Bigl[p_1 B(\Delta) - p_0 B(-\Delta)\Bigr] \tag{4}$$

$$\Delta = \frac{\psi_0 - \psi_1}{V_T}, \qquad B(x) = \frac{x}{e^{x} - 1}, \qquad V_T = \frac{kT}{q} \tag{5}$$

where:

- subscripts $0$, $1$: the two endpoints of a mesh edge; $L$: edge length, $\text{cm}$;
- $\mu_n$, $\mu_p$: electron and hole mobilities, $\text{cm}^2/(\text{V}\cdot\text{s})$;
- $k = 1.380649\times10^{-23}\ \text{J/K}$; $T$: device temperature `temperature`, $\text{K}$.

Recombination takes the Shockley-Read-Hall form [2]:

$$U_{\text{SRH}} = \frac{np - n_i^2}{\tau_p\,(n + n_1) + \tau_n\,(p + p_1)}, \qquad n_1 = p_1 = n_i \tag{6}$$

where $n_i$ is the intrinsic carrier concentration ($\text{cm}^{-3}$, given by `BAND_STRUCTURE` in [model.md](model.md) at temperature $T$), and $\tau_n$, $\tau_p$ are the lifetimes ($\text{s}$).

Code correspondence: `physics_drift_diffusion.CreateSiliconDriftDiffusion` sets up in order `CreatePE` (Eq. 1), `CreateBernoulli` and `CreateElectronCurrent`/`CreateHoleCurrent` (Eqs. 4, 5), `CreateSRH` (Eqs. 3, 6), and `CreateECE`/`CreateHCE` (Eq. 2). `create_parameter.create_parameter` writes constants for DEVSIM region materials `Silicon`, `SiliconCarbide`, `Diamond`, and `gas`. Mobility models are registered by name and selected by name in the device file, with each material having a default model (see [model.md](model.md)); in the DEVSIM solve, each material currently defaults to a constant mobility independent of electric field and doping, taken from region parameters `mu_n`, `mu_p` (Si `1450`/`500`, SiC `1100`/`114`, Diamond `1714`/`2064`, in $\text{cm}^2/(\text{V}\cdot\text{s})$). Lifetimes are taken from `SRH_LIFETIME` (Si `7e-3`/`7e-3` s, SiC `2.5e-6`/`0.5e-6` s, Diamond `5.6e-7`/`2.4e-7` s); the electron lifetime of SiC is taken from [20], and the hole lifetime `0.5e-6` s is confirmed by our group's time-resolved photoluminescence measurements [21].

All electrodes are treated as ohmic contacts (`set_contact_type` is `None` at every call site): at electrode nodes, $n = n_0$, $p = n_i^2/n_0$ (for $N_{\text{net}} > 0$) or $p = p_0$, $n = n_i^2/p_0$ (for $N_{\text{net}} \le 0$), and the potential is $\psi = V_{\text{bias}} + V_T \ln(n_0/n_i)$ or $\psi = V_{\text{bias}} - V_T \ln(p_0/n_i)$, where $n_0 = 10^{-10} + \tfrac12\bigl|N_{\text{net}} + \sqrt{N_{\text{net}}^2 + 4n_i^2}\bigr|$, and $p_0$ has the same expression with $N_{\text{net}}$ negated. The equations and contact conditions are adapted from DEVSIM examples [3].

### Impact Ionization

In high-field regions, carriers gain enough energy over one mean free path to ionize the lattice and create secondary electron-hole pairs. In the DEVSIM solve, the generation rate is given by the currents and impact ionization coefficients of both carrier types:

$$G_{\text{ii}} = \frac{\alpha_n(E)\,|J_n| + \alpha_p(E)\,|J_p|}{q} \tag{7}$$

where $\alpha_n$, $\alpha_p$ are the electron and hole impact ionization coefficients ($\text{cm}^{-1}$), and $E$ is the electric field magnitude on the mesh edge ($\text{V/cm}$). The coefficient formulas are taken from [model.md](model.md): $|E|$ is used in threshold checks, while $|E| + 1\ \text{V/cm}$ is used elsewhere so that $b/E$ stays finite (`EDGE_FIELD`, `EDGE_FIELD_IN_THRESHOLDS`).

Only when `has_avalanche` is true (`enable_gain` is true and `avalanche_model` is non-empty) does `physics_avalanche.CreateImpactGeneration` select the coefficients according to `avalanche_model` and the region material:

- `"NoAvalanche"`: $G_{\text{ii}} = 0$;
- material `Silicon` and name other than `"CustomAvalanche"`: van Overstraeten–de Man coefficients `VAN_OVERSTRAETEN` [4];
- material `SiliconCarbide` and name other than `"CustomAvalanche"` or `"Fine_exponential_models"`: Hatakeyama coefficients `hatakeyama` [5];
- material `SiliconCarbide` and name `"Fine_exponential_models"`: Eq. (9);
- all other combinations (including `"CustomAvalanche"`): coefficients taken from the function arguments `custom_ion_n`, `custom_ion_p`, default `'0'`.

In SiC regions, a trap-assisted tunneling term $R_{\text{TAT}}$ (`CreateFESRH`) is also subtracted from $G_{\text{ii}}$; its field enhancement factor uses the Hurkx form and is held constant above $F_{\text{sat}}$ [6]:

$$R_{\text{TAT}} = \Gamma(|E|)\,U_{\text{const}}, \qquad \Gamma(F) = 2\sqrt{3\pi}\,\frac{F'}{F_\Gamma}\exp\!\Bigl[\Bigl(\frac{F'}{F_\Gamma}\Bigr)^2\Bigr], \quad F' = \min(F, F_{\text{sat}}) \tag{8}$$

where $F_\Gamma = 3.9\times10^4\ \text{V/cm}$, $F_{\text{sat}}$ defaults to `TAT_SATURATION_FIELD` $= 10^5\ \text{V/cm}$ (parameter name `F_sat`, overridable via `parameter` in the device file), $\pi$ is taken as `3.14159`, and $U_{\text{const}}$ is evaluated at the `n1` endpoint node of the edge.

The coefficients of `"Fine_exponential_models"` take the Thornber form [13], with parameters from the measurements of Konstantinov et al. on 4H-SiC [14]:

$$\alpha_n = \frac{qE'}{\epsilon_{in}}\exp\!\Bigl[-\frac{\epsilon_{in}E_R}{(qE'\lambda_n)^2}\Bigr], \qquad \alpha_p = \frac{qE'}{\epsilon_{ip}}\exp\!\Bigl[-\frac{\epsilon_{ip}E_R}{qE'\lambda_p\,(E_R + qE'\lambda_p)}\Bigr] \tag{9}$$

where $E' = E + 1\ \text{V/cm}$; $\epsilon_{in} = 10\ \text{eV}$ and $\epsilon_{ip} = 7\ \text{eV}$ are the effective ionization threshold energies of electrons and holes; $E_R = 3E_p = 0.36\ \text{eV}$, with $E_p = 0.12\ \text{eV}$ the optical phonon energy; $\lambda_n = 2.99\times10^{-7}\ \text{cm}$ and $\lambda_p = 3.25\times10^{-7}\ \text{cm}$ are the mean free paths; energies are converted to J using $1.602176634\times10^{-19}\ \text{J/eV}$, and $\alpha$ is in $\text{cm}^{-1}$. $\alpha_p$ is the Thornber expression with $E_{kT} = 0$; $\alpha_n$ is its high-field limit $qE'\lambda_n \gg E_R$, using only the high-field asymptote for electrons following [14].

When `avalanche_model` is `"Tunnel"`, an additional term $R_{\text{improved}} = 3.11\,|E|^{2.5}\exp(|E|/3\times10^4)$ (`CreateTunnelModel_Zaiyi`) is added to $G_{\text{ii}}$, and in SiC regions $R_{\text{TAT}}$ is redefined as the unsaturated $\Gamma(|E|)\,U_{\text{SRH}}$.

`DevsimField` also provides the steady-state 1D planar multiplication integral used by the `"planar_integral"` algorithm in [current.md](current.md). Integrating along depth $z$ starting from the face $b$ where electrons exit [7]:

$$K(z) = \exp\!\int_b^z (\alpha_n - \alpha_p)\,dz', \qquad I_{\text{bd}} = \int_0^W \alpha_p K\,dz \tag{10}$$

$$G(z) = \frac{K(z)}{1 - I_{\text{bd}}} - 1 \tag{11}$$

where $W$ is the mesh depth ($\text{cm}$), $I_{\text{bd}}$ is the breakdown integral (dimensionless), and $G(z)$ is the number of additional pairs generated per electron-hole pair created at depth $z$. Here the coefficients are supplied by `Material(material, avalanche_model=avalanche_model).cal_coefficient`, which accepts only `"vanOverstraeten"`, `"Okuto"`, and `"Hatakeyama"` (see [model.md](model.md)).

### Irradiation Defects and Trapping Rates

Irradiation introduces deep-level defects into the band gap, and the material carries defects left from its growth. Defects are occupied by electrons according to SRH statistics; charged defects enter the Poisson equation, empty defects trap electrons, filled defects trap holes, and all defects contribute to recombination. For each defect $i$:

$$N_{t,i} = N_{0,i} + g_i\,\Phi, \qquad f_i = \frac{c_{n,i}\,n + c_{p,i}\,p_{1,i}}{c_{n,i}(n + n_{1,i}) + c_{p,i}(p + p_{1,i})} \tag{12}$$

$$U_r = \sum_i \frac{N_{t,i}\,c_{n,i}\,c_{p,i}\,(np - n_i^2)}{c_{n,i}(n + n_{1,i}) + c_{p,i}(p + p_{1,i})} \tag{13}$$

$$\Gamma_n = \sum_i c_{n,i} N_{t,i}\,(1 - f_i), \qquad \Gamma_p = \sum_i c_{p,i} N_{t,i}\,f_i \tag{14}$$

$$n_{1,i} = N_c \exp\!\Bigl(-\frac{E_g/2 - E_{t,i}}{kT}\Bigr), \qquad p_{1,i} = N_v \exp\!\Bigl(-\frac{E_{t,i} + E_g/2}{kT}\Bigr), \qquad c_{n,i} = v_{\text{th}}\sigma_{n,i},\ c_{p,i} = v_{\text{th}}\sigma_{p,i} \tag{15}$$

where:

- $\Phi$: irradiation fluence, $\text{cm}^{-2}$; $g_i$: defect introduction rate (`g_int`), $\text{cm}^{-1}$; $N_{0,i}$: background concentration independent of the fluence (`N_t0`, `0` when the defect dictionary does not give it), $\text{cm}^{-3}$; $N_{t,i}$: defect concentration, $\text{cm}^{-3}$;
- $f_i$: fraction of defects occupied by electrons (dimensionless); acceptor defects contribute $N_t^{-} = \sum N_{t,i} f_i$, and donor defects contribute $N_t^{+} = \sum N_{t,i}(1 - f_i)$;
- $E_{t,i}$: defect energy level (`E_t_ev`, referenced to midgap and positive toward the conduction band, $\text{eV}$, multiplied by $1.602176634\times10^{-19}\ \text{J/eV}$ to convert to J); $E_g$: band gap, J; $N_c$, $N_v$: conduction and valence band effective densities of states, $\text{cm}^{-3}$;
- $\sigma_{n,i}$, $\sigma_{p,i}$: electron and hole capture cross sections, $\text{cm}^2$; $v_{\text{th}}$ = `vel_mean` $= 10^7\ \text{cm/s}$;
- $\Gamma_n$, $\Gamma_p$: electron and hole trapping rates (`TrappingRate_n`, `TrappingRate_p`), $\text{s}^{-1}$, saved to disk and supplied to [current.md](current.md) via `DevsimField.get_trap_e` and `get_trap_h`.

`physics_irradiation.CreateIrradiation` selects the defect table according to `irradiation.irradiation_model`; `"CommonDefect"` takes the diamond background-defect table in a `Diamond` region and the SiC table in other regions; all other names take the parameter `custom_defect`, which defaults to an empty table. Irradiation terms are created when an `irradiation` block is present and the electric field is being solved; otherwise trapping rates are `0`. If `"type"` in a defect dictionary is neither `"donor"` nor `"acceptor"`, a `ValueError` is raised. `"Schwandt"` is the Hamburg Penta Trap Model [15], `"XingChen"` is our group's fit to proton-irradiated silicon [16], and `"Perugia"` is the three-level model for p-type FZ silicon [17]:

| Model | Defect | Type | `E_t_ev` [eV] | `g_int` [$\text{cm}^{-1}$] | $\sigma_n$ [$\text{cm}^2$] | $\sigma_p$ [$\text{cm}^2$] |
| --- | --- | --- | --- | --- | --- | --- |
| `"XingChen"` | `E30K` | donor | `0.56-0.1` | `2.0810` | `2.300e-14` | `2.920e-16` |
| | `V3` | acceptor | `0.56-0.458` | `1.6504` | `2.551e-14` | `1.511e-13` |
| | `Ip` | acceptor | `0.56-0.545` | `0.6936` | `4.478e-15` | `6.709e-15` |
| | `H220` | donor | `-0.56+0.48` | `2.6112` | `4.166e-15` | `1.965e-16` |
| | `CiOi` | donor | `-0.56+0.36` | `1.6511` | `3.230e-17` | `2.036e-14` |
| `"Perugia"` | `DA1` | acceptor | `0.56-0.42` | `1.613` | `1e-15` | `1e-14` |
| | `DA2` | acceptor | `0.56-0.46` | `0.9` | `7e-15` | `7e-14` |
| | `DD` | donor | `-0.56+0.36` | `0.9` | `3.23e-13` | `3.23e-14` |
| `"Schwandt"` | `E30K` | donor | `0.56-0.1` | `0.0497` | `2.300e-14` | `2.920e-16` |
| | `V3` | acceptor | `0.56-0.458` | `0.6447` | `2.551e-14` | `1.511e-13` |
| | `Ip` | acceptor | `0.56-0.545` | `0.4335` | `4.478e-15` | `6.709e-15` |
| | `H220` | donor | `-0.56+0.48` | `0.5978` | `4.166e-15` | `1.965e-16` |
| | `CiOi` | donor | `-0.56+0.36` | `0.3780` | `3.230e-17` | `2.036e-14` |
| `"CommonDefect"` (SiC) | `Z12` | acceptor | `1.63-0.67` | `1` | `3e-16` | `2e-12` |
| | `EH67` | donor | `1.63-1.65` | `1` | `2e-17` | `3e-17` |
| `"CommonDefect"` (diamond) | `BoronAcceptor` | acceptor | `-5.47/2+0.37` | `0` | `1.0e-15` | `2.0e-14` |
| | `SubstitutionalNitrogen_P1` | donor | `5.47/2-1.70` | `0` | `2.0e-14` | `1.0e-15` |
| | `VacancyRelated` | acceptor | `-5.47/2+2.00` | `0` | `1.0e-14` | `1.0e-14` |

Background concentrations `N_t0` of the diamond table: boron `2.0e14`, nitrogen `5.0e14`, vacancy `1.0e14` $\text{cm}^{-3}$. The levels are the boron acceptor at $E_v + 0.37\ \text{eV}$ [23] and the substitutional nitrogen donor at $E_c - 1.70\ \text{eV}$ [24]; the vacancy exists in the negative charge state $V^-$ [25] and is treated as an acceptor, with its level at $E_v + 2.00\ \text{eV}$. The background concentrations, the capture cross sections and the vacancy level are starting values to be fitted to IV, TCT and CCE data.

A `Diamond` region follows peiyao, so that undoped diamond can be solved: $n$ and $p$ in Eqs. (12)–(14) are taken as $\max(n, n_f)$ and $\max(p, n_f)$, with $n_f$ = `CARRIER_FLOOR` $= 1\ \text{cm}^{-3}$; every defect adds $N_{t,i} f_i$ to the trapped electrons and $N_{t,i}(1 - f_i)$ to the trapped holes, whether donor or acceptor; the potential of an ohmic contact equals its bias, and an undoped node at a contact holds $n_f$ electrons and holes; the drift-diffusion start is $\max(N_{\text{net}}, n_f)$ and $\max(-N_{\text{net}}, n_f)$. $n_f$ and this way of counting the charge have no source; they are assumptions that let the equations be solved.

### Weighting Potential

By the Shockley-Ramo theorem [8, 9], the weighting potential of a readout electrode is the electrostatic solution with that electrode set to $1$, all other electrodes set to $0$, and space charge removed. Conductive portions of a biased device act as conductors for signal induction: at each bias voltage, the code classifies nodes into conductive and dielectric classes; conductive nodes are equipotential with any electrode they touch, and the rest are dielectric. The equation solved is:

$$\nabla\cdot\bigl(\varepsilon_0\,[1 + 10^{10}\,c_0 c_1]\,\nabla\phi_w\bigr) = 0, \qquad \phi_w\big|_{\text{readout electrode}} = 1, \quad \phi_w\big|_{\text{other electrodes}} = 0 \tag{16}$$

where:

- $\phi_w$: dimensionless weighting potential;
- $c_0$, $c_1$: conductive flags (`Conductive`, `1.0` or `0.0`) at the two endpoint nodes of a mesh edge, read from `Conductive_<V>V.pkl` at that bias voltage, with the criterion in Eq. (19); edges whose endpoints are both conductive have their permittivity multiplied by `CONDUCTOR_PERMITTIVITY` $= 10^{10}$, leaving residual weighting potential variations inside conductors on the order of $10^{-10}$; conductive regions touching no electrode float, and one touching two electrodes is an error (see step 4 of "Weighting Field Solving");
- all dielectric regions use the vacuum permittivity $\varepsilon_0$: `DevsimMesh._regions` replaces every region's material with `"gas"` (`n_i = 1e-9`) and replaces doping with `Acceptors = "0"`, `Donors = "1"`, so the weighting potential does not depend on the material.

Thus, "changing material by resistivity" is implemented in code as follows: low-resistivity or undepleted nodes are merged into the electrodes as conductors, and the rest (including depleted semiconductor) are treated as a dielectric with permittivity $\varepsilon_0$. This step is implemented by `weighting.take_conductors_into_electrodes`.

When a single readout electrode is repeated in a row (`read_out_contact` lists only one entry and `read_ele_num > 1`), the mesh draws only one unit cell. The weighting potential is solved once on a row stitching $s$ unit cells on each side of that cell; the code takes the initial $s$ from the decay estimate of the weighting potential with distance in a fully depleted device:

$$s_0 = \Bigl\lceil \frac{d}{\pi\,p}\,\ln\frac{2}{\delta} \Bigr\rceil \tag{17}$$

where $d$ is `l_z`, $p$ is `p_x` (both in $\mu\text{m}$), and $\delta$ is `weighting_tolerance`; far from the electrode the weighting potential decays as $\exp(-\pi x/d)$, and reflection at the end of the row doubles the value there (comment in `cells_to_fall_off`).

The same solution gives the mutual capacitance per unit strip length from that strip to every other electrode:

$$C_j = \frac{\varepsilon_r\,|Q_j|}{V_1} \tag{18}$$

where $Q_j$ is the contact charge on electrode $j$ ($\text{C/cm}$), $V_1 = 1\ \text{V}$ is the voltage applied to the readout electrode, $\varepsilon_r$ is the relative permittivity of the device material (solved in $\varepsilon_0$ and then multiplied back), and $C_j$ is in $\text{F/cm}$. The left and right strips at distance $k$ from the readout strip are merged into a single electrode `neighbour<k>`.

The resistive charge-sharing layer (a device file with `resistive_layer`) is one continuous conductor and, for the drifting carriers, one planar electrode: only one weighting potential is solved, the solution with the contact `resistive_layer.contact` on which the layer sits set to $1$ and the other electrodes set to $0$, obtained by Eq. (16) on the device's own mesh, which on a 1D mesh is the weighting potential of a slab. The RC nodes do not each get a weighting potential; which RC nodes the total induced current falls on is distributed by [current.md](current.md) according to the lateral position of the carrier.

### Conductive Region Classification

After solving, the code determines whether each node is conductive at that bias voltage from its resistivity and depletion state:

$$\text{conductive} \iff \rho < \rho_0 \ \ \text{or}\ \ \bigl(|N_{\text{net}}| > 0 \ \text{and}\ n_{\text{maj}} > 0.5\,|N_{\text{net}}|\bigr), \qquad \rho = \frac{1}{q(\mu_n n + \mu_p p)} \tag{19}$$

where $\rho$ is the resistivity ($\Omega\cdot\text{cm}$), $\rho_0$ = `RESISTIVITY` $= 10\ \Omega\cdot\text{cm}$, $n_{\text{maj}}$ is the majority-carrier concentration ($n$ at n-type nodes, $N_{\text{net}} > 0$; $p$ at p-type nodes, $N_{\text{net}} < 0$), `UNDEPLETED` $= 0.5$ is the majority-carrier-count threshold per net dopant ion: the second condition asks whether the majority carriers are still there, not depleted, and minority carriers that spill in from elsewhere do not count, entering only through the resistivity of the first condition, and $q$ is taken as `1.602176634e-19` C. Nodes with zero net doping are judged by resistivity alone. Fields solved by DEVSIM use the mobility selected for the region (defaulting to the constant mobility parameters `mu_n`, `mu_p`); fields imported from TCAD use each node's `eMobility`, `hMobility` from the file. This is implemented in `conductive.conductive`, and the classification is written to `Conductive_<V>V.pkl`, used both in Eq. (16) and for the "collected" criterion in [current.md](current.md) (`DevsimField.get_conductive`).

### Device Circuit Parameters

In the electronics netlist, the device is represented as a network of capacitors, resistors, and induced current sources (`DeviceCircuit`). For each readout electrode `<e>`, the depletion-layer capacitance $C_{\text{dep}}$ is connected between `<e>_pad` and node `undepleted` at the back of the depletion layer, with the induced current source in parallel; all readout electrodes share this single `undepleted` node. The undepleted bulk is $R_{\text{und}} \parallel C_{\text{und}}$ connected between `undepleted` and ground. An optional bias resistor $R_{\text{bias}}$ connects `<e>_pad` to ground, and an optional coupling capacitor $C_{\text{c}}$ connects `<e>_pad` to the readout port `<e>_port`.

The junction capacitance $C_{\text{dep}}$ is obtained by `junction_capacitance` in order of preference from: `capacitance_pF` in the device file (measured value), the capacitance solved by the field at that bias voltage (specific capacitance in `<V>V.cv.json` times `area_factor`), and the parallel-plate estimate of `Detector.capacitance` (readout area divided by `depletion_depth`, defaulting to `l_z`); if none of the three is available, a `ValueError` is raised. Field capacitance comes from `<V>V.cv.json` written by the single-point capacitance subtask at that bias (recorded in `solved.capacitance`), which a full solve runs at the target bias; in field nodes where only the IV sweep or the weighting field was solved on its own, the junction capacitance falls back to the parallel-plate estimate.

The undepleted bulk is modeled by Riegler's lumped $R \parallel C$ model [10], using the same set of equations for 1D, 2D, and 3D devices [22]. The field provides the specific resistance $r$ and specific capacitance $c$ (per unit area), which the circuit multiplies by the device area $A$:

$$R_{\text{und}} = \frac{r}{A}, \qquad C_{\text{und}} = c\,A, \qquad c = \frac{\varepsilon}{W_{\text{und}}} \tag{20}$$

$$\text{1D:}\quad r = \sum_{k} w_k\,\bar\rho_k, \quad W_{\text{und}} = \sum_k w_k; \qquad \text{2D, 3D:}\quad r = \frac{1}{S}\sum_{i} \rho_i\,V_i, \quad W_{\text{und}} = \frac{1}{S}\sum_i V_i \tag{20a}$$

where:

- a bulk node must have non-zero net doping, $n_{\text{maj}} > 0.5|N_{\text{net}}|$ (majority carriers as in Eq. (19)), and $\rho \ge 10\ \Omega\cdot\text{cm}$ (heavily doped layers beneath electrodes are excluded);
- 1D: the sum runs over mesh intervals $k$ whose two adjacent nodes both belong to the undepleted bulk; $w_k$ is the interval width (cm), and $\bar\rho_k$ is the average resistivity of the two endpoint nodes ($\Omega\cdot\text{cm}$);
- 2D, 3D: the sum runs over undepleted bulk nodes $i$; $V_i$ is the node volume (DEVSIM's `NodeVolume`, in $\text{cm}^2$ for 2D and $\text{cm}^3$ for 3D), and $\rho_i$ is the node resistivity; $S$ is the mesh span in the electrode plane (lateral width in cm for 2D, lateral area in $\text{cm}^2$ for 3D); $W_{\text{und}}$ is the average thickness of the undepleted layer;
- $r$: $\Omega\cdot\text{cm}^2$; $c$: $\text{F/cm}^2$; $\varepsilon$: region parameter `Permittivity`, $\text{F/cm}$;
- $A$: `area_factor` for 1D, and $l_x l_y$ for 2D and 3D, $\text{cm}^2$.

At full depletion $W_{\text{und}} = 0$, and the `undepleted` node is connected directly to ground. The device file may specify $R_{\text{und}}$ and $C_{\text{und}}$ as the pair `undepleted_resistance_ohm` and `undepleted_capacitance_pF`, which takes precedence over the field.

The lumped model is exact in 1D. In 2D and 3D, the shared node retains only the in-phase part across all electrodes: it is exact for the sum of all electrode signals, approaches exactness for a single electrode when the shaping time is much greater than $\max(\tau_0, 2\tau_r)$, and is inaccurate for signals on neighboring electrodes ($\tau_r = \varepsilon\rho$, $\tau_0 = \tau_r\,l_z/d_0$, where $d_0 = l_z - W_{\text{und}}$ is the depletion depth). When a 2D or 3D device has an undepleted layer, the device-circuit assembly step prints a warning reporting the bias voltage, $d_0$, $\tau_r$, and $\tau_0$, noting that the bias is too low and the lumped undepleted-layer parameters are inaccurate for neighboring electrodes.

In a row of strip electrodes (when `field_circuit` reads `Capacitance_<V>V.json`), two strips separated by $k$ positions are connected by a capacitance $C_k = \tfrac12 C_{\text{neighbour}k}\,L$ for $k \le$ `neighbours_coupled`, where $L$ is the strip length `l_y` (converted to cm); each strip's capacitance to `undepleted` is $C_{\text{total}}L$ (or `capacitance_pF`) minus the sum of its mutual capacitances to all other strips in the row. When building the circuit only for a section of strips near the hit strip (`part_of_row`), the $n$ strips outside the section are at virtual ground, so their corresponding capacitance is lumped into $n$ times the value of a central strip in the row and connected between `undepleted` and ground (`C_undepleted_rest`).

A resistive charge-sharing layer (`resistive_layer`) divides the layer into RC nodes of width equal to the pitch; each RC node is a node connected via a depletion-layer capacitance to `undepleted`, and adjacent RC nodes are connected by layer resistances:

$$C_{\text{node}} = c_A\,w\,l, \qquad R_{\text{row}} = \frac{R_\square}{l}\,w\,\Bigl(1 - \frac{m}{2}\Bigr), \qquad R_{\text{grid}} = R_\square\,\frac{w_\parallel}{w_\perp}\Bigl(1 - \frac{m}{2}\Bigr) \tag{21}$$

where $c_A = C_{\text{dep}}/(w\,l)$ is the depletion-layer capacitance per unit area ($\text{F/m}^2$, with $C_{\text{dep}}$ the junction capacitance of one RC node); $w$, $l$ are the RC node width (`p_x`) and strip length (`l_y`), in $\text{m}$ (`p_x`, `p_y` in a grid); $R_\square$ is the sheet resistance, $\Omega$; $m \in \{0, 1\}$ is the number of RC nodes in the pair lying beneath an electrode (the electrode starts at the RC node edge, half an RC node from the neighboring RC node center); in a grid, $w_\parallel$ and $w_\perp$ are the RC node widths parallel and perpendicular to the resistor direction. RC nodes under an electrode are merged into a single node; when `coupling` is given, the electrode couples capacitively to the layer through a dielectric, the layer remains continuous beneath the electrode, and each RC node connects to the electrode via a capacitance $\varepsilon_0\varepsilon_r w l / t$ (where $t$ is `coupling.thickness`, given in $\mu\text{m}$ in the device file and converted to m in code).

The sheet resistance $R_\square$ is taken from `resistive_layer.sheet_resistance` in the device file; when omitted, it is computed from the Al-implanted 4H-SiC layer model [11]:

$$R_\square = \frac{1}{q\,p\,t\,\mu}, \qquad N = \frac{D}{t}, \quad N_A = N\,a(T_a), \quad N_D = N\,\frac{\langle N_D\rangle}{10^{20}}, \quad \mu = \frac{\langle\mu_H\rangle}{\mu_{\text{drift}}(300\,\text{K}, 10^{20})}\,\mu_{\text{drift}}(T, N) \tag{22}$$

$$a(T_a) = \min\!\Bigl[1,\ \exp\Bigl(b + \frac{s}{k_B T_a}\Bigr)\Bigr] \tag{23}$$

where:

- $D$: implanted dose `implanted`, $\text{cm}^{-2}$; $t$: layer thickness `thickness` ($\mu\text{m}$, converted to cm in code); $N$: implanted concentration, $\text{cm}^{-3}$;
- $a$: fraction activated as acceptors after annealing; $T_a$: annealing temperature `anneal` ($^\circ\text{C}$, converted to K by adding $273.15$); $s$, $b$: slope (eV) and intercept of the linear fit of $\ln(N_A/10^{20})$ against $1/(k_B T_a)$ across the three measurements at $1675$, $1775$, and $1825\ ^\circ\text{C}$ in Tables 1 and 2 of the reference; $k_B = 8.617333262\times10^{-5}\ \text{eV/K}$;
- $\langle N_D\rangle$, $\langle\mu_H\rangle$: averages of the compensating donor concentration and Hall mobility across the three measurements; $\mu_{\text{drift}}$: zero-field hole mobility from `Material("SiC").cal_mobility`, $\text{cm}^2/(\text{V}\cdot\text{s})$;
- $p$: free hole concentration obtained by incomplete ionization from `free_holes("SiC", "Al", N_A, N_D, T)` in [model.md](model.md), $\text{cm}^{-3}$; $T$: device temperature, K.

Approximation: outside $1675$–$1825\ ^\circ\text{C}$, Eq. (23) is an extrapolation (a code comment cites $1500\ ^\circ\text{C}$ for sicar3).

### Analytic Fields

`simple.py` provides closed-form toy fields combining a 1D drift field with planar, strip/pixel, or 3D-column weighting potentials, exposing the same `*_cached` method names as `DevsimField`.

Linear depletion field (`LinearDepletionField1D`, whose code comment notes it is modeled after Allpix² [12]):

$$E_z(z) = \operatorname{sgn}(V)\,\max\!\Bigl[0,\ \frac{|V| - V'_d}{d_{\text{eff}}} + \frac{2V'_d}{d_{\text{eff}}}\Bigl(1 - \frac{s}{d_{\text{eff}}}\Bigr)\Bigr]\times10^4 \tag{24}$$

$$d_{\text{eff}} = \begin{cases} d\sqrt{|V|/|V_d|}, & |V| < |V_d| \\ d, & |V| \ge |V_d| \end{cases}, \qquad V'_d = \min(|V_d|, |V|) \tag{25}$$

where $E_z$ is in $\text{V/cm}$ ($10^4$ converts from $\text{V}/\mu\text{m}$), $V$ is the bias voltage, $V_d$ is the full-depletion voltage (V), $d$ is the thickness ($\mu\text{m}$), $s = d - z$ (`deplete_from_implants=True`, default) or $s = z$, and $z$ is first clamped to $[0, d]$. For $V \ge 0$, $\operatorname{sgn}(V) = +1$. Below full depletion, the region $s > d_{\text{eff}}$ has zero field, representing the undepleted region. All three analytic fields take a constant doping `doping_cm3` (default $10^{12}\ \text{cm}^{-3}$) and trapping rate identically $0$.

Planar (`AnalyticPlanarField`): $\phi_w = z/d$ (with $z$ clamped to $[0, d]$); `get_w_p_cached` raises `ValueError` for positions outside $[0, l_x]\times[0, l_y]$; the electric field is given by Eq. (24).

Strip and pixel (`AnalyticStripPixelField`): each electrode is a rectangle of width $a$ = `pitch_x_um` and length $b$ ($b$ = `pitch_y_um` for pixels; for strips taken in order from `sensor_y_um`, `pitch_y_um`, `pitch_x_um`); the weighting potential is the image series for a rectangular electrode between two grounded planes [18]:

$$\phi_w = \frac{1}{2\pi}\Bigl\{F(x, y, u) - \sum_{n=1}^{N}\bigl[F(x, y, 2nd - u) - F(x, y, 2nd + u)\bigr]\Bigr\} \tag{26}$$

$$F(x, y, u) = \sum_{\pm,\pm} (\pm)(\pm)\arctan\frac{x_\pm\,y_\pm}{u\,\sqrt{x_\pm^2 + y_\pm^2 + u^2}}, \qquad x_\pm = x \pm \tfrac{a}{2},\ y_\pm = y \pm \tfrac{b}{2} \tag{27}$$

where $(x, y)$ is the position relative to the electrode center ($\mu\text{m}$), $u = d - z$ is the distance to the electrode plane, and $N$ = `weighting_series_terms` (default `100`); in $F$, the $(x_+, y_+)$ and $(x_-, y_-)$ terms carry a plus sign and the cross terms carry a minus sign; the result is clamped to $[0, 1]$. When only one readout electrode is listed (`central_electrode`), the electrode is centered in the device; otherwise electrodes are arranged by index into `round(l_x / p_x)` columns.

3D column (`AnalyticColumn3DField`): solves a 2D sine series with zero boundary conditions in a rectangular cell of size $W\times H$ (default $2p_x \times 2p_y$), ignoring $z$. The weighting potential is the Green's function averaged over 49 source points on the readout column, normalized at a point on the column surface $(x_r + r_c, y_r)$; the electric potential is the superposition of the weighting potential and the uniform space-charge solution, both being eigenfunction expansions of the Dirichlet problem on a rectangle [19]:

$$\mathcal{G}(x, y) = \sum_{m,n=1}^{M}\frac{4}{WH}\,\frac{\overline{\sin k_m x_s \sin k_n y_s}}{k_m^2 + k_n^2}\,\sin k_m x\,\sin k_n y, \qquad \phi_w = \frac{\mathcal{G}(x, y)}{\mathcal{G}(x_r + r_c, y_r)} \tag{28}$$

$$u_1 = \sum_{m,n\ \text{odd}}\frac{16}{\pi^2 mn\,(k_m^2 + k_n^2)}\sin k_m x\,\sin k_n y, \qquad P = u_1 - \frac{u_1(x_r + r_c, y_r)}{\mathcal{G}(x_r + r_c, y_r)}\,\mathcal{G} \tag{29}$$

$$\psi = -V\phi_w + \frac{qN}{\varepsilon_0\varepsilon_r}\,P, \qquad \mathbf{E} = \Bigl(V\nabla\phi_w - \frac{qN}{\varepsilon_0\varepsilon_r}\nabla P\Bigr)\times10^4 \tag{30}$$

where $k_m = m\pi/W$, $k_n = n\pi/H$ ($\mu\text{m}^{-1}$), and $M$ = `series_terms`; the source points are the column center plus 8, 16, and 24 points on rings of radius $0.35r_c$, $0.65r_c$, and $0.9r_c$; $(x_r, y_r)$ is the readout column position (default cell center) and $r_c$ is the column radius ($\mu\text{m}$); $N$ is `doping_cm3` and $\varepsilon_r$ defaults to `11.9`; $\psi$ is in V and $\mathbf{E}$ is in $\text{V/cm}$ ($q N/(\varepsilon_0\varepsilon_r)$ is computed in SI units and multiplied by $10^{-12}$ to convert to $\text{V}/\mu\text{m}^2$). Positions are first clamped inside the cell; $\phi_w = 1$ inside the readout column, $\phi_w = 0$ inside ground columns (default at the four corners), and the rest is clamped to $[0, 1]$.

`strip_pixel_field_from_detector` selects the analytic field from lowercased `det_model`: containing `"3d"` selects 3D column, containing `"planar"` or equal to `"lgad"` selects planar, containing `"strip"` or `"pixel"` selects strip/pixel (`"pixel"` for pixel), and all other values raise `ValueError`.

## Algorithms

### Built-in Constants

The quantities in the table below are written into the code. The "Key" column states whether the device file can override each one.

| Constant | Value | Unit | Location and Meaning | Key |
| --- | --- | --- | --- | --- |
| `q` (`ElectronCharge`) | `1.602176634e-19` | C | `CreateGlobalConstant`, DEVSIM equations | None |
| `k` | `1.380649e-23` | J/K | Same as above | None |
| `eps_0` | `8.8541878128e-14` | F/cm | Same as above, and `Permittivity` of each material | None |
| `T0` | `300.0` | K | Same as above, region parameter | None |
| `vel_mean` | `1e7` | cm/s | Thermal velocity $v_{\text{th}}$ for defect capture | None |
| `mu_n`, `mu_p` | Si `1450`/`500`; SiC `1100`/`114`; Diamond `1714`/`2064` | $\text{cm}^2/(\text{V}\cdot\text{s})$ | Constant mobility | None (`parameter` can override any region parameter) |
| `taun`, `taup` | Si `7e-3`/`7e-3`; SiC `2.5e-6`/`0.5e-6`; Diamond `5.6e-7`/`2.4e-7` | s | `SRH_LIFETIME` | None |
| `n1`, `p1` | $n_i$ | $\text{cm}^{-3}$ | SRH traps placed at the intrinsic level | None |
| `n_i` (`gas`) | `1e-9` | $\text{cm}^{-3}$ | Dielectric for weighting field | None |
| `F_sat` | `1e5` | V/cm | `TAT_SATURATION_FIELD` | `parameter: {"name": "F_sat", ...}` |
| `F_gamma` | `3.9e4` | V/cm | Eq. (8) | None |
| `epsilon_model_in`, `_ip`, `_0` | `10`, `7`, `0.36` times `1.602176634e-19` | J | Eq. (9) | None |
| `lambda_model_n`, `_p` | `2.99e-7`, `3.25e-7` | cm | Eq. (9) | None |
| `EDGE_FIELD` offset | `1` | V/cm | $|E| + 1$ in impact ionization coefficients | None |
| Defect energy conversion `e` | `1.602176634e-19` | J/eV | `CreateIrradiation` | None |
| `CONDUCTOR_PERMITTIVITY` | `1e10` | None | Eq. (16), DEVSIM and TCAD weighting fields | None |
| `RESISTIVITY` | `10.0` | $\Omega\cdot\text{cm}$ | Eq. (19) | None |
| `UNDEPLETED` | `0.5` | None | Eq. (19) | None |
| `ELEMENTARY_CHARGE` | `1.602176634e-19` | C | `conductive.py`, `simple.py` | None |
| Contact $n_0$ offset | `1e-10` | $\text{cm}^{-3}$ | Ohmic contact concentration | None |
| Minimum bias step size | `1e-7` | V | Bias sweep abort condition | None |
| Minimum fluence step | `1e-7` of the target fluence | $\text{cm}^{-2}$ | Abort condition of the fluence steps of the initial solution | None |
| Row cell expansion factor | `1.5`, upper limit `2` times $s_0$ | None | Single-cell stitching for weighting field | None |
| Cell width tolerance | `1e-6` times `p_x` | None | `createRowOfCells` | None |
| Node coincidence tolerance | `1e-9` times mesh span | None | `createRowOfCells`, `take_conductors_into_electrodes` | None |
| `STEP` | `1.0e-5` | cm | Central-difference step size in `gradient` | None |
| `max_size` | `50000` | $\mu\text{m}$ | Maximum coordinate accepted by cache | None |
| `resolution_default_1d` | `z: 0.05`, `x: 10000.0`, `y: 10000.0` | $\mu\text{m}$ | Cache bin width | None |
| `resolution_default_2d` | `z: 0.1`, `x: 0.5`, `y: 10000.0` | $\mu\text{m}$ | Same as above, axes `("z", "x")` | None |
| `resolution_default_plugin_2d` | `x: 0.1`, `y: 0.1`, `z: 10000.0` | $\mu\text{m}$ | Same as above, axes `("x", "y")` | None |
| `resolution_default_3d` | `z: 0.5`, `x: 1`, `y: 1` | $\mu\text{m}$ | Same as above | None |
| 3D regularization bin counts | `x: 30`, `y: 30`, `z: 30` | count | `interpolate_3d` | `field_interpolation_bins` |
| IDW neighbors, power, zero distance | `8`, `2`, `1e-15` | count, None, cm | `_idw_grid_3d` | None |
| TCAD permittivities | Silicon `11.9`, SiliconCarbide `9.76`, Oxide `3.9`, Nitride `7.5`; Aluminum as conductor | None | `tcad.PERMITTIVITY`, `METALS` | None |
| TCAD electrode clamping factor | `1e20` | None | `Hold` in `set_up_weighting` | None |
| TCAD weighting field convergence | absolute `1e-6`, relative `1e-6`, `20` iterations | None | `solve_weighting` | None |
| `DEFAULT_RELATIVE_PERMITTIVITY` | `11.9` | None | 3D column in `simple.py` | `relative_permittivity` |
| Analytic field doping | `1.0e12` | $\text{cm}^{-3}$ | `simple.py` | `input_doping` |
| `VACUUM_PERMITTIVITY_F_M` | `8.8541878128e-12` | F/m | Resistive-layer coupling capacitance | None |
| Al-implanted reference layer | concentration `1e20` $\text{cm}^{-3}$, thickness `300e-7` cm, measurement temperature `300.0` K, table `ANNEALED` | see left | `implanted_aluminium.py` | None |

The solver convergence settings `SOLVER` can be overridden via `field.solver` in the device file; see [Interface](#solver-settings-solver).

### Mesh

Meshes belong to `field`: the device file has no `mesh` section, since geometry (layer thicknesses, materials, and which face each electrode lies on) is an intrinsic property of the device; which mesh to use is specified by the `field` section settings.

1. **Coordinate axes**: `mesh_axes` maps saved coordinates to device axes: `("z",)` for 1D; `("x", "y")` (when the selected mesh lies in the transverse $x$-$y$ plane) or `("z", "x")` for 2D; `("x", "y", "z")` (when the selected mesh is generated by `sde`) or `("z", "x", "y")` for 3D. DEVSIM internal length units are cm.
2. **Mesh construction** (`DevsimMesh.mesh_define`): when solving a single-cell stitched weighting field ($s > 0$), calls `createRowOfCells`; otherwise, 1D uses `mesh_line`, `region`, and `contact` from the selected 1D mesh; 2D uses the selected Gmsh mesh file or built-in 2D mesh (`mesh_line`, `region`, `contact`); 3D always reads the Gmsh mesh file. Raises `ValueError` if `dimension` is not 1, 2, or 3.
3. **Materials and doping for weighting fields**: when solving a weighting field, `_regions` replaces every region's material with `"gas"` (the `"air"` region in a built-in 2D mesh is preserved; Gmsh meshes do not keep it), and `setDoping` replaces doping with `Acceptors = "0"`, `Donors = "1"`.
4. **Doping**: `Acceptors` is taken from `doping.Acceptors` and joined with `+` to `doping.Acceptors_ir` if present; `Donors` works identically; `NetDoping = Donors - Acceptors`. For 1D devices not solving a weighting field, `plots/doping` is plotted. Finally `<det_name>.dat` (Tecplot) is written.
5. **HEMT interface**: when `hemt_physics.transport_model == "drift_diffusion_v1"`, the 2D mesh also adds `interface` from the selected 2D mesh; raises `ValueError` if no interface is defined.
6. **Single-cell stitching** (`createRowOfCells`):
   - Supports only non-`plugin` 2D meshes; otherwise raises `ValueError`;
   - Builds one unit cell first and reads its node coordinates (depth, lateral); raises `ValueError` if the cell width differs from `p_x` by more than $10^{-6}\,p_x$;
   - Replicates the cell laterally $2s + 1$ times and merges coincident nodes after rounding coordinates to $10^{-9}$ times the cell width; raises `ValueError` if the merged node count is not $(2s+1)N - 2s\,N_{\text{face}}$ (where $N_{\text{face}}$ is the number of nodes on one side face), meaning nodes on the two side faces must match one-to-one;
   - The readout electrode of the center cell keeps its original name; the two copies of the readout electrode at distance $k$ cells from the center are merged into `neighbour<k>`; non-readout electrodes are merged into one across all cells; the entire row forms a single region with material `"gas"` and contact material `"metal"`.

### Bias Sweep and Convergence

When solving for the electric field, `solver_section.main` executes in the following order:

1. **Wrap the device**: `Reading(Detector(...))` records the attributes, keys, and mesh file hashes read during the solve. If the device file defines `frequency`, it overrides the small-signal frequency; `area_factor` defaults to `1.0`. HEMT devices are dispatched to `run_hemt_transport`.
2. **Build mesh and constants**: as described above; `create_parameter` writes temperature and material constants, optional `parameter`, and node model `U_const`.
3. **Irradiation and avalanche**: irradiation terms are enabled when an `irradiation` block is present and a weighting field is not being solved; the fluence is taken from `field.irradiation_flux`, falling back to `irradiation.irradiation_flux` when `null`. The avalanche model is taken from `avalanche_model` (`None` when `has_avalanche` is false).
4. **Circuit**: attaches voltage source `V1` to `bias.electrode` (DC `0`, AC amplitude `ac.real`, `ac.imaginary`).
5. **Initial solution** (`loop_section.initial_solver`): solves the Poisson equation alone first with intrinsic carrier distributions $n = n_i e^{\psi/V_T}$, $p = n_i^2/n$ using DC tolerances from `initial`; then sets up Eqs. (1)–(6) initialized from the intrinsic concentrations and solves; finally deletes the intrinsic carrier models. With the irradiation terms enabled, Eqs. (1)–(6) are first solved at a fluence of $0$, and the fluence is then raised in steps to its target $\Phi$: the concentration parameter `N_t_irr_<defect>` of each defect is set to $g_{\text{int}}\Phi_k$, and each step starts from the solution of the step before and is solved in DC with the tolerances of `initial`. The first step is $\Phi\times$ `flux_step.initial`; after a step that succeeds the step is multiplied by `flux_step.increase_factor`, and a step that would pass $\Phi$ is cut to $\Phi$; after a step that reports `"Convergence failure"` the solution of the step before is restored and the step is multiplied by `flux_step.decrease_factor` and tried again; a step below $10^{-7}\,\Phi$ raises `RuntimeError`, which names the device and the fluence reached.
6. **Zero bias**: solves and saves at $0\ \text{V}$, writing `0V.dd` and `0V.devsim`, and records `0.0` in `solved.potential` in `node.json`.
7. **Target and stop points**: target bias $V_g$ comes from `field.voltage`, falling back to `bias.voltage` when `null`. One field node corresponds to one target bias; intermediate bias files stored in the node are checkpoints saved along the ramp to $V_g$. Saved points are $\pm k\Delta_s$ ($k = 1, \dots, \lfloor |V_g|/\Delta_s\rfloor$, $\Delta_s$ = `saved_voltage_interval`), appending $V_g$ if the last point falls short of $|V_g|$; curve points are generated in the same way using `curve_voltage_interval`. Signs follow $V_g$. Raises `ValueError` if an interval is `0`.
8. **Stepping**: initial step size $\Delta$ = `voltage_step.initial`, with sign following $V_g$. Each step tries $V_t = V_c + \Delta$; if $|V_t|$ passes the nearest stop point (smallest magnitude among $V_g$, next saved point, and next curve point), $V_t$ is clamped to that stop point.
9. **Single-step solve** (`loop_solver`): initialized from the previous solution, with the electron and hole densities no lower than the smallest positive float; once two solutions exist, the potential is linearly extrapolated to $V_t$ from the last two points. After setting the bias, a DC solve is run with `voltage_step` tolerances.
10. **Success**: $\Delta \leftarrow \Delta \times$ `increase_factor`. When $V_t$ is a curve point, records the voltage, current $(I_n + I_p)\times$ `area_factor` (A), and the capacitance and noise described below. When $V_t$ is a saved point or $V_g$, saves to disk, writing `<V_t>V.dd` and `<V_t>V.devsim`, and records it in `solved.potential`; finishes upon reaching $V_g$.
11. **Failure**: on any DEVSIM error in a single step, writes `last_solvable.dd` first. If the error message contains `"Convergence failure"` or `"negative or zero value before update"`, sets $\Delta \leftarrow (V_t - V_c)\times$ `decrease_factor` and retries; any other DEVSIM error is re-raised as is. If $|\Delta| < 10^{-7}\ \text{V}$, stops and raises `RuntimeError("Step size too small (less than 1e-7). Exiting loop.")`.
12. **Wrap-up**: writes `read` to `node.json`, plots the IV curve; in CV mode plots CV and $1/C^2$ curves; plots the noise curve when the noise switch is enabled.

### Small-Signal Capacitance and Noise

1. **CV during sweep**: in CV mode (the full solve when none of the IV sweep, single-point capacitance, or weighting field subtasks is individually enabled in the `field` section), at each curve point `circuit_alter` sets the bias and runs an AC small-signal solve at frequency $f$:
   $$C = \frac{10^{12}\,\operatorname{Im} I_{V1}}{-2\pi f\,V_{\text{ac}}}\times\texttt{area\_factor}\quad[\text{pF}]$$

   where $I_{V1}$ is the AC small-signal current at the bias circuit node `V1` ($\text{A/cm}^2$ in 1D, $\text{A/cm}$ in 2D, A in 3D), $V_{\text{ac}} = 1\ \text{V}$ is the AC excitation amplitude, and $f$ is the frequency (Hz).
   Results are plotted in the CV plot; `cv.json` is written by the single-point capacitance step below.
2. **Single-point capacitance** (`saved_point.capacitance`, single-point capacitance subtask): loads `<V>V.devsim` (float-formatted filename, e.g. `200.0V.devsim`; raises `FileNotFoundError` listing available files if missing), recreates parameters, sets the bias electrode to $V$ and all others to $0$, runs a DC solve with `voltage_step` tolerances, then runs an AC solve to obtain the specific capacitance $10^{12}\operatorname{Im} I_{V1}/(-2\pi f)$: $\text{pF/cm}^2$ in 1D, $\text{pF/cm}$ in 2D, and pF in 3D. Only saved points (multiples of `saved_voltage_interval` and the target bias) have `.devsim` files.
3. **Noise**: when the noise switch is enabled, runs a DEVSIM noise solve at each curve point (output node `V1.I`) and records the mesh value of circuit node `V1.I`.

### Weighting Field Solving

1. **Prerequisite**: raises `FileNotFoundError` if `Conductive_<V_g>V.pkl` is missing, instructing to solve the field at that bias first.
2. **Electrodes**: readout electrodes are taken from `name` in `read_out_contact` (or from `name` in `ac_contact` of the selected 2D mesh if non-empty); one voltage source is attached to each electrode.
3. **Row cell count**: when `read_out_contact` has only one entry and `read_ele_num > 1`, $s$ is set by Eq. (17). When the device has a `resistive_layer`, $s = 0$ and only `resistive_layer.contact` is taken as the readout electrode.
4. **Per electrode**: solves only the Poisson equation (material `"gas"`); `take_conductors_into_electrodes` reads `Conductive_<V_g>V.pkl` and matches every region node to its nearest point in the file (for a stitched row, lateral coordinates are first taken modulo the cell width), raising `ValueError` for any node farther than $10^{-9}$ times the mesh span; then joins the conductive nodes into pieces along the mesh edges whose two ends are both conductive, raising `ValueError` when a piece holds contact nodes of two electrodes, naming the two electrodes, the bias $V_g$, the number of nodes of the piece and its coordinate range: such a piece makes the two electrodes one conductor and inflates the capacitances of Eq. (18) by about `CONDUCTOR_PERMITTIVITY`; finally rewrites `PotentialEdgeFlux` and `contactcharge_edge` according to Eq. (16), sets the readout electrode to $1\ \text{V}$ and solves.
5. **Row-end check** ($s > 0$): takes the maximum $r$ of $|\phi_w|$ within one unit cell at each end, computes mutual capacitances by Eq. (18), and counts `neighbours_coupled` as the number $c$ of consecutive neighbors starting from `neighbour1` satisfying $C_{\text{neighbour}k} \ge$ `crosstalk_tolerance` $\times\sum_j C_j$. If $r >$ `weighting_tolerance` or $c = s$: sets $s' = \lceil 1.5\,s\rceil$; raises `ValueError` if $s' > 2s_0$ (the weighting potential does not decay along the row, typically caused by a conductive region touching the readout electrode); otherwise clears DEVSIM (preserving `direct_solver` and `solver_callback`) and re-solves from scratch with $s'$.
6. **Saving**: saves the weighting potential to `weightingfield/<contact>/Potential_<V_g>V.pkl`; when $s > 0$, also writes `Capacitance_<V_g>V.json`; records $V_g$ in `solved.weighting`; writes `weightingfield/weightingfield.dat`.

### Saving to Disk

`save_milestone` dispatches by dimension and whether a weighting field is being saved, skipping regions whose material is `"Aluminum"` or `"air"`:

1. **Nodal quantities**: collects coordinates per region together with `Potential`, `NetDoping`, `Electrons`, `Holes`, `TrappingRate_n`, and `TrappingRate_p`; for DEVSIM fields, also computes `Conductive` (Eq. 19).
2. **Undepleted bulk** (DEVSIM fields, 1D, 2D, and 3D): computes $W_{\text{und}}$ and specific resistance $r$ using Eq. (20a), writes `<V>V.undepleted.json` with specific capacitance $10^{12}\varepsilon/W_{\text{und}}$ ($\text{pF/cm}^2$), or `null` at full depletion, and records the bias in `solved.undepleted`.
3. **Plotting**: plots potential, electron and hole trapping rates (not drawn without irradiation), and electric field. In 1D the electric field is the edge electric field at mesh edge midpoints for DEVSIM fields and `ElectricField_0` for TCAD fields. In 2D and 3D the plot shows the field strength $|\mathbf{E}| = |\nabla\psi|$: the gradient of the linear interpolation of the nodal potential on each mesh element (triangle, tetrahedron), averaged onto the nodes weighted by element area (volume), the same for DEVSIM and TCAD fields; the weighting field is plotted likewise as $|\nabla\phi_w|$.
4. **Writing pickles**: one file per quantity; `NetDoping` is written only at $V = 0$ or for TCAD fields. When `is_flip` is true, the two 2D coordinates are swapped.

### Reading: Assets in a Field Node

1. **Field node**: bias voltage, irradiation fluence, field mode, the selected mesh and its file hashes, and the device parts recorded in `read` (device attributes, device file keys and values such as `doping`, `bias`, and `irradiation` read during the solve) are all inputs of the field node, whose node ID is given by their fingerprint (see [../stages/field.md](../stages/field.md)); changing any of them produces a new node. This package reads from the given field node directory `field/<node_id>/`.
2. **Asset checks**: raises `FileNotFoundError` if the requested bias is absent from `solved.potential` or `solved.weighting`.
3. **Capacitance and undepleted layer**: `solved_capacitance` returns `specific_capacitance_pF × area_factor × 1e-12` (F); `solved_undepleted` returns $(r/A,\ c\cdot A\cdot10^{-12})$ ($\Omega$, F), where $A$ is as in Eq. (20), returning `None` when the undepleted width is `0`; raises `FileNotFoundError` if the corresponding bias has not been solved.
4. **Circuit lookup** (`field_circuit`): for a strip device listing a single readout electrode with `read_ele_num > 1`, reads `Capacitance_<V>V.json`, raising `FileNotFoundError` if missing; for other devices, takes the field capacitance if that bias is in `solved.capacitance`; for all devices, reads the undepleted layer.

### Interpolation and Caching

On constructing `DevsimField(device_name, voltage, read_out_contact, bounds, resolution, field_directory, interpolation_bins, pitch)`:

1. **Directory**: uses the field node directory `field/<node_id>/` given by `field_directory`. Raises `FileNotFoundError` if `node.json` is missing; `axes` is read from it.
2. **Loading**: `NetDoping` takes the first file matching `NetDoping_<V>V.pkl` in the directory; `Potential`, `TrappingRate_p`, `TrappingRate_n`, `Conductive`, and each readout electrode's weighting potential load the files for that bias voltage. Raises `FileNotFoundError` if a file is missing, and `ValueError` if a file's dimensionality is smaller than `len(axes)`.
3. **Interpolators**: 1D uses `interp1d` (linear, error outside bounds); 2D uses `LinearNDInterpolator` (a single Delaunay triangulation, `NaN` outside the convex hull); 3D uses `interpolate_3d`:
   - Raises `ValueError` if fewer than 2 points exist, non-finite values are present, point shape is not $N\times3$, or value count mismatches; returns a constant if all values are identical;
   - Directly populates a grid if the points form a complete regular grid (product of unique coordinate counts along all axes equals point count with no duplicates);
   - Otherwise builds `field_interpolation_bins` equally spaced coordinates on $[\min, \max]$ along each axis (default 30; raises `ValueError` if fewer than 2, an unknown axis appears, or any axis has zero span), evaluating each grid point by inverse-distance-squared weighting over the 8 nearest neighbors $\hat v = \sum v_j d_j^{-2}/\sum d_j^{-2}$ ($d_j$ floored at $10^{-15}$, taking that point's value when distance $\le 10^{-15}$);
   - Finally wraps the grid with `RegularGridInterpolator` (linear, error outside bounds).
4. **Unit-cell folding** (`_in_the_cell`): when only one readout electrode is listed, for each non-`z` axis given in `bounds`, if the device width exceeds $1 + 10^{-6}$ times the potential mesh span, folds query positions back into one unit cell of the mesh: the cell width is the pitch along that axis (`pitch`: `p_x` for `x`, `p_y` for `y`), selecting the middle cell of a multi-cell mesh. Potential, doping, trapping rates, and conductive flags are queried after folding; weighting potential is queried at the original position. The mesh is checked against the pitch at load (`_check_mesh_against_pitch`): a potential mesh that spans less than the pitch along `x` or `y` raises `ValueError`; along an axis to be folded, a mesh span that is not a whole number of pitches, or a missing pitch for that axis, raises `ValueError`; the message names the device, the bias, the axis, the mesh span and the pitch.
5. **Electric field**: `get_e_field` computes $\mathbf{E} = -\nabla\psi$, where `gradient` performs central differences of width `STEP` along each axis, clamped at mesh endpoints into one-sided differences; raises `ValueError` for points outside the mesh coordinate range. Returns $(E_x, E_y, E_z)$ (V/cm), with $0$ for components not in `axes`.
6. **Weighting potential**: `get_w_p` returns $0$ when the interpolated value is $< 0$ or `NaN`, and $1$ when $> 1$.
7. **Conductive flag**: `get_conductive` finds the enclosing interval in 1D and returns true only if both endpoints are conductive; in higher dimensions, locates the enclosing simplex in the Delaunay triangulation and returns true only if all vertices are conductive; outside the mesh, returns the value of the nearest node.
8. **Caching**: `*_cached` methods bin positions ($\mu\text{m}$) by `resolution`, clamping bin index $\lfloor u/r_u\rfloor$ to $[\lfloor u_{\min}/r_u\rfloor,\ \lfloor (u_{\max} - 10^{-12})/r_u\rfloor]$ (when `bounds` is provided), and reuse the first queried value within each bin. Coordinates with magnitude exceeding `max_size` or non-finite values bypass the cache and are evaluated directly. Non-positive or non-numeric entries in `resolution` revert to defaults. On query errors: electric field recomputes directly and lets the error propagate; doping and trapping rates log a warning and return `0.0`; weighting potential raises `RuntimeError`.
9. **Planar gain** (`_integrate_planar_gain`, cached after first call): raises `ValueError` if `"z"` is not in `axes`; extracts all depth nodes of the potential mesh along $(0.5l_x, 0.5l_y)$, takes piecewise-constant fields $E_m = -\Delta\psi_m/\Delta z_m$ across intervals, and integrates Eq. (10) analytically for the piecewise-constant field, raising `ValueError` if $I_{\text{bd}} \ge 1$; the midpoint of the strongest-field interval defines the gain-layer depth, and the field direction together with which half contains the gain layer determines the polarity of carriers being multiplied. Details of each step are given in [current.md](current.md).

### Importing TCAD Fields

`tcad.import_field(tdr, my_d, folder, asked, flip)`:

1. **Bias voltage**: reads the dataset named `ContactExternalVoltage` under `/collection/geometry_0/state_0` and extracts the voltage on `bias.electrode`. Raises `ValueError` if the file contains no electrode voltages and `field.voltage` is `null`, if that electrode is absent, or if the requested bias disagrees with the file.
2. **Mesh conversion**: `tdr_reader.read_tdr` reads geometry and nodal datasets (bulk regions and node-located scalar or vector datasets only; raises `RuntimeError` for mixed element types, multi-part regions, etc.); `tdr_import.import_tdr` builds the DEVSIM mesh and nodal solutions (multi-row datasets named `<name>_<row>`) and writes `converted.devsim`. Coordinates are converted from $\mu\text{m}$ to cm by multiplying by `1e-4`.
3. **Saving fields**: `save_milestone(..., is_tcad=True)` saves `ElectrostaticPotential`, `DopingConcentration`, `eDensity`, `hDensity`, `eGapStatesRecombination`, and `hGapStatesRecombination` as `Potential`, `NetDoping`, `Electrons`, `Holes`, `TrappingRate_n`, and `TrappingRate_p`.
4. **Conductive region**: `Aluminum` regions are entirely conductive; regions lacking `eDensity` and `hDensity` are non-conductive; semiconductor regions missing any of `eDensity`, `hDensity`, `DopingConcentration`, `eMobility`, or `hMobility` raise `ValueError`; all others are classified by Eq. (19) using nodal mobilities and written to `Conductive_<V>V.pkl`.
5. **Weighting field**: each region's permittivity comes from `PERMITTIVITY` (metals take `1.0` and are also conductive), raising `ValueError` for materials absent from the table; edge flux follows Eq. (16); all nodes coincident with an electrode node (including the opposite side of interfaces) are clamped to the electrode potential via $10^{20}(\phi - \phi_{\text{held}})$; potential is continuous across regions. Each readout electrode is set to $1$ and all others to $0$ in turn; raises `ValueError` if a readout electrode is missing from the file.
6. **Recording**: writes `axes` and `read` to `node.json` and records the bias in `solved.potential` and `solved.weighting`.

## Software Implementation

### File Layout

- `solver_section.py`: default `SOLVER` settings and main solve entry `main` (bias sweep, weighting field, row cell expansion).
- `loop_section.py`: `loop_section` class for initial solve, single-step solves, and IV/CV/noise recording.
- `initial.py`: initial-solution setup with Poisson and drift-diffusion equations only.
- `physics_drift_diffusion.py`: Poisson equation, Scharfetter-Gummel currents, SRH recombination, continuity equations, and ohmic/Schottky contacts.
- `physics_avalanche.py`: impact ionization generation rates and SiC trap-assisted tunneling term.
- `physics_irradiation.py`: irradiation defect tables, defect charges, recombination rate, and trapping rates.
- `create_mesh.py`: `DevsimMesh` for mesh construction, doping, and single-cell stitching; `mesh_axes`.
- `create_parameter.py`: DEVSIM region constants.
- `model_create.py`: wrappers for DEVSIM node, edge, and contact models (from DEVSIM).
- `weighting.py`: merges conductive nodes into electrodes.
- `conductive.py`: conductive classification and undepleted bulk parameters.
- `save_milestone.py`: disk saving, plotting, and `node.json` recording (`save_record`, `save_solved`).
- `saved_point.py`: single-point small-signal capacitance from a saved point.
- `reading.py`: `Reading` wrapper tracking device parts read during solving.
- `solved.py`: reads capacitance and undepleted layer from a field node; `DEFAULT_MODE` (`"full"` when DEVSIM is installed, otherwise `"fast"`).
- `assets.py`: field filenames (`voltage_label`, `field_pickle_path`, `resolve_field_pickle`).
- `devsim_field.py`: `DevsimField` interpolated queries, caching, and planar gain.
- `interpolation.py`: 1D/2D/3D interpolators and central-difference function `calculate_gradient`.
- `gradient.py`: central-difference gradient bounded to the mesh range.
- `device_circuit.py`: `DeviceCircuit`, `planar_circuit`, `side_by_side`, `row_of_electrodes`.
- `circuit_parameters.py`: lookup of junction capacitance, bias and coupling elements, undepleted layer, and sheet resistance; `field_circuit`, `device_circuit`, `part_of_row`, `device_row`, `device_grid`; `undepleted_layer` computes $R$ and $C$ of the undepleted layer by Riegler's planar formula from area, thickness, depleted width, permittivity, and resistivity.
- `resistive_layer.py`: resistive-layer row circuit `resistive_row` and grid circuit `resistive_grid`, and `shares(my_d, point_um)`: the shares of the charge of a point among the RC nodes.
- `implanted_aluminium.py`: sheet resistance of Al-implanted 4H-SiC layers.
- `simple.py`: analytic toy fields.
- `tcad.py`: TDR field import and weighting field solving.
- `tdr_reader.py`, `tdr_import.py`: TDR reading and DEVSIM device creation (adapted from DEVSIM LLC's tdr-convert 0.1.7, Apache-2.0).
- `devsim_draw.py`: IV/CV/noise curves (`draw_iv(V, I, path)`, `draw_cv(V, C, path)`, `draw_noise(V, noise, path)`, which also write the `.root` files `simIV`, `simCV`, `simnoise`) and 1D/2D/3D field plots; 1D profiles are drawn into `<path>/plots` by `draw_profile(x, curves, ylabel, path, name, *suffixes, log=False, boundaries=())`, which draws a thin gray dashed line at each depth of `boundaries`; the boundaries come from `doping_boundaries(depth, doping)`: the midpoint of neighbouring mesh nodes whose net doping differs in magnitude by more than a factor of 10, with boundaries closer than 0.5 μm merged into their mean. The weighting field is solved with a constant doping, so the boundaries of the weighting potential and weighting field come from `NetDoping_0V.pkl` of the field folder; `draw_electrons`, `draw_holes`, `draw_field` plot 1D electron/hole concentrations and electric field, and `save_field` writes electric field versus depth as a table.
- `hemt_solver_2d_transport_v1.py`: electron-only 2D AlGaN/GaN HEMT DC transfer-characteristic branch, dispatched from `solver_section.main`, writing `HEMT_TRANSPORT_*` files.
- `plot_hemt_transport_csv.py`: standalone script plotting the latest `HEMT_TRANSPORT_final_profile.csv` under `work/AlGaN_GaN_HEMT_TRANSPORT_V1/field` (or environment variable `RASER_HEMT_FIELD_DIR`).

### Core Data Structures

- Field pickle: dict `{"points", "values", "metadata"}`. `points` holds node coordinates (cm): a length-$N$ array in 1D, or $N$ `[u, v]` / `[u, v, w]` lists in 2D/3D ordered as in `axes`; `values` is a length-$N$ `float64` array with quantity-dependent units; `metadata` holds `voltage` (V) and `dimension`, and weighting potentials may additionally include `cells_either_side` (2D stitched row) or `contact_name` (3D).
- `node.json`: this package writes `axes` (list), `read` (`{"attributes", "keys", "files"}`, with values as numbers, strings, `null`, or `"sha256:<hex>"`, and absent entries recorded as `["absent"]`), and `solved` (`potential`, `weighting`, `capacitance`, `undepleted`, each a list of solved bias voltages in V). Remaining node inputs, code version, runtime environment, and run status are written by the command in [../stages/field.md](../stages/field.md).
- `DevsimField`: `axes`; `resolution` ($\mu\text{m}$); `potential_ranges`, `weighting_ranges` (axis endpoints in cm); `cells_either_side`; five cache dicts; `WeightingPotential` (list of interpolators for the readout electrodes).
- `DeviceCircuit`: `lines` (SPICE element lines with ground as node `0`, capacitance in F, resistance in $\Omega$), `sources` (mapping electrode name to induced current source node pair `(from, to)`), `outputs` (mapping readout name to first-stage amplifier input node), and `alike` (groups of outputs sharing identical noise spectra). `device_circuit` and related functions also return a record dict stating each value and its source (`"device file"`, `"field"`, `"parallel plate"`, `"chosen"`, `"implanted layer"`).

## Interface

Users can configure the device file keys in the table below and the solver settings under `field.solver`; meshes are not in the device file, and which mesh to use is specified by the `field` section settings; all other parameters are hardcoded. See [../stages/field.md](../stages/field.md) for command-line usage and [../components/device.md](../components/device.md) for general device file conventions.

### Keys Read from the Device File

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `det_name`, `default_dimension`, `field_dimension` | see [device.md](device.md) | None | Device name and solve dimension (1, 2, 3) |
| `l_x`, `l_y`, `l_z` | None (required) | $\mu\text{m}$ | Device dimensions; `l_z` used in Eq. (17), `l_y` is strip length |
| `electrodes`, `p_x`, `p_y`, `read_ele_num`, `x_ele_num`, `y_ele_num` | see [device.md](device.md) | $\mu\text{m}$ / count | Electrode layout; `p_x` is stitched unit-cell width |
| `area_factor` | `1.0` | 1D $\text{cm}^2$, 2D cm, 3D None | Factor converting specific mesh current and capacitance to device values |
| `temperature` | None (required) | K | Device temperature |
| `material` | None (required) | None | Device material; determines $\varepsilon_r$ in Eq. (18) and planar gain coefficients |
| `bias.electrode`, `bias.voltage` | None (required) | None, V | Bias electrode and target bias when `field.voltage` is `null` |
| `read_out_contact` | None (required) | None | List of readout electrodes, each with `name` and optional `x_span`, `y_span` (cell span) |
| `doping.Acceptors`, `doping.Donors` | None (required) | $\text{cm}^{-3}$ | DEVSIM expressions |
| `doping.Acceptors_ir`, `doping.Donors_ir` | None | $\text{cm}^{-3}$ | Additional doping expressions added on top |
| `irradiation.irradiation_model` | `None` if block absent | None | `"XingChen"`, `"Perugia"`, `"Schwandt"`, `"CommonDefect"`; other names yield an empty defect table |
| `irradiation.irradiation_flux` | `0` if block absent | $\text{cm}^{-2}$ | Fluence when `field.irradiation_flux` is `null` |
| `avalanche_model`, `enable_gain` | `None`, `False` | None | Enables Eq. (7) when both are active |
| `parameter` | None | parameter-dependent | A `{"name", "value"}` object written as a DEVSIM region parameter after material constants, e.g. `{"name": "mu_n", "value": 1350}`, `{"name": "F_sat", "value": 2e5}`; one parameter per device file |
| `U_const` | `0` | $\text{cm}^{-3}\,\text{s}^{-1}$ | Additional recombination rate (number or expression) |
| `frequency` | `ac.frequency` | Hz | Small-signal and noise frequency |
| `field.solver` | `SOLVER` | see table below | Deeply merged overrides for solver settings |
| `hemt_physics.transport_model` | None | None | Dispatches to HEMT solve when `"drift_diffusion_v1"` |
| `field_interpolation_bins` | `None` (`30` per axis) | count | Regularization bin counts for unstructured 3D point clouds, dict keyed by axis name, e.g. `{"x": 60, "y": 60, "z": 60}`; omitted axes default to `30` (passed in by [../stages/current.md](../stages/current.md)) |
| `capacitance_pF` | None | pF | Single-electrode junction capacitance; takes precedence over the field |
| `depletion_depth` | `l_z` | $\mu\text{m}$ | Depletion depth for parallel-plate estimate |
| `bias_resistance_ohm` | `None` | $\Omega$ | Single-electrode bias resistance |
| `coupling_capacitance_pF` | `None` | pF | Single-electrode coupling capacitance; requires `bias_resistance_ohm`, otherwise raises `ValueError` |
| `undepleted_resistance_ohm`, `undepleted_capacitance_pF` | `None` | $\Omega$, pF | Undepleted layer; must be given as a pair |
| `resistive_layer.sheet_resistance` | None | $\Omega$ | Sheet resistance |
| `resistive_layer.implanted`, `.thickness`, `.anneal` | None | $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | Computed via Eq. (22) when `sheet_resistance` is absent |
| `resistive_layer.strips` | None | RC node index | Row circuit: mapping strip name to first and last RC node indices `[first, last]` |
| `resistive_layer.pads` | None | RC node index | Grid circuit: mapping electrode name to `[x_first, x_last, y_first, y_last]` |
| `resistive_layer.grounded` | `{}` | RC node index | Grounded contacts; `[first, last]` for a row, list of rectangles for a grid |
| `resistive_layer.contact` | None (required when there is a `resistive_layer`) | None | Name of the mesh contact the resistive layer sits on; the weighting potential is solved for this contact and stored as `weightingfield/<contact>/Potential_<V>V.pkl` |
| `resistive_layer.coupling.thickness`, `.permittivity` | None | $\mu\text{m}$, None | Dielectric layer beneath electrodes |
| `det_model` | None | None | Selects analytic field type; if it contains `"3d"`, `Detector.capacitance` is `None` when `capacitance_pF` is absent |
| `depletion_voltage`, `input_doping` | `|bias.voltage|`, `1e12` | V, $\text{cm}^{-3}$ | Analytic fields |
| `column_radius_um`, `column_cell_x_um`, `column_cell_y_um`, `readout_column_x_um`, `readout_column_y_um`, `ground_columns_um`, `relative_permittivity`, `weighting_series_terms` | required, `2*p_x`, `2*p_y`, cell center, cell center, four corners, `11.9`, `100` | $\mu\text{m}$ / None | Analytic fields (3D column and strip/pixel) |

### Solver Settings `SOLVER`

In the device file, write `"field": {"solver": {...}}` nested along the key paths below to overlay selectively onto the defaults, specifying only keys to override, for example `"field": {"solver": {"voltage_step": {"initial": 0.2, "decrease_factor": 0.25}, "saved_voltage_interval": 50.0}}`.

| Key Path | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `initial.absolute_error`, `.relative_error`, `.maximum_iterations` | `1e10`, `1e-4`, `100` | None, None, iterations | Initial solve |
| `voltage_step.absolute_error`, `.relative_error`, `.maximum_iterations` | `1e20`, `1e-4`, `100` | None, None, iterations | Bias-step and single-point capacitance DC solve |
| `voltage_step.initial` | `1.0` | V | Initial step size |
| `voltage_step.increase_factor`, `.decrease_factor` | `2.0`, `0.5` | None | Multipliers on success and failure |
| `flux_step.initial` | `0.01` | None | First fluence step of the initial solution, as a share of the target fluence |
| `flux_step.increase_factor`, `.decrease_factor` | `2.0`, `0.5` | None | Multipliers of the fluence step on success and failure |
| `saved_voltage_interval` | `100.0` | V | Interval between saved points |
| `curve_voltage_interval` | `10.0` | V | Interval between IV/CV/noise curve points |
| `ac.real`, `ac.imaginary` | `1.0`, `0.0` | V | Small-signal excitation |
| `ac.frequency` | `1000.0` | Hz | Small-signal frequency |
| `weighting_tolerance` | `5e-2` | None | Upper limit $\delta$ on residual weighting potential at row ends |
| `crosstalk_tolerance` | `5e-2` | None | Lower limit on mutual-capacitance fraction deemed coupled |

### Output Files

Files are written to the field node directory `work/<device>/field/<node_id>/`. Bias voltages in pickles and `Capacitance_*.json` use `voltage_label` (integer values formatted as integers, e.g. `Potential_200V.pkl`); `.devsim`, `.dd`, `.undepleted.json`, and `.cv.json` use float formatting (e.g. `200.0V.devsim`, `0.0V.undepleted.json`), while zero-bias state files are `0V.devsim` and `0V.dd`. Negative bias voltages carry a leading minus sign accordingly, e.g. `Potential_-100V.pkl`, `-100.0V.devsim`.

| File | Content, Shape, Type | Unit |
| --- | --- | --- |
| `node.json` | `axes`, `read`, `solved`, see Core Data Structures | bias in V |
| `Potential_<V>V.pkl` | Nodal potential, `values` is `(N,)` `float64` | `points` cm; V |
| `Electrons_<V>V.pkl`, `Holes_<V>V.pkl` | Electron and hole concentrations | cm; $\text{cm}^{-3}$ |
| `TrappingRate_n_<V>V.pkl`, `TrappingRate_p_<V>V.pkl` | Electron and hole trapping rates | cm; $\text{s}^{-1}$ |
| `Conductive_<V>V.pkl` | Conductive flag, `1.0` or `0.0` | cm; None |
| `NetDoping_0V.pkl` (`NetDoping_<V>V.pkl` for TCAD) | Net doping | cm; $\text{cm}^{-3}$ |
| `<V>V.undepleted.json` | DEVSIM field: `voltage_V`, `undepleted_width_um`, `specific_resistance_ohm_cm2`, `specific_capacitance_pF` (`null` at full depletion), `per` (`"cm^2"`) | V, $\mu\text{m}$, $\Omega\cdot\text{cm}^2$, $\text{pF/cm}^2$ |
| `<V>V.cv.json` | Written by the single-point capacitance subtask: `voltage_V`, `specific_capacitance_pF`, `per` (`"cm^2"`, `"cm"`, `"device"`), `area_factor`, `frequency_Hz` | V, pF/unit, —, Hz |
| `weightingfield/<contact>/Potential_<V>V.pkl` | Weighting potential | cm; None |
| `weightingfield/<contact>/Capacitance_<V>V.json` | Stitched row: `unit` (`"F/cm"`), `of`, `total`, `to` (`neighbour<k>` and non-readout electrodes), `neighbours_coupled` | F/cm |
| `<V>V.devsim`, `<V>V.dd`, `0V.devsim`, `0V.dd` | DEVSIM state (reloaded by single-point capacitance) and Tecplot data | cm, V |
| `<det_name>.dat`, `weightingfield/weightingfield.dat`, `last_solvable.dd`, `converted.devsim` | Mesh, weighting field, last state before convergence failure, TCAD conversion result | cm, V |
| `simIV<min>to<max>.root` | TTree `SicarTestIV`, branches `voltage`, `Current` | V, A |
| `simCV<min>to<max>.root` | TTree `SicarTestCV`, branches `voltage`, `CAP` | V, pF |
| `simnoise<min>to<max>.root` | TTree `SicarTestnoise`, branches `voltage`, `Current` | V, — |
| `HEMT_TRANSPORT_IdVg.csv`, `HEMT_TRANSPORT_final_profile.csv`, `HEMT_TRANSPORT_final.devsim`, `HEMT_TRANSPORT_summary.json` | Transfer characteristics, final profile, state, and summary of the HEMT branch | V, mA/mm, $\text{cm}^{-3}$ |

### Generated Plots

Figures of 1D, 2D, and 3D devices are all stored in `plots/` of the field node directory, with the style of [Figures (`supports/figures`)](../supports/figures.md).

| File | Content | Axis Units |
| --- | --- | --- |
| `plots/iv.png/.pdf` | IV curve: absolute reverse bias versus absolute leakage current, log vertical axis; outlying points more than 6 orders of magnitude below the median of the whole curve (for example the point at 0 V on a curve of pA) are not drawn, while the `simIV` file keeps them; a curve that is small as a whole is drawn as it is; axes `Reverse bias [V]`, `Leakage current [A]` | V, A |
| `plots/cv.png/.pdf` | Left: capacitance versus reverse bias, axis `Capacitance [pF]`; right: $1/C^2$ versus reverse bias, axis `1/C² [pF⁻²]`; horizontal axis `Reverse bias [V]` | V, pF, $\text{pF}^{-2}$ |
| `plots/noise.png/.pdf` | Noise current versus reverse bias, log vertical axis `Noise current [A]` | V, A |
| `plots/doping.png/.pdf` | 1D donor and acceptor concentrations along depth, log vertical axis; axes `Depth [μm]`, `Doping [cm⁻³]` | μm, $\text{cm}^{-3}$ |
| `plots/potential_<V>V`, `plots/electric_field_<V>V`, `plots/trapping_rate_<V>V` (each with `.png/.pdf`) | 1D, per bias: potential `Potential [V]`, electric field `Electric field [kV/cm]`, and electron (blue) and hole (red) trapping rates on one figure with log vertical axis `Trapping rate [s⁻¹]`; the trapping rate is not drawn when both are zero (no irradiation); `<V>` is written in its shortest form (`200.0` as `200`) | μm; V, kV/cm, $\text{s}^{-1}$ |
| `plots/weighting_potential_<contact>_<V>V`, `plots/weighting_field_<contact>_<V>V` (each with `.png/.pdf`) | 1D, per readout electrode and per bias with a weighting field solved: weighting potential `Weighting potential` and weighting field `Weighting field [cm⁻¹]`; stored in `plots/` with the other figures, not under `weightingfield/<contact>/` | μm; None, $\text{cm}^{-1}$ |
| `plots/potential_<V>V`, `plots/electric_field_<V>V` (each `.png/.pdf`) | 2D and 3D, one per bias, three panels side by side: left the 2D slice (viridis map, color scale is the quantity), middle the depth profile, right the lateral profile; axes `Potential [V]`, `Electric field [kV/cm]` | μm; V, kV/cm |
| `plots/trapping_rate_<V>V` (`.png/.pdf`) | 2D and 3D electron (blue) and hole (red) trapping rates along the depth in one plot, log vertical axis; not drawn when both are zero (no irradiation) | μm; $\text{s}^{-1}$ |
| `plots/weighting_potential_<contact>_<V>V`, `plots/weighting_field_<contact>_<V>V` (each `.png/.pdf`) | 2D and 3D weighting potential and weighting field of each read-out electrode, three panels as above; axes `Weighting potential`, `Weighting field [cm⁻¹]` | μm; none, $\text{cm}^{-1}$ |
| `HEMT_TRANSPORT_IdVg.png/.pdf` | HEMT transfer characteristic | V, mA/mm |

The slices and profiles of 2D and 3D plots follow `mesh_axes`, and the axis titles name the device axes: lateral `x [μm]`, `y [μm]`, depth `Depth [μm]`. The "middle" of a coordinate is the mean of its minimum and maximum on the mesh.

- Mesh of depth and $x$, `("z", "x")`: the slice is the whole mesh; the depth profile is at the middle of $x$, the lateral profile runs along $x$ at the middle of the depth.
- Cross-section mesh `("x", "y")`: the slice is the whole mesh; there is no depth, and the two profiles run along $x$ (at the middle of $y$) and along $y$ (at the middle of $x$).
- 3D: the slice is the $x$-$z$ plane through the middle of $y$; the depth profile is at the middle of $x$ and $y$, the lateral profile runs along $x$ at the middle of $y$ and of the depth.
- Weighting potential and weighting field: the depth profile is at the mean lateral coordinate of the nodes of the read-out electrode, right below it; in a row of cells, the electrode of the middle cell.
- Values on profiles and on 3D slices are linear interpolations on the mesh elements.
- Each profile has a one-line panel title saying where it lies, such as `x = 29.0 μm` or `Depth = 25.0 μm`; a 3D slice says `y = <value> μm`.
- When the values of a panel vary by less than 1% of the largest of them in magnitude, its vertical axis (the colour scale of a slice) starts from 0 instead of closing in on the data, so that numerical noise on the mesh does not look like a variation of the field.

## References

- [1] D. L. Scharfetter, H. K. Gummel, “Large-signal analysis of a silicon Read diode oscillator”, IEEE Trans. Electron Devices 16 (1969) 64, doi:10.1109/T-ED.1969.16566
- [2] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), sec. 1.5.4, doi:10.1002/0470068329
- [3] J. E. Sanchez, “DEVSIM: A TCAD Semiconductor Device Simulator”, J. Open Source Softw. 7 (2022) 3898, doi:10.21105/joss.03898
- [4] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [5] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [6] G. A. M. Hurkx, D. B. M. Klaassen, M. P. G. Knuvers, “A new recombination model for device simulation including tunneling”, IEEE Trans. Electron Devices 39 (1992) 331, doi:10.1109/16.121690
- [7] R. J. McIntyre, “Multiplication noise in uniform avalanche diodes”, IEEE Trans. Electron Devices ED-13 (1966) 164, doi:10.1109/T-ED.1966.15651
- [8] W. Shockley, “Currents to Conductors Induced by a Moving Point Charge”, J. Appl. Phys. 9 (1938) 635, doi:10.1063/1.1710367
- [9] S. Ramo, “Currents Induced by Electron Motion”, Proc. IRE 27 (1939) 584, doi:10.1109/JRPROC.1939.228757
- [10] W. Riegler, “An application of extensions of the Ramo–Shockley theorem to signals in silicon sensors”, Nucl. Instrum. Methods Phys. Res. A 940 (2019) 453, eq. 50, doi:10.1016/j.nima.2019.06.056, arXiv:1812.07570
- [11] M. Spera, D. Corso, S. Di Franco, G. Greco, A. Severino, P. Fiorenza, F. Giannazzo, F. Roccaforte, “Effect of high temperature annealing (T > 1650 °C) on the morphological and electrical properties of p-type implanted 4H-SiC layers”, Mater. Sci. Semicond. Process. 93 (2019) 274, doi:10.1016/j.mssp.2019.01.019, arXiv:2001.08021
- [12] S. Spannagel et al., “Allpix²: A modular simulation framework for silicon detectors”, Nucl. Instrum. Methods Phys. Res. A 901 (2018) 164, doi:10.1016/j.nima.2018.06.020
- [13] K. K. Thornber, “Applications of scaling to problems in high-field electronic transport”, J. Appl. Phys. 52 (1981) 279, doi:10.1063/1.328490
- [14] A. O. Konstantinov, Q. Wahab, N. Nordell, U. Lindefelt, “Ionization rates and critical fields in 4H silicon carbide”, Appl. Phys. Lett. 71 (1997) 90, doi:10.1063/1.119478
- [15] J. Schwandt, E. Fretwurst, E. Garutti, R. Klanner, C. Scharf, G. Steinbrück, “A new model for the TCAD simulation of the silicon damage by high fluence proton irradiation”, 2018 IEEE NSS/MIC, doi:10.1109/NSSMIC.2018.8824412, arXiv:1904.10234
- [16] X. Li et al., “Simulation of radiation damage effect on silicon detectors using RASER”, JINST 20 (2025) P12009, doi:10.1088/1748-0221/20/12/P12009, arXiv:2504.20463
- [17] M. Petasecca, F. Moscatelli, D. Passeri, G. U. Pignatel, “Numerical simulation of radiation damage effects in p-type and n-type FZ silicon detectors”, IEEE Trans. Nucl. Sci. 53 (2006) 2971, doi:10.1109/TNS.2006.881910
- [18] W. Riegler, G. Aglieri Rinella, “Point charge potential and weighting field of a pixel or pad in a plane condenser”, Nucl. Instrum. Methods Phys. Res. A 767 (2014) 267, doi:10.1016/j.nima.2014.08.044; explicit series in W. Riegler, “Time resolution of silicon pixel sensors”, JINST 12 (2017) P11017, Appendix E, doi:10.1088/1748-0221/12/11/P11017
- [19] J. D. Jackson, *Classical Electrodynamics*, 3rd ed., Wiley (1999), sec. 3.12
- [20] A. Das, S. P. Duttagupta, “TCAD simulation for alpha-particle spectroscopy using SiC Schottky diode”, Radiat. Prot. Dosim. 167 (2015) 443, doi:10.1093/rpd/ncu369
- [21] Z. Li et al., “Mechanisms of proton irradiation-induced defects on the electrical performance of 4H-SiC PIN detectors”, JINST 21 (2026) P03010, doi:10.1088/1748-0221/21/03/P03010, arXiv:2503.09016
- [22] S. Mägdefessel, R. Mori, N. Sorgenfrei, U. Parzefall, “Understanding the frequency dependence of capacitance measurements of irradiated silicon detectors”, arXiv:2301.09371, eqs. (2), (3)
- [23] A. T. Collins, A. W. S. Williams, “The nature of the acceptor centre in semiconducting diamond”, J. Phys. C: Solid State Phys. 4 (1971) 1789, doi:10.1088/0022-3719/4/13/030
- [24] R. G. Farrer, “On the substitutional nitrogen donor in diamond”, Solid State Commun. 7 (1969) 685, doi:10.1016/0038-1098(69)90593-6
- [25] A. Mainwood, A. M. Stoneham, “Stability of electronic states of the vacancy in diamond”, J. Phys.: Condens. Matter 9 (1997) 2453, doi:10.1088/0953-8984/9/11/013
