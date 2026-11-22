# Materials and Physical Models (`core/model`)

`src/raser/core/model/` receives the material name `material`, operating temperature `temperature`, doping concentration, and impact ionization model name `avalanche_model` parsed by [device definition](device.md) from [detector components](../components/device.md), as well as local electric field strength and carrier concentrations passed in from [device field](field.md) and [carrier transport](current.md). This package defines relative permittivity, effective mass, carrier mobility, impact ionization coefficients, band structure, intrinsic carrier concentration, dopant incomplete ionization, and Shockley-Read-Hall (SRH) recombination models for silicon (`"Si"`), 4H silicon carbide (`"SiC"`), and diamond (`"Diamond"`), and uses `Formula` to compile a single set of physical expressions into both Python numerical evaluators and DEVSIM symbolic equations. The computed relative permittivity is handed to [device definition](device.md) to estimate parallel-plate junction capacitance and to [device field](field.md) to solve the Poisson equation and inter-strip mutual capacitance; symbolic expressions and material parameters for band structure, SRH recombination, incomplete ionization, and impact ionization are handed to [device field](field.md) for DEVSIM drift-diffusion solves, 1D planar avalanche gain integration, and sheet-resistance calculation of Al-implanted resistive layers; Python numerical values of mobility and impact ionization coefficients are handed to [carrier transport](current.md) to compute carrier drift, thermal diffusion, and multi-dimensional path avalanche multiplication.

## Physics

### Permittivity and Effective Mass

The static relative permittivity of a semiconductor determines the electrostatic potential distribution for a given space charge and the geometric capacitance, while the electron and hole effective masses characterize the inertial response of carriers to external forces in the periodic lattice potential. Material permittivity and effective masses are given by scaling free-space reference constants:

$$\varepsilon = \varepsilon_r \varepsilon_0, \qquad m_n^* = \left(\frac{m_n^*}{m_e}\right) m_e, \qquad m_p^* = \left(\frac{m_p^*}{m_e}\right) m_e \tag{1}$$

where:

- $\varepsilon$: material permittivity, in $\text{F/cm}$ in DEVSIM field solving and in $\text{F/m}$ in parallel-plate capacitance estimation;
- $\varepsilon_r$: dimensionless relative permittivity (`RELATIVE_PERMITTIVITY` and `Material.permittivity` in code), equal to `11.9` for `"Si"`, `9.76` for `"SiC"` (4H-SiC, along the $c$-axis), and `5.7` for `"Diamond"`;
- $\varepsilon_0$: vacuum permittivity, taken as $8.8541878128\times 10^{-12}\ \text{F/m}$ (CODATA 2018; in DEVSIM field solving, $8.8541878128\times 10^{-14}\ \text{F/cm}$ in $\text{F/cm}$);
- $m_e$: free electron rest mass, taken as $9.109\times 10^{-31}\ \text{kg}$ in code;
- $m_n^*, m_p^*$: electron and hole effective masses, $\text{kg}$ (`Material.electron_mass` and `Material.hole_mass` in code).

Basic physical properties and default models for each material in `Material.mat_database` (`material.py`) are listed below:

| Material Name (`mat_name`) | Relative Permittivity `RELATIVE_PERMITTIVITY` | Electron Effective Mass `electron_mass` ($\text{kg}$) | Hole Effective Mass `hole_mass` ($\text{kg}$) | Default `mobility_model` | Default `avalanche_model` |
| --- | --- | --- | --- | --- | --- |
| `"Si"` | `11.9` | `0.26 * m_e` | `0.386 * m_e` | `"Selberherr"` | `"vanOverstraeten"` |
| `"SiC"` | `9.76` | `0.29 * m_e` | `1.0 * m_e` | `"Das"` | `"Hatakeyama"` |
| `"Diamond"` | `5.7` | Not set | Not set | `"Pernegger"` | `None` |

Relative permittivity is defined in the global dictionary `RELATIVE_PERMITTIVITY` in `material.py` and assigned to `self.permittivity` in `Material(mat_name).mat_database()`; effective masses are assigned to `self.electron_mass` and `self.hole_mass` in `Material.mat_database()` (4H-SiC longitudinal effective masses for `"SiC"`, unset for `"Diamond"`). In call relationships, `Detector.capacitance` (`src/raser/core/device/build_device.py`) in [device.md](device.md) reads `Material(self.material).permittivity` to estimate parallel-plate junction capacitance; `CreateSiliconConstant`, `CreateSiliconCarbideConstant`, and `CreateDiamondConstant` (`src/raser/core/field/create_parameter.py`) in [field.md](field.md) read `RELATIVE_PERMITTIVITY` to set DEVSIM region parameters `eps` and `Permittivity`; and `capacitances` (`src/raser/core/field/solver_section.py`) in [field.md](field.md) reads `Material(MyDetector.material).permittivity` to convert contact charges computed in vacuum permittivity for weighting fields into mutual capacitance per unit length ($\text{F/cm}$) for periodic strip electrodes. The relative permittivity of silicon is from Ref. [1] (Appendix G).

### Mobility

At low electric fields, lattice phonon scattering (`L`) and ionized impurity scattering (`I`) jointly determine the low-field mobility $\mu_{LI}$; under high-field driving (`F`), the drift velocity approaches the saturation velocity $v_{\text{sat}}$, causing the effective mobility $\mu(T, N_{\text{eff}}, E)$ to decrease with field strength. Approximation: mobility is determined only by these three mechanisms; carrier-carrier scattering (`C`) and surface scattering (`S`) are omitted. Define the dimensionless temperature normalized to $300\ \text{K}$ as:

$$t = \frac{T}{300} \tag{2}$$

For silicon (`"Si"`) under the default `"Selberherr"` model, the low-field mobility takes the Caughey–Thomas form, and high-field saturation is given separately for holes ($\beta_p = 1.0$) and electrons ($\beta_n = 2$):

$$\mu_{LI} = \mu_{\min} + \frac{\mu_L - \mu_{\min}}{1 + \bigl(|N_{\text{eff}}| / C_{\text{ref}}\bigr)^{\alpha}} \tag{3}$$

$$\mu_p(T, N_{\text{eff}}, E) = \frac{\mu_{LI,p}}{1 + \mu_{LI,p} E / v_{\text{sat},p}} \tag{4}$$

$$\mu_n(T, N_{\text{eff}}, E) = \frac{2\mu_{LI,n}}{1 + \Bigl[1 + \bigl(2\mu_{LI,n} E / v_{\text{sat},n}\bigr)^{\beta_n}\Bigr]^{1/\beta_n}} \tag{5}$$

For 4H silicon carbide (`"SiC"`) under the default `"Das"` model, the numerator of the low-field impurity-scattering term uses $\mu_L$ directly (without subtracting $\mu_{\min}$), and high-field saturation uses the Canali form; the default `"Pernegger"` model of diamond (`"Diamond"`) takes $\mu_{LI} = \mu_L$, independent of temperature and doping, and its high-field saturation is Eq. (7) with $\beta = 1$:

$$\mu_{LI} = \mu_{\min} + \frac{\mu_L}{1 + \bigl(|N_{\text{eff}}| / C_{\text{ref}}\bigr)^{\alpha}} \tag{6}$$

$$\mu(T, N_{\text{eff}}, E) = \frac{\mu_{LI}}{\Bigl[1 + \bigl(\mu_{LI} E / v_{\text{sat}}\bigr)^{\beta}\Bigr]^{1/\beta}} \tag{7}$$

For silicon (`"Si"`) under the alternative `"Reggiani"` model, the code distinguishes donor concentration $N_D = \max(N_{\text{eff}}, 0)$ and acceptor concentration $N_A = \max(-N_{\text{eff}}, 0)$ by the sign of the input net doping `input_doping`, and includes a second-stage drop term $\mu_1$ at ultra-high doping:

$$\mu_0 = \frac{\mu_{0,d} N_D + \mu_{0,a} N_A}{N_D + N_A}, \qquad \mu_1 = \frac{\mu_{1,d} N_D + \mu_{1,a} N_A}{N_D + N_A} \tag{8}$$

$$\mu_{LI} = \mu_0 + \frac{\mu_L - \mu_0}{1 + (N_D / C_{r,d})^{\alpha_d} + (N_A / C_{r,a})^{\alpha_a}} - \frac{\mu_1}{1 + (N_D / C_{s,d} + N_A / C_{s,a})^2} \tag{9}$$

$$\mu_p(T, N_{\text{eff}}, E) = \frac{\mu_{LI,p}}{\Bigl[1 + \bigl(\mu_{LI,p} E / v_{\text{sat},p}\bigr)^{\beta_{p,1} + \beta_{p,2}}\Bigr]^{1/\beta_{p,1}}}, \qquad \mu_n(T, N_{\text{eff}}, E) = \frac{\mu_{LI,n}}{\Bigl[1 + \bigl(\mu_{LI,n} E / v_{\text{sat},n}\bigr)^{\beta_n}\Bigr]^{1/\beta_n}} \tag{10}$$

where:

