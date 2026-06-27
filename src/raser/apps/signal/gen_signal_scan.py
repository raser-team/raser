#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@Description: The main program of Raser induced current simulation      
@Date       : 2024/09/26 15:11:20
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''
import sys
import os
from array import array
import subprocess
import json
import random

import ROOT
ROOT.gROOT.SetBatch(True)

ELECTRON_CHARGE_C = 1.60217733e-19

from raser.core.device import build_device as bdv
from raser.core.interaction.interaction import GeneralG4Interaction
from raser.core.field import devsim_field as devfield
from raser.core.current import cal_current as ccrt
from raser.core.current.cross_talk import cross_talk
from raser.core.analog.readout import Amplifier
from raser.core.metrics import waveform_stats
from raser.supports.math import inversed_fast_fourier_transform as ifft
from raser.supports.output import create_path
from raser.supports.paths import component_path
from raser.supports.paths import optional_component_path
from raser.supports import runs
from .experiments import apply_signal_experiment
from .draw_save import draw_drift_path


def _copy_histogram(target, source):
    target_axis = target.GetXaxis()
    source_axis = source.GetXaxis()
    same_axis = (
        target.GetNbinsX() == source.GetNbinsX()
        and target_axis.GetXmin() == source_axis.GetXmin()
        and target_axis.GetXmax() == source_axis.GetXmax()
    )
    if not same_axis:
        raise ValueError(
            f"Cannot copy histogram {source.GetName()} to {target.GetName()}: "
            "binning differs"
        )
    target.Reset()
    for bin_idx in range(1, source.GetNbinsX() + 1):
        target.SetBinContent(bin_idx, source.GetBinContent(bin_idx))


def _current_axis(my_d):
    dimension = 1 if my_d.is_plugin() else my_d.dimension
    time_bin = ccrt.t_bin[dimension]
    time_start = ccrt.t_start[dimension]
    time_end = ccrt.t_end[dimension]
    n_bins = int((time_end + ccrt.t_tol - time_start) / time_bin)
    return n_bins, time_start, time_end


def _event_stats_file_path(output_path, instance_number):
    return os.path.join(output_path, "stats_%s.root"%(instance_number))


def _hist_abs_max(hist):
    max_value = 0.0
    for bin_idx in range(1, hist.GetNbinsX() + 1):
        max_value = max(max_value, abs(hist.GetBinContent(bin_idx)))
    return max_value


def _hist_abs_integral(hist, t_bin):
    charge = 0.0
    for bin_idx in range(1, hist.GetNbinsX() + 1):
        charge += abs(hist.GetBinContent(bin_idx)) * t_bin
    return charge


def _daq_thresholds(my_d):
    with open(component_path("electronics", "digital", my_d.daq + ".json")) as f_in:
        daq_dict = json.load(f_in)
    return daq_dict["threshold"], daq_dict["amplitude_threshold"]


def _nan_number(value):
    if value is None:
        return float("nan")
    return value


