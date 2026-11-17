#!/usr/bin/env python3
"""Scout: summarizes new YouTube stock videos with Claude (Claude Code CLI).

Structure (small step functions, so e-mail delivery or a scheduled run can be
added easily later -> see main()):
  load_settings -> resolve_channel_ids -> get_candidates -> load_metadata
  -> choose -> load_transcripts -> summarize -> save_output -> mark_seen
"""

import argparse
import concurrent.futures as cf
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SETTINGS_PATH = BASE / "settings.json"
SEEN_PATH = BASE / "seen.json"
TRANSCRIPTS_DIR = BASE / "transcripts"
SUMMARIES_DIR = BASE / "summaries"

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

DEFAULTS = {
    "mode": "latest",
    "max_per_channel": 3,
    "max_age_days": 7,
    "max_total": 5,
    "model": "haiku",
    "language": "en",
    "show_selection": True,
    "warn_words": 60000,
    "test": False,
    "test_minutes": 5,
}

SYSTEM_PROMPT = (
    "You are a precise summarizer of stock-related video transcripts. "
    "You only report what is actually said in the transcripts. No tools, no follow-up questions."
)

# Everything language-dependent in one place. English is built in; other languages reuse its structure.
LANG = {
    "en": {
        "output_language": "ENGLISH",
        "headings": ("GENERAL MARKET OUTLOOK", "STOCKS IN DETAIL", "MENTIONED BY MULTIPLE SOURCES",
                     "DISAGREEMENT", "DATES"),
        "title": "SCOUT",
        "videos": "Summarized videos",
        "date_fmt": "%Y-%m-%d",
        "format": """GENERAL MARKET OUTLOOK
Per source: view on the overall market, macro topics (interest rates, Fed, inflation, economy), sentiment, expected development.

STOCKS IN DETAIL
Per stock: TICKER – Name
  • Source: bullish/bearish/neutral, buys/sells/holds (if stated), reasoning in 1-2 sentences, price targets/time frame (only if stated)
  • [[PRICE:TICKER]]   (add this line ONLY if the speaker named concrete numbers for this stock, e.g. price, price target, entry; TICKER = the plain US ticker symbol, e.g. [[PRICE:AMD]]; the program replaces it with the live price)

MENTIONED BY MULTIPLE SOURCES: tickers with number of sources
DISAGREEMENT: stocks where the sources contradict each other
DATES: mentioned earnings, Fed dates etc. (only if mentioned) and their possible effect on the market""",
        "none": '"none"',
        "price_label": "Current price",
    },
}

LANGUAGE_NAME = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ -]{1,29}")


def valid_language(language):
    """'en', or a plain language name the user added; the name ends up in the prompt, so letters only."""
    return language == "en" or (isinstance(language, str) and bool(LANGUAGE_NAME.fullmatch(language)))


def lang_profile(language):
    if language == "en":
        return LANG["en"]
    return {**LANG["en"], "output_language": language.upper()}

TASK = """Summarize the following transcripts of YouTube videos about stocks in {output_language} (even if the transcripts are in another language).
Answer as PLAIN TEXT, no Markdown (no #, **, tables). Start directly with "{first_heading}". Use exactly this format:

{format}

Rules:
- Only report what was actually said. Add nothing, evaluate nothing.
- "Source" is the name after SOURCE: in each transcript header; videos with the same source count as one source.
- Auto-generated subtitles often mishear company names: mark uncertain tickers with (?).
- Fill sections without content with {none}.
- IGNORE pure price-movement reports (which stocks went up or down today/recently, daily gains/losses or percentages of model portfolios, portfolio balances). They are not wanted. A stock that is only mentioned in such a report MUST NOT appear in STOCKS IN DETAIL at all.
- Only include a stock if the speaker actually discusses it (analysis, opinion, reason to buy/sell, outlook, price target). Include nothing else.
- Write buys/sells/holds ONLY if the speaker explicitly says so; otherwise omit it entirely. Never write "holds (not explicitly said)" or similar.
- Leave out anything that was not said. NEVER write filler like "not stated" / "not mentioned" / "none named" inside a stock entry.
- The [[PRICE:TICKER]] line is ONLY for stocks where the speaker names a concrete dollar figure as a price level, price target or entry price. Percentages, gains/losses and "went up" do NOT count. If in doubt, leave it out.
- Be concise. Write {output_language} with correct spelling.

TRANSCRIPTS:
"""