- $T$: device temperature (`temperature`), $\text{K}$; $t = T/300$ is the dimensionless normalized temperature;
- $N_{\text{eff}}$: local effective net doping concentration (`input_doping`), $\text{cm}^{-3}$; $N_D, N_A$ are the donor and acceptor concentrations split by the sign of $N_{\text{eff}}$ in the `"Reggiani"` model, $\text{cm}^{-3}$;
- $E$: electric field magnitude (`electric_field`), $\text{V/cm}$;
- $\mu_L$: pure lattice phonon-scattering mobility, $\text{cm}^2/(\text{V}\cdot\text{s})$ (subscript $p$ for holes, $n$ for electrons);
- $\mu_{\min}, \mu_0, \mu_1$: baseline and correction mobilities in the heavy-doping limit, $\text{cm}^2/(\text{V}\cdot\text{s})$ (subscripts $d, a$ correspond to donors and acceptors);
- $C_{\text{ref}}, C_{r,d}, C_{r,a}, C_{s,d}, C_{s,a}$: characteristic reference doping concentrations for impurity scattering, $\text{cm}^{-3}$;
- $\alpha, \alpha_d, \alpha_a$: dimensionless impurity-scattering exponents;
- $v_{\text{sat}}$: high-field saturation drift velocity, $\text{cm/s}$;
- $\beta, \beta_{p,1}, \beta_{p,2}$: dimensionless transition exponents for high-field velocity saturation;
- $\mu_{LI}, \mu$: low-field doping-corrected mobility and total mobility including high-field saturation, $\text{cm}^2/(\text{V}\cdot\text{s})$.

All parameter values for the models selected by default for the three materials (`"Selberherr"`, `"Das"`, `"Pernegger"`, corresponding to Eqs. (3)–(7)) are listed below:

| Material and Model | Carrier (`charge`) | $\mu_L$ ($\text{cm}^2/(\text{V}\cdot\text{s})$) | $\mu_{\min}$ ($\text{cm}^2/(\text{V}\cdot\text{s})$) | $C_{\text{ref}}$ ($\text{cm}^{-3}$) | $\alpha$ (dimensionless) | $\beta$ (dimensionless) | $v_{\text{sat}}$ ($\text{cm/s}$) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `"Si"` / `"Selberherr"` | hole (`> 0`) | $460.0\,t^{-2.18}$ | $45.0\,t^{-0.45}$ | $2.23\times 10^{17}\,t^{3.2}$ | $0.72\,t^{0.065}$ | $1.0$ | $9.05\times 10^6\sqrt{\tanh(312.0/T)}$ |
| `"Si"` / `"Selberherr"` | electron (`<= 0`) | $1430.0\,t^{-2.0}$ | $80.0\,t^{-0.45}$ | $1.12\times 10^{17}\,t^{3.2}$ | $0.72\,t^{0.065}$ | $2$ | $1.45\times 10^7\sqrt{\tanh(155.0/T)}$ |
| `"SiC"` / `"Das"` | hole (`> 0`) | $124\,t^{-2}$ | $15.9$ | $1.76\times 10^{19}$ | $0.34$ | $1.213\,t^{0.17}$ | $2\times 10^7\,t^{0.52}$ |
| `"SiC"` / `"Das"` | electron (`<= 0`) | $947\,t^{-2}$ | $0$ | $1.94\times 10^{17}$ | $0.61$ | $1\cdot t^{0.66}$ | $2\times 10^7\,t^{0.87}$ |
| `"Diamond"` / `"Pernegger"` | hole (`> 0`) | $2064$ | $0$ | — | — | $1$ | $1.41\times 10^7$ |
| `"Diamond"` / `"Pernegger"` | electron (`<= 0`) | $1714$ | $0$ | — | — | $1$ | $0.96\times 10^7$ |

All parameter values for the alternative `"Reggiani"` model of silicon (corresponding to Eqs. (8)–(10)) are listed below:

| Parameter | Hole (`charge > 0`) | Electron (`charge <= 0`) | Unit |
| --- | --- | --- | --- |
| $\mu_L$ | $470.50\,t^{-2.16}$ | $1441.0\,t^{-2.45 + 0.07t}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\mu_{0,d}, \mu_{0,a}$ | $90.0\,t^{-1.3},\; 44.0\,t^{-0.8}$ | $62.2\,t^{-1.3},\; 132.0\,t^{-1.3}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\mu_{1,d}, \mu_{1,a}$ | $28.2\,t^{-2.0},\; 28.2\,t^{-0.2}$ | $48.6\,t^{-0.7},\; 73.5\,t^{-1.25}$ | $\text{cm}^2/(\text{V}\cdot\text{s})$ |
| $\alpha_d, \alpha_a$ | $0.77,\; 0.719$ | $0.68,\; 0.72$ | dimensionless |
| $C_{r,d}, C_{r,a}$ | $1.30\times 10^{18}\,t^{2.2},\; 2.45\times 10^{17}\,t^{3.1}$ | $8.30\times 10^{16}\,t^{3.65},\; 1.22\times 10^{17}\,t^{2.65}$ | $\text{cm}^{-3}$ |
| $C_{s,d}, C_{s,a}$ | $1.10\times 10^{18}\,t^{6.2},\; 6.10\times 10^{20}$ | $4\times 10^{20},\; 7\times 10^{20}$ | $\text{cm}^{-3}$ |
| $\beta_{p,1}$ or $\beta_n$ | $2\,t^{-0.2} + \dfrac{0.6 N_A^2}{N_A^2 + (8\times 10^{17})^2} + \dfrac{0.6 N_D^2}{N_D^2 + (10^{19})^2}$ | $2.1\,t^{-0.2} + \dfrac{2 N_A^2}{N_A^2 + (10^{19})^2} + \dfrac{3 N_D^2}{N_D^2 + (10^{19})^2}$ | dimensionless |
| $\beta_{p,2}$ | $0.15\,t + \dfrac{0.8 N_A^2}{N_A^2 + (8\times 10^{17})^2} + \dfrac{0.8 N_D^2}{N_D^2 + (10^{19})^2}$ | None | dimensionless |
| $v_{\text{sat}}$ | $9.1\times 10^6\,t^{-0.4}$ | $\dfrac{2.4\times 10^7}{1 + 0.8\exp(t/2)}$ | $\text{cm/s}$ |

Mobility calculation is implemented by `Material.cal_mobility(temperature, input_doping, charge, electric_field)` in `material.py`. Mobility models are registered by name and selected by name in the device file; each material has a default model: `"Selberherr"` for `"Si"`, `"Das"` for `"SiC"`, and `"Pernegger"` for `"Diamond"`. In call relationships:

- `CalCurrent.drift_all` (`src/raser/core/current/cal_current.py`) in [current.md](current.md) passes `Material(my_d.material).cal_mobility` to `advance` (`src/raser/core/current/drift.py`), evaluating the local mobility at each time step using the mobility model selected by the device to compute drift displacement and the Einstein thermal diffusion standard deviation;
- `collect_by_diffusion` (`src/raser/core/current/diffusion.py`) in [current.md](current.md) calls `Material(my_d.material).cal_mobility(my_d.temperature, neff, -1, 0)` to compute the zero-field electron mobility in field-free pixel sensors;
- `_fits` and `sheet_resistance` (`src/raser/core/field/implanted_aluminium.py`, called by `sheet_resistance` in `src/raser/core/field/circuit_parameters.py`) in [field.md](field.md) call `Material("SiC").cal_mobility(..., 1, 0)` to calibrate the measured Hall mobility reduction ratio `MOBILITY_LEFT` against the zero-field hole mobility of `"Das"` and compute the sheet resistance of Al-implanted 4H-SiC resistive layers;
- `Material.draw_velocity` (`material.py`) calls `self.cal_mobility` to plot electron and hole drift velocities versus electric field;
- when a silicon device's device file selects `"Reggiani"`, `Material("Si", mobility_model="Reggiani")` is constructed.

The `"Selberherr"` model for silicon is from Ref. [2], and the `"Reggiani"` model for silicon is from Ref. [3]; the `"Das"` model for 4H-SiC is from Ref. [19], with its doping parameters originating from Ref. [20], where electron $C_{\text{ref}}$ takes the original value $1.94\times 10^{17}\ \text{cm}^{-3}$ from Ref. [20] ($1.94\times 10^{19}$ in Ref. [19] is a typo) and hole $C_{\text{ref}}$ takes $1.76\times 10^{19}\ \text{cm}^{-3}$. The `"Pernegger"` model for diamond is from Ref. [22]: transient-current measurements of a $470\ \mu\text{m}$ thick single-crystal CVD diamond at room temperature with Am-241 α particles, at fields of $0.2$–$1.5\ \text{V}/\mu\text{m}$; $\mu_L$ and $v_{\text{sat}}$ are the fitted values of Eq. (7) of that paper.

### Impact Ionization Coefficients

Under high electric fields, drifting carriers acquire kinetic energy exceeding the band-gap ionization threshold within a free path and collide with the lattice to create secondary electron-hole pairs; the average number of secondary pairs generated per unit drift path length is the impact ionization coefficient $\alpha(E, T)$. Three models are implemented in code:

1. **van Overstraeten–de Man model (`"vanOverstraeten"`, default for `"Si"`)**: joins low-field and high-field Chynoweth laws at $E_0 = 4.0\times 10^5\ \text{V/cm}$, sets the coefficient to zero below the fit lower bound $1.75\times 10^5\ \text{V/cm}$, and introduces a temperature scaling factor $\gamma(T)$ via the optical phonon energy $\hbar\omega$:

$$\gamma(T) = \frac{\tanh\bigl(\hbar\omega / (2 k T_0)\bigr)}{\tanh\bigl(\hbar\omega / (2 k T)\bigr)} \tag{11}$$

$$\alpha(E, T) = \begin{cases} 0, & E < 1.75\times 10^5\ \text{V/cm} \\ \gamma(T)\,a_{\text{low}}\exp\!\left(-\dfrac{\gamma(T)\,b_{\text{low}}}{E}\right), & 1.75\times 10^5\ \text{V/cm} \le E \le E_0 \\ \gamma(T)\,a_{\text{high}}\exp\!\left(-\dfrac{\gamma(T)\,b_{\text{high}}}{E}\right), & E > E_0 \end{cases} \tag{12}$$

