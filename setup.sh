#!/usr/bin/env bash
#
# setup.sh — One-step interactive setup wizard for yt-dlp Browser Extension
#
# Usage:
#   ./setup.sh                 # Standard automatic setup & diagnostic self-test
#   ./setup.sh <EXTENSION_ID>  # Setup locked to a specific Chrome Extension ID
#   ./setup.sh --doctor        # Run system diagnostics and verify connection
#   ./setup.sh --uninstall     # Remove native messaging host registrations
#   ./setup.sh --help          # Show help
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_DIR="$REPO_ROOT/extension"
HOST_SCRIPT="$REPO_ROOT/native-host/host.py"
HOST_NAME="com.yt_dlp_extension.host"

# Colors for terminal output
if [[ -t 1 ]]; then
  BOLD="\033[1m"
  GREEN="\033[32m"
  CYAN="\033[36m"
  YELLOW="\033[33m"
  RED="\033[31m"
  DIM="\033[2m"
  RESET="\033[0m"
else
  BOLD="" GREEN="" CYAN="" YELLOW="" RED="" DIM="" RESET=""
fi

banner() {
  cat << "EOF"
 __   _______    ____  _     ____  
 \ \ / /_   _|  |  _ \| |   |  _ \ 
  \ V /  | |____| | | | |   | |_) |
   | |   | |____| |_| | |___|  __/ 
   |_|   |_|    |____/|_____|_|    
EOF
  echo -e "${BOLD}yt-dlp Browser Extension — Setup & Diagnostics${RESET}"
  echo -e "${DIM}Repository: $REPO_ROOT${RESET}"
  echo "--------------------------------------------------------"
}

have() { command -v "$1" >/dev/null 2>&1; }

