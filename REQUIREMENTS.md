# scout: requirements

Written 2026-11-17. This file is the project's memory: what was asked for, what the model
council said, what is built, and what is still open. Update it when a decision changes.

## 1. Goal

Grow the working `pipeline.py` tool into a small app, working name **scout**. It checks
sources for new videos, lets me tick the ones I want, and summarizes only those.
**Top priority: low model usage.** Nothing is sent to a model until I run it.

## 2. What I want

- **Sources:** YouTube (channels as today, plus pasting any link) and Instagram Reels from my
  saved posts only. No Instagram feed.
- **Sessions:** "New session" fetches what is new. I tick the videos I want.
- **Summarizer only:** the model does nothing but summarize. It runs through headless terminal
  CLIs on my existing subscriptions: `claude`, `codex` and `gemini`, with a model selected per run. No API key.
- **Input depth, per run:** transcript only, or transcript plus frames. Frames are chosen one of
  three ways: every few seconds, where the transcript points to something visual, or at
  timestamps I give.
- **Defaults that work untouched:** YouTube uses transcript only. Reels use transcript plus a
  frame every few seconds.
- **Output:** summaries and cleaned transcripts saved as files, all browsable in the app.
- **Interface:** one fast, clean dashboard screen.

## 3. Interface spec

Source design: https://claude.ai/code/artifact/fc2cd28c-b69e-4661-9dcc-bc5824bd9c55

One screen, three areas.

- **Header:** name, search across videos and summaries, New session, settings icon.
- **Inbox (left):** source filter (All, YouTube, Reels saved), paste-link field, tickable list
  with a status per video, then summarizer choice, input depth choice, Summarize button.
- **Reader (right):** thesis, key points, tickers with live price, "on screen, not spoken",
  "check before trusting", links to the original, the transcript and the summary file. Below it,
  a process log showing the headless commands.
- **Settings popover:** immediate theme switching; preview font, text size and density, then Save/Revert; summary language,
  Instagram session status with Reconnect, and a link to edit `settings.json`.

### Colour tokens (every colour in the UI comes from these seven)

| Token | Ink (default) | Paper | Phosphor |
|---|---|---|---|
| Background | `#0F1115` | `#EEF0F3` | `#050A07` |
| Panel | `#171A21` | `#FFFFFF` | `#0B140F` |
| Line (borders) | `#2A2F3A` | `#CDD2DA` | `#1E3327` |
| Text | `#E8E6DF` | `#14171C` | `#C9F5D6` |
| Muted text | `#9AA1AE` | `#555D6B` | `#7FB592` |
| Accent | `#F2B13C` | `#1F4FD8` | `#5CF08C` |
| Text on accent | `#14110A` | `#FFFFFF` | `#04130A` |

### Type

- Space Grotesk 600: app name (26px), panel titles (17px), open video's title (28px).
- Inter: interface and reading text, 15px base, line height 1.5.
- JetBrains Mono 12 to 13px: metadata, statuses, CLI names, ticker lines, process log.
- Reader section labels: 12px, weight 600, uppercase, letter spacing 0.08em, muted.
- Reading font switchable to Source Serif 4 or JetBrains Mono; text size 14, 15 or 17px.

### Layout

- Page padding 20px top, 24px sides and bottom; 16px gaps between areas.
- Two columns that wrap: inbox about 400px minimum, reader takes the rest (560px minimum).
  On a narrow window the inbox stacks above the reader.
- Panels: panel colour, 1px line border, 10px radius. No shadows except the settings popover,
  no gradients.
- Reader text column capped at 720px.

### Controls

- Every choice is a row of segmented buttons: 44px tall, 6px radius, 1px line border, muted
  text. The selected one inverts (text colour as background, background colour as text).
- The only accent-filled element is the Summarize button (48px tall, 8px radius). Label:
  "Summarize N selected", or "Select videos to summarize" when nothing unsummarized is ticked.
- Inbox rows: checkbox, title (one line, truncated) over a mono metadata line (source, creator,
  length), status at the right. The open row gets the background colour and a 3px accent bar on
  its left edge. Row height 60px, or 44px in compact density.
- The frame-method row appears only when "Transcript + frames" is chosen, with one muted line
  under it explaining the cost of the current choice.
- A video that is not summarized shows a dashed-border empty state in the reader.
- Settings popover: 360px wide, anchored under the sliders icon, with a Close button.
- Process log: mono lines, one per command, appended as things run, horizontal scroll.
- Keyboard focus shows a 2px accent outline. All targets are at least 44px.

## 4. Known constraints and risks

