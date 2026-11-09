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
#   ./install.sh                 # register host (uses existing ID or prompt)
#   ./install.sh <EXTENSION_ID>  # register host locked to the given extension ID
#
# After installing, load the unpacked extension in Chromium, open
# chrome://extensions, copy the extension's ID, and re-run:
#   ./install.sh <EXTENSION_ID>
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_NAME="com.yt_dlp_extension.host"
OLD_HOST_NAME="com.yt-dlp-extension.host"
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
mkdir -p "$DOWNLOAD_DIR" 2>/dev/null || true
echo "   download dir: $DOWNLOAD_DIR"

# --- browser profile roots (Chromium-based) ---------------------------------

browser_configs=(
  "chromium:$HOME/.config/chromium"
  "google-chrome:$HOME/.config/google-chrome"
  "google-chrome-beta:$HOME/.config/google-chrome-beta"
  "google-chrome-unstable:$HOME/.config/google-chrome-unstable"
  "brave:$HOME/.config/BraveSoftware/Brave-Browser"
  "brave-browser:$HOME/.config/BraveSoftware/Brave-Browser"
  "microsoft-edge:$HOME/.config/microsoft-edge"
  "microsoft-edge-dev:$HOME/.config/microsoft-edge-dev"
)

# --- build the host manifest -----------------------------------------------

# If no extension ID provided as argument, check if an existing manifest already has an ID
if [[ -z "$EXTENSION_ID" ]]; then
  for m in "$HOME/.config/chromium/NativeMessagingHosts/$HOST_NAME.json" "$HOME/.config/chromium/NativeMessagingHosts/$OLD_HOST_NAME.json"; do
    if [[ -f "$m" ]]; then
      detected_id="$(grep -o 'chrome-extension://[a-z]*/' "$m" | head -1 | sed 's|chrome-extension://||;s|/||' || true)"
      if [[ -n "$detected_id" ]]; then
        EXTENSION_ID="$detected_id"
        echo "   detected existing extension ID: $EXTENSION_ID"
        break
      fi
    fi
  done
fi

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
for entry in "${browser_configs[@]}"; do
  binary="${entry%%:*}"
  dir="${entry#*:}"

  # Register if directory exists OR if browser binary is installed on PATH
  if [[ -d "$dir" ]] || have "$binary"; then
    if ( mkdir -p "$dir/NativeMessagingHosts" && rm -f "$dir/NativeMessagingHosts/$OLD_HOST_NAME.json" && printf '%s\n' "$manifest" > "$dir/NativeMessagingHosts/$HOST_NAME.json" ) 2>/dev/null; then
      echo "   registered in $dir/NativeMessagingHosts/$HOST_NAME.json"
      registered=$((registered + 1))
    fi
  fi
done

if [[ $registered -eq 0 ]]; then
  if ( mkdir -p "$HOME/.config/chromium/NativeMessagingHosts" && rm -f "$HOME/.config/chromium/NativeMessagingHosts/$OLD_HOST_NAME.json" && printf '%s\n' "$manifest" > "$HOME/.config/chromium/NativeMessagingHosts/$HOST_NAME.json" ) 2>/dev/null; then
    echo "   registered in default: $HOME/.config/chromium/NativeMessagingHosts/$HOST_NAME.json"
    registered=1
  else
    echo "   Notice: $HOME/.config is currently read-only in this subshell."
    echo "   Run './scripts/install.sh $EXTENSION_ID' in your host terminal if needed."
  fi
fi

# --- register for Firefox if firefox is available ---------------------------

FIREFOX_MANIFEST_TEMPLATE="$REPO_ROOT/native-host/firefox-host-manifest.json"
if [[ -f "$FIREFOX_MANIFEST_TEMPLATE" ]]; then
  firefox_manifest="$(sed -e "s|__HOST_PATH__|$HOST_SCRIPT|g" "$FIREFOX_MANIFEST_TEMPLATE")"
  if have firefox || [[ -d "$HOME/.mozilla" ]]; then
    if ( mkdir -p "$HOME/.mozilla/native-messaging-hosts" && rm -f "$HOME/.mozilla/native-messaging-hosts/$OLD_HOST_NAME.json" && printf '%s\n' "$firefox_manifest" > "$HOME/.mozilla/native-messaging-hosts/$HOST_NAME.json" ) 2>/dev/null; then
      echo "   registered for Firefox: $HOME/.mozilla/native-messaging-hosts/$HOST_NAME.json"
    fi
  fi
fi

# --- next steps -------------------------------------------------------------

echo
echo "==> Installation complete."
echo
if [[ "$ALLOWED_ORIGIN" == *"PLACEHOLDER"* ]]; then
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
