# Hallmark audit — Scout, 2026-11-17

Scope: a modern-minimal app screen, preserving `REQUIREMENTS.md` and the supplied dashboard.
This is an audit/polish, not a new theme or layout. No theme was dealt. Real material is the
inbox and reader; no photographs, placeholder slots, invented metrics or claims were added.

## Preserved

Seven-colour Ink/Paper/Phosphor themes, Space Grotesk/Inter/JetBrains Mono and reading-font
switches, two wrapping columns, segmented controls, 44px targets, the sole accent-filled
Summarize action, dashed reader empty states, settings popover and process log.

## Corrections made

Moved palette/font values into root/theme tokens; clipped horizontal page overflow; bounded
container and settings width; extended keyboard focus to all controls; supplied disabled and
active states; corrected heading levels; retained visible loading/noscript messages. Split the
markup, styles and script into `src/scout/web/`. Prices now say snapshot. Preparation, errors
and unavailable modes use real application state.

## Final mechanical result

Command:

```sh
node ~/.agents/skills/hallmark/scripts/sloplint.mjs src/scout/web --scope app --genre modern-minimal --render
```

**3 FAIL, 1 WARN, 13 NOTE across 2 files; exit 1. This is not a clean Hallmark pass.**

- Two FAIL 47a findings identify the real `window-controls` markup/selector as re-drawn OS
  chrome. These controls actually invoke the native window's minimize/maximize/close operations;
  they are not a faux browser/product screenshot. They fulfill the user's explicit frameless-window
  request. The findings are retained as mechanical false positives, not hidden through renaming.
- FAIL 67: `styles.css` `.label` uses uppercase and 0.08em tracking. This is explicitly required
  by the product specification. The user's instruction to preserve the design takes precedence.
  It is recorded as an unresolved conflict, not a Hallmark Floor waiver.
- WARN F24: settings popover combines a fine border with a broad shadow. The supplied design
  specifically permits the settings shadow; retained on that basis.
- NOTE 24b: 13 off-scale spacing declarations match the supplied control/layout measurements.
  The Reflex spacing rule is waived in the stylesheet with that evidence.

A cached Puppeteer/Chromium was found and the render tier was attempted explicitly. Chromium
failed with `sandbox_host_linux.cc:41 ... shutdown: Operation not permitted`. No screenshots,
contrast measurement, narrow-screen render or visual finish score is claimed. Codex's in-thread
review checked source/state wiring and retained the original composition; a fresh visual review
cannot be completed without rendering. There are no image slots awaiting supplied material.
The user confirmed initial native launch and the earlier reading preview; later Save/Revert and
frameless changes are not yet user-verified. The most useful next design evidence is a real
dashboard capture at desktop and phone widths,
including a filled reader and an open settings popover in each theme.