# ───────────────────────── helpers ─────────────────────────

def info(msg=""):
    print(msg, flush=True)


def error(msg):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)


def read_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    temporary.replace(path)


def strip_comments(text):
    """Removes //-comments (outside of strings) so settings.json may contain comments."""
    out, in_str, esc, i = [], False, False, 0
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def read_settings_file():
    return json.loads(strip_comments(SETTINGS_PATH.read_text(encoding="utf-8")))


def find_program(name, extra=()):
    path = shutil.which(name)
    if path:
        return path
    for candidate in extra:
        candidate = os.path.expanduser(candidate)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def fmt_duration(sec):
    if not sec:
        return "?"
    sec = int(sec)
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def source_of(channel):
    return channel.get("group") or channel["name"]


# ───────────────────────── 1. settings & channel IDs ─────────────────────────

def load_settings(args):
    if not SETTINGS_PATH.exists():
        error(f"{SETTINGS_PATH.name} is missing.")
        sys.exit(1)
    settings = {**DEFAULTS, **read_settings_file()}
    # command line overrides settings
    if args.mode:
        settings["mode"] = args.mode
    if args.model:
        settings["model"] = args.model
    if args.language:
        settings["language"] = args.language
    if args.test:
        settings["test"] = True
    if args.no_selection:
        settings["show_selection"] = False
    if settings["mode"] not in ("latest", "unseen"):
        error('"mode" must be "latest" or "unseen".')
        sys.exit(1)
    if not valid_language(settings["language"]):
        error('"language" must be "en" or a language name such as "Romanian".')
        sys.exit(1)
    return settings


def resolve_channel_ids(settings, ytdlp):
    changed = False
    for channel in settings["channels"]:
        if channel.get("channel_id"):
            continue
        if not channel.get("url"):
            error(f"Channel '{channel['name']}' has no url.")
            sys.exit(1)
        info(f"Resolving channel ID for {channel['name']} ...")
        r = subprocess.run(
            [ytdlp, "--ignore-config", "--no-warnings", "--flat-playlist", "--playlist-items", "1",
             "--print", "%(playlist_channel_id,channel_id,uploader_id)s", channel["url"].rstrip("/") + "/videos"],
            capture_output=True, text=True, timeout=120,
        )
        cid = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
        if not cid.startswith("UC"):
            error(f"Could not resolve channel ID for {channel['name']}:\n{r.stderr.strip()}")
            sys.exit(1)
        channel["channel_id"] = cid
        changed = True
    if changed:  # insert IDs textually so comments in settings.json are preserved
        text = SETTINGS_PATH.read_text(encoding="utf-8")
        for c in settings["channels"]:
            text = re.sub(r'("name"\s*:\s*"%s"[^}]*?"channel_id"\s*:\s*)(null|"")' % re.escape(c["name"]),
                          lambda m: m.group(1) + json.dumps(c["channel_id"]), text, count=1, flags=re.S)
        SETTINGS_PATH.write_text(text, encoding="utf-8")
    return settings


# ───────────────────────── 2. RSS & candidates ─────────────────────────

def fetch_feed(channel):
    url = RSS_URL.format(channel["channel_id"])
    last = None
    for attempt in range(3):  # YouTube's RSS endpoint is flaky (random 404/500)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                root = ET.fromstring(r.read())
            break
        except Exception as e:  # network / HTTP / XML
            last = e
            time.sleep(1 + attempt)
    else:
        raise last
    videos = []
    for e in root.findall("a:entry", NS):
        videos.append({
            "id": e.findtext("yt:videoId", namespaces=NS),
            "title": e.findtext("a:title", namespaces=NS),
            "date": (e.findtext("a:published", namespaces=NS) or "")[:10],
            "channel": channel["name"],
            "source": source_of(channel),
        })
    videos.sort(key=lambda v: v["date"], reverse=True)  # stable: feed order kept within a day
    return videos


