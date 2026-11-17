# Scout implementation plan

2026-11-17. Source of requirements: `REQUIREMENTS.md`; original project is an untouched,
untracked reference in `stock-update-main/`. The working app is Scout in `src/scout/`, launched from the repository root.

Use small modules with a narrow public interface (Matt Pocock codebase-design): media preparation,
engine execution, and the dashboard job. Test through these interfaces, with stand-in external
programs where network, subscriptions or optional binaries are unavailable. No extra model passes.

1. **Foundation / engine adapters.** Preserve the supplied dashboard and seven-colour themes;
   use a project `.venv`; run all available engine diagnostics; enforce timeouts, isolated working
   directories, per-video failure/retry and local HTTP guards. Acceptance: reproducible adapter,
   parser, pipeline and HTTP tests; truthful report of live integration limits.
2. **Timestamped transcripts.** Keep cue times in exported files and model input; deduplicate rolling
   subtitles without deleting later repeated speech. Acceptance: independent VTT fixtures.
3. **Public Reels paste-links.** No cookies, login, saved-post fetching or background discovery.
   Captions first, optional local faster-whisper fallback. Acceptance: supported URL validation,
   caption-first and missing-dependency behavior tested without touching an Instagram account.
4. **On-screen text.** Capped periodic/manual/regex visual-cue frame sampling and local OCR;
   explicit media-download cost; never claim the model saw images. Acceptance: bounds and OCR
   provenance tested; missing local tools reported. Real images remain deferred pending containment.
5. **Usage / cache.** Explicit prepare and preview before one batch call; cache includes transcript,
   prompt version, engine/model, language and mode. Acceptance: cached reruns use zero engine calls,
   changed inputs miss the cache, over-limit input never calls an engine.
6. **Transcript search.** Rebuildable SQLite FTS5 index over saved files. No prediction ledger:
   a mention is not a forecast and current prices are never historical evidence.
7. **Saved Instagram.** Deferred by explicit user decision (2026-11-17).

Finish: rewrite README for Scout, synchronize requirements status, run tests and Hallmark audit
in app scope. Preserve requirements over conflicting Hallmark typography rules. Commit cohesive
milestones; never add the reference folder or generated/user data.


## Reliability and desktop follow-up (2026-11-17)

- Reproduced missing in-app settings/library with failing HTTP regression tests (both 404).
- Implemented separate validated configuration and file modules, all-provider model selection,
  auth-only/no-hook/no-skill/no-memory headless sessions, and explicit interactive terminal mode.
- Built the file library and reading-style preview; refined it to Save/Revert at the user's request.
- Added the Ubuntu native shell and frameless controls without rewriting the shared interface.
- Isolated personal settings from tracked defaults; preserve the user's live preferences.
- Added actual subprocess contract workflows for all providers, plus native-dispatch, persistence,
  file/API and browser-controller checks. Live account/GUI evidence remains separate.
- Capture durable decisions in the conventional Obsidian Scout Project Overview; keep the
  implementation and detailed verification in the repository. Export cohesive commits as a bundle
  because the current checkout's `.git` cannot be written. No push.
