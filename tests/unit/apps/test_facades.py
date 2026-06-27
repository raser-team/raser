from array import array
import json
from pathlib import Path

import pytest

from raser.apps import cce
from raser.apps import field
from raser.apps import timeres
from raser.apps.timeres import summary as timeres_summary


def test_cce_run_prepares_signal_workflow(monkeypatch):
    called = []
    collected = []
    kwargs = {
        "source": None,
        "field": None,
        "events_per_job": None,
        "config": None,
        "collect": False,
        "job": 0,
    }

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(cce.signal, "run_signal", lambda data: called.append(data.copy()))
    monkeypatch.setattr(cce.summary, "collect", lambda data: collected.append(data.copy()))

    cce.run(kwargs)

    assert called[0]["source"] == "decay/Sr90"
    assert called[0]["field"] == "default"
    assert called[0]["events_per_job"] == 10000
    assert called[0]["workflow"] == "cce"
    assert called[0]["experiment"] == "charge_collection"
    assert collected == []


def test_cce_run_collects_local_jobs(monkeypatch):
    calls = []
    kwargs = {
        "_argv": ["cce", "HPK-Si-PiN", "-s", "100"],
        "_entry_command_prefix": ("cce",),
        "source": None,
        "field": None,
        "events_per_job": None,
        "config": None,
        "collect": False,
        "scan": 100,
        "job": None,
        "run": None,
        "signal_batch": False,
        "mem": 1,
    }

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    def ensure_run_id(data):
        data["run"] = "run-1"
        return "run-1"

    monkeypatch.setattr(cce.runs, "ensure_run_id", ensure_run_id)
    monkeypatch.setattr(
        cce.jobs,
        "run_indexed_jobs",
        lambda *args, **kwargs: calls.append(("jobs", args, kwargs)),
    )
    monkeypatch.setattr(cce.summary, "collect", lambda data: calls.append(("collect", data.copy())))

    cce.run(kwargs)

    assert calls[0][0] == "jobs"
    assert calls[0][1][0] == ("cce",)
    assert calls[0][1][1] == ["HPK-Si-PiN", "--run", "run-1", "--events-per-job", "100"]
    assert calls[0][1][2] == 1
    assert calls[0][2]["use_cluster"] is False
    assert calls[1][0] == "collect"


def test_cce_g4_visualization_keeps_experiment_workflow(monkeypatch):
    calls = []
    kwargs = {
        "_argv": ["cce", "HPK-Si-PiN", "-g4_vis"],
        "_entry_command_prefix": ("cce",),
        "source": None,
        "field": None,
        "events_per_job": 100,
        "config": None,
        "collect": False,
        "scan": None,
        "job": None,
        "run": "g4vis",
        "signal_batch": False,
        "mem": 1,
        "g4_vis": True,
    }

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(
        cce.jobs,
        "run_indexed_jobs",
        lambda *args, **kwargs: calls.append(("jobs", args, kwargs)),
    )
    monkeypatch.setattr(cce.summary, "collect", lambda data: calls.append(("collect", data.copy())))

    cce.run(kwargs)

    assert [call[0] for call in calls] == ["jobs", "collect"]


def test_cce_collect_prepares_metrics_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(cce.summary, "collect", lambda data: called.append(data.copy()))

    cce.collect(kwargs)

    assert called[0]["workflow"] == "cce"
    assert called[0]["signal_output_label"] == "cce"
    assert called[0]["signal_source"] == "Sr90"
    assert called[0]["run"] == "latest"


