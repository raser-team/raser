import numpy as np

from raser.core.trigger import draw


def _scale(monkeypatch, tmp_path, recorded_V, discarded_V):
    """Return the y-axis scale of a one-panel ``trigger_amplitude`` figure."""
    captured = []
    monkeypatch.setattr(
        draw.figures,
        "save",
        lambda figure, folder, name, *suffixes: captured.append(figure),
    )
    draw.draw_trigger_amplitude(tmp_path, [("channel", recorded_V, discarded_V, 0.0)])
    return captured[0].axes[0].get_yscale()


def test_skewed_amplitude_counts_give_log_axis(monkeypatch, tmp_path):
    # 60 events in one bin and a single event in another: ratio 60 > 30
    recorded = np.array([-1.0] * 60 + [-0.5])
    assert _scale(monkeypatch, tmp_path, recorded, np.array([])) == "log"


def test_flat_amplitude_counts_give_linear_axis(monkeypatch, tmp_path):
    recorded = np.array([-1.0, -1.0, -0.5, -0.5])
    discarded = np.array([-0.2, -0.2])
    assert _scale(monkeypatch, tmp_path, recorded, discarded) == "linear"
