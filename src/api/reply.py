"""Reply text and chart for a /claim result. The reply rules in docs/DEMO.md are enforced here."""
import io
import re

from src import config as cfg

TRUTH_LINE = "I don't judge whether the claim is true."
DECLINE = "I can't run checks on claims about a private person. I can check claims about public stories, like the Jensen Huang week."
FAILURE = "Something broke on my end and I couldn't finish that check. The team has a recording of a full check at the table."
STILL_CHECKING = "Still checking, the live search is slow on this one."
OPERATOR_WORDS = re.compile(r"\b(run by|operated by|controlled by|behind these accounts|paid by)\b", re.I)


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _unprofiled(a: dict) -> bool:
    return a.get("id") == "unknown" or (a.get("label") or "").strip().lower() == "not profiled"


def _window(result: dict) -> str:
    return "Nov 5 to 13" if result.get("scope", "corpus") == "corpus" else "recent posts"


def compose(result: dict) -> str:
    """Templates from docs/DEMO.md, Build specification: Reply text templates."""
    # The live path marks declines and failures; src.api.app recomposes every result, so these must win here
    # (otherwise a declined private-person claim came back as the insufficient-data reply).
    if result.get("declined"):
        return DECLINE
    if result.get("error"):
        return FAILURE
    n = result["matched_posts"]
    if n < cfg.MIN_MATCHES:
        return (
            f"I found {n} Bluesky posts making this claim, which isn't enough to measure automation reliably (I need at least {cfg.MIN_MATCHES}). "
            "Try a broader wording, or ask about the Jensen Huang story from Nov 5 to 13. " + TRUTH_LINE
        )
    narrs = [nr for nr in result["narratives"] if nr["share_of_matches"] >= 0.05][:4] or result["narratives"][:1]
    base = result.get("baseline_bot_share") or 0
    lines = [f"I found {n:,} Bluesky posts making this claim ({_window(result)})."]
    for nr in narrs:
        lo, hi = nr["bot_post_share_ci"]
        line = f"{nr['label']}: {pct(nr['share_of_matches'])} of posts. Likely automated: {pct(nr['bot_post_share'])} ({lo * 100:.0f} to {hi * 100:.0f}%)"
        if base and nr["bot_post_share"] >= 2 * base:
            line += f", about {nr['bot_post_share'] / base:.0f}x the story's baseline"
        lines.append(line + ".")
    if len(result["narratives"]) > len(narrs):
        k = len(result["narratives"]) - len(narrs)
        lines.append(f"+ {k} smaller narrative{'s' if k > 1 else ''} in the full view.")
    com = [c for c in result.get("bot_commonalities", []) if c.get("accounts")]
    if com and narrs:
        top = max(narrs, key=lambda nr: nr["bot_post_share"])["label"]
        parts = [c["signal"] if "account" in c["signal"] else f"{c['signal']} ({c['accounts']} accounts)" for c in com[:2]]
        lines.append(f"The likely automated accounts pushing {top}: " + "; ".join(parts) + ".")
    amp = result.get("amplifiers", {})
    n_h = amp.get("n_humans", 0) or 0
    # Only profiled archetypes count: "Not profiled" is missing data, not a kind of account. The line needs at least
    # MIN_HUMANS profiled amplifiers, and the largest profiled group must have a lift above 1, so it never says
    # "mostly X (0.8x more likely)" or names a group that rests on one account.
    prof = [a for a in amp.get("archetype_mix", []) if a.get("lift") and not _unprofiled(a)]
    n_prof = round(n_h * sum(a.get("share", 0) for a in prof))
    top = max(prof, key=lambda a: (a.get("share", 0), a["lift"])) if prof else None
    if n_h >= cfg.MIN_HUMANS_FOR_AMPLIFIER_LINE and n_prof >= cfg.MIN_HUMANS_FOR_AMPLIFIER_LINE and top and top["lift"] > 1:
        lines.append(f"The real accounts spreading their posts are mostly \"{top['label']}\" ({top['lift']:.1f}x more likely than similar accounts).")
    tail = TRUTH_LINE + (f" Full view: {result['dashboard_url']}" if result.get("dashboard_url") else "")
    lines.append(tail)
    return OPERATOR_WORDS.sub("linked to", "\n".join(lines))


def chart_png(result: dict) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    narrs = result["narratives"][:6]
    fig, ax = plt.subplots(figsize=(7, 0.6 * max(len(narrs), 1) + 1.4), dpi=150)
    labels = [nr["label"] for nr in narrs][::-1]
    share = [nr["share_of_matches"] for nr in narrs][::-1]
    bot = [nr["share_of_matches"] * nr["bot_post_share"] for nr in narrs][::-1]
    ax.barh(labels, share, color="#c8ccd4", label="share of matching posts")
    ax.barh(labels, bot, color="#e5484d", label="from likely automated accounts")
    for y, nr in enumerate(narrs[::-1]):
        ax.text(nr["share_of_matches"] + 0.01, y, f"{pct(nr['bot_post_share'])} automated", va="center", fontsize=8)
    ax.set_xlim(0, max(share + [0.1]) * 1.35)
    ax.set_xlabel("share of posts matching the claim")
    ax.set_title(f"\"{result['claim'][:60]}\"  ({result['matched_posts']:,} posts)", fontsize=9)
    ax.legend(loc="lower right", fontsize=7, frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
