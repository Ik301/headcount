"""Bug 19: an account that opted out of logged-out viewing is never named, even with 5,000+ followers."""
from src.model.schema import is_public


def test_public_rules():
    assert is_public({"followersCount": 6000})
    assert is_public({"followersCount": 10, "verification": {"verifiedStatus": "valid"}})
    assert is_public({"followersCount": 10, "labels": [{"val": "bot"}]})
    assert not is_public({"followersCount": 4999})


def test_opt_out_label_wins():
    opt = [{"val": "!no-unauthenticated"}]
    assert not is_public({"followersCount": 90000, "labels": opt})
    assert not is_public({"followersCount": 10, "verification": {"verifiedStatus": "valid"}, "labels": opt})
    assert not is_public({"followersCount": 10, "labels": opt + [{"val": "bot"}]})
