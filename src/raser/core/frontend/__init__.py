"""Sensor electrical modelling and analog front-end circuit assembly."""

from .network import CurrentSource
from .network import FrontendCircuit
from .network import FrontendWaveforms
from .network import assemble_frontend
from .network import solve_frontend
from .noise import ELEMENTARY_CHARGE_C
from .noise import enc_to_charge_fC
from .noise import equivalent_noise_charge
from .noise import load_noise_spectrum
from .noise import output_noise_rms_from_enc
from .noise import spieler_noise_spectrum
from .noise import synthesize_noise_from_spectrum
from .noise import white_noise_spectrum_for_rms
from .sensor_network import SensorNetwork
from .sensor_network import SheetContact
from .sensor_network import build_resistive_sheet_sensor

__all__ = [
    "CurrentSource",
    "FrontendCircuit",
    "FrontendWaveforms",
    "assemble_frontend",
    "solve_frontend",
    "ELEMENTARY_CHARGE_C",
    "enc_to_charge_fC",
    "equivalent_noise_charge",
    "load_noise_spectrum",
    "output_noise_rms_from_enc",
    "spieler_noise_spectrum",
    "synthesize_noise_from_spectrum",
    "white_noise_spectrum_for_rms",
    "SensorNetwork",
    "SheetContact",
    "build_resistive_sheet_sensor",
]


def trans(name):
    from .legacy import trans as legacy_trans

    return legacy_trans(name)


def readout(name):
    from .legacy import readout as legacy_readout

    return legacy_readout(name)
