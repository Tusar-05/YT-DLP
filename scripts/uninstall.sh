#!/usr/bin/env bash
#
# uninstall.sh — Remove the yt-dlp Extension Native Messaging host from
# all Chromium-based browser profiles on this machine.
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_NAME="com.yt_dlp_extension.host"
OLD_HOST_NAME="com.yt-dlp-extension.host"

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
  for name in "$HOST_NAME" "$OLD_HOST_NAME"; do
    target="$dir/NativeMessagingHosts/$name.json"
    if [[ -f "$target" ]]; then
      rm -f "$target"
      echo "removed $target"
      removed=$((removed + 1))
    fi
  done
done

# Firefox
for name in "$HOST_NAME" "$OLD_HOST_NAME"; do
  firefox_target="$HOME/.mozilla/native-messaging-hosts/$name.json"
  if [[ -f "$firefox_target" ]]; then
    rm -f "$firefox_target"
    echo "removed $firefox_target"
    removed=$((removed + 1))
  fi
done

if [[ $removed -eq 0 ]]; then
  echo "No yt-dlp extension Native Messaging hosts found."
else
  echo "Removed $removed host registration(s)."
fi
