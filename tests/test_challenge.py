"""M7 challenge set: committed file shape and privacy. No torch, no raw data."""
import json
import re


def test_challenge_file_shape_and_privacy():
    d = json.load(open("data/sample/challenge.json"))
    acc = d["accounts"]
    assert len(acc) == 20
    tiers = [a["tier"] for a in acc]
    assert tiers.count("automated") == 5 and tiers.count("human") == 5 and tiers.count("middle") == 10
    for a in acc:
        assert set(a) >= {"account_ref", "posts", "p_automated", "reasons", "hand_label"}
        assert a["account_ref"] == a["public_handle"]  # only public accounts are in this file
        assert 3 <= len(a["posts"]) <= 5 and 0 <= a["p_automated"] <= 1
        assert a["hand_label"] in ("automated", "human", "")
        assert (a["hand_label"] == "") == (a["tier"] == "middle")  # middle 10 wait for Isaac
    blob = json.dumps(d)
    assert "did:plc" not in blob and "did:web" not in blob
    # mentions of other accounts are masked; this frozen file has no unmasked @handle left at all
    assert re.findall(r"@([a-z0-9][a-z0-9.\-]*\.[a-z]{2,})", blob, re.I) == []