def fetch_channel_page(channel, ytdlp):
    """Fallback if the RSS feed fails: newest videos AND shorts from the channel's tabs via yt-dlp.
    The flat listing has no reliable dates, so they are fetched per video (in parallel)."""
    videos, seen_ids, last_err = [], set(), ""
    for tab, count in (("videos", 5), ("shorts", 3)):
        r = subprocess.run(
            [ytdlp, "--ignore-config", "--no-warnings", "--flat-playlist", "--playlist-end", str(count),
             "--print", "%(id)s\t%(title)s", f"https://www.youtube.com/channel/{channel['channel_id']}/{tab}"],
            capture_output=True, text=True, timeout=120,
        )
        if r.stderr.strip():
            last_err = r.stderr.strip().splitlines()[-1]
        for line in r.stdout.splitlines():
            vid, _, title = line.partition("\t")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                videos.append({"id": vid, "title": title, "date": "", "channel": channel["name"],
                               "source": source_of(channel)})
    if not videos:
        raise RuntimeError(last_err or "no videos found")

    def date_of(v):
        out = subprocess.run([ytdlp, "--ignore-config", "--no-warnings", "--skip-download", "--print", "%(upload_date)s",
                              f"https://www.youtube.com/watch?v={v['id']}"],
                             capture_output=True, text=True, timeout=120).stdout.strip()
        return f"{out[:4]}-{out[4:6]}-{out[6:8]}" if re.fullmatch(r"\d{8}", out) else ""
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for v, d in zip(videos, ex.map(date_of, videos)):
            v["date"] = d
    videos = [v for v in videos if v["date"]]
    videos.sort(key=lambda v: v["date"], reverse=True)
    return videos


def get_candidates(settings, seen, ytdlp):
    candidates = []
    channels = settings["channels"][:1] if settings["test"] else settings["channels"]
    for channel in channels:
        try:
            videos = fetch_feed(channel)
        except Exception as e:
            info(f"RSS feed of {channel['name']} not available ({e}); using yt-dlp fallback ...")
            try:
                videos = fetch_channel_page(channel, ytdlp)
            except Exception as e2:
                error(f"Could not get videos of {channel['name']}: {e2}")
                continue
        for v in videos:
            v["seen"] = v["id"] in seen
        if settings["test"]:
            pick = videos[:1]
        elif settings["mode"] == "latest":  # newest N per channel, whether seen or not
            pick = [v for v in videos if v["id"] not in seen][: settings["max_per_channel"]]
        else:  # "days": unseen videos from the last max_age_days, newest first
            limit = (datetime.now() - timedelta(days=settings["max_age_days"])).strftime("%Y-%m-%d")
            pick = [v for v in videos if not v["seen"] and v["date"] >= limit][: settings["max_per_channel"]]
        candidates += pick
    # per-run cap: newest first
    cap = 1 if settings["test"] else settings["max_total"]
    candidates.sort(key=lambda v: v["date"], reverse=True)
    return candidates[:cap]


def load_metadata(candidates, ytdlp):
    """Duration, live status and available subtitles via yt-dlp (parallel, best effort)."""
    def one(v):
        r = subprocess.run(
            [ytdlp, "--ignore-config", "-J", "--skip-download", "--no-warnings", "--no-playlist",
             f"https://www.youtube.com/watch?v={v['id']}"],
            capture_output=True, text=True, timeout=120,
        )
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return {}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for v, meta in zip(candidates, ex.map(one, candidates)):
            v["duration"] = meta.get("duration")
            v["live_status"] = meta.get("live_status")
            v["_subs"] = meta.get("subtitles") or {}
            v["_auto"] = meta.get("automatic_captions") or {}
            v["_language"] = meta.get("language")


# ───────────────────────── 3. selection list ─────────────────────────

def choose(candidates, settings):
    info("\nCandidates:")
    for i, v in enumerate(candidates, 1):
        mark = "  [already summarized]" if v["seen"] else ""
        info(f"  {i}. {v['channel']} | {v['title']} | {v['date']} | {fmt_duration(v['duration'])}{mark}")
    if not settings["show_selection"] or settings["test"] or not sys.stdin.isatty():
        return candidates
    while True:
        answer = input("\nSelection (Enter = all, e.g. 1,3, q = quit): ").strip().lower()
        if answer == "":
            return candidates
        if answer == "q":
            return []
        try:
            nums = sorted({int(x) for x in re.split(r"[,\s]+", answer) if x})
            if nums and all(1 <= n <= len(candidates) for n in nums):
                return [candidates[n - 1] for n in nums]
        except ValueError:
            pass
        info("Invalid input.")


