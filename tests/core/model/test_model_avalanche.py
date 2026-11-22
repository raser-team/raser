import pytest

from raser.core.model.material import Material


@pytest.mark.parametrize("material", ["Diamond", "SiC"])
def test_an_avalanche_model_of_silicon_is_refused_for_another_material(material: str) -> None:
    coefficient = Material(material, avalanche_model="vanOverstraeten").cal_coefficient

    with pytest.raises(ValueError, match=f"vanOverstraeten is not defined for {material}"):
        coefficient(3.0e5, -1, 300.0)


@pytest.mark.parametrize(
    ("material", "model", "field"),
    [("Si", "vanOverstraeten", 3.0e5), ("Si", "Okuto", 3.0e5), ("SiC", "Hatakeyama", 3.0e6)],
)
def test_a_material_ionizes_with_its_own_avalanche_models(material: str, model: str, field: float) -> None:
    coefficient = Material(material, avalanche_model=model).cal_coefficient

    assert coefficient(field, -1, 300.0) > 0.0
    assert coefficient(field, +1, 300.0) > 0.0
