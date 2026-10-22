# Current

_RASER 5.0 carrier transport and induced current_

Current transports the electron and hole populations created by Interaction
and calculates the instantaneous current induced on every readout electrode.

## Carrier populations

Each entry in `ionized_pairs` creates an electron population and a hole
population at the corresponding `[x, y, z, t]` entry in `track_position`.
Their population weights have equal magnitude and opposite charge signs.

Each population records its position, creation time, transported charge, and
path through detector coordinates. Device supplies the material, temperature,
runtime bounds, readout electrodes, and selected Transport, Damage, and Gain
settings.

## Transport

Field supplies the electric field, doping, electron trapping rate, and hole
trapping rate at each carrier position. The selected mobility model evaluates

```math
\mu=\mu(T,N_{\mathrm{eff}},|\mathbf E|),
```

for electrons and holes. Their drift velocities are

```math
\mathbf v_e=-\mu_e\mathbf E,
\qquad
\mathbf v_h=+\mu_h\mathbf E.
```

Diffusion follows the Einstein relation

```math
D=\frac{k_B T}{q}\mu.
```

During a time step `Δt`, each spatial diffusion component is sampled from a
Gaussian distribution with variance `2DΔt`. Drift and diffusion together give
the next carrier position.

The Transport settings define the time step, maximum drift time, spatial
boundary tolerance, and minimum field strength. A carrier path ends at a
detector boundary, at the configured drift limit, or at the configured
low-field condition.

## Trapping

For a local trapping rate `Γ`, the transported population after one path
segment is

```math
Q(t+\Delta t)=Q(t)\exp(-\Gamma\Delta t).
```

Electron and hole populations use their corresponding trapping rates from
Field. The accumulated attenuation along the path determines the charge used
for signal induction.

## Gain

Gain creates secondary electron–hole populations and transports them through
the same field. The selected avalanche model provides electron and hole
ionization coefficients as functions of electric field and temperature.

The `planar_integral` calculation creates secondary populations at the
declared gain boundary from the configured gain rate. The `local_path`
calculation integrates the ionization coefficient along each carrier path:

```math
N_{\mathrm{secondary}}
=N_{\mathrm{primary}}
\left[\exp\left(\int\alpha\,ds\right)-1\right].
```

The generated electrons and holes enter transport at their generation
positions and times. Their induced currents are added to the primary signal.

## Induced current

Field supplies one weighting potential `ψ_k` for each readout electrode `k`.
For a carrier population of charge `q` moving from `r_n` to `r_{n+1}`, the
induced charge on that electrode is

```math
\Delta Q_k
=q\left[\psi_k(\mathbf r_{n+1})-\psi_k(\mathbf r_n)\right].
```

The corresponding current over the time step is

```math
I_k=\frac{\Delta Q_k}{\Delta t}.
```

This calculation produces the instantaneous Norton current source associated
with each electrode. The complete result contains electron, hole, gain, and
summed current contributions on a common time axis. Electrode order follows
the readout layout declared by Device.

[Frontend](frontend.md) connects these current sources to the sensor electrical
model and the AFE circuit.
