import json

from raser.apps.ana.files import job_file
from raser.apps.ana.files import slice_file
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import write_deposits


def test_slice_file_is_in_the_point_that_holds_the_slice(tmp_path) -> None:
    # two amplifiers on the same events: the second point reads the deposits
    # and the currents of the first, the electronics scan as a whole reads
    # nothing above the experiment
    folder = tmp_path / "amplifier=B" / "seed_7"
    folder.mkdir(parents=True)
    held = {"deposits": "", "currents": "amplifier=A", "waveforms": "amplifier=B"}
    (folder / "run.json").write_text(json.dumps({"point": "amplifier=B", "held_in": held}))

    assert slice_file(folder, 3, "deposits") == tmp_path / "seed_7" / "batch" / "deposits_3.h5"
    assert (
        slice_file(folder, 3, "currents")
        == tmp_path / "amplifier=A" / "seed_7" / "batch" / "currents_3.h5"
    )
    assert slice_file(folder, 3, "waveforms") == folder / "batch" / "waveforms_3.h5"


def test_job_without_events_is_known_from_the_deposits_of_the_point_that_holds_them(tmp_path) -> None:
    folder = tmp_path / "amplifier=B" / "seed_7"
    folder.mkdir(parents=True)
    held = {"deposits": "", "currents": "", "waveforms": "amplifier=B"}
    (folder / "run.json").write_text(json.dumps({"point": "amplifier=B", "held_in": held}))
    (tmp_path / "seed_7" / "batch").mkdir(parents=True)
    write_deposits(str(tmp_path / "seed_7" / "batch" / "deposits_3.h5"), Deposits(50, None, None, []))

    assert job_file(folder, 3, "waveforms") is None