def test_cce_summary_reads_typed_event_statistics(tmp_path):
    import ROOT

    batch_path = tmp_path / "batch"
    batch_path.mkdir()
    for file_index, rows in enumerate(
        (
            [(0.0, 1.0, 2.0, 5.0, 200.0), (1.0, 3.0, 4.0, 7.0, 200.0)],
            [(2.0, 5.0, 6.0, 9.0, 200.0)],
        )
    ):
        root_file = ROOT.TFile(str(batch_path / f"stats_{file_index}.root"), "RECREATE")
        tree = ROOT.TTree("events", "CCE scalar event statistics")
        branches = {
            "event": array("d", [0.0]),
            "amplified_charge": array("d", [0.0]),
            "generated_charge": array("d", [0.0]),
            "current_peak_0": array("d", [0.0]),
            "voltage": array("d", [0.0]),
        }
        for name, value in branches.items():
            tree.Branch(name, value, f"{name}/D")
        for event, amplified_charge, generated_charge, current_peak, voltage in rows:
            branches["event"][0] = event
            branches["amplified_charge"][0] = amplified_charge
            branches["generated_charge"][0] = generated_charge
            branches["current_peak_0"][0] = current_peak
            branches["voltage"][0] = voltage
            tree.Fill()
        tree.Write()
        root_file.Close()

    columns = cce.summary._read_event_arrays(batch_path)
    result = cce.summary._summary(columns)

    assert result["events"] == 3
    assert result["measured"]["amplified_charge"]["mean"] == pytest.approx(3.0)
    assert result["truth"]["generated_charge"]["max"] == pytest.approx(6.0)
    assert result["intermediate"]["current_peak_0"]["min"] == pytest.approx(5.0)
    assert result["run"]["voltage"]["std"] == pytest.approx(0.0)


def test_cce_summary_rejects_mismatched_event_statistics_schema(tmp_path):
    import ROOT

    batch_path = tmp_path / "batch"
    batch_path.mkdir()
    for file_name, branch_name in (
        ("stats_0.root", "event"),
        ("stats_1.root", "other"),
    ):
        root_file = ROOT.TFile(str(batch_path / file_name), "RECREATE")
        tree = ROOT.TTree("events", "CCE scalar event statistics")
        value = array("d", [0.0])
        tree.Branch(branch_name, value, f"{branch_name}/D")
        tree.Fill()
        tree.Write()
        root_file.Close()

    with pytest.raises(ValueError, match="schema mismatch"):
        cce.summary._read_event_arrays(batch_path)


def test_timeres_run_prepares_signal_workflow(monkeypatch):
    called = []
    collected = []
    kwargs = {
        "source": None,
        "field": None,
        "events_per_job": None,
        "config": None,
        "collect": False,
        "job": 0,
    }

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(timeres.signal, "run_signal", lambda data: called.append(data.copy()))
    monkeypatch.setattr(timeres.summary, "collect", lambda run_root: collected.append(run_root))

    timeres.run(kwargs)

    assert called[0]["source"] == "decay/Sr90"
    assert called[0]["field"] == "default"
    assert called[0]["events_per_job"] == 10000
    assert called[0]["workflow"] == "timeres"
    assert called[0]["experiment"] == "time_resolution"
    assert collected == []


def test_timeres_run_collects_local_jobs(monkeypatch):
    calls = []
    kwargs = {
        "_argv": ["timeres", "HPK-Si-PiN", "-s", "100"],
        "_entry_command_prefix": ("timeres",),
        "source": None,
        "field": None,
        "events_per_job": None,
        "config": None,
        "collect": False,
        "scan": 100,
        "job": None,
        "run": None,
        "signal_batch": False,
        "mem": 1,
    }

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    def ensure_run_id(data):
        data["run"] = "run-1"
        return "run-1"

    monkeypatch.setattr(timeres.runs, "ensure_run_id", ensure_run_id)
    monkeypatch.setattr(
        timeres.jobs,
        "run_indexed_jobs",
        lambda *args, **kwargs: calls.append(("jobs", args, kwargs)),
    )
    monkeypatch.setattr(timeres.runs, "run_path", lambda workflow, run_id: Path(f"/tmp/{workflow}/{run_id}"))
    monkeypatch.setattr(timeres.summary, "collect", lambda run_root: calls.append(("collect", run_root)))

    timeres.run(kwargs)

    assert calls[0][0] == "jobs"
    assert calls[0][1][0] == ("timeres",)
    assert calls[0][1][1] == ["HPK-Si-PiN", "--run", "run-1", "--events-per-job", "100"]
    assert calls[0][1][2] == 1
    assert calls[0][2]["use_cluster"] is False
    assert calls[1][0] == "collect"