# ───────────────────────── 4./5. transcripts ─────────────────────────

def _match(keys, prefix):
    for k in keys:
        if k == prefix or k.startswith(prefix + "-"):
            return k
    return None


def pick_subtitles(v):
    """Manual preferred, otherwise automatic; original language de or en. -> (lang, is_auto) | None"""
    for lang in ("de", "en"):
        k = _match(v["_subs"], lang)
        if k:
            return k, False
    auto = v["_auto"]
    for lang in ("de", "en"):  # '-orig' = original language of the video
        if f"{lang}-orig" in auto:
            return f"{lang}-orig", True
    declared = (v.get("_language") or "").split("-")[0]
    for lang in ([declared] if declared in ("de", "en") else ["de", "en"]):
        if lang in auto:
            return lang, True
    return None


TS = re.compile(r"(\d+):(\d+):(\d+)[.,]\d+\s+-->")


def clean_vtt(text, max_minutes=None):
    """Keep cue timestamps; suppress adjacent rolling-caption duplicates only."""
    out, previous = [], []
    timestamp, cue = None, []
    last_end = None

    def emit():
        nonlocal previous
        words = html.unescape(re.sub(r"<[^>]*>", "", " ".join(cue)))
        words = re.sub(r"\[[^\]]*\]", "", words).split()
        overlap = 0
        for size in range(1, min(len(previous), len(words)) + 1):
            if previous[-size:] == words[:size]:
                overlap = size
        if words[overlap:]:
            out.append(f"[{timestamp}] " + " ".join(words[overlap:]))
        previous = words

    for raw in text.splitlines() + [""]:
        line = raw.strip()
        match = re.match(r"(?:(\d{2,}):)?(\d{2}):(\d{2})[.,]\d+\s+-->", line)
        if match:
            if cue:
                emit()
            cue = []
            h, m, sec = int(match[1] or 0), int(match[2]), int(match[3])
            start_seconds = h * 3600 + m * 60 + sec
            if last_end is not None and start_seconds > last_end + 1:
                previous = []
            end_match = re.search(r"-->\s+(?:(\d{2,}):)?(\d{2}):(\d{2})[.,]", line)
            last_end = (int(end_match[1] or 0) * 3600 + int(end_match[2]) * 60 + int(end_match[3])) if end_match else start_seconds
            timestamp = f"{h:02}:{m:02}:{sec:02}"
            if max_minutes and h * 3600 + m * 60 + sec > max_minutes * 60:
                timestamp = None
        elif not line:
            if timestamp and cue:
                emit()
            timestamp, cue = None, []
        elif timestamp:
            cue.append(line)
    return "\n".join(out)


