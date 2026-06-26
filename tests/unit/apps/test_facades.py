from raser.apps import cce
from raser.apps import field
from raser.apps import timeres


def test_cce_run_prepares_signal_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(cce.signal, "run_signal", lambda data: called.append(data.copy()))

    cce.run(kwargs)

    assert called[0]["source"] == "decay/Am241"
    assert called[0]["field"] == "default"
    assert called[0]["events_per_job"] == 10000
    assert called[0]["workflow"] == "cce"
    assert called[0]["experiment"] == "charge_collection"


def test_cce_analyze_prepares_metrics_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(cce.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(cce.metrics, "main", lambda data: called.append(data.copy()))

    cce.analyze(kwargs)

    assert called[0]["workflow"] == "cce"
    assert called[0]["signal_output_label"] == "cce"
    assert called[0]["signal_source"] == "Am241"


def test_timeres_run_prepares_signal_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(timeres.signal, "run_signal", lambda data: called.append(data.copy()))

    timeres.run(kwargs)

    assert called[0]["source"] == "decay/Sr90"
    assert called[0]["field"] == "default"
    assert called[0]["events_per_job"] == 10000
    assert called[0]["workflow"] == "timeres"
    assert called[0]["experiment"] == "time_resolution"


def test_timeres_analyze_prepares_metrics_workflow(monkeypatch):
    called = []
    kwargs = {"source": None, "field": None, "events_per_job": None, "config": None}

    monkeypatch.setattr(timeres.runs, "apply_run_config", lambda data: data.update({"_run_config": {}}))
    monkeypatch.setattr(timeres.metrics, "main", lambda data: called.append(data.copy()))

    timeres.analyze(kwargs)

    assert called[0]["workflow"] == "timeres"
    assert called[0]["signal_output_label"] == "timeres"
    assert called[0]["signal_source"] == "Sr90"


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