2. **Okuto–Crowell model (`"Okuto"`, alternative for `"Si"`)**: expresses the prefactor and critical field as linear functions of temperature relative to $T_0 = 300.0\ \text{K}$, and sets the coefficient to zero for fields not exceeding $1.0\times 10^5\ \text{V/cm}$:

$$\alpha(E, T) = \begin{cases} 0, & E \le 1.0\times 10^5\ \text{V/cm} \\ a\bigl[1 + c(T - T_0)\bigr] E^{\gamma_0} \exp\!\left(-\left(\dfrac{b\bigl[1 + d(T - T_0)\bigr]}{E}\right)^{\delta}\right), & E > 1.0\times 10^5\ \text{V/cm} \end{cases} \tag{13}$$

3. **Hatakeyama model (`"Hatakeyama"`, default for `"SiC"`)**: accounts for the hexagonal crystal anisotropy of 4H-SiC; when the electric field tilts by angle $\theta$ from $\langle 0001\rangle$ toward $\langle 11\bar{2}0\rangle$ (direction cosines `along_0001` $= \cos\theta$, `along_1120` $= \sin\theta$), effective coefficients are synthesized from the two principal-axis pairs $(a_{0001}, b_{0001})$ and $(a_{1120}, b_{1120})$, and set to zero for fields not exceeding $10^4\ \text{V/cm}$:

$$B = \left[\left(\frac{\sin\theta}{b_{1120}}\right)^2 + \left(\frac{\cos\theta}{b_{0001}}\right)^2\right]^{-1/2}, \qquad A = \ln\!\left(\frac{a_{0001}}{a_{1120}}\right) \tag{14}$$

$$a = a_{1120}^{(B\sin\theta / b_{1120})^2}\,a_{0001}^{(B\cos\theta / b_{0001})^2}, \qquad b(E) = B\sqrt{1 - A^2\left(\frac{B\sin\theta\cos\theta\,E}{b_{1120} b_{0001}}\right)^2} \tag{15}$$

$$\alpha(E, T) = \begin{cases} 0, & E \le 10^4\ \text{V/cm} \\ \gamma(T)\,a\exp\!\left(-\dfrac{\gamma(T)\,b(E)}{E}\right), & E > 10^4\ \text{V/cm} \end{cases} \tag{16}$$

where:

- $\alpha(E, T)$: impact ionization coefficient, $\text{cm}^{-1}$;
- $E$: electric field magnitude, $\text{V/cm}$; $T$: device temperature, $\text{K}$;
- $k$: Boltzmann constant, `BOLTZMANN_EV_PER_K` $= 8.617333262\times 10^{-5}\ \text{eV/K}$ (CODATA 2018);
- $\gamma(T)$: dimensionless temperature factor from optical phonon scattering; $\hbar\omega$ (`hbarOmega` in code) is the optical phonon energy, $\text{eV}$; $T_0$ is the reference temperature, $\text{K}$;
- $E_0$: low/high-field boundary in `"vanOverstraeten"`, $4.0\times 10^5\ \text{V/cm}$; $a_{\text{low}}, a_{\text{high}}$ are low-field and high-field prefactors, $\text{cm}^{-1}$; $b_{\text{low}}, b_{\text{high}}$ are low-field and high-field critical electric fields, $\text{V/cm}$;
- $\gamma_0, \delta$: electric-field exponents in `"Okuto"` (`_gamma` and `_delta` in code, dimensionless), equal to $1.0$ and $2.0$ respectively; $a$ is the prefactor, $\text{V}^{-1}$; $b$ is the critical electric field, $\text{V/cm}$; $c, d$ are temperature coefficients, $\text{K}^{-1}$;
- $\theta$: off-axis angle (`angle_deg`) of the electric field from $\langle 0001\rangle$ toward $\langle 11\bar{2}0\rangle$ in `"Hatakeyama"`, in degrees, defaulting to `OFF_AXIS_DEG = 4.0` (corresponding to a surface-normal planar device electric field on a $4^\circ$ off-axis 4H-SiC epitaxial wafer);
- $a_{0001}, a_{1120}$: 4H-SiC prefactors along $\langle 0001\rangle$ and $\langle 11\bar{2}0\rangle$, $\text{cm}^{-1}$; $b_{0001}, b_{1120}$ are the critical fields along those two axes, $\text{V/cm}$; $A$ (dimensionless), $B$ ($\text{V/cm}$), $a$ ($\text{cm}^{-1}$), and $b(E)$ ($\text{V/cm}$) are the synthesized parameters.

All parameter values for the three impact ionization models are listed below:

| Model | Common Parameters | Carrier | Carrier-Specific Parameters |
| --- | --- | --- | --- |
| `"vanOverstraeten"` | $E_{\text{th}} = 1.75\times 10^5\ \text{V/cm}$, $E_0 = 4.0\times 10^5\ \text{V/cm}$, $\hbar\omega = 0.063\ \text{eV}$, $T_0 = 293.0\ \text{K}$ | electron (`charges < 0`) | $a_{\text{low}} = 7.03\times 10^5\ \text{cm}^{-1}$, $a_{\text{high}} = 7.03\times 10^5\ \text{cm}^{-1}$, $b_{\text{low}} = 1.231\times 10^6\ \text{V/cm}$, $b_{\text{high}} = 1.231\times 10^6\ \text{V/cm}$ |
| `"vanOverstraeten"` | Same as above | hole (`charges > 0`) | $a_{\text{low}} = 1.582\times 10^6\ \text{cm}^{-1}$, $a_{\text{high}} = 6.71\times 10^5\ \text{cm}^{-1}$, $b_{\text{low}} = 2.036\times 10^6\ \text{V/cm}$, $b_{\text{high}} = 1.693\times 10^6\ \text{V/cm}$ |
| `"Okuto"` | $E_{\text{th}} = 1.0\times 10^5\ \text{V/cm}$, $T_0 = 300.0\ \text{K}$, $\gamma_0 = 1.0$, $\delta = 2.0$ | electron (`charges < 0`) | $a = 0.426\ \text{V}^{-1}$, $b = 4.81\times 10^5\ \text{V/cm}$, $c = 3.05\times 10^{-4}\ \text{K}^{-1}$, $d = 6.86\times 10^{-4}\ \text{K}^{-1}$ |
| `"Okuto"` | Same as above | hole (`charges > 0`) | $a = 0.243\ \text{V}^{-1}$, $b = 6.53\times 10^5\ \text{V/cm}$, $c = 5.35\times 10^{-4}\ \text{K}^{-1}$, $d = 5.67\times 10^{-4}\ \text{K}^{-1}$ |
| `"Hatakeyama"` | $E_{\text{th}} = 10^4\ \text{V/cm}$, $\theta = 4.0^\circ$ (`OFF_AXIS_DEG`), $\hbar\omega = 0.19\ \text{eV}$, $T_0 = 300.0\ \text{K}$ | electron (`charges < 0`) | $a_{0001} = 1.76\times 10^8\ \text{cm}^{-1}$, $a_{1120} = 2.10\times 10^7\ \text{cm}^{-1}$, $b_{0001} = 3.30\times 10^7\ \text{V/cm}$, $b_{1120} = 1.70\times 10^7\ \text{V/cm}$ |
| `"Hatakeyama"` | Same as above | hole (`charges > 0`) | $a_{0001} = 3.41\times 10^8\ \text{cm}^{-1}$, $a_{1120} = 2.96\times 10^7\ \text{cm}^{-1}$, $b_{0001} = 2.50\times 10^7\ \text{V/cm}$, $b_{1120} = 1.60\times 10^7\ \text{V/cm}$ |

The dictionary `VAN_OVERSTRAETEN` and the function `hatakeyama(carrier, angle_deg=OFF_AXIS_DEG)` are defined in `impact_ionization.py` (returning `Formula` objects with independent variables `["E", "T"]`), and the unified Python evaluation entry point is `Material.cal_coefficient(electric_field, charges, temperature)` in `material.py`. The default `avalanche_model` of `Material` is `"vanOverstraeten"` for `"Si"`, `"Hatakeyama"` for `"SiC"`, and `None` for `"Diamond"` (a code comment notes that undoped MIM diamond devices have no gain). The models each material can select are listed in `AVALANCHE_MODELS` in `material.py`: `"vanOverstraeten"` and `"Okuto"` for `"Si"`, `"Hatakeyama"` for `"SiC"`, none for `"Diamond"`. In call relationships:

- `CreateImpactModel_vanOvenstraeten` and `CreateImpactModel_Hatakeyama` (`src/raser/core/field/physics_avalanche.py`) in [field.md](field.md) call `VAN_OVERSTRAETEN[...].devsim(EDGE_FIELD_IN_THRESHOLDS, E=EDGE_FIELD, T="T")` and `hatakeyama(...).devsim(EDGE_FIELD_IN_THRESHOLDS, E=EDGE_FIELD, T="T")` (with default `OFF_AXIS_DEG = 4.0` degrees) to generate the DEVSIM continuity-equation edge models `Ion_coeff_n` and `Ion_coeff_p` for silicon and silicon carbide; when the device file sets `avalanche_model` to `"Okuto"`, `Silicon` regions still use `VAN_OVERSTRAETEN` for the edge model (`"Fine_exponential_models"`, `"Tunnel"`, `"sze"`, `"chynoweth"`, `"bologna"`, and `"sic_custom"` in that module are written directly inside `physics_avalanche.py`, see [field.md](field.md));
- `DevsimField._integrate_planar_gain` (`src/raser/core/field/devsim_field.py`) in [field.md](field.md) calls `Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient(abs(E), ±1, my_d.temperature)` to integrate along the 1D centerline depth profile for the steady-state planar multiplication factor (used by `CalCurrentGain._build_planar_gain_carriers` in [current.md](current.md));
- `CalCurrentGain._build_local_gain_carriers` (`src/raser/core/current/cal_current.py`) in [current.md](current.md) calls `Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient(field, charge_sign, my_d.temperature)` to integrate impact ionization coefficients piecewise along primary carrier drift paths in multi-dimensional fields.