def load_transcripts(chosen, settings, ytdlp):
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    max_min = settings["test_minutes"] if settings["test"] else None
    done = []
    with tempfile.TemporaryDirectory() as tmp:
        for v in chosen:
            label = f"{v['channel']} – {v['title']}"
            if v.get("live_status") in ("is_live", "is_upcoming"):
                info(f"  skipped (livestream running/scheduled): {label}")
                continue
            pick = pick_subtitles(v)
            if not pick:
                info(f"  skipped (no transcript, e.g. livestream just ended; NOT marked as seen): {label}")
                continue
            lang, auto = pick
            r = subprocess.run(
                [ytdlp, "--ignore-config", "--skip-download", "--no-warnings", "--no-playlist",
                 "--write-auto-subs" if auto else "--write-subs",
                 "--sub-langs", lang, "--sub-format", "vtt",
                 "-o", os.path.join(tmp, "%(id)s.%(ext)s"),
                 f"https://www.youtube.com/watch?v={v['id']}"],
                capture_output=True, text=True, timeout=120,
            )
            files = list(Path(tmp).glob(f"{v['id']}*.vtt"))
            if not files:
                info(f"  skipped (subtitle download failed): {label}")
                if r.stderr.strip():
                    info("    " + r.stderr.strip().splitlines()[-1])
                continue
            raw = files[0].read_text(encoding="utf-8", errors="replace")
            clean = clean_vtt(raw, max_min)
            if len(clean) < 200:
                info(f"  skipped (transcript empty/too short): {label}")
                continue
            v["transcript"] = clean
            v["subtitles"] = f"{lang}{' (auto)' if auto else ' (manual)'}"
            name = f"{v['date']}_{re.sub(r'[^A-Za-z0-9]+', '-', v['channel']).strip('-')}_{v['id']}"
            (TRANSCRIPTS_DIR / f"{name}{'_test' if max_min else ''}.txt").write_text(clean, encoding="utf-8")
            shrink = 100 - 100 * len(clean) / max(len(raw), 1)
            info(f"  ✓ {label}: {len(raw):,} → {len(clean):,} chars ({shrink:.0f}% smaller), "
                 f"~{len(clean.split()):,} words, subtitles {v['subtitles']}"
                 + (f", cut to {max_min} min." if max_min else ""))
            done.append(v)
    return done


# ───────────────────────── 7. Claude ─────────────────────────

def build_prompt(videos, language):
    L = lang_profile(language)
    parts = [TASK.format(output_language=L["output_language"], first_heading=L["headings"][0],
                         format=L["format"], none=L["none"])]
    for v in videos:
        parts.append(f"\n=== SOURCE: {v['source']} | CHANNEL: {v['channel']} | TITLE: {v['title']} "
                     f"| DATE: {v['date']} ===\n{v['transcript']}\n")
    return "".join(parts)


def summarize(prompt, settings):
    claude = find_program("claude", [settings.get("claude_path") or "~/.local/bin/claude",
                                     "~/.claude/local/claude"])
    if not claude:
        error("'claude' not found (see README).")
        sys.exit(1)
    cmd = [
        claude, "-p",
        "--model", settings["model"],
        "--tools", "",                    # no tool definitions in the context
        "--system-prompt", SYSTEM_PROMPT, # replaces the long default prompt
        "--setting-sources", "",          # no user/project settings, hooks, CLAUDE.md
        "--strict-mcp-config",            # no MCP servers
        "--disable-slash-commands",       # no skills
        "--no-session-persistence",
        "--output-format", "json",
    ]
    with tempfile.TemporaryDirectory() as empty:  # empty cwd: nothing to auto-discover
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=120, cwd=empty)
    if r.returncode != 0:
        error(f"claude -p failed (exit {r.returncode}):\n{r.stderr.strip() or r.stdout.strip()}")
        sys.exit(1)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        error(f"Unexpected output from claude:\n{r.stdout[:500]}")
        sys.exit(1)
    if data.get("is_error"):
        error(f"Claude reported an error: {data.get('result')}")
        sys.exit(1)
    return data["result"].strip(), data.get("usage", {})


# ───────────────────────── live prices ─────────────────────────

PRICE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=1d&interval=1d"
PLACEHOLDER = re.compile(r"\[\[PRICE:\s*([A-Za-z0-9.\-]{1,10})\s*\]\]")


