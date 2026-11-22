"""The cable between the amplifier and the oscilloscope: a lossless line in
the netlist, and the losses of its data sheet applied to the waveforms after."""

import json
import math
from dataclasses import dataclass

import numpy as np

from raser.supports.paths import component_path

# speed of light in vacuum [m/s]
SPEED_OF_LIGHT = 299792458.0
# decibel per neper, 20 / ln 10
DB_PER_NEPER = 20.0 / math.log(10.0)
KEYS = ("impedance_ohm", "velocity_factor", "attenuation_db_per_m", "source")


@dataclass(frozen=True)
class CableComponent:
    """A cable of the data sheet.

    impedance_ohm : characteristic impedance [Ohm].
    velocity : speed of the signal on the cable [m/s].
    skin : a_s [Np / (m sqrt(Hz))], the loss of the conductor.
    dielectric : a_d [Np / (m Hz)], the loss of the dielectric.
    """

    name: str
    impedance_ohm: float
    velocity: float
    skin: float
    dielectric: float


@dataclass(frozen=True)
class Cable:
    """The cable of a read-out: the component and the length of the cable
    behind each output.

    length_m : length [m] of the cable of each output, by the name of the
        output; an output of length zero has no cable.
    """

    component: CableComponent
    length_m: dict[str, float]

    @property
    def impedance_ohm(self):
        return self.component.impedance_ohm

    def delay_s(self, output):
        """Delay [s] of the signal on the cable of the output."""
        return self.length_m[output] / self.component.velocity

    def transfer(self, output, frequencies_hz):
        """Transfer factor H of the cable of the output, complex, at the
        frequencies [Hz]."""
        return transfer_factor(self.component, self.length_m[output], frequencies_hz)


def loss_coefficients(attenuation_db_per_m):
    """The skin and the dielectric coefficients (a_s [Np / (m sqrt(Hz))],
    a_d [Np / (m Hz)]) that give the attenuation [dB / m] at two frequencies,
    as A = 8.686 (a_s sqrt(f) + a_d f).

    attenuation_db_per_m : {frequency [MHz] as text: attenuation [dB / m]},
        of two frequencies.
    """
    if len(attenuation_db_per_m) != 2:
        raise ValueError(
            "attenuation_db_per_m has to give the attenuation at two "
            f"frequencies, not {len(attenuation_db_per_m)}"
        )
    frequencies = np.array([float(f) * 1e6 for f in attenuation_db_per_m])
    nepers = np.array(list(attenuation_db_per_m.values()), dtype=np.float64)
    nepers = nepers / DB_PER_NEPER
    if frequencies[0] == frequencies[1]:
        raise ValueError("attenuation_db_per_m has to give two different frequencies")
    skin, dielectric = np.linalg.solve(
        np.column_stack([np.sqrt(frequencies), frequencies]), nepers
    )
    return float(skin), float(dielectric)


def read_cable(name):
    """The cable component of that name: the JSON file among the afe
    components, with the keys impedance_ohm, velocity_factor,
    attenuation_db_per_m and source."""
    path = component_path("afe", f"{name}.json")
    values = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in KEYS if key not in values]
    if missing:
        raise ValueError(f"{path} has no {missing}: it needs all of {list(KEYS)}")
    skin, dielectric = loss_coefficients(values["attenuation_db_per_m"])
    return CableComponent(
        name=name,
        impedance_ohm=float(values["impedance_ohm"]),
        velocity=SPEED_OF_LIGHT * float(values["velocity_factor"]),
        skin=skin,
        dielectric=dielectric,
    )


def attenuation_db_per_m(component, frequency_hz):
    """Attenuation [dB / m] of the component at the frequency [Hz]."""
    return DB_PER_NEPER * (
        component.skin * np.sqrt(frequency_hz) + component.dielectric * frequency_hz
    )


def transfer_factor(component, length_m, frequencies_hz):
    """Transfer factor of a cable of that length [m] at the frequencies [Hz],
    complex: exp(-length (a_s sqrt(f) (1 + i) + a_d f)). It is 1 at zero
    frequency and for length zero."""
    frequencies_hz = np.asarray(frequencies_hz, dtype=np.float64)
    return np.exp(
        -length_m
        * (
            component.skin * np.sqrt(frequencies_hz) * (1 + 1j)
            + component.dielectric * frequencies_hz
        )
    )


def through_cable(component, length_m, voltage, dt):
    """Waveform after a cable of that length [m]: the waveform [V] on bins of
    width dt [s] with the losses and the dispersion of the cable, as long as
    the waveform.

    The first bin is the reference and stays as it is: what follows it is
    transformed on a record of twice the length, padded with zeros, so that
    the dispersion does not wrap round to the start of the waveform.
    """
    voltage = np.asarray(voltage, dtype=np.float64)
    bins = voltage.shape[-1]
    reference = voltage[..., :1]
    record = 2 * bins
    spectrum = np.fft.rfft(voltage - reference, n=record)
    factor = transfer_factor(component, length_m, np.fft.rfftfreq(record, d=dt))
    return np.fft.irfft(spectrum * factor, n=record)[..., :bins] + reference
