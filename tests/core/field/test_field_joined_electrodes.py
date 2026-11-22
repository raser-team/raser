from raser.core.field.weighting import joined_electrodes

ROW = [(0, 1), (1, 2), (2, 3), (3, 4)]


def test_a_conductive_row_joins_the_electrodes_at_its_ends() -> None:
    joined = joined_electrodes([True] * 5, ROW, {"a": [0], "b": [4]})
    assert len(joined) == 1
    names, nodes = joined[0]
    assert names == ("a", "b")
    assert list(nodes) == [0, 1, 2, 3, 4]


def test_a_dielectric_node_in_the_middle_separates_the_electrodes() -> None:
    conductive = [True, True, False, True, True]
    assert joined_electrodes(conductive, ROW, {"a": [0], "b": [4]}) == []


def test_two_contacts_of_one_electrode_are_not_two_electrodes() -> None:
    assert joined_electrodes([True] * 5, ROW, {"a": [0, 4]}) == []


def test_only_the_piece_that_touches_two_electrodes_is_reported() -> None:
    edges = [(0, 1), (3, 4), (5, 6)]
    conductive = [True, True, False, True, True, True, True]
    contacts = {"a": [0], "b": [4], "c": [5], "d": [6]}
    joined = joined_electrodes(conductive, edges, contacts)
    assert [names for names, _ in joined] == [("c", "d")]
    assert list(joined[0][1]) == [5, 6]
