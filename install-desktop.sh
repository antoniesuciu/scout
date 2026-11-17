#!/bin/sh
# Adds Scout to the Ubuntu app grid / search (per user, no sudo). Re-run after moving this folder.
# Remove with: ./install-desktop.sh --uninstall
set -eu
here=$(cd "$(dirname "$0")" && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$data/applications/io.scout.Scout.desktop" "$data/applications/scout.desktop" "$data/icons/hicolor/scalable/apps/scout.svg"
  for s in 16 24 32 48 64 128 256 512; do rm -f "$data/icons/hicolor/${s}x${s}/apps/scout.png"; done
  echo "Scout launcher removed."; exit 0
fi
for s in 16 24 32 48 64 128 256 512; do
  install -Dm644 "$here/assets/icons/scout-$s.png" "$data/icons/hicolor/${s}x${s}/apps/scout.png"
done
install -Dm644 "$here/assets/icons/scout.svg" "$data/icons/hicolor/scalable/apps/scout.svg"
mkdir -p "$data/applications"
rm -f "$data/applications/scout.desktop"  # pre-single-instance name
cat > "$data/applications/io.scout.Scout.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Scout
GenericName=Video summaries
Comment=Follow YouTube channels and summarize new videos
Exec="$here/scout" --desktop --port 0
Path=$here
Icon=scout
Terminal=false
Categories=Utility;
Keywords=youtube;summary;video;transcript;
StartupWMClass=scout
SingleMainWindow=true
DESKTOP
command -v update-desktop-database >/dev/null && update-desktop-database "$data/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$data/icons/hicolor" || true
echo "Scout installed: press Super and type Scout."
