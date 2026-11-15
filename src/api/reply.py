"""Reply text and chart for a /claim result. The reply rules in docs/DEMO.md are enforced here."""
import io
import re
from pathlib import Path

from src import config as cfg

TRUTH_LINE = "Not a truth check: I measure who is pushing it."
DECLINE = "I can't check claims about private people. Public stories are fine, like the Jensen Huang week."
FAILURE = "Something broke on my end and I couldn't finish that check. Try again in a minute."
STILL_CHECKING = "Still checking, the live search is slow on this one."
OPERATOR_WORDS = re.compile(r"\b(run by|operated by|controlled by|behind these accounts|paid by)\b", re.I)


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _unprofiled(a: dict) -> bool:
    return a.get("id") == "unknown" or (a.get("label") or "").strip().lower() == "not profiled"


def _window(result: dict) -> str:
    return "Nov 5 to 13" if result.get("scope", "corpus") == "corpus" else "recent posts"


def pct1(x: float) -> str:
    """The story baseline keeps its one decimal (4.5%, as on the dashboard); claim shares are whole numbers."""
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


def share_str(x: float) -> str:
    return "under 1%" if 0 < x < 0.005 else pct(x)


def claim_level(result: dict) -> tuple[float, float, float]:
    """The claim's overall likely-automated post share with its 95% interval (matched posts, accounts resampled).

    Results stored before the claim-level field existed fall back to the narrative-weighted share and bounds."""
    if result.get("bot_post_share") is not None and result.get("bot_post_share_ci"):
        lo, hi = result["bot_post_share_ci"]
        return float(result["bot_post_share"]), float(lo), float(hi)
    narrs = result.get("narratives") or []
    tot = sum(nr.get("share_of_matches", 0) for nr in narrs) or 1
    def w(f):
        return sum(nr.get("share_of_matches", 0) * f(nr) for nr in narrs) / tot
    return w(lambda nr: nr.get("bot_post_share", 0) or 0), w(lambda nr: (nr.get("bot_post_share_ci") or [0, 0])[0]), w(lambda nr: (nr.get("bot_post_share_ci") or [0, 0])[1])


def has_baseline(result: dict) -> bool:
    """A live search's baseline is its own sample, so there is no usual level to compare with."""
    return result.get("scope", "corpus") == "corpus" and bool(result.get("baseline_bot_share"))


def verdict(result: dict) -> str:
    """Plain verdict from the claim's share interval against the story baseline (corpus), or against half (live)."""
    share, lo, hi = claim_level(result)
    if has_baseline(result):
        base = result["baseline_bot_share"]
        if lo > base:
            return "More automated than usual."
        if hi < base:
            return "Mostly real people, less automation than usual."
        return "Mostly real people."
    if hi < 0.5:
        return "Mostly real people."
    if lo > 0.5:
        return "Mostly likely automated accounts."
    return "About half likely automated, too close to call."


def _shown_narratives(result: dict, k: int = 4) -> list[dict]:
    narrs = result.get("narratives") or []
    return [nr for nr in narrs if nr["share_of_matches"] >= 0.05][:k] or narrs[:1]


def compose(result: dict) -> str:
    """Bubble 1, the answer: a verdict, one number line, the truth line. Detail goes to the card and the follow-ups."""
    # The live path marks declines and failures; src.api.app recomposes every result, so these must win here
    # (otherwise a declined private-person claim came back as the insufficient-data reply).
    if result.get("declined"):
        return DECLINE
    if result.get("error"):
        return FAILURE
    n = result["matched_posts"]
    if n < cfg.MIN_MATCHES:
        return (
            f"Only {n} Bluesky posts match that, too few to measure automation (I need {cfg.MIN_MATCHES}). "
            "Try broader wording, or ask about the Jensen Huang story.\n" + TRUTH_LINE
        )
    share = claim_level(result)[0]
    line = f"{share_str(share)} of the {n:,} posts making this claim come from likely automated accounts."
    if has_baseline(result):
        line += f" Across all posts about the Jensen Huang story: {pct1(result['baseline_bot_share'])}."
    return OPERATOR_WORDS.sub("linked to", "\n".join([verdict(result), line, TRUTH_LINE]))


# ---- menu and follow-ups (deterministic: every number comes from the stored result, no model involved)

