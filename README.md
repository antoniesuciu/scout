# Scout

A private video inbox and file library. Discover YouTube uploads or paste a public video/Reel
link, choose what to summarize, and read saved summaries, transcripts and Markdown notes.
Scout uses your terminal subscriptions; discovery and input preparation make no model calls.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./scout --desktop --port 0
./install-desktop.sh   # adds Scout to the app grid/search with its icon; --uninstall removes it
```

In the inbox, **Following** lists the YouTube channels you follow: add one by its channel link,
remove one, or check them all for new videos (no model calls). **Summary length** picks Brief,
Standard, Deep dive (timestamped points) or Plain words (jargon explained) per run.

Desktop mode currently targets **Ubuntu with GTK3/WebKit2**. It uses a frameless native window
with in-app minimize/maximize/close controls; drag the Scout brand and resize from the lower-right
handle. Import and download use native file dialogs. Ctrl+R/F5 reload; Ctrl+W closes the window.
Stop/restart an older Scout process to pick up backend and window changes.

For browser mode, use `./scout` and open **http://127.0.0.1:8765**. `--no-browser` suppresses
browser launching. `--port 0` chooses a free port. Both modes share the same Python backend and UI.
macOS/Windows desktop support is not implemented; see [desktop options](docs/DESKTOP.md).

## Use it

1. **New session** checks configured YouTube channels; **Add** accepts a public video link.
2. Select videos, choose **Claude / Codex / Gemini**, and pick or type a model. Claude and Gemini
   offer aliases; Codex suggestions come from its non-secret local model catalog when available.
   A blank model uses the CLI default. Suggestions do not establish subscription access.
3. Leave **Headless summary** selected. **Preview input** downloads transcripts and optional local
   OCR, shows words/characters/cache hits and the number of model calls, then enables **Summarize**.
4. Re-selecting a summarized video lets you use another model/language; identical inputs reuse the
   summary cache. A partial batch failure leaves only the failed videos needing a model retry.
5. **Library** lists summary/transcript files even without an inbox record. Toggle **Rendered / Raw
   text**, download or open in your editor. Import `.md`/`.txt`, create notes, edit and save them.
   Files stay local. Markdown supports headings, paragraphs, lists, code, blockquotes and safe links;
   it escapes raw HTML, does not load remote images and is not a full CommonMark implementation.

Prices are labelled snapshots, not streaming quotes. Cached summaries retain their original prices.
Mentions are not forecasts; there is no trading ledger.

## Settings

Open the sliders button. **Font, size and density affect the preview until Save reading style**;
**Revert** discards pending changes. Saved font/size apply to the workspace and readers; display
headings/code/metadata keep their designated roles. Theme changes apply immediately.

Save a default model per provider. The channels/runtime editor validates JSON and saves inside the
app; it no longer relies on opening an external settings editor. `settings.example.json` supplies
initial defaults. First run copies it to personal `settings.json`, which is ignored by Git. Existing
personal settings are preserved. Saving normalizes JSON; comments remain in the example file.

## Headless isolation and terminal sessions

Every new app window and **New session** starts in headless mode. New session is discovery only.
Every summarization runs with disposable configuration, required auth files only, no user hooks,
Claude-Mem capture, coding skills or MCP. No app headless path can opt into configured context.

- **Claude:** safe mode, empty tool set/settings sources, no MCP/skills/session persistence,
  explicit hooks/auto-memory off, and auth-only configuration directory.
- **Codex:** auth-only home, ephemeral execution, no user config/rules or project documents;
  hooks/plugins/skill discovery/catalog disabled; minimal summarizer instructions replace the
  coding instructions. Shell/web/apps/browser/image features are disabled. This is not a verified
  guarantee that the CLI exposes absolutely no built-in tools.
- **Gemini:** auth-only home, empty core-tool allowlist, hooks/skills/MCP/auto-memory/extensions
  disabled, minimal system instructions. Temporary session data is removed after completion.

API-key and cloud-provider routing variables are removed from engine environments; Codex API-key
credentials are refused. No subscription login is performed by Scout. Managed enterprise policies
and external observers are outside the app's isolation guarantee.

**Interactive terminal** is a separate explicit action, with the same model choice. **Isolated**
uses the restricted session; **My CLI setup** inherits that CLI's own configuration, tools, hooks,
skills and memory. This can consume more context/quota. It does not promise cross-provider
Claude-Mem integration. Interactive answers are not automatically imported into Scout summaries.
Ubuntu terminal launching currently supports GNOME Terminal and xterm. `agy` is no longer offered.

Each headless engine process group has a timeout (`engine_timeout`, default 180 seconds), with no
automatic retry. Run the CLI's normal subscription login in your terminal first.

## Optional Reels and OCR

Scout never reads browser cookies or logs in to Instagram. Saved posts/direct account APIs are
explicitly deferred. Public captions are tried first; authentication-required links fail clearly.
Without captions, install optional local STT and supply an already-downloaded model:

```sh
.venv/bin/python -m pip install -r requirements-media.txt
```

Set `whisper_model_path` to a local CTranslate2 model, preferably under `.venv/models/`. Scout uses
CPU int8/VAD and never downloads model weights automatically. For audio conversion/OCR, provide
`ffmpeg` and `tesseract` executables in `.venv/bin/`, with their runtime libraries/language data
available (`TESSDATA_PREFIX` if needed). No system packages are installed by Scout.

**Transcript + on-screen text** downloads video and sends local OCR text, not images. Sampling is
periodic, regex visual-cue or manual; at most 12 frames. Video downloads request a 150 MB size limit,
which yt-dlp cannot guarantee for streams of unknown size; each media command times out after
120 seconds. Reels default to OCR. Choose **Transcript only** when optional tools are unavailable.
There is no silent fallback to another input mode. Real STT/OCR remain unverified in this environment.

## Source and local files

```text
src/scout/
  app.py             HTTP endpoints, discovery/preparation/summary jobs, launcher
  config.py          validated settings and model preferences
  engines.py         auth-only CLI sessions, execution and terminal launching
  library.py         constrained note/file operations
  media.py           public Reel captions/STT and capped frame OCR
  pipeline.py        YouTube, VTT and price helpers adapted from the reference
  search.py          disposable SQLite FTS5 index of saved files
  desktop.py         Ubuntu GTK/WebKit shell, native file/window actions
  web/               markup/styles and separate app/settings/library/desktop controllers
