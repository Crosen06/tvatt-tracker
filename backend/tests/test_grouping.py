from app.grouping import Item, Prog, care_class, check_selection, group_items, suggest_program

PROGS = [
    Prog(1, "Bomull 40°", 40, "normal"),
    Prog(2, "Bomull 60°", 60, "normal"),
    Prog(3, "Syntet 40°", 40, "synthetic"),
    Prog(4, "Fintvätt 30°", 30, "delicate"),
    Prog(5, "Ull 30°", 30, "wool"),
]


def item(id, color="dark", temp=40, spin=1200, care="normal", dry=True, person=1):
    return Item(id=id, person_id=person, max_temp=temp, color=color, max_spin=spin, care=care, tumble_dry=dry)


def test_care_class():
    assert care_class("normal") == "standard"
    assert care_class("synthetic") == "standard"
    assert care_class("wool") == "wool"


def test_empty_basket_returns_no_groups():
    assert group_items([], PROGS) == []


def test_single_item_one_group():
    groups = group_items([item(1)], PROGS)
    assert len(groups) == 1
    g = groups[0]
    assert (g.color, g.care, g.temp, g.spin, g.item_ids, g.program_id) == ("dark", "normal", 40, 1200, [1], 1)


def test_colors_split():
    groups = group_items([item(1, color="white"), item(2, color="dark")], PROGS)
    assert sorted(g.color for g in groups) == ["dark", "white"]


def test_normal_and_synthetic_combine_as_synthetic():
    groups = group_items([item(1, temp=60), item(2, care="synthetic", temp=40)], PROGS, split_hot=False)
    assert len(groups) == 1
    assert groups[0].care == "synthetic"
    assert groups[0].temp == 40
    assert groups[0].program_id == 3


def test_wool_separate_from_normal():
    groups = group_items([item(1), item(2, care="wool", temp=30)], PROGS)
    assert len(groups) == 2


def test_hot_split_on():
    groups = group_items([item(1, temp=60), item(2, temp=40)], PROGS, split_hot=True)
    assert len(groups) == 2


def test_hot_split_off():
    groups = group_items([item(1, temp=60), item(2, temp=40)], PROGS, split_hot=False)
    assert len(groups) == 1
    assert groups[0].temp == 40


def test_min_spin_and_temp():
    groups = group_items([item(1, spin=1200, temp=40), item(2, spin=800, temp=30)], PROGS)
    assert groups[0].spin == 800
    assert groups[0].temp == 30


def test_no_dry_ids_listed():
    groups = group_items([item(1), item(2, dry=False)], PROGS)
    assert groups[0].no_dry_ids == [2]


def test_groups_sorted_largest_first():
    groups = group_items([item(1, color="white"), item(2), item(3)], PROGS)
    assert [len(g.item_ids) for g in groups] == [2, 1]


def test_suggest_program_picks_closest_not_above():
    assert suggest_program("normal", 50, PROGS) == 1
    assert suggest_program("normal", 90, PROGS) == 2
    assert suggest_program("wool", 20, PROGS) is None


def test_check_selection_compatible():
    basket = [item(1), item(2), item(3, color="white"), item(4, temp=60), item(5, care="synthetic")]
    sel = check_selection([basket[0]], basket, PROGS)
    assert sel.conflicts == []
    assert sel.compatible_ids == [2, 5]
    assert sel.group.item_ids == [1]


def test_check_selection_conflicts():
    a, b, c = item(1, color="white"), item(2, color="dark"), item(3, color="white", care="wool", temp=30)
    sel = check_selection([a, b], [a, b, c], PROGS)
    assert sel.conflicts == ["Olika färggrupper: vitt + mörkt"]
    assert sel.group is None and sel.compatible_ids == []
    sel2 = check_selection([a, c], [a, b, c], PROGS)
    assert "Ull måste tvättas för sig" in sel2.conflicts


def test_check_selection_hot_conflict():
    a, b = item(1, temp=60), item(2, temp=40)
    assert check_selection([a, b], [a, b], PROGS).conflicts == ["60° och varmare tvättas för sig"]
    assert check_selection([a, b], [a, b], PROGS, split_hot=False).conflicts == []
