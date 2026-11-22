"""Sparse, append-only HDF5 files of digitised waveforms."""

import os
from dataclasses import dataclass

import h5py
import numpy as np


_DATASETS = (
    "event",
    "count",
    "stored",
    "index",
    "t0",
    "clipped",
    "noise_only",
    "code",
)


@dataclass
class EventDigitized:
    event: int
    code: np.ndarray
    clipped: np.ndarray
    t0: np.ndarray
    electrodes: list[str]
    noise_only: np.ndarray


@dataclass(frozen=True)
class DigitizerFileSettings:
    """Attributes stored in a digitizer waveform file."""

    sampling_period: float
    lsb_V: float
    offset_V: float
    bits: int
    channels: int
    device: str
    pre_window: float  # [s], as the readout file

    @classmethod
    def from_settings(cls, settings, device, pre_window):
        return cls(
            float(settings.period_s),
            float(settings.lsb_V),
            float(settings.offset_V),
            int(settings.bits),
            int(settings.channels),
            str(device),
            float(pre_window),
        )

    @classmethod
    def from_digitizer_settings(cls, settings, device, pre_window):
        return cls.from_settings(settings, device, pre_window)

    @classmethod
    def from_waveforms(cls, waveforms):
        return cls(
            float(waveforms.sampling_period),
            float(waveforms.lsb_V),
            float(waveforms.offset_V),
            int(waveforms.bits),
            int(waveforms.channels),
            str(waveforms.device),
            float(waveforms.pre_window),
        )


@dataclass
class DigitizedWaveforms:
    electrodes: list[str]
    sampling_period: float
    lsb_V: float
    offset_V: float
    bits: int
    pulse_edge: list[str]
    device: str
    channels: int
    events: list[EventDigitized]
    pre_window: float  # [s]

    @property
    def file_settings(self):
        return DigitizerFileSettings.from_waveforms(self)


def _check_layout(file, path):
    missing = [name for name in _DATASETS if name not in file]
    if missing or file["code"].ndim != 1 or file["t0"].ndim != 1:
        raise ValueError(
            f"{path} is a digitizer file of an older layout or is missing {missing or ['one-dimensional code/t0']}"
        )
    if "channels" not in file.attrs:
        raise ValueError(f"{path} is missing digitizer attribute 'channels'")


def _check_pulse_edge(pulse_edge, electrodes):
    if len(pulse_edge) != len(electrodes) or not set(pulse_edge) <= {
        "rising",
        "falling",
    }:
        raise ValueError(
            "pulse_edge must contain rising or falling for every electrode"
        )


def create_digitized(path, electrodes, attributes: DigitizerFileSettings, pulse_edge):
    """Create a digitizer file with all attributes and empty datasets."""
    if not isinstance(attributes, DigitizerFileSettings):
        raise TypeError("attributes must be DigitizerFileSettings")
    electrodes = list(electrodes)
    pulse_edge = list(pulse_edge)
    _check_pulse_edge(pulse_edge, electrodes)
    with h5py.File(str(path), "w") as file:
        file.attrs.create("electrodes", electrodes, dtype=h5py.string_dtype())
        file.attrs["sampling_period"] = attributes.sampling_period
        file.attrs["lsb_V"] = attributes.lsb_V
        file.attrs["offset_V"] = attributes.offset_V
        file.attrs["bits"] = attributes.bits
        file.attrs.create("pulse_edge", pulse_edge, dtype=h5py.string_dtype())
        file.attrs["device"] = attributes.device
        file.attrs["channels"] = attributes.channels
        file.attrs["pre_window"] = attributes.pre_window
        for name, kind in (
            ("event", "int64"),
            ("count", "int64"),
            ("stored", "int64"),
            ("index", "int64"),
            ("t0", "float64"),
            ("clipped", "int64"),
            ("noise_only", "bool"),
        ):
            file.create_dataset(name, shape=(0,), maxshape=(None,), dtype=kind)
        file.create_dataset(
            "code", shape=(0,), maxshape=(None,), dtype="int16", compression="gzip"
        )


