"""Bug 14: corpus /claim example posts never carry a private account's handle (mentions or own-domain links)."""
from src.api import analysis


class _Store:
    def __init__(self, public):
        self.public = public

    def ref(self, did):
        return {"ref": "x", "public_handle": "news.example.com" if did in self.public else None}


def test_private_author_links_and_mentions_masked():
    s = _Store(public={"did:plc:pub"})
    priv = analysis._example(s, {"account_id": "did:plc:priv", "text": "read my take at trendy.example.com and ask @friend.bsky.social"})
    assert "trendy.example.com" not in priv["text"] and "@friend.bsky.social" not in priv["text"]
    assert priv["public_handle"] is None
    pub = analysis._example(s, {"account_id": "did:plc:pub", "text": "full story https://news.example.com/a cc @someone.bsky.social"})
    assert "https://news.example.com/a" in pub["text"]  # a public outlet's own links stay
    assert "@someone.bsky.social" not in pub["text"]  # mentions are always masked
    assert pub["public_handle"] == "news.example.com"


def test_long_text_truncated_and_empty_ok():
    s = _Store(public=set())
    assert len(analysis._example(s, {"account_id": "d", "text": "a" * 500})["text"]) == 280
    assert analysis._example(s, {"account_id": "d", "text": None})["text"] == ""