def _amplified_metrics(ele_current, my_d, threshold, amplitude_threshold):
    amplitudes = []
    charges = []
    toas = []
    tots = []
    cfd50s = []
    row = {}
    for i in range(my_d.read_ele_num):
        amplified_current = ele_current.amplified_currents[i]
        amplitude, peak_bin = waveform_stats.get_amplitude(amplified_current)
        if amplitude < threshold:
            amplitude = 0
            charge = 0
            toa = None
            tot = 0
            cfd50 = None
        else:
            charge = waveform_stats.get_charge(amplified_current)
            toa = waveform_stats.get_ToA(amplified_current, threshold, peak_bin)
            tot = waveform_stats.get_ToT(amplified_current, threshold, peak_bin)
            cfd50 = waveform_stats.get_CFD50(
                amplified_current,
                waveform_stats.CFD,
                peak_bin,
            )
        amplitudes.append(amplitude)
        charges.append(charge)
        toas.append(toa)
        tots.append(tot)
        cfd50s.append(cfd50)
        row["amplified_amplitude_%s"%(i)] = amplitude
        row["amplified_charge_%s"%(i)] = charge
        row["amplified_ToA_%s"%(i)] = _nan_number(toa)
        row["amplified_ToT_%s"%(i)] = tot
        row["amplified_CFD50_%s"%(i)] = _nan_number(cfd50)

    if max(amplitudes) < amplitude_threshold:
        row["amplified_amplitude"] = float("nan")
        row["amplified_charge"] = float("nan")
        row["amplified_ToA"] = float("nan")
        row["amplified_ToT"] = float("nan")
        row["amplified_CFD50"] = float("nan")
    elif my_d.read_ele_num == 1:
        row["amplified_amplitude"] = amplitudes[0]
        row["amplified_charge"] = charges[0]
        row["amplified_ToA"] = _nan_number(toas[0])
        row["amplified_ToT"] = tots[0]
        row["amplified_CFD50"] = _nan_number(cfd50s[0])
    else:
        row["amplified_amplitude"] = _nan_number(
            waveform_stats.get_total_amp(amplitudes, amplitude_threshold)
        )
        row["amplified_charge"] = _nan_number(waveform_stats.get_total_amp(charges, 0.0))
        row["amplified_ToA"] = _nan_number(waveform_stats.get_conjoined_time(toas))
        row["amplified_ToT"] = _nan_number(waveform_stats.get_total_amp(tots, 10e-9))
        row["amplified_CFD50"] = _nan_number(
            waveform_stats.get_conjoined_time(cfd50s)
        )
    return row


def _write_cce_event_stats(
    my_d,
    my_f,
    my_g4,
    total_events,
    instance_number,
    output_path,
):
    start_n = instance_number * total_events
    end_n = (instance_number + 1) * total_events
    fieldnames = [
        "event",
        "e_dep",
        "par_in_x",
        "par_in_y",
        "par_in_z",
        "par_out_x",
        "par_out_y",
        "par_out_z",
        "voltage",
        "irradiation_flux",
        "generated_pairs",
        "generated_charge",
        "amplified_amplitude",
        "amplified_charge",
        "amplified_ToA",
        "amplified_ToT",
        "amplified_CFD50",
    ]
    for i in range(my_d.read_ele_num):
        fieldnames.append("induced_charge_%s"%(i))
        fieldnames.append("current_peak_%s"%(i))
        fieldnames.append("amplified_amplitude_%s"%(i))
        fieldnames.append("amplified_charge_%s"%(i))
        fieldnames.append("amplified_ToA_%s"%(i))
        fieldnames.append("amplified_ToT_%s"%(i))
        fieldnames.append("amplified_CFD50_%s"%(i))

    effective_number = 0
    threshold, amplitude_threshold = _daq_thresholds(my_d)
    file_path = _event_stats_file_path(output_path, instance_number)
    root_file = ROOT.TFile(file_path, "RECREATE")
    event_tree = ROOT.TTree("events", "CCE scalar event statistics")
    branches = {name: array("d", [0.0]) for name in fieldnames}
    for name, value in branches.items():
        event_tree.Branch(name, value, "%s/D"%(name))

    for event in range(start_n,end_n):
        print("run events number:%s"%(event))
        if len(my_g4.p_steps[event-start_n]) <= 5:
            continue
        effective_number += 1
        my_current = ccrt.CalCurrentG4P(
            my_d,
            my_f,
            my_g4,
            event-start_n,
            keep_drift_paths=False,
        )
        if ("strip" in my_d.det_model or "pixel" in my_d.det_model) and my_d.cross_talk != None:
            my_current.cross_talk_cu = cross_talk(my_d.det_name, my_d.cross_talk, my_current.sum_cu)
        else:
            my_current.cross_talk_cu = my_current.sum_cu

        ele_current = Amplifier(
            my_current.cross_talk_cu,
            my_d.amplifier,
            seed=event,
            CDet=my_d.capacitance,
            is_cut=True,
        )
        par_in = my_g4.p_steps_current[my_g4.selected_batch_number][0]
        par_out = my_g4.p_steps_current[my_g4.selected_batch_number][-1]
        row = {
            "event": event,
            "e_dep": my_g4.edep_devices[event-start_n],
            "par_in_x": par_in[0],
            "par_in_y": par_in[1],
            "par_in_z": par_in[2],
            "par_out_x": par_out[0],
            "par_out_y": par_out[1],
            "par_out_z": par_out[2],
            "voltage": my_d.voltage,
            "irradiation_flux": my_d.irradiation_flux,
            "generated_pairs": my_current.generated_pairs,
            "generated_charge": my_current.generated_pairs * ELECTRON_CHARGE_C,
        }
        for i in range(my_d.read_ele_num):
            row["induced_charge_%s"%(i)] = _hist_abs_integral(
                my_current.cross_talk_cu[i],
                my_current.t_bin,
            )
            row["current_peak_%s"%(i)] = _hist_abs_max(my_current.cross_talk_cu[i])
        row.update(_amplified_metrics(ele_current, my_d, threshold, amplitude_threshold))
        for name in fieldnames:
            branches[name][0] = _nan_number(row.get(name))
        event_tree.Fill()

    detection_efficiency = effective_number/(end_n-start_n)
    run_tree = ROOT.TTree("run", "CCE run statistics")
    run_stats = {
        "generated_events": array("d", [float(end_n-start_n)]),
        "effective_events": array("d", [float(effective_number)]),
        "detection_efficiency": array("d", [float(detection_efficiency)]),
    }
    for name, value in run_stats.items():
        run_tree.Branch(name, value, "%s/D"%(name))
    run_tree.Fill()
    root_file.cd()
    event_tree.Write()
    run_tree.Write()
    root_file.Close()
    print("detection_efficiency=%s"%detection_efficiency, flush=True)