The van Overstraeten–de Man model is from Ref. [4], the Okuto–Crowell model is from Ref. [5], and the Hatakeyama principal-axis parameters and off-axis synthesis formulas are from Refs. [6, 7]. The physical origin of the temperature factor $\gamma(T)$ introduced via the optical phonon energy $\hbar\omega$ is given in Ref. [16]; the formulation of `"vanOverstraeten"` using $\hbar\omega = 0.063\ \text{eV}$ is taken from Ref. [17]; and $\hbar\omega = 0.19\ \text{eV}$ for `"Hatakeyama"` is from Ref. [18], where it is given only for electrons while the code uses the same value for holes.

### Band Structure and Intrinsic Carrier Concentration

In a non-degenerate semiconductor in thermal equilibrium, the conduction-band effective density of states $N_c(T)$ and valence-band effective density of states $N_v(T)$ scale as $T^{1.5}$ with temperature and together with the band gap $E_g$ determine the intrinsic carrier concentration $n_i(T)$:

$$N_c(T) = N_{c0}\left(\frac{T}{T_{\text{ref}}}\right)^{1.5}, \qquad N_v(T) = N_{v0}\left(\frac{T}{T_{\text{ref}}}\right)^{1.5} \tag{17}$$

$$n_i(T) = \sqrt{N_c(T)\,N_v(T)}\,\exp\!\left(-\frac{E_g}{2 k T}\right) \tag{18}$$

where:

- $T$: temperature, $\text{K}$;
- $N_c(T), N_v(T)$: conduction and valence band effective densities of states, $\text{cm}^{-3}$; $N_{c0}, N_{v0}$ are the prefactors at reference temperature $T_{\text{ref}}$ ($300\ \text{K}$ for `"Si"` and `"Diamond"`, $1\ \text{K}$ for `"SiC"`);
- $E_g$: temperature-independent band gap, $\text{J}$ (obtained by multiplying the band gap in $\text{eV}$ by the CODATA 2018 elementary charge $1.602176634\times 10^{-19}\ \text{J/eV}$);
- $k$: Boltzmann constant, taken as the CODATA 2018 value $1.380649\times 10^{-23}\ \text{J/K}$ (corresponding to $8.617333262\times 10^{-5}\ \text{eV/K}$);
- $n_i(T)$: intrinsic carrier concentration, $\text{cm}^{-3}$.

Formulas and parameters for each material in `BAND_STRUCTURE` (`band_structure.py`) are listed below:

| Material | `N_c` ($\text{cm}^{-3}$) | `N_v` ($\text{cm}^{-3}$) | `E_g` ($\text{J}$) | $N_c, N_v$ at $300\ \text{K}$ ($\text{cm}^{-3}$) |
| --- | --- | --- | --- | --- |
| `"Si"` | `2.82e19*pow(T/300, 1.5)` | `1.83e19*pow(T/300, 1.5)` | `1.12*1.602176634e-19` | $2.82\times 10^{19},\; 1.83\times 10^{19}$ |
| `"SiC"` | `3.25e15*pow(T, 1.5)` | `4.8e15*pow(T, 1.5)` | `3.26*1.602176634e-19` | $1.69\times 10^{19},\; 2.49\times 10^{19}$ |
| `"Diamond"` | `1.8e19*pow(T/300, 1.5)` | `1.5e19*pow(T/300, 1.5)` | `5.47*1.602176634e-19` | $1.80\times 10^{19},\; 1.50\times 10^{19}$ |

This model is built by `_material` in `band_structure.py` as the dictionary `BAND_STRUCTURE[material]`, whose entries contain four `Formula` objects `"N_c"`, `"N_v"`, `"E_g"`, and `"n_i"` in the independent variable `["T"]`. In call relationships, `CreateSiliconConstant`, `CreateSiliconCarbideConstant`, and `CreateDiamondConstant` (`src/raser/core/field/create_parameter.py`) in [field.md](field.md) call `.value(T=T)` on the four `Formula` entries in `BAND_STRUCTURE[material]` to write the DEVSIM region parameters `N_c`, `N_v`, `E_g`, `n_i`, along with `n1 = n_i` and `p1 = n_i`; `free_holes` in `incomplete_ionization.py` of this package calls `BAND_STRUCTURE[material]["N_v"].value(T=temperature_k)` to compute the valence-band effective density of states (used by `implanted_aluminium.py` in [field.md](field.md) to compute the sheet resistance of Al-implanted 4H-SiC layers). The effective densities of states of 4H-SiC are derived from $N = 2 M_c (2\pi m^* k T / h^2)^{3/2}$ with $M_c = 3$ conduction-band valleys ($0.37\,m_0$ per valley) and valence-band hole mass $1.0\,m_0$, see Ref. [8] (Sec. 6).

### Dopants and Incomplete Ionization

Substitutional dopants can occupy crystallographically inequivalent lattice sites of different symmetry (such as hexagonal and cubic sites in 4H-SiC, each with fraction $0.5$), and at heavy doping the ionization energy decreases linearly with the cube root of total dopant concentration $N$ according to the Pearson–Bardeen relation; when the ionization energy is not negligible, each level is only partially ionized under Boltzmann statistics. The effective ionization energy $\Delta E_i(N)$, characteristic carrier concentration $n_{1,i}(T)$, and total ionized fraction $N_{\text{ion}}/N$ for the $i$-th site level are:

$$\Delta E_i(N) = \Delta E_{0,i} - \alpha_{\text{fall}}\,N^{1/3} \tag{19}$$

$$n_{1,i}(T) = N_{\text{band}}\exp\!\left(-\frac{\Delta E_i(N)}{k T}\right) \tag{20}$$

$$\frac{N_{\text{ion}}}{N} = \sum_{i} \begin{cases} \dfrac{f_i\,n_{1,i}(T)}{n_{1,i}(T) + g\,c}, & c > 0 \\ f_i, & c \le 0 \end{cases} \tag{21}$$

For a semiconductor layer containing a single-level acceptor concentration $N_A$ (partially ionized) and a fully ionized compensating donor concentration $N_D$, neglecting free electrons and intrinsic carrier concentration $n_i$, the free hole concentration $p$ solved from the charge-neutrality condition $p + N_D = N_A^-$, i.e., $p(p + N_D) = (N_A - N_D - p)\,p_1 / g$ (where $p_1 = N_v(T)\exp\!\left(-\Delta E(N_A)/(k T)\right)$), is:

$$p_{\text{freed}} = \frac{N_v(T)}{g}\exp\!\left(-\frac{\Delta E(N_A)}{k T}\right), \qquad p_{\text{taken}} = N_D + p_{\text{freed}} \tag{22}$$

$$p = \frac{\sqrt{p_{\text{taken}}^2 + 4\,p_{\text{freed}}(N_A - N_D)} - p_{\text{taken}}}{2} \tag{23}$$

where:

- $\Delta E_{0,i}, \Delta E_i(N)$: ionization energy of the $i$-th level (relative to the corresponding band edge) in the low-doping limit and at concentration $N$, $\text{eV}$;
- $f_i$: fraction of dopant atoms occupying the $i$-th site level (dimensionless, satisfying $\sum_i f_i = 1$);
- $\alpha_{\text{fall}}$: Pearson–Bardeen coefficient for concentration-dependent reduction of ionization energy (`fall_ev_cm` in code), $\text{eV}\cdot\text{cm}$;
- $N$: concentration of the dopant species (`concentration_cm3` or `acceptors_cm3`), $\text{cm}^{-3}$;
- $N_{\text{band}}$: effective density of states of the corresponding band ($N_c$ for donors, $N_v$ for acceptors), $\text{cm}^{-3}$;
- $n_{1,i}(T)$: characteristic carrier concentration of the $i$-th level, $\text{cm}^{-3}$;
- $c$: free carrier concentration (`carriers` in code; electron concentration $n$ for donors, hole concentration $p$ for acceptors), $\text{cm}^{-3}$; when $c \le 0$, complete ionization $f_i$ is returned directly to avoid $0/0$ if $n_{1,i}$ underflows to $0$ during low-temperature freeze-out;
- $g$: dopant level degeneracy factor (`degeneracy` in code, dimensionless), $2.0$ for donors and $4.0$ for acceptors;
- $k$: Boltzmann constant, `BOLTZMANN_EV_PER_K` $= 8.617333262\times 10^{-5}\ \text{eV/K}$;
- $T$: temperature (`T` or `temperature_k`), $\text{K}$;
- $N_A, N_D$: acceptor concentration (`acceptors_cm3`) and compensating donor concentration (`donors_cm3`), $\text{cm}^{-3}$;
- $\Delta E(N_A)$: effective ionization energy at acceptor concentration $N_A$ (computed by Eq. (19)), $\text{eV}$;
- $p_1$: characteristic hole concentration of the single-level acceptor $N_v(T)\exp\!\left(-\Delta E(N_A)/(k T)\right)$, $\text{cm}^{-3}$;
- $p_{\text{freed}}, p_{\text{taken}}, p$: reduced characteristic hole concentration ($p_1 / g$), its sum with compensating donors, and the resulting free hole concentration (`freed_cm3`, `taken_cm3`, and return value in code), $\text{cm}^{-3}$.

All material and dopant parameters registered in `DOPANTS` (`dopants.py`) are listed below:

