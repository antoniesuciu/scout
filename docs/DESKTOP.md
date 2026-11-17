# Desktop direction — 2026-11-17

The original implementation used a localhost browser because its supplied design was HTML and the
backend was Python. A desktop window can reuse that UI; a desktop conversion alone does not fix
settings, model selection or file operations. Those now live in shared modules used by both modes.

## Current choice

Optional Ubuntu GTK3 + WebKit2 shell (`./scout --desktop --port 0`), kept in `src/scout/desktop.py`.
It is frameless at the owner's request. Native minimize/maximize/close/drag/resize actions use a
narrow WebKit message bridge; arbitrary commands/paths are not accepted through that bridge.
File import uses the webview's native chooser; downloads use a native Save dialog. Known library
files can be opened in the default editor. External links go to the system browser. Close confirms
before stopping an active job; headless engine process groups are cancelled and the server closes.

Installed OS runtime verified through introspection: GTK 3.24.41, WebKitGTK 2.52.6 (WebKit2 API 4.1),
PyGObject available to system Python. The project venv explicitly bridges Ubuntu's
`/usr/lib/python3/dist-packages` when `gi` is absent. This adds no downloaded GUI package, but **is an
OS-runtime dependency, not a self-contained venv**. Missing/inaccessible GUI runtime has a clear
error and browser mode remains available.

The user reported the window opened and the earlier reading controls changed the preview. The
agent cannot access the display; current frameless controls/native dialogs and the latest Save flow
have not been visually verified. Window-control dispatch/origin handling are tested with stand-ins.

## Cross-platform options

| Option | Consequence for Scout |
|---|---|
| Current GTK/WebKit shell | Smallest change on this Ubuntu laptop; Linux-specific runtime/glue |
| pywebview | Small cross-platform Python wrapper; reuses backend/UI; platform backend and packaging still required |
| PySide6 + QtWebEngine | Python development model with Qt/Chromium runtime; adds a second GUI stack |
| Tauri | Reuses frontend but adds Rust integration, permissions and Python sidecar packaging |
| Electron | Reuses frontend but adds Node main process and bundled Chromium, with Python as a managed child |

For a three-platform product, pywebview is a reasonable follow-up to evaluate. This is a recommendation,
not an implemented migration. Windows needs process-group/cancellation and terminal/file-launcher
adapters: the current implementation uses POSIX signals, `/bin/sh`, `xdg-open` and Linux terminals.
macOS also needs native window and launcher integration. Both need packaging and execution tests on
real target OSes. The existing UI/Python core can be shared; current desktop support is Ubuntu only.

Primary sources consulted during research:

- [pywebview installation](https://pywebview.flowrl.com/guide/installation.html),
  [API/lifecycle](https://pywebview.flowrl.com/api/), [local-server security](https://pywebview.flowrl.com/guide/security.html).
- [GTK native chooser](https://docs.gtk.org/gtk3/class.FileChooserNative.html),
  [Gio default-app launcher](https://docs.gtk.org/gio/type_func.AppInfo.launch_default_for_uri.html),
  [WebKit navigation policy](https://webkitgtk.org/reference/webkit2gtk/stable/signal.WebView.decide-policy.html).
- [Qt for Python installation](https://doc.qt.io/qtforpython-6/gettingstarted.html).
- [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) and [sidecars](https://v2.tauri.app/develop/sidecar/).
- [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model) and
  [security guidance](https://www.electronjs.org/docs/latest/tutorial/security).