def fetch_price(ticker):
    """Latest price via Yahoo Finance's public chart endpoint (no key; only the ticker is sent)."""
    try:
        req = urllib.request.Request(PRICE_URL.format(ticker), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.load(r)["chart"]["result"][0]["meta"]
        when = datetime.fromtimestamp(meta["regularMarketTime"]).strftime("%d.%m. %H:%M")
        name = meta.get("longName") or meta.get("shortName") or ticker
        return f"{meta['regularMarketPrice']:,.2f} {meta.get('currency', 'USD')} ({name}, {when})"
    except Exception:
        return None


def insert_prices(summary, language):
    """Replaces the [[PRICE:TICKER]] placeholder lines with the live price; drops them if unavailable."""
    lines = summary.splitlines()
    wanted = {i: m.group(1).upper() for i, line in enumerate(lines) if (m := PLACEHOLDER.search(line))}
    tickers = sorted(set(wanted.values()))
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        prices = dict(zip(tickers, ex.map(fetch_price, tickers)))
    label = lang_profile(language)["price_label"]
    for i, t in wanted.items():
        lines[i] = f"  • {label}: {prices[t]}" if prices[t] else None
    # leftover placeholders (malformed) are removed
    return "\n".join(l for l in lines if l is not None and "[[PRICE" not in l)


# ───────────────────────── 8./9. output ─────────────────────────

def save_output(videos, summary, settings):
    now = datetime.now()
    L = lang_profile(settings["language"])
    head = (f"═══ {L['title']} {now.strftime(L['date_fmt'])}{' (TEST)' if settings['test'] else ''} ═══\n"
            f"{L['videos']}: " + "; ".join(f"{v['channel']} – {v['title']}" for v in videos) + "\n\n")
    text = head + summary + "\n"
    SUMMARIES_DIR.mkdir(exist_ok=True)
    path = SUMMARIES_DIR / f"{now.strftime('%Y-%m-%d_%H-%M')}{'_test' if settings['test'] else ''}.txt"
    path.write_text(text, encoding="utf-8")
    return text, path


def mark_seen(videos):
    seen = read_json(SEEN_PATH, {})
    for v in videos:
        seen[v["id"]] = {"channel": v["channel"], "title": v["title"],
                         "summarized": datetime.now().isoformat(timespec="seconds")}
    write_json(SEEN_PATH, seen)


# ───────────────────────── main ─────────────────────────

def main():
    p = argparse.ArgumentParser(description="Summarizes new YouTube stock videos with Claude.")
    p.add_argument("--mode", choices=["latest", "unseen"], help="overrides settings.json")
    p.add_argument("--model", help="e.g. haiku, sonnet, opus (overrides settings.json)")
    p.add_argument("--language", help="summary language: en (default) or a language name, e.g. Romanian (overrides settings.json)")
    p.add_argument("--test", action="store_true",
                   help="test mode: 1 video, only the first minutes, nothing is marked as seen")
    p.add_argument("--no-selection", action="store_true", help="skip the selection list (for automation)")
    args = p.parse_args()

    ytdlp = find_program("yt-dlp", [str(BASE / ".venv/bin/yt-dlp")])
    if not ytdlp:
        error("yt-dlp is missing (see README: python3 -m venv .venv && .venv/bin/pip install yt-dlp)")
        sys.exit(1)

    settings = load_settings(args)
    settings = resolve_channel_ids(settings, ytdlp)
    seen = read_json(SEEN_PATH, {})

    if settings["test"]:
        info(f"*** TEST MODE: 1 video, first {settings['test_minutes']} min., model {settings['model']} ***")

    candidates = get_candidates(settings, seen, ytdlp)
    if not candidates:
        info("No new videos.")
        return
    load_metadata(candidates, ytdlp)
    chosen = choose(candidates, settings)
    if not chosen:
        info("Nothing selected.")
        return

    info("\nLoading transcripts ...")
    videos = load_transcripts(chosen, settings, ytdlp)
    if not videos:
        info("No transcripts available. Aborting.")
        return

    prompt = build_prompt(videos, settings["language"])
    words = sum(len(v["transcript"].split()) for v in videos)
    if words > settings["warn_words"]:
        info(f"\nWARNING: total text ~{words:,} words (threshold {settings['warn_words']:,}). "
             "This uses a lot of your Claude quota.")
        if not sys.stdin.isatty() or input("Continue anyway? (y/N): ").strip().lower() not in ("y", "j"):
            info("Aborted.")
            return

    info(f"\nSummarizing {len(videos)} video(s) with {settings['model']} ...")
    summary, usage = summarize(prompt, settings)
    summary = insert_prices(summary, settings["language"])
    text, path = save_output(videos, summary, settings)

    info("\n" + text)
    info(f"Saved: {path.relative_to(BASE)}")
    if usage:
        info("Claude usage: " + ", ".join(f"{k}={v}" for k, v in usage.items() if isinstance(v, int)))

    if settings["test"]:
        info("Test mode: video NOT marked as seen.")
    else:
        mark_seen(videos)


if __name__ == "__main__":
    main()
