"""The events of one signal job.

The device, its solved field, the events Geant4 recorded, and for each of
them the induced current and the amplified waveform of every read-out
electrode. Everything the job reads comes from the run.json of its seed
folder (kwargs["_files"]); nothing is written onto the device.
"""

import os
from array import array
from copy import deepcopy
from pathlib import Path

import ROOT

from raser.core.current import cal_current as ccrt
from raser.core.device import build_device as bdv
from raser.core.field import devsim_field as devfield
from raser.core.field.solved import solved_field
from raser.core.frontend.toy_readout import Amplifier
from raser.core.interaction.interaction import GeneralG4Interaction

from .draw_save import draw_drift_path

ROOT.gROOT.SetBatch(True)

# Geant4 set-up of a run that names none: the device alone in vacuum, one event.
DEVICE_ALONE = {
    "geant4_model": "device",
    "total_events": 1,
    "object": {},
    "world": "G4_Galactic",
    "maxstep": 2,
    "g4_vis": False,
}


def g4_config(kwargs):
    """Geant4 configuration of the job: the set-up, then the source over it."""
    files = kwargs["_files"]
    if files["source"].get("kind") == "toy_mip":
        raise NotImplementedError(
            "a toy_mip source does not hand over Deposits yet; this job only runs Geant4"
        )
    config = deepcopy(files.get("g4setup", DEVICE_ALONE))
    config.update(files["source"])
    for key in ("name", "kind", "description"):
        config.pop(key, None)
    if kwargs.get("events_per_job") is not None:
        config["total_events"] = int(kwargs["events_per_job"])
    if kwargs.get("g4_vis_driver"):
        config["g4_vis_driver"] = kwargs["g4_vis_driver"]
    if kwargs.get("g4_vis"):
        config["g4_vis_output"] = os.path.join(kwargs["_run_path"], "g4_geometry")
    return config


def _same_bins(name, hist):
    axis = hist.GetXaxis()
    return ROOT.TH1F(name, name, hist.GetNbinsX(), axis.GetXmin(), axis.GetXmax())


def _copy(target, source):
    """Bin contents of source into target; the two must have the same bins."""
    bins = [
        (h.GetNbinsX(), h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax())
        for h in (target, source)
    ]
    if bins[0] != bins[1]:
        raise ValueError(
            f"{source.GetName()} has bins {bins[1]}, the tree branch has {bins[0]}"
        )
    target.Reset()
    target.Add(source)


def run_events(my_d, my_f, my_g4, amplifier, file_path, plots, plot_path):
    """Current and waveform of every event Geant4 recorded, one tree entry each.

    The first `plots` events are also drawn, each in plot_path/event_<number>:
    drift paths, currents, waveform.

    Branches: event (Geant4 event number), e_dep [MeV], par_in and par_out
    (first and last deposit, [um]), current_<i> [A] and amplified_waveform_<i>
    of read-out electrode i.
    """
    deposits = my_g4.deposits()
    index = {number: i for i, number in enumerate(my_g4.eventIDs)}
    print(
        "detection_efficiency=%s" % (len(deposits.events) / deposits.generated_events),
        flush=True,
    )
    if not deposits.events:
        print("no event left a deposit in the device; nothing is written", flush=True)
        return
    if 0 < plots < len(deposits.events):
        print(
            "%s events recorded; only the first %s are drawn (--plots)"
            % (len(deposits.events), plots),
            flush=True,
        )

    event_array = array("i", [0])
    e_dep_array = array("d", [0.0])
    par_in_array = array("d", [0.0, 0.0, 0.0])
    par_out_array = array("d", [0.0, 0.0, 0.0])

    tree = ROOT.TTree("tree", "Waveform Data")
    tree.Branch("event", event_array, "event/I")
    tree.Branch("e_dep", e_dep_array, "e_dep/D")
    tree.Branch("par_in", par_in_array, "par_in[3]/D")
    tree.Branch("par_out", par_out_array, "par_out[3]/D")
    current, amplified_waveform = [], []
    # Note: TTree.Branch() needs the binded variable (namely the address) to be valid and the same while Fill(),
    # so don't put the Branch() into other methods/functions!

    for count, record in enumerate(deposits.events):
        print("run events number:%s" % (record.event))
        drawn = count < plots
        my_current = ccrt.CalCurrentG4P(
            my_d, my_f, my_g4, index[record.event], keep_drift_paths=drawn
        )
        ele_current = Amplifier(my_current.sum_cu, amplifier, CDet=my_d.capacitance)

        if drawn:
            path = os.path.join(plot_path, "event_%s" % (record.event))
            os.makedirs(path, exist_ok=True)
            draw_drift_path(my_d, my_g4, my_f, my_current, path)
            my_current.draw_currents(path)
            ele_current.draw_waveform(my_current.sum_cu, path)
            if my_d.is_strip:
                my_current.charge_collection_strip(path)
            if my_d.is_pixel:
                my_current.charge_collection_pixel(path)

        if not current:
            for i in range(my_d.read_ele_num):
                current.append(_same_bins("current_%s" % (i), my_current.sum_cu[i]))
                amplified_waveform.append(
                    _same_bins(
                        "amplified_waveform_%s" % (i), ele_current.amplified_currents[i]
                    )
                )
                tree.Branch("current_%s" % (i), current[i])
                tree.Branch("amplified_waveform_%s" % (i), amplified_waveform[i])

        event_array[0] = record.event
        e_dep_array[0] = sum(record.e)
        par_in_array[0], par_in_array[1], par_in_array[2] = record.x[0], record.y[0], record.z[0]
        par_out_array[0], par_out_array[1], par_out_array[2] = record.x[-1], record.y[-1], record.z[-1]
        for i in range(my_d.read_ele_num):
            _copy(current[i], my_current.sum_cu[i])
            _copy(amplified_waveform[i], ele_current.amplified_currents[i])
        tree.Fill()

    file = ROOT.TFile(str(file_path), "RECREATE")
    tree.Write()
    file.Close()


def main(kwargs):
    files = kwargs["_files"]
    my_d = bdv.Detector(kwargs["det_name"], files["device"])

    # The flux is of the field the run takes, not of the device.
    flux = my_d.irradiation_flux if kwargs["irradiation"] is None else float(kwargs["irradiation"])
    my_f = devfield.DevsimField(
        my_d.device,
        my_d.voltage,
        my_d.read_out_contact,
        irradiation_flux=flux,
        bounds=my_d.bound,
        field_directory=solved_field(my_d, my_d.voltage, flux),
        interpolation_bins=my_d.device_dict.get("field_interpolation_bins"),
    )

    interaction_options = {}
    if kwargs.get("_g4_action_initialization") is not None:
        interaction_options["MyActionInitialization"] = kwargs["_g4_action_initialization"]
    my_g4 = GeneralG4Interaction(
        my_d,
        g4_config(kwargs),
        kwargs["seed"],
        kwargs.get("g4_vis", False),
        **interaction_options,
    )

    # The amplifier is still found by the name of its file.
    amplifier = Path(str(kwargs["amplifier"])).stem
    job = kwargs.get("job_index") or 0
    try:
        run_events(
            my_d,
            my_f,
            my_g4,
            amplifier,
            Path(kwargs["_run_batch_path"]) / ("signal_%s.root" % (job)),
            int(kwargs["plots"]),
            os.path.join(kwargs["_run_path"], "plots", "job_%s" % (job)),
        )
    finally:
        my_g4.close()