- **Instagram:** saved posts need a logged-in session (Instaloader `:saved`, or yt-dlp with
  browser cookies for single reels). Cookies expire, and logged-in automation carries account
  risk on my main account. Fetch only on "New session", never on a schedule.
- **Reels transcripts:** usually no subtitle track, so they need local speech-to-text
  (whisper.cpp or faster-whisper). No model usage, but local compute.
- **Frames vs no-tools:** with `--tools ""` the claude CLI cannot open image files.
- **Rust:** would not make it faster; time goes to network, yt-dlp and the model.
- **Hardware:** Ryzen 7, RTX 4050 (6 GB VRAM), 16 GB RAM. Python 3.12.

## 5. Council review (2026-11-17)

Members: `claude-cli:opus`, `claude-cli:sonnet`, `codex-cli:default`. Mode: categorized, no web
access. **Every claim about CLI flags below came from the members' memory, not from a test.**

### All three agreed

- **Python first, no Rust core now.** Share a CLI/JSON contract with the orchestrator rather
  than a Rust crate.
- **Standalone app over a headless pipeline** that the orchestrator can call later.
- **Reels start as paste-link.** Saved-post fetching is an explicit opt-in: browser cookies,
  capped item count, stop on a checkpoint or auth error, never auto-retry, never scheduled.
- **Local OCR is the frame default**; real images opt-in and capped.
- **Idea 2:** keep the regex pass, cut the model fallback (it breaks "summarizer only").
  Keep timestamps in the stored transcript.
- **Keep** idea 4 (FTS5 search, `.md` files as the rebuildable source) and idea 8 (cost preview,
  per-video status and retry, cache, token usage).
- **Cut or defer** idea 6 (engine A/B): it doubles usage.
- **State:** `seen.json` cannot hold discovered, skipped, failed and summarized.
- **Safety:** transcripts are untrusted input; run every CLI contained.
- **Order of work:** test the three CLIs headlessly before building the UI around them.

### Where they disagreed

| Topic | `claude-cli:opus` | `claude-cli:sonnet` | `codex-cli:default` |
|---|---|---|---|
| Frame selection (idea 1) | Scene-change plus perceptual hash | Scene-change, dedupe on OCR text | Periodic sampling first, scene detection later |
| Ticker ledger (idea 3) | Collect data from day one, defer UI | Same | Defer; mentions are not predictions |
| Batch vs per-video calls | Per-video | Per-video above a token threshold | One batch call, retry only failed entries |
| Consensus (idea 5) | Keep if model-free | Keep if model-free | Defer; show co-mentions only |

### Single-member points worth keeping

- Paste-link does not remove Instagram account risk if the download still uses my cookies (codex).
- "Reels have no subtitles" is too categorical: try captions first, then speech-to-text (codex).
- Label the OCR mode "Transcript + on-screen text" so it does not imply the model saw charts,
  and never silently fall back to OCR when images cannot run (codex).
- YouTube frames need the video downloaded, which ends the subtitles-only cheapness; show this
  in the cost preview (sonnet).
- Cache key needs more than the video ID: prompt version, engine, language, input mode (codex).
- A price fetched now must never become the ledger's "price then" (codex).
- Validate tickers against a symbol list: "AI", "IT", "NOW" are false positives (opus).
- Claude images cost roughly 1.5k tokens per ~1 MP frame, so 30 frames is about 45k tokens (opus, unverified).
- PaddleOCR or RapidOCR over Tesseract for stylised Reel overlays; drop OCR text that matches
  the transcript, and what remains is "on screen, not spoken" (opus).
- Whisper `large-v3-turbo` or `distil-large-v3` in `int8_float16` for 6 GB VRAM, with VAD on;
  also a fallback for YouTube videos without subtitles (opus, unverified on this card).
- Instagram's "Download your information" export is a zero-automation way to get saved posts (sonnet, unverified).

Full report with the raw answers: it was saved to a scratch directory that is cleared on reboot;
the content above is the durable copy.

## 6. Current decisions (2026-11-17)

- Name **Scout**. Source is grouped under `src/scout/`, with separate configuration, sessions,
  library, media, search, native shell and browser-controller modules. The reference folder is
  untouched/uncommitted. Source documents remain authoritative over memory notes.
- Python backend and original HTML/CSS/JS design, shared by browser and optional Ubuntu GTK/WebKit
  desktop mode. At the user's request, the native window is frameless with in-app controls. macOS/
  Windows are possible future targets, not supported builds; compare `docs/DESKTOP.md`.
- Providers: Claude, Codex, Gemini, with exact model/alias per run and saved defaults per provider.
  This supersedes the earlier agy choice; no agy adapter is offered in the UI.
