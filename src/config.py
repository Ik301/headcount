"""Thresholds shared by both halves (docs/DEMO.md, Build specification: Global conventions). Change only via a [contract] PR."""

HEADLINE_THRESHOLD = 0.5  # likely automated, for headline shares
STRIP_THRESHOLDS = (0.3, 0.5, 0.7, 0.9)  # threshold sensitivity strip
HUMAN_MAX = 0.3  # amplifier definition: humans have p_automated < 0.3
AUTOMATED_MIN = 0.7  # amplifier definition: amplified posts come from p_automated >= 0.7
MIN_MATCHES = 30  # fewer matched posts -> insufficient-data reply
MIN_BOT_ACCOUNTS_FOR_COMMONALITY = 5
MIN_HUMANS_FOR_AMPLIFIER_LINE = 10
SIMILARITY_FLOOR = 0.60  # hybrid retriever; best floor in eval/retrieval/report-hybrid.md (recall@20 first 20 claims 0.787)
STORY_START = "2026-11-05T00:00:00Z"
STORY_END = "2026-11-14T00:00:00Z"
