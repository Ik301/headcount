"""Pick Muse's modules when they exist, the stubs otherwise. Everything Hermes builds imports from here."""
import importlib


def _load(primary: str, fallback: str):
    try:
        return importlib.import_module(primary), primary
    except ImportError:
        return importlib.import_module(fallback), fallback


bots, BOTS_SOURCE = _load("src.bots.score", "src.stubs.bots")
coordination, COORD_SOURCE = _load("src.bots.coordination", "src.stubs.analysis")
archetypes, ARCH_SOURCE = _load("src.archetypes.assign", "src.stubs.analysis")


def versions() -> dict:
    return {"bots": BOTS_SOURCE, "coordination": COORD_SOURCE, "archetypes": ARCH_SOURCE}
