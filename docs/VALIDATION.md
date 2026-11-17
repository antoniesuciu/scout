# Validation — 2026-11-17

## Executed successfully

- `./scout --selftest`: parser/export check passed.
- `.venv/bin/python -m unittest discover -s tests -v`: **54 tests passed**, no skips.
- `node tests/test_ui.cjs`: escaping, selection, model/language preview invalidation,
  preview-only typography controls, raw/rendered library, execution modes and real element IDs.
- `node tests/test_settings_ui.cjs`: pending preview does not change workspace or save;
  Save applies/persists; Revert discards; failed saves retain the old workspace style.
- `node tests/test_markdown.cjs`: headings/lists/code/safe links and escaped HTML.
- JavaScript syntax checks and Python compileall passed. Git diff whitespace check passed.
- `./scout --doctor`: all three CLIs and local yt-dlp detected; ffmpeg/Tesseract/STT absent.

The Python suite includes actual HTTP parsing/handlers through an in-memory transport, validated
settings persistence, auth-only temporary configuration, absence of copied hooks/skills/instructions,
all-provider model cache keys, stale model rejection, library read/write/download/traversal guards,
frame limits, FTS5 rebuilds, window-control dispatch and navigation origin rules.

`test_process_workflow.py` launches real subprocesses for downloader/engine stand-ins and exercises
metadata, VTT cleaning, preview, all three engine adapters, exports and zero-extra-call cache reuse.
This establishes process/application contracts; it does **not** establish real platform/provider access.
Other workflow tests cover partial failures, timeout, changed word limits and retry behavior.

## User-reported desktop evidence

The user ran `./scout --desktop --port 0` outside the sandbox and reported that the native window
opened and reading controls worked **for the preview**. The subsequent workspace styling,
Preview → Save/Revert flow and frameless controls were added after that report; they are tested
at the controller/dispatch seams but are not yet user-verified in the running desktop.

## Live attempts without successful provider integration

Installed versions: Claude Code 2.1.326, Codex CLI 0.169.0, Gemini CLI 0.68.0.
Latest tiny `./scout --test-engine ...` checks, with isolated configuration and a 30-second bound:

| Provider | Observed result |
|---|---|
| Claude / haiku | Timed out; process group killed |
| Codex / CLI default | Exit 1; no successful answer |
| Gemini / flash | Exit 41, the installed CLI's fatal-authentication exit code |

A `gemini --list-models` probe also timed out after 10 seconds. Model suggestions therefore use
published aliases and the existing non-secret local Codex catalog, not a claimed live account query.
No successful real video summary, live Reel preparation, local Whisper inference or real OCR was
established for Scout in this session. Existing subscription login/network must be tested outside
the restricted sandbox; the CLI diagnostics retain isolation. No API-key auth or paid fallback is added.

## Environment limits

- Local TCP binding returns `Operation not permitted`; HTTP tests use the real parser/handler
  with in-memory transport, rather than falsely claiming a localhost integration pass.
- GTK imports and API signatures are verified, but `Gtk.init_check()` cannot reach the display.
- A cached Chromium and Puppeteer were found and tried. Chromium exits with
  `sandbox_host_linux.cc:41 ... shutdown: Operation not permitted`. No browser-render pass is claimed.
- Optional ffmpeg, Tesseract and faster-whisper/model are absent. Dependency errors are explicit.
- Initial pip resolution of yt-dlp failed in the restricted network. Existing yt-dlp 2026.10.26 was
  copied read-only from the reference environment into Scout's independent venv and its launcher verified.
- The working checkout's `.git` is read-only. Cohesive commits were made in `/tmp/scout-delivery.git`,
  rooted at the initial commit; `.cache/scout-commits.bundle` contains their complete history.
  The original branch/index remain untouched. No push was attempted.

Import that history into a local inspection branch without changing current working files:

```sh
git fetch .cache/scout-commits.bundle main:scout-implementation
```

The source is already in the checkout. Review/integrate the imported branch using your normal Git
workflow. Do not blindly add the deliberately untracked `stock-update-main/` reference.
Personal `settings.json`, notes and generated files are ignored and excluded from the delivery.

## Primary isolation evidence

- Installed CLI help/features output, plus Context7 queries of primary sources.
- [Claude CLI flags](https://code.claude.com/docs/en/cli-reference),
  [hooks](https://code.claude.com/docs/en/hooks) and [memory](https://code.claude.com/docs/en/memory):
  safe mode, settings-source isolation, explicit hooks/auto-memory off and no session persistence.
- [Codex skills configuration](https://github.com/openai/codex/blob/main/codex-rs/config/src/skills_config.rs),
  [feature flags](https://github.com/openai/codex/blob/main/codex-rs/features/src/lib.rs) and
  [configuration](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs):
  skip host discovery, suppress skills/catalog/bundled skills, disable hooks/plugins, replace base instructions.
  Empty auth-only home prevents inherited global AGENTS/config/plugin data.
- [Gemini settings schema](https://github.com/google-gemini/gemini-cli/blob/main/packages/cli/src/config/settingsSchema.ts)
  and [configuration precedence](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md).
  Installed Gemini source confirms an empty `tools.core` allowlist suppresses tool registration and
  installs a deny rule. System overrides disable hooks, skills, MCP and auto-memory; separate auth-only
  home and replacement context/system instructions avoid user/project coding context.
- [faster-whisper v1.2.1](https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1): local model, CPU int8/VAD.

The no-memory requirement applies to spawned summary sessions, not the active engineering session's
project knowledge. The user explicitly requested Obsidian persistence; the Scout project overview
records durable decisions and these acceptance limits, with repository documents remaining authoritative.