def _sample_plot_events(start_n, end_n, sample_count):
    if sample_count <= 0:
        return set()
    total_events = end_n - start_n
    if total_events <= sample_count:
        return set(range(start_n, end_n))
    step = total_events / sample_count
    return {start_n + int(index * step) for index in range(sample_count)}


def _draw_signal_sample(my_d, my_g4, my_f, my_current, ele_current, event, output_path):
    sample_path = os.path.join(
        os.path.dirname(output_path),
        "plots",
        "event_%03d"%(event),
    )
    create_path(sample_path)
    draw_drift_path(my_d, my_g4, my_f, my_current, sample_path)
    my_current.draw_currents(sample_path)
    ele_current.draw_waveform(my_current.cross_talk_cu, sample_path)


def batch_loop(
    my_d,
    my_f,
    my_g4,
    g4_seed,
    total_events,
    instance_number,
    output_path,
    store_waveforms=True,
    plot_samples=0,
):
    """
    Description:
        Batch run some events to get time resolution
    Parameters:
    ---------
    start_n : int
        Start number of the event
    end_n : int
        end number of the event 
    detection_efficiency: float
        The ration of hit particles/total_particles           
    @Returns:
    ---------
        None
    @Modify:
    ---------
        2021/09/07
    """
    if not store_waveforms:
        _write_cce_event_stats(
            my_d,
            my_f,
            my_g4,
            total_events,
            instance_number,
            output_path,
        )
        return

    start_n = instance_number * total_events
    end_n = (instance_number + 1) * total_events

    effective_number = 0
    plot_events = _sample_plot_events(start_n, end_n, plot_samples)

    # datas that varies in each event

    event_array = array('i', [0])
    e_dep_array = array('d', [0.])
    par_in_array = array('d', [0., 0., 0.])
    par_out_array = array('d', [0., 0., 0.])

    # TODO: manage the extra datas inside a dict

    tree = ROOT.TTree("tree", "Waveform Data")
    tree.Branch("event", event_array, "event/I")
    tree.Branch("e_dep", e_dep_array, "e_dep/D")
    tree.Branch("par_in", par_in_array, "par_in[3]/D")
    tree.Branch("par_out", par_out_array, "par_out[3]/D")

    # datas that are constant in each event

    voltage_array = array('d', [my_d.voltage])
    irradiation_array = array('d', [my_d.irradiation_flux])
    g4_str = ROOT.std.string()
    g4_str.assign(my_d.g4experiment)
    amplifier_str = ROOT.std.string()
    amplifier_str.assign(my_d.amplifier)
    
    tree.Branch("voltage", voltage_array, "voltage/D")
    tree.Branch("irradiation_flux", irradiation_array, "irradiation_flux/D")
    tree.Branch("g4experiment", g4_str)
    tree.Branch("amplifier", amplifier_str)

    if store_waveforms:
        n_bins, time_start, time_end = _current_axis(my_d)
        current = [
            ROOT.TH1F("current_%s"%(i), "current_%s"%(i), n_bins, time_start, time_end)
            for i in range(my_d.read_ele_num)
        ]
        cross_talked_current = [
            ROOT.TH1F(
                "cross_talked_current_%s"%(i),
                "cross_talked_current_%s"%(i),
                n_bins,
                time_start,
                time_end,
            )
            for i in range(my_d.read_ele_num)
        ]
        amplified_waveform = [
            ROOT.TH1F(
                "amplified_waveform_%s"%(i),
                "amplified_waveform_%s"%(i),
                n_bins,
                time_start,
                time_end,
            )
            for i in range(my_d.read_ele_num)
        ]
        for i in range(my_d.read_ele_num):
            tree.Branch("current_%s"%(i), current[i])
            tree.Branch("cross_talked_current_%s"%(i), cross_talked_current[i])
            tree.Branch("amplified_waveform_%s"%(i), amplified_waveform[i])
    # Note: TTree.Branch() needs the binded variable (namely the address) to be valid and the same while Fill(), 
    # so don't put the Branch() into other methods/functions!

    for event in range(start_n,end_n):
        print("run events number:%s"%(event))
        if len(my_g4.p_steps[event-start_n]) > 5:
            effective_number += 1
            my_current = ccrt.CalCurrentG4P(
                my_d,
                my_f,
                my_g4,
                event-start_n,
                keep_drift_paths=event in plot_events,
            )

            if ("strip" in my_d.det_model or "pixel" in my_d.det_model) and my_d.cross_talk != None:
                my_current.cross_talk_cu = cross_talk(my_d.det_name, my_d.cross_talk, my_current.sum_cu)
            else:
                my_current.cross_talk_cu = my_current.sum_cu

            if store_waveforms:
                ele_current = Amplifier(
                    my_current.cross_talk_cu,
                    my_d.amplifier,
                    seed=event,
                    CDet=my_d.capacitance,
                    is_cut=True,
                )
            else:
                ele_current = None

            if event in plot_events:
                _draw_signal_sample(
                    my_d,
                    my_g4,
                    my_f,
                    my_current,
                    ele_current,
                    event,
                    output_path,
                )

            event_array[0] = event
            e_dep_array[0] = my_g4.edep_devices[event-start_n]
            # assume the list of electrons is sorted by particle injection trace
            # and all inside the active region of the detector
            par_in_array[0], par_in_array[1], par_in_array[2] = my_g4.p_steps_current[my_g4.selected_batch_number][0]
            par_out_array[0], par_out_array[1], par_out_array[2] = my_g4.p_steps_current[my_g4.selected_batch_number][-1]

            # Note: TTree.Fill() needs the binded variable (namely the address) to be valid and the same with Branch(), 
            # so don't put Fill() into other methods/functions!
            if store_waveforms:
                for i in range(my_d.read_ele_num):
                    _copy_histogram(current[i], my_current.sum_cu[i])
                    _copy_histogram(cross_talked_current[i], my_current.cross_talk_cu[i])
                    _copy_histogram(amplified_waveform[i], ele_current.amplified_currents[i])

            # Barely clone another TH1F will cause segmentation fault
            tree.Fill()

    detection_efficiency =  effective_number/(end_n-start_n) 
    print("detection_efficiency=%s"%detection_efficiency, flush=True)

    file_path = os.path.join(
        output_path,
        "signal_"+
        str(instance_number)+
        str(my_d.voltage)+
        str(my_d.irradiation_flux)+
        str(my_d.bound)+
        str(my_d.g4experiment)+
        str(my_d.amplifier)+
        ".root",
    )
    file = ROOT.TFile(file_path, "RECREATE")
    tree.Write()
    file.Close()