| Material | Element | Type `kind` | Levels and Fractions `levels` ($(\Delta E_{0,i}\ [\text{eV}],\, f_i)$) | Degeneracy `degeneracy` | `fall_ev_cm` ($\text{eV}\cdot\text{cm}$) |
| --- | --- | --- | --- | --- | --- |
| `"Si"` | `"P"` | `"donor"` | `((0.046, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"As"` | `"donor"` | `((0.054, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"Sb"` | `"donor"` | `((0.043, 1.0),)` | `2.0` | `0.0` |
| `"Si"` | `"B"` | `"acceptor"` | `((0.044, 1.0),)` | `4.0` | `0.0` |
| `"SiC"` | `"N"` | `"donor"` | `((0.0533, 0.5), (0.0996, 0.5))` | `2.0` | `0.0` |
| `"SiC"` | `"P"` | `"donor"` | `((0.057, 0.5), (0.113, 0.5))` | `2.0` | `0.0` |
| `"SiC"` | `"Al"` | `"acceptor"` | `((0.216, 1.0),)` | `4.0` | `3e-8` |
| `"SiC"` | `"B"` | `"acceptor"` | `((0.311, 1.0),)` | `4.0` | `0.0` |
| `"Diamond"` | `"B"` | `"acceptor"` | `((0.3685, 1.0),)` | `4.0` | `0.0` |
| `"Diamond"` | `"N"` | `"donor"` | `((1.7, 1.0),)` | `2.0` | `0.0` |
| `"Diamond"` | `"P"` | `"donor"` | `((0.60, 1.0),)` | `2.0` | `0.0` |

The dopant table is defined in `DOPANTS` and `Dopant` in `dopants.py`; the ionized-fraction formula constructor `ionized_fraction(material, element, concentration_cm3=0.0)` (returning a `Formula` in independent variables `["carriers", "N_band", "T"]`) and the free-hole solver `free_holes(material, element, acceptors_cm3, donors_cm3, temperature_k)` are defined in `incomplete_ionization.py`. In call relationships, `holes` (`src/raser/core/field/implanted_aluminium.py`, called by `sheet_resistance`, which is in turn used by `src/raser/core/field/circuit_parameters.py` to build resistive-layer equivalent circuits) in [field.md](field.md) calls `free_holes("SiC", "Al", acceptors_cm3, donors_cm3, temperature_k)` to compute the free hole concentration in Al-implanted 4H-SiC layers. Degeneracy factors, silicon dopant ionization energies, and Boltzmann incomplete-ionization statistics are from Ref. [1] (Sec. 1.4.3); the $N^{1/3}$ ionization-energy lowering law is from Ref. [9]; 4H-SiC site-resolved ionization energies and incomplete ionization are reviewed in Ref. [8] (Secs. 10.1–10.2, where nitrogen donors follow the fit of Schöner et al. and boron uses only the shallow acceptor level $311\ \text{meV}$); the concentration dependence of the Al acceptor ionization energy and compensated charge-neutrality equation in 4H-SiC are from Ref. [10]; and the ionization energies of boron, nitrogen, and phosphorus in diamond are from Refs. [11, 12, 13], respectively.

### SRH Recombination

Non-equilibrium electrons and holes undergo indirect recombination or thermal generation via localized deep-level trap centers in the band gap (Shockley-Read-Hall process); in 4H-SiC at high electric fields, the local field also introduces a Hurkx trap-assisted tunneling (TAT) field-enhancement factor with a saturation field cap. The SRH net recombination rate $U_{\text{SRH}}$ and the TAT field-enhancement factor $\Gamma_{\text{TAT}}(E, F_{\text{sat}})$ are:

$$U_{\text{SRH}} = \frac{n p - n_i^2}{\tau_p (n + n_1) + \tau_n (p + p_1)} \tag{24}$$

$$\Gamma_{\text{TAT}}(E, F_{\text{sat}}) = \begin{cases} 2\sqrt{3\pi}\,\dfrac{E}{F_\gamma}\exp\!\left[\left(\dfrac{E}{F_\gamma}\right)^2\right], & E < F_{\text{sat}} \\ 2\sqrt{3\pi}\,\dfrac{F_{\text{sat}}}{F_\gamma}\exp\!\left[\left(\dfrac{F_{\text{sat}}}{F_\gamma}\right)^2\right], & E \ge F_{\text{sat}} \end{cases} \tag{25}$$

where:

- $U_{\text{SRH}}$: SRH net recombination rate, $\text{cm}^{-3}\cdot\text{s}^{-1}$;
- $n, p$: electron and hole concentrations, $\text{cm}^{-3}$;
- $n_i$: intrinsic carrier concentration, $\text{cm}^{-3}$;
- $n_1, p_1$: electron and hole concentrations when the Fermi level coincides with the trap level, $\text{cm}^{-3}$; the code places traps at the intrinsic level, setting $n_1 = p_1 = n_i$ (a comment notes that if traps were at midgap, $n_1/p_1 = N_c/N_v$);
- $\tau_n, \tau_p$: electron and hole SRH lifetimes, $\text{s}$; in `SRH_LIFETIME`, `"Si"` uses $\tau_n = 7\times 10^{-3}\ \text{s}$, $\tau_p = 7\times 10^{-3}\ \text{s}$, `"SiC"` uses $\tau_n = 2.5\times 10^{-6}\ \text{s}$, $\tau_p = 0.5\times 10^{-6}\ \text{s}$, and `"Diamond"` uses $\tau_n = 5.6\times 10^{-7}\ \text{s}$, $\tau_p = 2.4\times 10^{-7}\ \text{s}$, all temperature-independent constants;
- $\Gamma_{\text{TAT}}$: dimensionless trap-assisted tunneling field-enhancement factor (`TAT_FIELD_ENHANCEMENT` in code);
- $E$: electric field magnitude, $\text{V/cm}$;
- $F_{\text{sat}}$: upper saturation field cap for TAT enhancement, $\text{V/cm}$, defaulting to `TAT_SATURATION_FIELD = 1e5` $\text{V/cm}$;
- $F_\gamma$: characteristic TAT field, fixed in code to `F_gamma = 3.9e4` $\text{V/cm}$;
- $\pi$: approximate value of pi, fixed in code to `pi = 3.14159`.

`SRH` (a `Formula` in independent variables `["n", "p", "n_i", "n1", "p1", "tau_n", "tau_p"]`), `SRH_LIFETIME`, `TAT_SATURATION_FIELD`, and `TAT_FIELD_ENHANCEMENT` (a `Formula` in independent variables `["E", "F_sat"]`) are all defined in `recombination.py`. In call relationships:

- `CreateSiliconConstant`, `CreateSiliconCarbideConstant`, `CreateDiamondConstant`, and `CreateTAT` (`src/raser/core/field/create_parameter.py`) in [field.md](field.md) read `SRH_LIFETIME` to set DEVSIM region parameters `taun` and `taup` (while setting `n1` and `p1` to `n_i`), and in `"SiliconCarbide"` regions set `F_sat` to `TAT_SATURATION_FIELD` (overridable via the `parameter` key in the device file);
- `CreateSRH` (`src/raser/core/field/physics_drift_diffusion.py`) in [field.md](field.md) calls `SRH.devsim(n="Electrons", p="Holes", n_i="n_i", n1="n1", p1="p1", tau_n="taun", tau_p="taup")` to create node model `USRH`, which is added to the additional recombination term `U_const` (and, when irradiation is enabled, the irradiation-defect recombination rate `U_r` generated by `src/raser/core/field/physics_irradiation.py`, see [field.md](field.md)) to form the continuity-equation source terms `ElectronGeneration` and `HoleGeneration`;
- `CreateFESRH` (`src/raser/core/field/physics_avalanche.py`) in [field.md](field.md), when impact ionization is enabled in a `"SiliconCarbide"` region, calls `TAT_FIELD_ENHANCEMENT.devsim(E="abs(ElectricField)", F_sat="F_sat")` to build the edge model `R_TAT = (TAT_FIELD_ENHANCEMENT)*(U_const@n1)` and subtracts `R_TAT` from `Ion_coeff_rate`.