EXAMPLES = ["Was Jensen Huang's mistress a Chinese spy?", "Did bots defend Jensen Huang?"]
_MENU_ITEMS = ["What people are saying", "What the automated accounts share", "Who spreads it", "How newsrooms covered it"]
_ALSO_NEED_CLAIM = "Text me a claim first, like \"{ex}\", then reply with a number."


def menu(dashboard_url: str | None = None, examples: bool = False) -> str:
    lines = ["Reply with a number:"] + [f"{i + 1}  {t}" for i, t in enumerate(_MENU_ITEMS)]
    lines.append("Or text any other claim.")
    if examples:
        lines += ["For example:"] + [f"\u201c{e}\u201d" for e in EXAMPLES]
    if dashboard_url:
        lines.append(f"Full view: {dashboard_url}")
    return "\n".join(lines)


def intro() -> str:
    return "I'm Headcount. Text me any claim or story and I'll show how much of the posting behind it is automated."


def intent(text: str) -> int | str | None:
    """'help' for the intro and menu, 1 to 4 for a follow-up, None for anything else (a claim or a free-form question)."""
    t = re.sub(r"[^a-z0-9?# ]+", " ", (text or "").lower()).strip()
    t = re.sub(r"^(please |show me |show |tell me |give me |what about |option |number |no |#)+", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    t = t if t.strip("?") == "" else t.rstrip("?").strip()  # "who shares it?" counts; a bare "?" stays
    if re.fullmatch(r"(help|menu|\?+|hi|hello|hey|yo|start|hiya|sup|hello there|hi there|hey there|what can you do|how does this work)( headcount)?", t):
        return "help"
    table = {
        1: r"1|narratives?|the narratives?|what people are saying|what are people saying|what people say|people are saying",
        2: r"2|bots?|the bots?|automated|automated accounts?|the automated accounts?|what the automated accounts share|what do the bots share",
        3: r"3|who shares it|who spreads it|who is sharing it|who is spreading it|who shares|who spreads|amplifiers?|who shares them",
        4: r"4|news|the news|newsrooms?|news coverage|coverage|how newsrooms covered it|newsroom coverage",
    }
    for k, pat in table.items():
        if re.fullmatch(pat, t):
            return k
    return None


def no_claim_yet() -> str:
    return _ALSO_NEED_CLAIM.format(ex=EXAMPLES[0])


def followup(kind: int, result: dict) -> str:
    """Numbered follow-up from the stored result: at most 4 short lines, ends with the reminder of the other numbers."""
    if result.get("declined") or result.get("error") or result.get("matched_posts", 0) < cfg.MIN_MATCHES:
        return no_claim_yet()
    body = [_followup_narratives, _followup_automated, _followup_spreaders, _followup_news][kind - 1](result)
    return OPERATOR_WORDS.sub("linked to", "\n".join(body))  # the menu rides on the first answer only


def _too_few(nr: dict, result: dict) -> bool:
    """Fewer than MIN_MATCHES posts in a narrative: its automated share is not reported (same rule as the web headline)."""
    n = nr.get("n_posts") or round((nr.get("share_of_matches") or 0) * (result.get("matched_posts") or 0))
    return n < cfg.MIN_MATCHES


def _followup_narratives(result: dict) -> list[str]:
    narrs = result.get("narratives") or []
    if not narrs:
        return ["No narratives to show for this claim."]
    shown = _shown_narratives(result, 3)
    out = [
        f"{nr['label']}: {pct(nr['share_of_matches'])} of posts, too few to measure automation."
        if _too_few(nr, result)
        else f"{nr['label']}: {pct(nr['share_of_matches'])} of posts, {share_str(nr['bot_post_share'])} likely automated."
        for nr in shown
    ]
    rest = len(narrs) - len(shown)
    if rest > 0 and len(out) < 3:
        out.append(f"+ {rest} smaller narrative{'s' if rest > 1 else ''}.")
    return out


def _followup_automated(result: dict) -> list[str]:
    com = [c for c in result.get("bot_commonalities", []) if c.get("accounts")]
    narrs = result.get("narratives") or []
    if not com:
        return [f"Not enough likely automated accounts here to say what they have in common (I need at least {cfg.MIN_BOT_ACCOUNTS_FOR_COMMONALITY}).", "Likely automated = bot score of 0.5 or more."]
    big = [nr for nr in narrs if nr["share_of_matches"] >= 0.05 and not _too_few(nr, result)]
    top = max(big, key=lambda nr: nr["bot_post_share"]) if big else None
    out = ["What the likely automated accounts have in common:"]
    for c in com[:2]:
        sig = c["signal"][:1].upper() + c["signal"][1:]
        out.append(sig if "account" in sig else f"{sig} ({c['accounts']} accounts)")
    if top and top["bot_post_share"] > 0 and len(out) < 3:
        out.append(f"Most automated narrative: {top['label']} ({pct(top['bot_post_share'])}).")
    return out


def _followup_spreaders(result: dict) -> list[str]:
    amp = result.get("amplifiers") or {}
    n = amp.get("n_humans", 0) or 0
    if not n:
        return ["I found no real accounts spreading the likely automated posts."]
    prof = [(a, round(n * a.get("share", 0))) for a in amp.get("archetype_mix", []) if not _unprofiled(a)]
    n_prof = sum(k for _, k in prof)
    out = [f"{n} real account{'s' if n != 1 else ''} spread the likely automated posts; {n_prof} could be profiled."]
    if n_prof < cfg.MIN_HUMANS_FOR_AMPLIFIER_LINE:
        out.append("That is too few to compare with similar accounts.")
        return out
    for a, k in sorted(prof, key=lambda x: -x[1])[:2]:
        lift = a.get("lift")
        tail = f", {lift:.1f}x more likely than similar accounts" if lift and lift > 1 else ""
        out.append(f"\"{a['label']}\": {k} accounts{tail}.")
    return out


MIN_NEWS_FOR_HEDGE = 10  # fewer matching headlines make the hedge comparison noise (0% of 3 vs 0%)


def _followup_news(result: dict) -> list[str]:
    nw = result.get("news") or {}
    hed = nw.get("hedging") or {}
    n_news = nw.get("n_headlines") or hed.get("n_news") or 0
    if nw.get("error") or not n_news:
        return ["No matching headlines from the newsrooms I check (wire services and public broadcasters)."]
    outlets = nw.get("outlets") or {}
    top = ", ".join(f"{o} {k}" for o, k in sorted(outlets.items(), key=lambda kv: -kv[1])[:3])
    out = [f"{n_news} matching headlines from wire services and public broadcasters" + (f" ({top})." if top else ".")]
    if n_news < MIN_NEWS_FOR_HEDGE:
        out.append("Too few headlines to compare how careful their wording is.")
    elif hed.get("news_share") is not None and hed.get("social_share") is not None:
        out.append(f"{pct(hed['news_share'])} of the headlines hedge (\"alleged\", \"suspected\"), vs {pct(hed['social_share'])} of matching Bluesky posts.")
    only = nw.get("narratives_only_on_social") or []
    if only and len(out) < 3:
        o = only[0]
        out.append(f"Only on social media: {o['label']} ({pct(o['social_share'])} of posts).")
    return out


# Chart palette and type match the web app (DESIGN.md): magenta means "likely automated" and nothing else.
PAPER, INK, INK_2, INK_3, RULE, MAGENTA = "#ECEEE7", "#111814", "#3B4640", "#7C867F", "#CBD1C4", "#C81E66"
CAPTION = "#56615A"  # DESIGN.md caption: small text on paper stays above 4.5:1 (INK_3 is for rules and large marks)
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


FOOTER_LINE = "Headcount \u00b7 not a truth check"
CARD_W = 1080  # px; the figure is built at 72 dpi so one point is one pixel and sizes below read as pixels


def card_facts(result: dict) -> dict:
    """What the card says, as plain data (tested without rendering)."""
    n = result.get("matched_posts") or 0
    enough = n >= cfg.MIN_MATCHES and not result.get("declined") and not result.get("error")
    share, lo, hi = claim_level(result) if enough else (0.0, 0.0, 0.0)
    f = {"claim": result.get("claim", ""), "n": n, "enough": enough, "share": share, "lo": lo, "hi": hi}
    f["verdict"] = verdict(result) if enough else ("Too few posts to measure." if not (result.get("declined") or result.get("error")) else "No check to show.")
    f["baseline"] = result["baseline_bot_share"] if enough and has_baseline(result) else None
    f["narratives"] = (result.get("narratives") or [])[:5] if enough else []
    com = [c for c in result.get("bot_commonalities", []) if c.get("accounts")] if enough else []
    f["common"] = ("; ".join((c["signal"] if "account" in c["signal"] else f"{c['signal']} ({c['accounts']} accounts)") for c in com[:2])) if com else None
    nw = result.get("news") or {}
    hed = nw.get("hedging") or {}
    ok = enough and not nw.get("error") and (hed.get("n_news") or 0) >= MIN_NEWS_FOR_HEDGE and hed.get("news_share") is not None and hed.get("social_share") is not None
    f["news"] = (
        f"{pct(hed['news_share'])} of {hed['n_news']} matching headlines hedge (\u201calleged\u201d, \u201csuspected\u201d), vs {pct(hed['social_share'])} of matching Bluesky posts"
        if ok else None
    )
    return f


def chart_png(result: dict) -> bytes:
    """One portrait card for a phone (1080 px wide, nothing under 30 px): verdict and the automated share against the
    story baseline, narratives as bars (magenta = likely automated), what the automated accounts share, the newsroom
    comparison, then the source footer. Palette and fonts are the web app's (DESIGN.md); magenta only ever means
    likely automated."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

    sans = _font("SchibstedGrotesk-Regular.ttf", "DejaVu Sans")
    bold = _font("SchibstedGrotesk-SemiBold.ttf", "DejaVu Sans", "bold")
    mono = _font("FragmentMono-Regular.ttf", "DejaVu Sans Mono")
    F = card_facts(result)
    W, M = CARD_W, 64
    CW = W - 2 * M
    probe = FigureCanvasAgg(Figure(figsize=(W / 72, 1), dpi=72))

    def width(text: str, fp, size: float) -> float:
        fp = fp.copy()
        fp.set_size(size)
        return probe.get_renderer().get_text_width_height_descent(text, fp, False)[0]

    def wrap(text: str, fp, size: float, maxw: float, max_lines: int | None = None) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w_ in words:
            trial = (cur + " " + w_).strip()
            if cur and width(trial, fp, size) > maxw:
                lines.append(cur)
                cur = w_
            else:
                cur = trial
        if cur:
            lines.append(cur)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            while lines[-1] and width(lines[-1] + "\u2026", fp, size) > maxw:
                lines[-1] = lines[-1][:-1].rstrip()
            lines[-1] += "\u2026"
        return lines or [""]

    ops: list = []  # (kind, ...) drawn after the height is known
    y = 56.0

    def text(x, yy, s, fp, size, color, ha="left", va="top"):
        ops.append(("text", x, yy, s, fp, size, color, ha, va))

    def rect(x, yy, w_, h_, color):
        ops.append(("rect", x, yy, w_, h_, color))

    def para(s, fp, size, color, lead, max_lines=None, gap=0.0):
        nonlocal y
        for line in wrap(s, fp, size, CW, max_lines):
            text(M, y, line, fp, size, color)
            y += lead
        y += gap

    # claim
    para(f"\u201c{F['claim']}\u201d", sans, 38, INK_2, 50, max_lines=3, gap=26)

    # verdict
    para(F["verdict"], bold, 62, INK, 70, gap=18)

    if F["enough"]:
        # the number, with what it is a share of
        big = share_str(F["share"]).replace("under 1%", "<1%")
        text(M, y - 8, big, bold, 190, MAGENTA if F["share"] > 0 else INK)
        bw = width(big, bold, 190)
        sub = wrap(f"of the {F['n']:,} posts making this claim come from likely automated accounts", sans, 36, CW - bw - 36)
        sy = y + 38
        for line in sub[:4]:
            text(M + bw + 36, sy, line, sans, 36, INK_2)
            sy += 46
        y += 212

        # scale: 0 to a little past the larger of the interval, the baseline and the share
        base = F["baseline"]
        hi_ = max(F["hi"], base or 0, F["share"])
        amax = max(0.05, hi_ * 1.3)
        amax = min(1.0, float(int(amax * 20 + 0.999)) / 20)  # up to the next 5%
        X = lambda v: M + CW * min(v / amax, 1.0)
        ty, th = y + 52, 40
        rect(M, ty, CW, th, RULE)
        if F["share"] > 0:
            rect(M, ty, max(X(F["share"]) - M, 5), th, MAGENTA)
        # interval whisker under the bar
        wy = ty + th + 18
        rect(X(F["lo"]), wy, max(X(F["hi"]) - X(F["lo"]), 3), 4, INK_2)
        rect(X(F["lo"]), wy - 8, 3, 20, INK_2)
        rect(X(F["hi"]) - 3, wy - 8, 3, 20, INK_2)
        rng = f"likely range {pct(F['lo'])} to {pct(F['hi'])}"
        rx = X(F["lo"])
        rw = width(rng, mono, 30)
        text(min(max(rx, M), W - M - rw), wy + 22, rng, mono, 30, INK_2)
        if base is not None:
            bx = X(base)
            rect(bx - 2, ty - 16, 4, th + 32, INK)
            lab = f"all Huang-story posts {pct1(base)}"
            lw = width(lab, mono, 30)
            right = bx > M + CW * 0.55
            text(bx - lw - 10 if right else bx + 10, ty - 48, lab, mono, 30, INK)
        else:
            text(M, ty - 48, "live search: no story baseline to compare with", mono, 30, CAPTION)
        y = wy + 22 + 30 + 50

        # narratives
        if F["narratives"]:
            ops.append(("rule", y))
            y += 38
            text(M, y, "What people are saying", bold, 40, INK)
            y += 62
            smax = max([nr.get("share_of_matches", 0) for nr in F["narratives"]] + [0.1])
            span = CW - 110  # room for the share after the longest bar
            for nr in F["narratives"]:
                share = nr.get("share_of_matches", 0) or 0
                bot = nr.get("bot_post_share", 0) or 0
                few = _too_few(nr, result)
                if few:  # a share from a handful of posts is noise: never show it in magenta
                    bot = 0
                auto = "too few posts" if few else (f"{share_str(bot)} automated" if bot > 0 else "0% automated")
                aw = width(auto, mono, 32)
                label = wrap(nr.get("label", ""), sans, 38, CW - aw - 30, 2)
                for line in label:
                    text(M, y, line, sans, 38, INK)
                    if line is label[0]:
                        text(W - M, y + 3, auto, mono, 32, MAGENTA if bot > 0 else CAPTION, ha="right")
                    y += 46
                by, bh = y + 6, 34
                w_ = span * share / smax
                rect(M, by, w_, bh, RULE)
                if bot > 0:
                    rect(M, by, max(w_ * bot, 4), bh, MAGENTA)
                text(M + w_ + 14, by + bh / 2, pct(share), mono, 32, INK_2, va="center")
                y = by + bh + 34
            y += 4

        if F["common"]:
            ops.append(("rule", y))
            y += 38
            text(M, y, "What the automated accounts share", bold, 40, INK)
            y += 58
            for line in wrap(F["common"][:1].upper() + F["common"][1:] + ".", sans, 36, CW, 3):
                text(M, y, line, sans, 36, INK_2)
                y += 46
            y += 14

        if F["news"]:
            ops.append(("rule", y))
            y += 38
            text(M, y, "Newsrooms vs Bluesky", bold, 40, INK)
            y += 58
            for line in wrap(F["news"] + ".", sans, 36, CW, 4):
                text(M, y, line, sans, 36, INK_2)
                y += 46
            y += 14
    else:
        text(M, y, f"{F['n']:,}" if F["n"] else "0", bold, 190, INK)
        y += 200
        para(f"posts match this claim. I need at least {cfg.MIN_MATCHES} to measure automation reliably.", sans, 38, INK_2, 50, gap=24)

    # footer
    ops.append(("rule", y))
    y += 30
    for i, line in enumerate(_source_lines(result) + [FOOTER_LINE]):
        text(M, y, line, mono, 29, CAPTION if i < 2 else INK_2)
        y += 40
    H = int(y + 28)

    fig = plt.figure(figsize=(W / 72, H / 72), dpi=72, facecolor=PAPER)
    for op in ops:
        if op[0] == "text":
            _, x, yy, s_, fp, size, color, ha, va = op
            fp = fp.copy()
            fp.set_size(size)
            fig.text(x / W, 1 - yy / H, s_, fontproperties=fp, color=color, ha=ha, va=va)
        elif op[0] == "rect":
            _, x, yy, w_, h_, color = op
            fig.patches.append(Rectangle((x / W, 1 - (yy + h_) / H), w_ / W, h_ / H, transform=fig.transFigure, color=color, lw=0))
        else:
            fig.add_artist(plt.Line2D([M / W, (W - M) / W], [1 - op[1] / H] * 2, transform=fig.transFigure, color=RULE, lw=2))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=PAPER, dpi=72)
    plt.close(fig)
    return buf.getvalue()