def test_timeres_g4_visualization_keeps_experiment_workflow(monkeypatch):
    calls = []
    kwargs = {
        "_argv": ["timeres", "HPK-Si-PiN", "-g4_vis"],
        "_entry_command_prefix": ("timeres",),
        "source": None,
        "field": None,
        "events_per_job": 100,
        "config": None,
        "collect": False,
        "scan": None,
        "job": None,
        "run": "g4vis",
        "signal_batch": False,
        "mem": 1,
        "g4_vis": True,
    }

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(
        timeres.jobs,
        "run_indexed_jobs",
        lambda *args, **kwargs: calls.append(("jobs", args, kwargs)),
    )
    monkeypatch.setattr(timeres.summary, "collect", lambda run_root: calls.append(("collect", run_root)))

    timeres.run(kwargs)

    assert [call[0] for call in calls] == ["jobs", "collect"]


def test_timeres_collect_prepares_metrics_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(timeres.runs, "latest_run_path", lambda *args, **kwargs: Path("/tmp/timeres/latest"))
    monkeypatch.setattr(timeres.summary, "collect", lambda run_root: called.append(run_root))

    timeres.collect(kwargs)

    assert called[0] == Path("/tmp/timeres/latest")


def test_timeres_summary_uses_run_record_as_input_contract(tmp_path, monkeypatch):
    calls = []
    run_root = tmp_path / "timeres" / "run-1"
    batch_path = run_root / "batch"
    batch_path.mkdir(parents=True)
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "sensor": "HPK-Si-PiN",
                "voltage": 200,
                "amplifier": "Broad_Band_UCSC",
                "daq": "Alibava",
                "run": "run-1",
            }
        )
        + "\n"
    )
    daq_json = tmp_path / "Alibava.json"
    daq_json.write_text('{"threshold": 0.1, "amplitude_threshold": 0.2}\n')

    class Detector:
        def __init__(self, det_name):
            self.det_name = det_name
            self.voltage = 200
            self.irradiation_flux = None
            self.amplifier = "Broad_Band_UCSC"
            self.daq = "Alibava"

    monkeypatch.setattr(timeres_summary.bdv, "Detector", Detector)
    monkeypatch.setattr(timeres_summary, "component_path", lambda *parts: str(daq_json))
    class Statistics:
        def draw(self, output_path, tag):
            calls.append(("draw", output_path, tag))

    class WaveformStatistics:
        @classmethod
        def from_batch(cls, input_path, detector, threshold, amplitude_threshold):
            calls.append(("from_batch", input_path, detector, threshold, amplitude_threshold))
            return Statistics()

    monkeypatch.setattr(timeres_summary.waveform_stats, "WaveformStatistics", WaveformStatistics)

    timeres_summary.collect(run_root)

    assert calls[0][0] == "from_batch"
    assert calls[0][1] == batch_path
    assert calls[0][2].voltage == 200
    assert calls[0][2].amplifier == "Broad_Band_UCSC"
    assert calls[0][2].daq == "Alibava"
    assert calls[0][3] == 0.1
    assert calls[0][4] == 0.2
    assert calls[1] == ("draw", run_root / "analysis", "run-1")


def test_waveform_statistics_requires_explicit_draw_tag():
    from raser.core.metrics import waveform_stats

    class Detector:
        det_model = "planar"
        read_ele_num = 1
        l_x = 1
        l_y = 1

    statistics = waveform_stats.WaveformStatistics(Detector(), 0.1, 0.2)

    with pytest.raises(ValueError, match="tag must be explicit"):
        statistics.draw("/tmp/unused", None)


def test_field_app_dispatches_asset_actions(monkeypatch):
    called: list[tuple] = []

    monkeypatch.setattr(
        field.solver_section,
        "main",
        lambda kwargs: called.append(("solve", kwargs)),
    )
    monkeypatch.setattr(
        field.extract_from_tcad,
        "main",
        lambda target, is_flip=False: called.append(("import", target, is_flip)),
    )
    monkeypatch.setattr(
        field.weighting_potential,
        "main",
        lambda voltage, electrode, target: called.append(
            ("weight", voltage, electrode, target)
        ),
    )

    kwargs = {
        "target": "HPK-Si-PiN",
        "verbose": 0,
        "umf": False,
        "extract": False,
        "wf_sub": None,
    }
    field.main(kwargs)
    field.import_field({"target": "field.tdr", "verbose": 0, "flip": True})
    field.weight("200", "top", "HPK-Si-PiN")

    assert called == [
        ("solve", kwargs),
        ("import", "field.tdr", True),
        ("weight", "200", "top", "HPK-Si-PiN"),
    ]
