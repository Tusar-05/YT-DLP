#!/usr/bin/env bash
#
# package.sh — Create a distributable .zip archive of the extension
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$REPO_ROOT/extension"
DIST_DIR="$REPO_ROOT/dist"
OUTPUT_ZIP="$DIST_DIR/yt-dlp-extension.zip"

mkdir -p "$DIST_DIR"
rm -f "$OUTPUT_ZIP"

echo "==> Packaging yt-dlp Extension..."

python3 -c "
import os, zipfile

src = '$EXT_DIR'
dst = '$OUTPUT_ZIP'

with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(src):
        # Filter hidden or unwanted files
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.startswith('.') or f.endswith(('.tmp', '.swp')):
                continue
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, src)
            z.write(abs_p, arcname=rel_p)
            print(f'   + {rel_p}')

print(f'\n✓ Package created: {dst} ({os.path.getsize(dst)} bytes)')
"
