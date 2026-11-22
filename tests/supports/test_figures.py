from __future__ import annotations

from pathlib import Path

import pytest

from raser.supports import figures


def test_file_name_writes_numbers_in_shortest_form_with_units() -> None:
    assert figures.file_name("electric_field", (200.0, "V")) == "electric_field_200V"
    assert figures.file_name("electric_field", (-200, "V")) == "electric_field_-200V"
    assert figures.file_name("cfd", 0.5) == "cfd_0.5"


def test_file_name_joins_event_and_electrode_suffixes() -> None:
    assert figures.file_name("current", 17, "electrode", 2) == "current_17_electrode_2"


@pytest.mark.parametrize(
    ("name", "suffixes"),
    [
        ("Electric Field", ()),
        ("a__b", ()),
        ("current", (True,)),
        ("field", ((1, "kV/cm"),)),
    ],
)
def test_file_name_rejects_names_that_are_not_lowercase_words(name, suffixes) -> None:
    with pytest.raises(
        ValueError, match="figure name must be lowercase words joined by _: "
    ):
        figures.file_name(name, *suffixes)


def test_label_shows_micro_and_exponents() -> None:
    assert figures.label("Depth", "um") == "Depth [μm]"
    assert figures.label("Depth", "um", root=True) == "Depth [#mum]"
    assert figures.label("Doping", "cm-3") == "Doping [cm⁻³]"


def test_label_without_unit_is_the_quantity() -> None:
    assert figures.label("Weighting potential") == "Weighting potential"


def test_label_rejects_unknown_unit() -> None:
    with pytest.raises(ValueError, match="unknown unit: furlong"):
        figures.label("Length", "furlong")


def test_unit_converts_si_values_to_plot_units() -> None:
    assert 4.2e6 / figures.UNIT["kV/cm"] == pytest.approx(42, rel=1e-12)
    assert 3e-9 / figures.UNIT["ns"] == pytest.approx(3, rel=1e-12)
    joules = 100 * 1e3 * 1.602176634e-19
    assert joules / figures.UNIT["keV"] == pytest.approx(100, rel=1e-12)


def test_save_creates_folder_and_writes_png_and_pdf(tmp_path: Path) -> None:
    figure, axis = figures.new()
    axis.plot([0, 1], [0, 1])
    png = figures.save(figure, tmp_path / "plots" / "field", "current", 17)
    assert png == tmp_path / "plots" / "field" / "current_17.png"
    assert png.is_file()
    assert png.with_suffix(".pdf").is_file()


def test_events_axis_has_integer_ticks_and_title() -> None:
    figure, axis = figures.new()
    axis.set_ylim(0, 7.5)
    figures.events(axis)
    ticks = axis.get_yticks()
    assert all(float(t).is_integer() for t in ticks)
    assert axis.get_ylabel() == "Events"


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ([14, 7, 4, 1], False),
        ([500, 40, 2, 1], True),
        ([0, 0, 31, 1], True),
        ([5, 5, 5], False),
        ([], False),
        ([0, 0], False),
        ([30, 1], False),
        ([0, 20, 10], False),
    ],
)
def test_log_counts_needs_the_tallest_bin_over_30_times_the_lowest_filled_one(
    counts, expected
) -> None:
    assert figures.log_counts(counts) is expected


@pytest.mark.parametrize(
    ("counts", "scale"), [([600, 30, 1], "log"), ([14, 7, 1], "linear")]
)
def test_events_axis_follows_the_counts_of_its_histogram(counts, scale) -> None:
    figure, axis = figures.new()
    heights, _, _ = axis.hist(range(len(counts)), bins=len(counts), weights=counts)
    figures.events(axis, counts=heights)
    assert axis.get_yscale() == scale
    if scale == "linear":
        assert all(float(t).is_integer() for t in axis.get_yticks())