def append_digitized(
    path,
    electrodes,
    attributes: DigitizerFileSettings,
    record: EventDigitized,
    pulse_edge,
):
    """Append one sparse event; the file is created with the first event."""
    if not isinstance(attributes, DigitizerFileSettings):
        raise TypeError("attributes must be DigitizerFileSettings")
    electrodes = list(electrodes)
    names = list(record.electrodes)
    unknown = sorted(set(names) - set(electrodes))
    if unknown or len(set(names)) != len(names):
        raise ValueError(
            f"the event {record.event} has traces of {names}, not each once of the electrodes {electrodes}"
        )
    codes = np.asarray(record.code, dtype=np.int16)
    clipped = np.asarray(record.clipped, dtype=np.int64)
    starts = np.asarray(record.t0, dtype=np.float64)
    noise_only = np.asarray(record.noise_only, dtype=bool)
    if codes.ndim != 2 or codes.shape[0] != len(names):
        raise ValueError(
            f"code has shape {codes.shape}, expected ({len(names)}, count)"
        )
    if (
        clipped.shape != (len(names),)
        or starts.shape != (len(names),)
        or noise_only.shape != (len(names),)
    ):
        raise ValueError(
            "clipped, t0, and noise_only must have one value per stored electrode"
        )
    pulse_edge = list(pulse_edge)
    _check_pulse_edge(pulse_edge, electrodes)
    if not os.path.exists(path):
        create_digitized(path, electrodes, attributes, pulse_edge)
    with h5py.File(str(path), "a") as file:
        _check_layout(file, path)
        if file.attrs["electrodes"].tolist() != electrodes:
            raise ValueError(
                f"{path} holds waveforms of electrodes {file.attrs['electrodes'].tolist()}, not {electrodes}"
            )
        if (
            float(file.attrs["sampling_period"]) != attributes.sampling_period
            or float(file.attrs["lsb_V"]) != attributes.lsb_V
            or float(file.attrs["offset_V"]) != attributes.offset_V
            or int(file.attrs["bits"]) != attributes.bits
            or int(file.attrs["channels"]) != attributes.channels
            or str(file.attrs["device"]) != attributes.device
            or "pre_window" not in file.attrs
            or float(file.attrs["pre_window"]) != attributes.pre_window
            or file.attrs["pulse_edge"].tolist() != pulse_edge
        ):
            raise ValueError(
                f"{path} has digitizer settings different from the requested settings"
            )
        rows = {
            "event": np.array([int(record.event)], dtype="int64"),
            "count": np.array([codes.shape[1]], dtype="int64"),
            "stored": np.array([len(names)], dtype="int64"),
            "index": np.array(
                [electrodes.index(name) for name in names], dtype="int64"
            ),
            "t0": starts,
            "clipped": clipped,
            "noise_only": noise_only,
            "code": codes.reshape(-1),
        }
        for name, values in rows.items():
            dataset = file[name]
            first = dataset.shape[0]
            dataset.resize(first + len(values), axis=0)
            dataset[first:] = values


def read_digitized(path):
    """Read a complete digitizer file and reconstruct every sparse event."""
    with h5py.File(str(path), "r") as file:
        _check_layout(file, path)
        electrodes = file.attrs["electrodes"].tolist()
        if "pulse_edge" not in file.attrs:
            raise ValueError(f"{path} is missing digitizer attribute 'pulse_edge'")
        pulse_edge = file.attrs["pulse_edge"].tolist()
        required_attrs = (
            "sampling_period",
            "lsb_V",
            "offset_V",
            "bits",
            "device",
            "channels",
        )
        missing = [name for name in required_attrs if name not in file.attrs]
        if missing:
            raise ValueError(f"{path} is missing digitizer attribute {missing[0]!r}")
        if "pre_window" not in file.attrs:
            raise ValueError(
                f"{path} has no pre_window: the digitizer of this version did "
                "not write it; run the digitizer again"
            )
        pre_window = float(file.attrs["pre_window"])
        period = float(file.attrs["sampling_period"])
        lsb = float(file.attrs["lsb_V"])
        offset = float(file.attrs["offset_V"])
        bits = int(file.attrs["bits"])
        device = file.attrs["device"]
        if isinstance(device, bytes):
            device = device.decode()
        channels = int(file.attrs["channels"])
        numbers, counts, stored = (
            file[name][()] for name in ("event", "count", "stored")
        )
        index, starts, clipped, noise_only, code = (
            file[name][()] for name in ("index", "t0", "clipped", "noise_only", "code")
        )
    events: list[EventDigitized] = []
    trace = sample = 0
    for number, count_value, many_value in zip(numbers, counts, stored, strict=True):
        many, count = int(many_value), int(count_value)
        events.append(
            EventDigitized(
                int(number),
                code[sample : sample + many * count].reshape(many, count),
                clipped[trace : trace + many],
                starts[trace : trace + many],
                [electrodes[k] for k in index[trace : trace + many]],
                noise_only[trace : trace + many],
            )
        )
        trace += many
        sample += many * count
    return DigitizedWaveforms(
        electrodes,
        period,
        lsb,
        offset,
        bits,
        pulse_edge,
        str(device),
        channels,
        events,
        pre_window,
    )