- Every **headless summarization** uses auth-only disposable configuration: no user hooks,
  Claude-Mem capture, coding skills, inherited project instructions or MCP. New session is
  model-free discovery and resets the UI to headless. Interactive terminals are a separate
  explicit action: isolated or the user's configured CLI setup. Configured context is forbidden
  for headless jobs; using configured interactive terminals may invoke hooks/skills/memory.
- Subscription authentication only: no new API client, no API-key fallback. Common API-key/cloud
  routing variables are stripped; Codex stored API-key mode is refused. CLI managed policies and
  external observers remain outside Scout's guarantee. Actual live provider success is unverified.
- One prepared batch model call per run, for cache misses only. Model identity is part of every
  provider's cache key. Changed selection/model/language requires a new preview. Word limits are
  checked again at dispatch; engine processes/timeouts include child processes. No automatic retry.
- Personal settings are ignored `settings.json`, initialized from tracked `settings.example.json`
  without overwriting an existing file. In-app JSON/default-model editing validates before saving.
  Font/size/density preview locally until **Save reading style**; **Revert** discards them. Saved
  fonts/size affect the workspace and file/summary readers; designated display/metadata/code roles
  remain distinct. Theme applies immediately. Files/notes are not added to Git.
- File library is independent of inbox state: saved summaries/transcripts and personal `.md`/`.txt`
  notes, rendered/raw toggle, import/create/edit/save, download and open-in-editor. Markdown is an
  escaped subset with no raw HTML or remote images. Only personal notes are editable in the app.
- State remains atomic `scout.json`. FTS5 is a disposable index over summaries/transcripts/notes;
  saved files remain authoritative. No ticker prediction ledger; prices are snapshots only.
- Reels remain public paste-links only: captions first, optional local STT. No browser cookies,
  login/session automation, saved-post API or scheduled fetching. Saved Instagram is deferred by
  explicit user decision. Frames use capped local OCR, never a model pass for selection, and are
  labelled on-screen text. Real image input remains deferred.
- The no-memory requirement is for summary subprocesses. Normal engineering project memory is
  allowed; the user explicitly requested a concise Scout overview in Obsidian.

## 7. Implementation and acceptance evidence

| Area | Implemented | Evidence / remaining gate |
|---|---|---|
| Settings/models | Validated in-app settings, saved per-provider models, preview/Save/Revert | Persistence/controller/API tests pass; user confirmed earlier native preview only; latest Save flow needs desktop confirmation |
| Summary sessions | Explicit Claude/Codex/Gemini model; auth-only isolated homes; hooks/skills/memory off | Isolation tests and real-subprocess stand-in workflows pass; live Claude timeout, Codex exit 1, Gemini auth exit 41 |
| Native app | GTK/WebKit, frameless window, drag/resize/min/max/close, native file actions | User confirmed initial window opened; current controls/dialogs not visually verified by agent |
| Library | Browse files independent of inbox; safe Markdown/raw; import and editable notes | File/API/UI/escaping tests pass; native picker/editor behavior still needs user verification |
| Timestamps/discovery | Cue timestamps, rolling-caption cleanup, known entries filtered before cap | VTT/discovery fixtures pass |
| Public Reels/STT/OCR | Public URL allowlist, captions first, local fallback and bounded sampling | Offline caption/dependency/sampling tests pass; real media/STT/OCR still unverified and optional tools absent |
| Preview/cache/usage | Explicit preparation and guarded batch dispatch; per-model caches and partial failure/retry | Full workflows with real child-program stand-ins pass for all three providers; cache hits make no additional engine call |
| Search | Rebuildable FTS5 over files | Search/rebuild/delete/notes tests pass |

Latest automated result: **54 Python tests**, JavaScript syntax/controller/Markdown/Save-flow checks,
Python compilation and launcher selftest pass. HTTP is exercised via its real parser/handler over
an in-memory transport: the sandbox denies TCP sockets. Chromium was found but cannot launch
under this sandbox. User-reported evidence is recorded separately in `docs/VALIDATION.md`.

## 8. Remaining acceptance gates

1. Successful isolated Claude/Codex/Gemini summary from the user's normal environment using
   `./scout --test-engine ...`; sandbox attempts did not establish real provider connectivity.
2. Restart the latest native build; verify Save/Revert changes actual library/reader text and
   persists, then check frameless drag/resize/buttons, file import/download and external editor.
3. Install optional local tools/model and verify a real public captioned Reel, local STT fallback,
   frame extraction and OCR. No silent fallback or inferred performance claims.
4. Cross-platform packaging/native adapters require a deliberate follow-up and target-OS tests.
5. Saved Instagram/API integration, actual images, semantic scene selection and a prediction
   ledger remain deferred. No Rust core, engine A/B or extra model-selection passes are planned.
