PY ?= python
RAW := data/raw
POSTS := $(RAW)/bsky_jensen_nov5_13.jsonl

.PHONY: data tables

# Pull the story posts, profiles and author histories from Bluesky's public API (about 15 minutes), then build tables.
data: $(POSTS) $(RAW)/profiles.jsonl $(RAW)/history.jsonl tables

$(POSTS):
	mkdir -p $(RAW)
	$(PY) -m src.ingest.bluesky_search --q "jensen huang" --since 2026-11-05T00:00:00Z --until 2026-11-14T00:00:00Z --out $(POSTS)

$(RAW)/profiles.jsonl: $(POSTS)
	$(PY) -m src.ingest.bluesky_profiles --posts $(POSTS) --out $(RAW)/profiles.jsonl

$(RAW)/history.jsonl: $(RAW)/profiles.jsonl
	$(PY) -m src.ingest.bluesky_history --profiles $(RAW)/profiles.jsonl --out $(RAW)/history.jsonl --limit 50

tables:
	$(PY) -m src.model.tables --raw $(RAW) --out data/processed
