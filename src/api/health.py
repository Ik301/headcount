"""Which bot model is actually serving, for /health (end-to-end check 7, bug 16). No FastAPI import, so it is testable."""
import json
import os
from pathlib import Path

from src.integration import versions


def bot_model_version(artifacts: Path | None = None) -> str:
    """"stub" when the stub module is loaded, or when src.bots.score has no model file (it then falls back to the
    stub); otherwise the version recorded in manifest.json by src.bots.train."""
    if "stubs" in versions()["bots"]:
        return "stub"
    art = Path(artifacts) if artifacts else Path(os.environ.get("DATA_DIR", "data/processed")) / "artifacts"
    if not (art / "bot_model.joblib").exists():
        return "stub (no bot_model.joblib)"
    try:
        return str(json.loads((art / "manifest.json").read_text())["bot_model"]["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown (bot_model.joblib present, manifest.json missing or unreadable)"