scout                launcher using .venv
settings.example.json tracked initial configuration
settings.json        ignored personal configuration
notes/               personal Markdown/text files
summaries/           generated Markdown summaries
transcripts/         timestamped cleaned transcripts
.cache/              summary cache and rebuildable search index
```

Runtime data and `.venv/` are ignored by Git. Search includes saved notes/transcripts/summaries;
deleting `.cache/search.sqlite3` rebuilds the index on the next query. The original
`stock-update-main/` remains untouched and deliberately uncommitted. Fonts use the supplied
Google Fonts link, with system fallbacks offline.

## Verify

```sh
./scout --doctor
./scout --selftest
.venv/bin/python -m unittest discover -s tests -v
node tests/test_ui.cjs
node tests/test_settings_ui.cjs
node tests/test_markdown.cjs
```

Explicit live checks consume a small amount of subscription quota and keep isolation enabled:

```sh
./scout --test-engine claude --model haiku
./scout --test-engine codex
./scout --test-engine gemini --model flash
```

**No live provider has successfully summarized through these adapters in the restricted sandbox.**
The user confirmed desktop launch and the earlier reading preview work on their desktop; the latest
Save flow and frameless controls still need user verification. See [validation](docs/VALIDATION.md)
and [Hallmark audit](docs/DESIGN-AUDIT.md) for the distinction between tested behavior and open gates.
