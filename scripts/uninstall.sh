#!/usr/bin/env bash
#
# uninstall.sh — Remove the yt-dlp Extension Native Messaging host from
# all Chromium-based browser profiles on this machine.
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_NAME="com.yt-dlp-extension.host"

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

removed=0
for dir in "${browser_dirs[@]}"; do
  target="$dir/NativeMessagingHosts/$HOST_NAME.json"
  if [[ -f "$target" ]]; then
    rm -f "$target"
    echo "removed $target"
    removed=$((removed + 1))
  fi
done

if [[ $removed -eq 0 ]]; then
  echo "No yt-dlp extension Native Messaging hosts found."
else
  echo "Removed $removed host registration(s)."
fi
