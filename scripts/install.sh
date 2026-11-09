#!/usr/bin/env bash
#
# install.sh — Install the yt-dlp Extension Native Messaging host on
# Omarchy / Arch Linux.
#
# Per plan.md section 13:
#   - Check for Python 3, yt-dlp, FFmpeg (install missing via pacman)
#   - Register the Native Messaging host for each Chromium-based browser
#   - Create the default download directory ~/Videos/Downloads
#   - Set executable permissions on host.py
#   - No root required for normal downloads (root only for pacman installs)
#
# Usage:
#   ./install.sh                 # register host (you must then set the extension ID)
#   ./install.sh <EXTENSION_ID>  # register host locked to the given extension ID
#
# After installing, load the unpacked extension in Chromium, open
# chrome://extensions, copy the extension's ID, and re-run:
#   ./install.sh <EXTENSION_ID>
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_NAME="com.yt-dlp-extension.host"
HOST_SCRIPT="$REPO_ROOT/native-host/host.py"
HOST_MANIFEST_TEMPLATE="$REPO_ROOT/native-host/native-host-manifest.json"
EXTENSION_ID="${1:-}"

# --- dependency checks ------------------------------------------------------

have() { command -v "$1" >/dev/null 2>&1; }

echo "==> Checking dependencies"

if ! have python3; then
  echo "python3 not found. Installing via pacman..."
  if have sudo; then sudo pacman -Sy --needed --noconfirm python; else pacman -Sy --needed --noconfirm python; fi
fi
echo "   python3: $(python3 --version)  ($(command -v python3))"

if ! have yt-dlp; then
  echo "yt-dlp not found. Installing via pacman..."
  if have sudo; then sudo pacman -Sy --needed --noconfirm yt-dlp; else pacman -Sy --needed --noconfirm yt-dlp; fi
fi
echo "   yt-dlp:  $(yt-dlp --version 2>/dev/null || echo unknown)  ($(command -v yt-dlp))"

if ! have ffmpeg; then
  echo "ffmpeg not found. Installing via pacman..."
  if have sudo; then sudo pacman -Sy --needed --noconfirm ffmpeg; else pacman -Sy --needed --noconfirm ffmpeg; fi
fi
echo "   ffmpeg:  $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f3)  ($(command -v ffmpeg))"

# --- make host executable ---------------------------------------------------

chmod +x "$HOST_SCRIPT"
echo "   host.py executable: $HOST_SCRIPT"

# --- create default download directory --------------------------------------

DOWNLOAD_DIR="$HOME/Videos/Downloads"
mkdir -p "$DOWNLOAD_DIR"
echo "   download dir: $DOWNLOAD_DIR"

# --- browser profile roots (Chromium-based) ---------------------------------

browser_dirs=(
  "$HOME/.config/chromium"
  "$HOME/.config/google-chrome"
  "$HOME/.config/google-chrome-beta"
  "$HOME/.config/google-chrome-unstable"
  "$HOME/.config/BraveSoftware/Brave-Browser"
  "$HOME/.config/BraveSoftware/Brave-Browser-Beta"
  "$HOME/.config/BraveSoftware/Brave-Browser-Nightly"
  "$HOME/.config/microsoft-edge"
  "$HOME/.config/microsoft-edge-dev"
)

# --- build the host manifest -----------------------------------------------

if [[ -n "$EXTENSION_ID" ]]; then
  ALLOWED_ORIGIN="chrome-extension://$EXTENSION_ID/"
else
  ALLOWED_ORIGIN="__EXTENSION_ORIGIN_PLACEHOLDER__"
fi

manifest="$(sed \
  -e "s|__HOST_PATH__|$HOST_SCRIPT|g" \
  -e "s|__EXTENSION_ORIGIN__|$ALLOWED_ORIGIN|g" \
  "$HOST_MANIFEST_TEMPLATE")"

# --- register host in each browser profile ----------------------------------

registered=0
for dir in "${browser_dirs[@]}"; do
  if [[ ! -d "$dir" ]]; then
    continue
  fi
  mkdir -p "$dir/NativeMessagingHosts"
  printf '%s\n' "$manifest" > "$dir/NativeMessagingHosts/$HOST_NAME.json"
  echo "   registered in $dir/NativeMessagingHosts/$HOST_NAME.json"
  registered=$((registered + 1))
done

if [[ $registered -eq 0 ]]; then
  echo "   (no Chromium-based browser profiles found yet; they will be created on first launch)"
fi

# --- next steps -------------------------------------------------------------

echo
echo "==> Installation complete."
echo
if [[ -z "$EXTENSION_ID" ]]; then
  echo "IMPORTANT: The host manifest currently uses a placeholder origin."
  echo "1. Load the unpacked extension in Chromium:"
  echo "       chrome://extensions -> Developer mode -> Load unpacked"
  echo "       Select: $REPO_ROOT/extension"
  echo "2. Copy the extension ID from chrome://extensions."
  echo "3. Re-run this script with the ID to lock the host to your extension:"
  echo "       $0 <EXTENSION_ID>"
  echo
  echo "Without step 3 the host will refuse connections from the extension."
else
  echo "Host is locked to extension ID: $EXTENSION_ID"
  echo "Load the unpacked extension at: $REPO_ROOT/extension"
fi
echo
echo "Normal downloads do NOT require root. Root was only used (if needed) to"
echo "install missing system packages via pacman."
