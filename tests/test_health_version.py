"""Bug 16: /health reports the bot model version from the manifest, and 'stub' when the stub is what's serving."""
import json

from src.api import health as app


def test_version_from_manifest(tmp_path):
    (tmp_path / "bot_model.joblib").write_bytes(b"x")
    (tmp_path / "manifest.json").write_text(json.dumps({"bot_model": {"version": "v1-hgb-test"}}))
    assert app.bot_model_version(tmp_path) == "v1-hgb-test"


def test_missing_model_file_reports_stub(tmp_path):
    assert app.bot_model_version(tmp_path).startswith("stub")


def test_unreadable_manifest(tmp_path):
    (tmp_path / "bot_model.joblib").write_bytes(b"x")
    assert app.bot_model_version(tmp_path).startswith("unknown")
