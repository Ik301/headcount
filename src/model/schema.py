"""Shared helpers for privacy rules.

Local tables keep DIDs. Anything that leaves the machine (site_data.json, API replies, committed samples)
goes through public_ref: public accounts keep their handle, private ones become a salted hash.
"""
import hashlib
import os

PUBLIC_FOLLOWERS = 5000


OPT_OUT_LABELS = ("!no-unauthenticated",)  # the account asked not to be shown to logged-out viewers


def is_public(profile: dict) -> bool:
    """README rule: 5,000+ followers, verified, or self-labeled bot. News organizations are usually verified.
    An account that opted out of logged-out viewing is never public, whatever its size (bug 19)."""
    labels = [l.get("val") for l in (profile.get("labels") or [])]
    if any(l in OPT_OUT_LABELS for l in labels):
        return False
    if (profile.get("followersCount") or 0) >= PUBLIC_FOLLOWERS:
        return True
    if (profile.get("verification") or {}).get("verifiedStatus") == "valid":
        return True
    return any(l in ("bot", "!bot") for l in labels)


def hashed_id(did: str) -> str:
    salt = os.environ.get("SALT", "")
    if not salt:
        import warnings

        warnings.warn("SALT is not set; using the dev salt 'dev-salt' (fine for local runs, not for exports)")
        salt = "dev-salt"
    return hashlib.sha256((salt + did).encode()).hexdigest()[:16]


def public_ref(did: str, handle: str | None, public: bool) -> dict:
    """What may be shown outside the machine for one account."""
    if public and handle:
        return {"ref": handle, "public_handle": handle}
    return {"ref": hashed_id(did), "public_handle": None}
