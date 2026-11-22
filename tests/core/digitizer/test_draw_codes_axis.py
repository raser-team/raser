import numpy as np

from raser.core.digitizer import draw


def _scale(monkeypatch, tmp_path, codes, bits):
    """Return the y-axis scale of the ``codes`` figure drawn from ``codes``."""
    captured = []
    monkeypatch.setattr(
        draw.figures,
        "save",
        lambda figure, folder, name, *suffixes: captured.append(figure),
    )
    draw.draw_codes(tmp_path, codes, bits)
    return captured[0].axes[0].get_yscale()


def test_skewed_code_counts_give_log_axis(monkeypatch, tmp_path):
    # code 1 is hit 60 times, code 2 once: ratio 60 > 30
    codes = np.array([1] * 60 + [2])
    assert _scale(monkeypatch, tmp_path, codes, 2) == "log"


def test_flat_code_counts_give_linear_axis(monkeypatch, tmp_path):
    codes = np.array([0, 1, 2, 3, 1, 2])
    assert _scale(monkeypatch, tmp_path, codes, 2) == "linear"
