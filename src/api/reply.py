"""Reply text and chart for a /claim result. The reply rules in docs/DEMO.md are enforced here."""
import io
import re
from pathlib import Path

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


# Chart palette and type match the web app (DESIGN.md): magenta means "likely automated" and nothing else.
PAPER, INK, INK_2, INK_3, RULE, MAGENTA = "#ECEEE7", "#111814", "#3B4640", "#7C867F", "#CBD1C4", "#C81E66"
_FONT_DIR = Path(__file__).resolve().parent / "fonts"  # Schibsted Grotesk + Fragment Mono, SIL OFL 1.1 (licences alongside)


def _font(file: str, fallback: str, weight: str = "normal"):
    """The web app's font when the TTF ships with the repo, else a DejaVu fallback (never fails)."""
    from matplotlib.font_manager import FontProperties

    path = _FONT_DIR / file
    if path.is_file():
        return FontProperties(fname=str(path))
    return FontProperties(family=fallback, weight=weight)


def _source_lines(result: dict) -> list[str]:
    days = (result.get("live") or {}).get("days")
    when = f"last {days} days" if days and result.get("scope") == "live" else _window(result).replace(" to ", "\u2013")
    first = ["Bluesky public posts", when]
    if result.get("matched_posts") is not None:
        first.append(f"n={result['matched_posts']:,}")
    return [" \u00b7 ".join(first), f"likely automated = bot score \u2265 {cfg.HEADLINE_THRESHOLD:g}"]


def chart_png(result: dict) -> bytes:
    """Bar per narrative: share of matching posts (rule tone) with its likely automated part in magenta.

    Sized for iMessage on a phone (about 350 px wide): 6 in wide at 200 dpi, labels above the bars."""
    import textwrap

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    sans = _font("SchibstedGrotesk-Regular.ttf", "DejaVu Sans")
    bold = _font("SchibstedGrotesk-SemiBold.ttf", "DejaVu Sans", "bold")
    mono = _font("FragmentMono-Regular.ttf", "DejaVu Sans Mono")

    narrs = (result.get("narratives") or [])[:6]
    claim = textwrap.wrap(f"\u201c{result.get('claim', '')}\u201d", 38, max_lines=2, placeholder="\u2026\u201d") or ["\u201c\u201d"]
    line_h, row_h, foot_h = 0.32, 0.78, 0.78
    head_h = 0.32 + line_h * len(claim) + 0.08 + 0.34 + 0.46  # inches: margin, claim, subtitle, legend
    W = 6.0
    H = max(3.6, head_h + row_h * max(len(narrs), 1) + foot_h)
    fig = plt.figure(figsize=(W, H), dpi=200, facecolor=PAPER)
    L, R = 0.32 / W, 1 - 0.32 / W  # side margins in figure fraction

    def y(inches_from_top: float) -> float:
        return 1 - inches_from_top / H

    # Header: the claim, then what is shown, then the two-colour legend.
    top = 0.32
    for i, line in enumerate(claim):
        fig.text(L, y(top + line_h * i), line, fontproperties=bold, fontsize=17, color=INK, va="top")
    top += line_h * len(claim) + 0.08
    n = result.get("matched_posts")
    sub = f"{n:,} posts making this claim, by narrative" if n is not None else "posts making this claim, by narrative"
    fig.text(L, y(top), sub, fontproperties=sans, fontsize=12, color=INK_2, va="top")
    top += 0.34
    lx = L
    for colour, text in ((RULE, "share of posts"), (MAGENTA, "from likely automated accounts")):
        fig.patches.append(Rectangle((lx, y(top + 0.14)), 0.12 / W, 0.12 / H, transform=fig.transFigure, color=colour, lw=0))
        t = fig.text(lx + 0.19 / W, y(top + 0.08), text, fontproperties=mono, fontsize=9.5, color=INK_2, va="center")
        fig.canvas.draw()
        bb = t.get_window_extent().transformed(fig.transFigure.inverted())
        lx = bb.x1 + 0.28 / W
    top += 0.46

    if not narrs:
        fig.text(L, y(top + 0.3), "No narratives to chart for this claim.", fontproperties=sans, fontsize=13, color=INK_3, va="top")
    smax = max([nr.get("share_of_matches", 0) for nr in narrs] + [0.1])
    span = (R - L) * 0.86  # room for the share value after the longest bar
    bar_h = 0.24
    for nr in narrs:
        share = nr.get("share_of_matches", 0) or 0
        bot = nr.get("bot_post_share", 0) or 0
        label = textwrap.shorten(nr.get("label", ""), 40, placeholder="\u2026")
        fig.text(L, y(top), label, fontproperties=sans, fontsize=13.5, color=INK, va="top")
        fig.text(R, y(top + 0.03), f"{pct(bot)} automated", fontproperties=mono, fontsize=11.5,
                 color=MAGENTA if bot > 0 else INK_3, va="top", ha="right")
        by = y(top + 0.3 + bar_h)
        w = span * share / smax
        fig.patches.append(Rectangle((L, by), w, bar_h / H, transform=fig.transFigure, color=RULE, lw=0))
        if bot > 0:
            fig.patches.append(Rectangle((L, by), max(w * bot, 0.025 / W), bar_h / H, transform=fig.transFigure, color=MAGENTA, lw=0))
        fig.text(L + w + 0.08 / W, by + bar_h / H / 2, pct(share), fontproperties=mono, fontsize=11.5, color=INK_2, va="center")
        top += row_h

    # Footer: thin rule, then the mono source line.
    fy = y(H - foot_h + 0.12)
    fig.add_artist(plt.Line2D([L, R], [fy, fy], transform=fig.transFigure, color=RULE, lw=1))
    for i, line in enumerate(_source_lines(result)):
        fig.text(L, y(H - foot_h + 0.3 + 0.2 * i), line, fontproperties=mono, fontsize=9, color=INK_3, va="center")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=PAPER)
    plt.close(fig)
    return buf.getvalue()
