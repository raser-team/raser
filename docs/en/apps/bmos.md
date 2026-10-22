# BMOS

BMOS describes a beam-monitor setup and its sensor response. Its project binds
a Device, a particle Source, frontend electronics, and the G4Setup containing
the monitor geometry.

## Calculation

The Source is transported through the BMOS G4Setup. Energy deposited in the
Device becomes carrier populations, electrode current sources, and frontend
waveforms through the Core Interaction, Current, and Frontend calculations.

BMOS records the event response and derives signal-amplitude distributions for
the selected Device state, beam, geometry, and electronics.