run_selftest() {
  echo -e "\n${BOLD}==> Testing Native Messaging Host over stdio...${RESET}"
  test_result="$(python3 -c "
import struct, json, subprocess, sys
try:
    p = subprocess.Popen(['python3', '$HOST_SCRIPT'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = json.dumps({'type': 'ping', 'req_id': 'setup-selftest'}).encode('utf-8')
    p.stdin.write(struct.pack('<I', len(raw)) + raw)
    p.stdin.flush()
    hdr = p.stdout.read(4)
    if len(hdr) < 4:
        sys.exit(1)
    reply_len = struct.unpack('<I', hdr)[0]
    res = json.loads(p.stdout.read(reply_len).decode('utf-8'))
    p.terminate()
    if res.get('type') == 'pong' and res.get('ok'):
        print('SUCCESS')
    else:
        print('UNEXPECTED')
except Exception as e:
    print('ERROR:', e)
    sys.exit(1)
" 2>/dev/null || echo "FAILED")"

  if [[ "$test_result" == *"SUCCESS"* ]]; then
    echo -e "   ${GREEN}[✓] Host stdio 4-byte binary protocol test: PASSED${RESET}"
    return 0
  else
    echo -e "   ${RED}[✗] Host stdio binary protocol test: FAILED${RESET}"
    return 1
  fi
}

run_doctor() {
  banner
  echo -e "${BOLD}==> Running Environment Diagnostics${RESET}\n"

  # Python
  if have python3; then
    echo -e "   ${GREEN}[✓] Python 3:${RESET} $(python3 --version) at $(command -v python3)"
  else
    echo -e "   ${RED}[✗] Python 3: NOT FOUND${RESET}"
  fi

  # yt-dlp
  if have yt-dlp; then
    echo -e "   ${GREEN}[✓] yt-dlp:${RESET}   $(yt-dlp --version 2>/dev/null || echo unknown) at $(command -v yt-dlp)"
  else
    echo -e "   ${RED}[✗] yt-dlp:   NOT FOUND${RESET} (install with: sudo pacman -S yt-dlp)"
  fi

  # ffmpeg
  if have ffmpeg; then
    echo -e "   ${GREEN}[✓] FFmpeg:${RESET}   $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f3) at $(command -v ffmpeg)"
  else
    echo -e "   ${RED}[✗] FFmpeg:   NOT FOUND${RESET} (install with: sudo pacman -S ffmpeg)"
  fi

  # Host script
  if [[ -x "$HOST_SCRIPT" ]]; then
    echo -e "   ${GREEN}[✓] Host file:${RESET} $HOST_SCRIPT (executable)"
  else
    echo -e "   ${YELLOW}[!] Host file:${RESET} $HOST_SCRIPT (fixing permissions...)"
    chmod +x "$HOST_SCRIPT"
  fi

  # Self test
  run_selftest

  # Registered manifests check
  echo -e "\n${BOLD}==> Checking Registered Browser Host Manifests${RESET}"
  found=0
  for dir in "$HOME/.config/chromium" "$HOME/.config/google-chrome" "$HOME/.config/BraveSoftware/Brave-Browser" "$HOME/.config/microsoft-edge" "$HOME/.mozilla"; do
    if [[ "$dir" == *".mozilla"* ]]; then
      mf="$dir/native-messaging-hosts/$HOST_NAME.json"
    else
      mf="$dir/NativeMessagingHosts/$HOST_NAME.json"
    fi
    if [[ -f "$mf" ]]; then
      echo -e "   ${GREEN}[✓] Found:${RESET} $mf"
      found=$((found + 1))
    fi
  done
  if [[ $found -eq 0 ]]; then
    echo -e "   ${YELLOW}[!] No host manifests found. Run './setup.sh' to install.${RESET}"
  fi
}

# --- CLI Argument Handling --------------------------------------------------

ACTION="${1:-}"

if [[ "$ACTION" == "--help" || "$ACTION" == "-h" ]]; then
  echo "Usage: ./setup.sh [EXTENSION_ID | --doctor | --uninstall | --help]"
  echo
  echo "Commands:"
  echo "  ./setup.sh                 Run setup, register host manifests, and self-test"
  echo "  ./setup.sh <EXTENSION_ID>  Run setup locked to an explicit extension ID"
  echo "  ./setup.sh --doctor        Run comprehensive diagnostics and connection check"
  echo "  ./setup.sh --uninstall     Remove all registered native messaging hosts"
  echo "  ./setup.sh --help          Show this help message"
  exit 0
fi

if [[ "$ACTION" == "--doctor" || "$ACTION" == "-d" ]]; then
  run_doctor
  exit 0
fi

if [[ "$ACTION" == "--uninstall" || "$ACTION" == "-u" ]]; then
  banner
  echo -e "${BOLD}==> Uninstalling Native Messaging Host${RESET}\n"
  "$REPO_ROOT/scripts/uninstall.sh"
  exit 0
fi

# --- Standard Setup ---------------------------------------------------------

banner

# 1. Run install script
echo -e "${BOLD}==> 1. Configuring and Registering Native Host${RESET}"
"$REPO_ROOT/scripts/install.sh" "$@"

# 2. Run self-test
run_selftest

# 3. Present clear user-friendly instructions
echo
echo -e "${BOLD}========================================================${RESET}"
echo -e "${GREEN}${BOLD}✓ Setup Finished! You are ready to load the extension.${RESET}"
echo -e "${BOLD}========================================================${RESET}"
echo
echo -e "${BOLD}How to Load in Chromium / Google Chrome / Brave / Edge:${RESET}"
echo -e "  1. Open ${CYAN}chrome://extensions${RESET} in your browser."
echo -e "  2. Enable ${BOLD}Developer mode${RESET} (toggle in top-right corner)."
echo -e "  3. Click ${BOLD}Load unpacked${RESET}."
echo -e "  4. Select this folder:"
echo -e "     ${BOLD}${CYAN}$EXTENSION_DIR${RESET}"
echo
echo -e "${BOLD}How to Load in Mozilla Firefox:${RESET}"
echo -e "  1. Open ${CYAN}about:debugging#/runtime/this-firefox${RESET}"
echo -e "  2. Click ${BOLD}Load Temporary Add-on…${RESET}"
echo -e "  3. Select:"
echo -e "     ${BOLD}${CYAN}$EXTENSION_DIR/manifest.json${RESET}"
echo
echo -e "${DIM}Tip: You can re-run diagnostics anytime with: ./setup.sh --doctor${RESET}"
echo
