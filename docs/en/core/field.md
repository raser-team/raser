# Field

_RASER 5.0 semiconductor field calculation_

Field contains physics equations, mesh construction, numerical solving, TCAD
conversion, and field-data I/O. A resolved configuration selects the complete
calculation and the resulting data is stored under its Device project.

---

## ⚙️ Configuration

Bias, temperature, irradiation state, `field_dimension`, `field_source`,
physics settings, mesh settings, and solver settings belong to one Field
configuration. `field_source` is one configuration value alongside the other
values. The current sources are `devsim` and `tcad`.

The configuration used for a result is stored as `config.json`. Its hash names
the corresponding directory under `field/`:

```text
<device>/field/
└── <config-hash>/
    ├── config.json
    └── <field-files>
```

The configuration records resolved Field settings and the Device revision that
supplies the sensor structure. Together, these values identify the inputs used
by Physics, Mesher, Solver, Converter, and I/O. A changed value produces a new
hash and directory.

## 🧮 Physics

Physics defines the equations solved on the semiconductor domain. The basic
system contains the Poisson equation and the electron and hole continuity
equations.

The electrostatic potential `φ` gives the electric field

```math
\mathbf{E}=-\nabla\phi.
```

The Poisson equation is

```math
\nabla\cdot(\varepsilon\nabla\phi)=-\rho,
```

where the charge density contains electrons, holes, ionized doping, and charge
introduced by the selected irradiation correction.

The electron and hole continuity equations are

```math
\frac{\partial n}{\partial t}
=\frac{1}{q}\nabla\cdot\mathbf{J}_n+G_n-R_n,
```

```math
\frac{\partial p}{\partial t}
=-\frac{1}{q}\nabla\cdot\mathbf{J}_p+G_p-R_p.
```

`J_n` and `J_p` contain carrier drift and diffusion. `G_n`, `G_p`, `R_n`, and
`R_p` collect the configured generation and recombination terms.

### Irradiation correction

The irradiation correction defines defect levels, introduction rates, capture
cross-sections, and fluence. These values determine trapped electron and hole
densities, defect-assisted generation and recombination, and electron and hole
trapping rates. The trapped charge enters the Poisson equation, while the
generation and recombination rates enter the continuity equations.

### Impact-ionization and breakdown correction

The impact-ionization correction calculates electron and hole ionization
coefficients from material parameters and electric field. The resulting
carrier-generation terms enter the two continuity equations. Solving this
coupled system during voltage stepping gives the avalanche and breakdown
behaviour in the IV result.

### Tunnelling correction

The tunnelling correction adds the configured tunnelling rates to the carrier
generation and recombination terms. The current implementation contains
band-to-band tunnelling, trap-assisted tunnelling, and field-enhanced
recombination expressions.

## 🕸️ Mesher

Mesher defines the materials, interfaces, contacts, solve region, and numerical
mesh used by Physics and Solver.

The DEVSIM route creates the mesh from mesh lines, regions, contacts, and
interfaces. DEVSIM provides the 1D and 2D mesh construction functions used by
this route.

The Gmsh route reads a Gmsh mesh and maps its physical groups to DEVSIM
regions, contacts, and interfaces. The mapping is stored in the Field
configuration together with the Gmsh file and mesh settings.

Both routes produce a DEVSIM device containing the configured materials,
regions, interfaces, contacts, coordinates, and doping distribution. Mesher
validates these definitions before equation construction begins.

## 🧭 Solver

Solver receives the equations and mesh, establishes an initial solution, and
applies the configured voltage. Its numerical settings include absolute and
relative error limits, iteration limits, initial voltage step, maximum voltage
step, step-increase factor, step-decrease factor, and saved voltage points.

### Voltage stepping

Voltage stepping begins from the initial solution and advances toward the
configured bias. A converged solve becomes the starting point for the next
step. Convergence increases the following step according to the configured
factor. A convergence failure reduces the step and repeats the trial from the
preceding converged solution.

The solver saves the requested voltage points and the final bias point. Each
saved point contains the field quantities produced by the selected physics
settings.

### IV and CV

The IV calculation records voltage, electron current, hole current, and total
current at each converged voltage point.

The CV calculation performs an AC solve at each converged DC voltage. Its
configuration contains the frequency and AC voltage. The result records
voltage and capacitance.

Field AC calculations also provide sensor electrical values for
[Frontend](frontend.md). These values may include bulk capacitance,
inter-electrode coupling, bias resistance, and AC coupling capacitance. They
remain associated with the Field configuration and operating conditions used
for the calculation.

<!-- TODO: Define the Field AC output schema used to generate a sensor netlist. -->

### Weighting field

The weighting-potential solve is performed for each configured readout
electrode. For electrode `k`, the weighting potential `ψ_k` satisfies

```math
\nabla\cdot\left(\varepsilon\nabla\psi_k\right)=0.
```

Electrode `k` is set to `1 V`, and the remaining electrodes are set to `0 V`.
The weighting field is

```math
\mathbf{E}_{w,k}=-\nabla\psi_k.
```

The result is saved under the corresponding electrode name. The current
implementation stores the weighting potential and derives the weighting field
from that potential when required.

## 🔄 Converter

Converter calls Juan Sanchez's `tdr-convert` package to convert a TCAD TDR file
into DEVSIM format. The converted file is loaded through DEVSIM, and the
requested datasets are then passed to Field I/O.

The conversion configuration contains the TDR file, bias voltage, coordinate
orientation, and requested TCAD datasets. The current implementation reads the
TCAD potential, electric field, doping, space charge, electron density, hole
density, and electron and hole recombination data.

## 💾 I/O

I/O reads the resolved Field configuration and writes the calculated field
quantities into the directory selected by its configuration hash.

The current implementation writes separate Python pickle (`.pkl`) files for
potential, net doping, electron trapping rate, hole trapping rate, and
weighting potential. Each pickle contains

```text
points
values
metadata:
    voltage
    dimension
```

Potential, trapping rates, and doping are stored by bias voltage. Weighting
potential is stored by electrode name. The electric field is calculated from
the stored potential during loading.

<!-- TODO: Define the final field-file format; `.pkl` records the current implementation. -->
