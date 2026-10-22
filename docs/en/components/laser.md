# Laser component

A Laser component defines the optical injection used by TCT. It contains the
absorption technique, incidence direction, wavelength, refractive index,
absorption parameters, pulse energy and timing, focus, spatial width, and
sampling resolution.

SPA uses its linear absorption coefficient. TPA uses its two-photon absorption
coefficient and Rayleigh-length description. The focus is expressed in Device
coordinates when [Interaction](../core/interaction.md) generates carrier
populations.

The [TCT application](../apps/tct.md) adds injection positions for a scan and
records the selected Laser definition with every result.