def main(kwargs):
    det_name = kwargs['det_name']
    my_d = bdv.Detector(det_name)
    apply_signal_experiment(my_d, kwargs)
    if kwargs['voltage'] != None:
        my_d.voltage = kwargs['voltage']

    if kwargs['irradiation'] != None:
        my_d.irradiation_flux = float(kwargs['irradiation'])
    if kwargs.get("events_per_job") is not None:
        my_d.g4_config["total_events"] = int(kwargs["events_per_job"])
    if kwargs.get("g4_vis_driver"):
        my_d.g4_config["g4_vis_driver"] = kwargs["g4_vis_driver"]

    runs.prepare_run_record(kwargs, my_d)
    if kwargs.get("g4_vis"):
        my_d.g4_config["g4_vis_output"] = os.path.join(
            kwargs["_run_path"],
            "g4_geometry",
        )
    my_d.device = kwargs["_field_source"]
    my_d.region = kwargs["_field_source"]

    my_f = devfield.DevsimField(
        my_d.device,
        my_d.dimension,
        my_d.voltage,
        my_d.read_out_contact,
        my_d.mesher,
        is_plugin=my_d.is_plugin(),
        irradiation_flux=my_d.irradiation_flux,
        bounds=my_d.bound,
        field_set=kwargs["_field_set"],
    )
    if "lgad" in my_d.det_model:
        my_d.gain_rate_cal(my_f)

    g4_dic = my_d.g4_config
    total_events = int(g4_dic['total_events'])

    job_number = kwargs['job']
    instance_number = job_number

    g4_seed = instance_number * total_events
    random.seed(g4_seed)
    my_g4 = GeneralG4Interaction(my_d, my_d.g4_config, g4_seed, kwargs.get("g4_vis", False))

    ele_json = optional_component_path(
        "electronics", "analog", my_d.amplifier + ".json"
    )
    ele_cir = optional_component_path(
        "electronics", "analog", my_d.amplifier + ".cir"
    )
    if ele_json is not None and os.path.exists(ele_json):
        ROOT.gRandom.SetSeed(instance_number) # to ensure time resolution result reproducible
    elif ele_cir is not None and os.path.exists(ele_cir):
        # subprocess.run(['ngspice -b '+ele_cir], shell=True)
        # noise_raw = "./output/elec/" + amplifier + "/noise.raw" # need to be fixed in the .cir
        # try:
        #     with open(noise_raw, 'r') as f_in:
        #         lines = f_in.readlines()
        #         freq, noise = [],[]
        #         for line in lines:
        #             freq.append(float(line.split()[0]))
        #         noise.append(float(line.split()[1]))
        # except FileNotFoundError:
        #     print("Warning: ngspice .noise experiment is not set.")
        #     print("Please check the .cir file or make sure you have set an TRNOISE source.")
        # TODO: fix noise seed, add noise from ngspice .noise spectrum
        pass
    
    store_waveforms = kwargs.get("workflow") != "cce"
    batch_loop(
        my_d,
        my_f,
        my_g4,
        g4_seed,
        total_events,
        instance_number,
        kwargs["_run_batch_path"],
        store_waveforms=store_waveforms,
        plot_samples=kwargs.get("_signal_plot_samples", 0),
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    del my_g4