The SRH recombination formula is from Ref. [1] (Sec. 1.5.4) and the original paper [14], and the Hurkx trap-assisted tunneling field-enhancement formula is from Ref. [15]; the electron lifetime $2.5\ \mu\text{s}$ of 4H-SiC is from Ref. [19], and the hole lifetime $0.5\ \mu\text{s}$ is from Ref. [21] (confirmed by our group's time-resolved photoluminescence measurements).

## Algorithms

### Built-in Constants

The table below lists all built-in physical constants and hardcoded numerical parameters across the modules of `src/raser/core/model/`. The device JSON key `"parameter": {"name": ..., "value": ...}` is applied in `create_parameter` of [field.md](field.md) after region constants are written and can override any single DEVSIM region parameter; consequently, `TAT_SATURATION_FIELD` (DEVSIM parameter `"F_sat"`) as well as the DEVSIM copies of `RELATIVE_PERMITTIVITY`, `BAND_STRUCTURE`, and `SRH_LIFETIME` (`eps`, `Permittivity`, `N_c`, `N_v`, `E_g`, `n_i`, `n1`, `p1`, `taun`, `taup`) can be overridden during field solving, whereas Python-side calculations such as `Material` and `free_holes` use the values in the table. All remaining constants are hardcoded:

| Constant or Built-in Parameter | `"Si"` | `"SiC"` | `"Diamond"` | Common / Fixed Value | Unit | Location and Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `RELATIVE_PERMITTIVITY` | `11.9` | `9.76` | `5.7` | — | dimensionless | `material.py`, static relative permittivity $\varepsilon_r$ |
| `m_e` | — | — | — | `9.109e-31` | $\text{kg}$ | `material.py` (`Material.mat_database`), free electron rest mass |
| `electron_mass` | `0.26 * m_e` | `0.29 * m_e` | Not set | — | $\text{kg}$ | `material.py`, electron effective mass |
| `hole_mass` | `0.386 * m_e` | `1.0 * m_e` | Not set | — | $\text{kg}$ | `material.py`, hole effective mass |
| `x_step`, sample count | — | — | — | `1000`, `1001` | $\text{V/cm}$, points | `material.py` (`Material.draw_velocity`), electric-field step and number of points plotted ($0$ to $10^6\ \text{V/cm}$) |
| `BOLTZMANN_EV_PER_K` | — | — | — | `8.617333262e-5` | $\text{eV/K}$ | `impact_ionization.py` (also imported by `incomplete_ionization.py`), CODATA 2018 Boltzmann constant |
| `_VAN_OVERSTRAETEN` thresholds and constants | $E_{\text{th}} = 1.75\times 10^5$, $E_0 = 4.0\times 10^5$, $\hbar\omega = 0.063$, $T_0 = 293.0$ | — | — | — | $\text{V/cm}$, $\text{V/cm}$, $\text{eV}$, $\text{K}$ | `impact_ionization.py`, van Overstraeten–de Man ionization threshold, low/high-field boundary, optical phonon energy, and reference temperature |
| `"Okuto"` thresholds and constants | $E_{\text{th}} = 1.0\times 10^5$, $T_0 = 300.0$, `_gamma = 1.0`, `_delta = 2.0` | — | — | — | $\text{V/cm}$, $\text{K}$, dimensionless, dimensionless | `material.py` (`Material.cal_coefficient`), Okuto–Crowell ionization threshold, reference temperature, and exponents |
| `_HATAKEYAMA` thresholds and constants | — | $E_{\text{th}} = 10^4$, `OFF_AXIS_DEG = 4.0`, $\hbar\omega = 0.19$, $T_0 = 300.0$ | — | — | $\text{V/cm}$, deg, $\text{eV}$, $\text{K}$ | `impact_ionization.py`, Hatakeyama ionization threshold, off-axis angle, optical phonon energy, and reference temperature |
| `_K_J_PER_K`, band-gap conversion factor | — | — | — | `1.380649e-23`, `1.602176634e-19` | $\text{J/K}$, $\text{J/eV}$ | `band_structure.py`, CODATA 2018 Boltzmann constant and elementary-charge conversion factor used for $n_i(T)$ and $E_g$ |
| `SRH_LIFETIME` (`tau_n`, `tau_p`) | `7e-3`, `7e-3` | `2.5e-6`, `0.5e-6` | `5.6e-7`, `2.4e-7` | — | $\text{s}$ | `recombination.py`, default electron and hole SRH lifetimes |
| `TAT_SATURATION_FIELD` | — | `1e5` | — | — | $\text{V/cm}$ | `recombination.py`, default saturation field for 4H-SiC trap-assisted tunneling enhancement (overridable as `"F_sat"` via the device file `parameter` key) |
| `F_gamma`, `pi` | — | `3.9e4`, `3.14159` | — | — | $\text{V/cm}$, dimensionless | `recombination.py` (`TAT_FIELD_ENHANCEMENT`), TAT characteristic field and pi constant |

### Dual-Target Formula Compilation and Evaluation (`formula.py`)

So that carrier drift (Python numerical evaluation) and the DEVSIM field solver (symbolic expressions and automatic differentiation `diff`) share the same physical definitions, `Formula(text, variables, **parameters)` writes each formula once in a subset of DEVSIM expressions (`abs`, `exp`, `log`, `pow`, `sqrt`, `tanh`, `ifelse(condition, a, b)`, and power operator `^`), and initializes and evaluates as follows:

1. **Lexical parameter substitution (`_substitute` and `Formula.__init__`)**: converts `variables` to a tuple `self.variables = tuple(variables)`. Iterates through `(name, value)` in the order passed in `**parameters`, matching standalone identifiers with the regex `(?<![\w.@])<name>(?![\w@])` (excluding partial words adjacent to decimal points or DEVSIM node suffixes `@n0`/`@n1`), and replaces them with parenthesized `f"({value})"` into `self.text`. Because substitution runs sequentially, earlier string parameters may reference independent variables as well as parameters listed after them (for example, `n_i` in `BAND_STRUCTURE` expands first into sub-expressions for `N_c`, `N_v`, `E_g` in terms of `T`, and `_VAN_OVERSTRAETEN` expands the `gamma` expression before substituting numeric values for `hbarOmega`, `k`, and `T0`).
2. **Recursive `ifelse` rewriting and Python bytecode compilation (`_closing` and `_python`)**: searches `self.text` for `ifelse(` using regex `(?<!\w)ifelse\(`:
   - If not found, replaces `^` with Python's power operator `**` and returns;
   - If found, records the left-parenthesis index `opening = match.end() - 1` and calls `_closing(text, opening)` to scan character by character tracking parenthesis depth `depth` (`+1` on `(`, `-1` on `)`, recording top-level comma positions at `depth == 1`, and returning the right-parenthesis index `closing` and comma list `commas` when `depth == 0`). If the string ends before `depth` returns to zero, raises `ValueError: unbalanced parentheses in <text>`; if `len(commas) != 2`, raises `ValueError: ifelse takes three arguments in <text>`. Recursively calls `_python` on `condition`, `if_true`, `if_false`, and the substrings before and after the call, assembling the Python ternary expression `(({if_true}) if ({condition}) else ({if_false}))`.
   - Calls `compile(_python(self.text), "<formula>", "eval")` to produce the bytecode object `self._code`.
3. **Python numerical evaluation (`Formula.value(**variables)`)**: verifies `set(variables) == set(self.variables)`; if not, raises `ValueError: the formula takes <self.variables>, not <tuple(variables)>`. Evaluates `eval(self._code, ..., variables)` in a restricted globals dict `{"__builtins__": {}, **_FUNCTIONS}` (exposing only `abs`, `math.exp`, `math.log`, `math.pow`, `math.sqrt`, and `math.tanh` in `_FUNCTIONS`). Because `ifelse` is translated into a Python ternary expression, evaluation short-circuits and executes only the taken branch (for example, returning `0` directly when $E = 0$ without triggering division by zero in `b / E` of the other branch).
4. **DEVSIM symbolic expression generation (`Formula.devsim(in_conditions=None, **variables)`)**: first verifies `set(variables) == set(self.variables)`, raising `ValueError: the formula takes <self.variables>, not <tuple(variables)>` on mismatch.
   - If an `in_conditions` dict is provided, first calls `_substitute_in_conditions(self.text, in_conditions)`: recursively locates every `ifelse(condition, if_true, if_false)` (likewise raising `ValueError` on unbalanced parentheses or non-3 argument count) and runs `_substitute` **only within the first argument `condition`** using the expressions in `in_conditions`;
   - Next runs `_substitute(..., variables)` on the entire expression to replace remaining independent variable names with solver variable names or expressions.
   - This step supports zero-field protection in DEVSIM edge models (`physics_avalanche.py` in [field.md](field.md) passes `in_conditions={"E": "abs(ElectricField)"}` and `E="abs(ElectricField)+1"`): DEVSIM evaluates both branches of `ifelse`, so `b / E` inside the branches uses `abs(ElectricField)+1` to avoid division by zero while threshold comparisons in the condition retain exact `abs(ElectricField) >= 1.75e5` or `abs(ElectricField) > 1e4`.

### Material Initialization, Mobility, and Impact Ionization Calculation (`material.py`, `impact_ionization.py`)

1. **Constructing a `Material` instance (`Material.__init__` and `mat_database`)**: stores `self.mat_name = mat_name` and calls `self.mat_database()` to populate `permittivity`, `hole_mass`, `electron_mass`, default `avalanche_model`, and default `mobility_model` across three `if` branches for `"Si"`, `"SiC"`, and `"Diamond"`. If constructor argument `mobility_model != None`, overrides `self.mobility_model`; if `avalanche_model != None`, overrides `self.avalanche_model`. `mat_name` takes one of `"Si"`, `"SiC"`, or `"Diamond"`.
2. **Computing carrier mobility (`Material.cal_mobility(temperature, input_doping, charge, electric_field)`)**:
   - Sets $T = \text{temperature}$, $t = T / 300$, $E = \text{electric\_field}$, and $N_{\text{eff}} = \text{input\_doping}$.
   - For `mat_name == 'SiC'` with `mobility_model == "Das"`, `mat_name == 'Diamond'` with `mobility_model == "Pernegger"`, or `mat_name == 'Si'` with `mobility_model == "Selberherr"`: takes `Neff = abs(Neff)`, then selects `charge > 0` (hole) or `charge <= 0` (electron), evaluates Eqs. (3)–(7) with the corresponding parameters, and returns `mu`.
   - For `mat_name == 'Si'` with `mobility_model == "Reggiani"`: sets `N_D = Neff, N_A = 0` when `Neff >= 0`, otherwise `N_A = -Neff, N_D = 0`; then selects `charge > 0` or `charge <= 0`, evaluates Eqs. (8)–(10), and returns `mu`.
3. **Computing impact ionization coefficients (`Material.cal_coefficient(electric_field, charges, temperature)` and `hatakeyama`)**:
   - Checks `self.avalanche_model not in AVALANCHE_MODELS[self.mat_name]`; if true (including `None` for `"Diamond"`, and a model of another material such as `"vanOverstraeten"` selected for `"Diamond"` or `"SiC"`), raises `ValueError: Avalanche model <self.avalanche_model> is not defined for <self.mat_name>`.
   - Initializes `coefficient = 0.0` and sets $E = \text{electric\_field}$, $T = \text{temperature}$. `charges` is `-1` (electron) or `+1` (hole); when `charges` is `0`, `coefficient` stays `0.0`.
   - For `avalanche_model == 'vanOverstraeten'`: calls `VAN_OVERSTRAETEN["electron"].value(E=E, T=T)` or `VAN_OVERSTRAETEN["hole"].value(E=E, T=T)` according to the sign of `charges`, returning the result of Eqs. (11)–(12).
   - For `avalanche_model == 'Okuto'`: selects electron or hole parameters $a, b, c, d$ according to the sign of `charges`; computes `coefficient` by Eq. (13) if $E > 1.0\times 10^5\ \text{V/cm}$, otherwise sets `coefficient = 0.0`.
   - For `avalanche_model == 'Hatakeyama'`: calls the `@functools.cache`-cached `hatakeyama("electron")` or `hatakeyama("hole")` (with default `angle_deg = OFF_AXIS_DEG`) according to the sign of `charges`. On the first call for a given `(carrier, angle_deg)`, `hatakeyama` converts `angle_deg` (default `4.0` degrees) to radians, computes `along_0001 = cos(angle)` and `along_1120 = sin(angle)`, precomputes floating-point constants `B`, `a`, `A` and sub-expression string `b` via Eqs. (14)–(15), and builds and returns a `Formula` object; `.value(E=E, T=T)` then evaluates Eq. (16). At the default $4^\circ$ off-axis angle, $b(E)$ in Eq. (15) is defined for $E \lesssim 1.16\times 10^8\ \text{V/cm}$ (electrons) and $E \lesssim 9.44\times 10^7\ \text{V/cm}$ (holes).
4. **Plotting drift velocity curves (`Material.draw_velocity(temperature, Neff)`)**:
   - Checks if `plt is None` (`matplotlib` not installed); if so, raises `RuntimeError: matplotlib is required for draw_velocity`.
   - For `i in range(1001)` with step `x_step = 1000` ($x = 1000\,i\ \text{V/cm}$, spanning $0$ to $10^6\ \text{V/cm}$), computes electron drift velocity `y_e = x * self.cal_mobility(temperature, Neff, -1, x)` and hole drift velocity `y_h = x * self.cal_mobility(temperature, Neff, +1, x)` ($\text{cm/s}$).
   - Creates a log-log plot (`plt.xscale("log")`, `plt.yscale("log")`), plots the `"electron"` and `"hole"` velocity curves, obtains the output directory via `output(__file__, "model")`, and saves the figure to `<output_directory>/<mat_name>Mobility<mobility_model>.png`.

### Incomplete Ionization and Free Hole Concentration Solving (`incomplete_ionization.py`)

1. **Concentration-adjusted levels (`_levels(dopant, concentration_cm3)`)**: computes the Pearson–Bardeen ionization-energy reduction $\Delta E_{\text{fall}} = \text{dopant.fall\_ev\_cm} \cdot N^{1/3}$ ($\text{eV}$) and transforms each level $(\Delta E_{0,i}, f_i)$ in `dopant.levels` into $(\Delta E_{0,i} - \Delta E_{\text{fall}}, f_i)$.
2. **Ionized-fraction `Formula` generation (`ionized_fraction(material, element, concentration_cm3=0.0)`)**: looks up `Dopant` from `DOPANTS[material][element]` (raising `KeyError` for unknown materials or elements). Iterating over the $i$-th level from `_levels(dopant, concentration_cm3)`, forms the $n_{1,i}$ sub-expression `N_band*exp(-E<i>/(k*T))` and the zero-carrier underflow-protected term `ifelse(carriers > 0, f<i>*N_band*exp(-E<i>/(k*T))/(N_band*exp(-E<i>/(k*T)) + g*carriers), f<i>)`, joins all level terms with `" + "`, and returns a `Formula` in independent variables `["carriers", "N_band", "T"]`.
3. **Free hole concentration in a compensated acceptor layer (`free_holes(material, element, acceptors_cm3, donors_cm3, temperature_k)`)**:
   - Looks up `dopant = DOPANTS[material][element]` (raising `KeyError` for unknown material or element).
   - Checks `dopant.kind != "acceptor" or len(dopant.levels) != 1`; if the dopant is not a single-level acceptor (e.g. donors `"N"`, `"P"`), raises `ValueError: <element> in <material> is not an acceptor of one level`.
   - Calls `_levels(dopant, acceptors_cm3)` to obtain the sole ionization energy `level_ev` ($\text{eV}$), and calls `BAND_STRUCTURE[material]["N_v"].value(T=temperature_k)` to compute the valence-band effective density of states $N_v(T)$ ($\text{cm}^{-3}$).
   - Evaluates `freed_cm3`, `taken_cm3`, and the positive root of the quadratic in Eqs. (22)–(23) and returns the free hole concentration ($\text{cm}^{-3}$). Approximation: valid above donor freeze-out where compensating donors $N_D$ are fully ionized, with free electrons and intrinsic carrier concentration $n_i$ neglected, for p-type regions with $N_A \ge N_D$.

## Software Implementation

### Module and Function Responsibilities

- `formula.py`: provides the `Formula` class compiling DEVSIM expression text into both a Python evaluator and DEVSIM symbolic expression strings, along with lexical substitution `_substitute`, parenthesis-matching scanner `_closing`, Python ternary converter `_python`, and conditional-branch substitution `_substitute_in_conditions`.
- `material.py`: defines the static relative permittivity dictionary `RELATIVE_PERMITTIVITY`, the `Material` class (`mat_database`, `cal_mobility`, `cal_coefficient`, `draw_velocity`), and the script entry `main` that plots drift velocity curves for `"Si"` ($300\ \text{K}, 5\times 10^{12}\ \text{cm}^{-3}$) and `"SiC"` ($300\ \text{K}, 5\times 10^{13}\ \text{cm}^{-3}$).
- `impact_ionization.py`: defines the Boltzmann constant `BOLTZMANN_EV_PER_K`, the default 4H-SiC off-axis angle `OFF_AXIS_DEG`, the silicon van Overstraeten–de Man formula dictionary `VAN_OVERSTRAETEN`, and the cached 4H-SiC Hatakeyama formula generator `hatakeyama`.
- `band_structure.py`: constructs `BAND_STRUCTURE` via `_material` with conduction-band density of states `"N_c"`, valence-band density of states `"N_v"`, band gap `"E_g"`, and intrinsic carrier concentration `"n_i"` formulas for silicon, 4H-SiC, and diamond.
- `dopants.py`: defines the dopant dataclass `Dopant`, helper constructors `_donor` and `_acceptor`, and the dopant-level registry `DOPANTS` for the three materials.
- `incomplete_ionization.py`: provides the concentration-adjusted level helper `_levels`, ionized-fraction formula generator `ionized_fraction`, and compensated p-type free-hole solver `free_holes`.
- `recombination.py`: defines the SRH recombination formula `SRH`, the default carrier lifetime dictionary `SRH_LIFETIME` for the three materials, the default trap-assisted tunneling saturation field `TAT_SATURATION_FIELD`, and the field-enhancement formula `TAT_FIELD_ENHANCEMENT`.

### Core Data Structures

- `Formula` (`formula.py`): cross-solver physical formula object containing the tuple of independent variable names `variables` (`tuple[str, ...]`, with units determined by the physical quantity: `E` and `F_sat` in $\text{V/cm}$, `T` in $\text{K}$, `n`, `p`, `n_i`, `n1`, `p1`, `carriers`, and `N_band` in $\text{cm}^{-3}$, `tau_n` and `tau_p` in $\text{s}$), the parameter-expanded DEVSIM expression string `text` (`str`), and the precompiled Python bytecode `_code` (`code` object).
- `Material` (`material.py`): material property and transport evaluator instance containing material name `mat_name` (`str`), relative permittivity `permittivity` (`float`, dimensionless), electron effective mass `electron_mass` and hole effective mass `hole_mass` (`float`, $\text{kg}$; unset for `"Diamond"`), mobility model name `mobility_model` (`str`), and impact ionization model name `avalanche_model` (`str | None`).
- `Dopant` (`dopants.py`): frozen dataclass (`@dataclass(frozen=True)`) containing dopant type `kind` (`str`, `"donor"` or `"acceptor"`), tuple of levels and site fractions `levels` (`tuple[tuple[float, float], ...]`, each entry `(zero-doping ionization energy [eV], site fraction [dimensionless])`), degeneracy factor `degeneracy` (`float`, dimensionless), and ionization-energy reduction coefficient `fall_ev_cm` (`float`, default `0.0`, in $\text{eV}\cdot\text{cm}$).

## Interface

Users can configure in the device file only the keys listed below that relate to this package's models; all other model parameters (relative permittivity, effective masses, default mobility models for each material and their coefficients, impact ionization parameters and the $4.0^\circ$ off-axis angle, band parameters, dopant levels and degeneracies, SRH lifetimes, and TAT characteristic field `F_gamma`) are hardcoded, though the copies written as DEVSIM region parameters can be overridden during field solving via `parameter` (one per device file, see Built-in Constants above). On the command line, use `raser model --draw <model>` to plot model curves (see [Command-Line Interface](../cli.md)); command-line usage for field solving and carrier transport is documented in [../stages/field.md](../stages/field.md) and [../stages/current.md](../stages/current.md).

### Keys Read from the Device File

The following keys in the device JSON are read by [device.md](device.md), [field.md](field.md), and [current.md](current.md) and passed to this package's interfaces:

| Key | Default | Unit | Meaning |
| --- | --- | --- | --- |
| `material` | None (required) | None | Semiconductor material identifier: `"Si"`, `"SiC"`, or `"Diamond"`; `"Silicon"` and `"SiliconCarbide"` inside mesh regions are DEVSIM region material names, separate from this key. For other values, `Material` sets no property attributes, causing `AttributeError` when estimating capacitance and `UnboundLocalError` when computing mobility. Determines the material branch of `Material`, `RELATIVE_PERMITTIVITY`, `BAND_STRUCTURE`, `DOPANTS`, `SRH_LIFETIME`, and the default `mobility_model` |
| `temperature` | None (required) | $\text{K}$ | Device temperature $T$, passed to `Material.cal_mobility`, `Material.cal_coefficient`, `BAND_STRUCTURE`, `free_holes`, and the DEVSIM region parameter `"T"` |
| `avalanche_model`, `enable_gain` | `None`, `False` | None | Enables multiplication when `has_avalanche` is true; passed to `Material(material, avalanche_model=...).cal_coefficient` in `_integrate_planar_gain` of [field.md](field.md) and `_build_local_gain_carriers` of [current.md](current.md) (supporting `"vanOverstraeten"`, `"Okuto"`, `"Hatakeyama"`), and controls `VAN_OVERSTRAETEN`, `hatakeyama`, and `TAT_FIELD_ENHANCEMENT` in `physics_avalanche.py` of [field.md](field.md); DEVSIM field solving selects coefficients by region material (`VAN_OVERSTRAETEN` for `Silicon`, `hatakeyama` for `SiliconCarbide`), so `"Okuto"` enters only planar gain integration and local-path gain on the drift side |
| `doping.Donors`, `doping.Acceptors` | None (required for field solving and diffusion-only collection) | $\text{cm}^{-3}$ | Donor and acceptor concentration expressions; [field.md](field.md) computes mesh net doping `NetDoping`, which [current.md](current.md) passes to `Material.cal_mobility`, while diffusion-only collection `collect_by_diffusion` passes their numeric difference directly to `Material.cal_mobility` |
| `parameter` | None (optional) | parameter-dependent | `{"name": <str>, "value": <float>}`, written to the DEVSIM region parameters by `create_parameter` in [field.md](field.md); when `"name"` is `"F_sat"`, overrides the default saturation field `TAT_SATURATION_FIELD` (`1e5` $\text{V/cm}$) in `"SiliconCarbide"` regions |
| `resistive_layer.implanted`, `resistive_layer.thickness`, `resistive_layer.anneal` | None (required when `sheet_resistance` is omitted for a resistive layer) | $\text{cm}^{-2}$, $\mu\text{m}$, $^\circ\text{C}$ | Implanted dose, thickness, and annealing temperature of an Al-implanted 4H-SiC resistive layer, converted by `implanted_aluminium.sheet_resistance` in [field.md](field.md) into activated acceptor and compensating donor concentrations and passed to `free_holes("SiC", "Al", ...)` and `Material("SiC").cal_mobility` |

### Input and Output Files

`core/model` is an in-memory physical model library; its numerical values and symbolic expressions are passed directly in memory to [device.md](device.md), [field.md](field.md) (which writes `.pkl` and `.json` files into the `<project>/field/nodes/<node_id>/` field node), and [current.md](current.md) (which writes `current.h5`).

### Plot Outputs

On the command line, use `raser model --draw <model>` to plot curves of physical models such as mobility, drift velocity, and impact ionization coefficients versus electric field, temperature, or doping concentration (see [Command-Line Interface](../cli.md)). You can also call `Material(<material>).draw_velocity(temperature, Neff)` in Python (for example `Material("SiC").draw_velocity(300, 1e14)`) to generate a drift-velocity plot under `<project_root>/model/model/` via `output(__file__, "model")` in [../supports/README.md](../supports/README.md); `<project_root>` comes from the environment variable `RASER_PROJECT_PATH`, defaulting to the current working directory:

| Filename | Content | Unit |
| --- | --- | --- |
| `<mat_name>Mobility<mobility_model>.png` | Log-log drift-velocity curves of electrons (`"electron"`) and holes (`"hole"`) from $0$ to $10^6\ \text{V/cm}$ (step $1000\ \text{V/cm}$, $1001$ points total) at temperature `temperature` ($\text{K}$) and effective doping `Neff` ($\text{cm}^{-3}$), with figure title `"Mobility Model"` | horizontal axis `ElectricField  [V/cm]`, vertical axis `Velocity [cm/s]` |

## References

- [1] S. M. Sze, K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley-Interscience (2007), doi:10.1002/0470068329
- [2] S. Selberherr, W. Hänsch, M. Seavey, J. Slotboom, “The Evolution of the MINIMOS Mobility Model”, Solid-State Electronics 33 (1990) 1425, doi:10.1016/0038-1101(90)90117-W
- [3] S. Reggiani, M. Valdinoci, L. Colalongo, M. Rudan, G. Baccarani, “An Analytical, Temperature-Dependent Model for Majority- and Minority-Carrier Mobility in Silicon Devices”, VLSI Design 10 (2000) 467, doi:10.1155/2000/52147
- [4] R. van Overstraeten, H. de Man, “Measurement of the ionization rates in diffused silicon p-n junctions”, Solid-State Electronics 13 (1970) 583, doi:10.1016/0038-1101(70)90139-5
- [5] Y. Okuto, C. R. Crowell, “Threshold energy effect on avalanche breakdown voltage in semiconductor junctions”, Solid-State Electronics 18 (1975) 161, doi:10.1016/0038-1101(75)90099-4
- [6] T. Hatakeyama, T. Watanabe, T. Shinohe, K. Kojima, K. Arai, N. Sano, “Impact ionization coefficients of 4H silicon carbide”, Appl. Phys. Lett. 85 (2004) 1380, doi:10.1063/1.1784520
- [7] T. Hatakeyama, J. Nishio, C. Ota, T. Shinohe, “Physical modeling and scaling properties of 4H-SiC power devices”, Proc. Int. Conf. Simulation of Semiconductor Processes and Devices (SISPAD) (2005) 171, doi:10.1109/SISPAD.2005.201500
- [8] J. Burin, P. Gaggl, S. Waid, A. Gsponer, T. Bergauer, “TCAD Parameters for 4H-SiC: A Review”, arXiv:2410.06798 (2024), doi:10.48550/arXiv.2410.06798
- [9] G. L. Pearson, J. Bardeen, “Electrical Properties of Pure Silicon and Silicon Alloys Containing Boron and Phosphorus”, Phys. Rev. 75 (1949) 865, doi:10.1103/PhysRev.75.865
- [10] M. Spera, D. Corso, S. Di Franco, G. Greco, A. Severino, P. Fiorenza, F. Giannazzo, F. Roccaforte, “Effect of high temperature annealing ($T > 1650\ ^\circ\text{C}$) on the morphological and electrical properties of p-type implanted 4H-SiC layers”, Mater. Sci. Semicond. Process. 93 (2019) 274, doi:10.1016/j.mssp.2019.01.019
- [11] A. T. Collins, A. W. S. Williams, “The nature of the acceptor centre in semiconducting diamond”, J. Phys. C: Solid State Phys. 4 (1971) 1789, doi:10.1088/0022-3719/4/13/030
- [12] R. G. Farrer, “On the substitutional nitrogen donor in diamond”, Solid State Commun. 7 (1969) 685, doi:10.1016/0038-1098(69)90593-6
- [13] E. Gheeraert, S. Koizumi, T. Teraji, H. Kanda, “Electronic transitions of electrons bound to phosphorus donors in diamond”, Solid State Commun. 113 (2000) 577, doi:10.1016/S0038-1098(99)00546-3
- [14] W. Shockley, W. T. Read, Jr., “Statistics of the Recombinations of Holes and Electrons”, Phys. Rev. 87 (1952) 835, doi:10.1103/PhysRev.87.835
- [15] G. A. M. Hurkx, D. B. M. Klaassen, M. P. G. Knuvers, “A new recombination model for device simulation including tunneling”, IEEE Trans. Electron Devices 39 (1992) 331, doi:10.1109/16.121690
- [16] C. R. Crowell, S. M. Sze, “Temperature dependence of avalanche multiplication in semiconductors”, Appl. Phys. Lett. 9 (1966) 242, doi:10.1063/1.1754731
- [17] Synopsys, *Sentaurus Device User Guide*, Synopsys Inc., section on the van Overstraeten–de Man impact ionization model
- [18] T. Hatakeyama, “Measurements of impact ionization coefficients of silicon carbide for high voltage power devices”, Phys. Status Solidi A 206 (2009) 2284, doi:10.1002/pssa.200925213
- [19] A. Das, S. P. Duttagupta, “TCAD simulation for alpha-particle spectroscopy using SiC Schottky diode”, Radiat. Prot. Dosim. 167 (2015) 443, doi:10.1093/rpd/ncu369
- [20] W. J. Schaffer, G. H. Negley, K. G. Irvine, J. W. Palmour, “Conductivity anisotropy in epitaxial 6H and 4H SiC”, MRS Proc. 339 (1994) 595, doi:10.1557/PROC-339-595
- [21] Z. Li et al., “Mechanisms of proton irradiation-induced defects on the electrical performance of 4H-SiC PIN detectors”, JINST 21 (2026) P03010, doi:10.1088/1748-0221/21/03/P03010, arXiv:2503.09016
- [22] H. Pernegger et al., “Charge-carrier properties in synthetic single-crystal diamond measured with the transient-current technique”, J. Appl. Phys. 97 (2005) 073704, doi:10.1063/1.1863417
