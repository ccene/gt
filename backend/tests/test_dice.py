import pytest

from dice import FACES, ability_scores, roll


def test_roll_bounds():
    for _ in range(2000):
        r = roll(3, 20, 2)
        assert len(r["rolls"]) == 3
        assert all(1 <= x <= 20 for x in r["rolls"])
        assert r["total"] == sum(r["rolls"]) + 2


def test_roll_deterministic_total():
    r = roll(1, 6, -1)
    assert 0 <= r["total"] <= 5


@pytest.mark.parametrize("faces", FACES)
def test_all_supported_faces(faces):
    r = roll(5, faces)
    assert all(1 <= x <= faces for x in r["rolls"])


def test_invalid_faces():
    with pytest.raises(ValueError):
        roll(1, 7)


def test_invalid_count():
    with pytest.raises(ValueError):
        roll(0, 20)
    with pytest.raises(ValueError):
        roll(101, 20)


def test_modifier_range():
    with pytest.raises(ValueError):
        roll(1, 20, 1000)


def test_label_formatting():
    assert roll(2, 6, 3)["dice"] == "2d6+3"
    assert roll(1, 20)["dice"] == "1d20"


def test_ability_scores():
    scores = ability_scores()
    assert len(scores) == 6
    assert all(3 <= s <= 18 for s in scores)
