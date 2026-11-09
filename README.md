# YT-DLP Browser Extension

A modern, production-grade browser extension (Manifest V3) and local Python Native Messaging host that brings the full power of **yt-dlp** and **FFmpeg** directly to your browser on Arch / Omarchy Linux.

All downloads are processed locally on your computer with zero external cloud dependencies.

---

## Architecture

- **Extension Frontend**: Manifest V3 (HTML, CSS, JavaScript).
- **Background Worker**: `background.js` service worker manages native messaging lifecycles, progress streaming, and download history so downloads persist even when the popup is closed.
- **Native Host**: Python 3 host (`com.yt_dlp_extension.host`) communicating via standard 4-byte framed Native Messaging JSON protocol over stdio.
- **Media Engine**: Local `yt-dlp` for format extraction/streams and `FFmpeg` for merging and audio conversion.

---

## Features

- **Video Downloads**:
  - Quality selector: 144p, 240p, 360p, 480p, 720p, 1080p, 1440p, 2160p (4K).
  - Codec preference: Auto (Best), H.264 (AVC), VP9, AV1, H.265 / HEVC.
  - Container selection: MP4, WebM.
- **Audio Extraction**:
  - Direct audio stream extraction (`-f ba/b`) without downloading unwanted video tracks.
  - Formats: MP3, M4A (AAC), OPUS, WAV, FLAC.
  - Bitrate selection: 64, 128, 192, 256, 320 kbps.
- **Real-Time Progress & Cancellation**:
  - Exact progress percentage, download speed, and estimated time remaining (ETA).
  - One-click download cancellation terminating process groups cleanly.
  - Progress and history persist across popup open/close.
- **Playlist Support**:
  - Automatic playlist detection.
  - Opt-in toggle to download individual video or entire playlist with clean folder naming.
  - Selective playlist item range input (e.g. `1-5, 8, 10-12`) to download specific videos from long playlists.
- **Subtitles & Thumbnails**:
  - Optional subtitle and thumbnail downloading.
  - Subtitle language selector (`en`, `es`, `fr`, `de`, `ja`, `zh`, auto-generated, or all).
- **Network Resilience & Speed Limits**:
  - Automatic download continuation (`--continue`) and automatic network fragment retries (`--retries 3`, `--fragment-retries 3`).
  - Optional speed throttling (Unlimited, 1 MB/s, 2.5 MB/s, 5 MB/s, 10 MB/s).
- **Authentication & Age-Gated Media**:
  - Optional browser cookie extraction (`--cookies-from-browser`) supporting Chromium, Google Chrome, Brave, Firefox, Edge, Opera, and Vivaldi for member-only and age-restricted videos.
- **Download History & Dashboard**:
  - Recent completed, failed, and cancelled downloads directly in the popup with deduplication.
- **Cross-Browser Compatibility**:
  - Manifest V3 for Chromium, Google Chrome, Brave, and Edge.
  - Gecko Native Messaging support for Firefox (`ytdlp-extension@local`).
- **Settings & Tool Diagnostics**:
  - Configurable default quality, container, audio format, download directory (`~/Videos/Downloads` by default), speed limit, and cookies source.
  - Version checking and upgrade instructions for `yt-dlp`, `ffmpeg`, and `python`.

---

## Installation (Arch / Omarchy Linux)

### 1. Run the installer

```bash
cd /path/to/YT-DLP
./scripts/install.sh
```

The script verifies system dependencies (`python3`, `yt-dlp`, `ffmpeg`), makes `host.py` executable, creates `~/Videos/Downloads`, and prepares the Native Messaging host manifest.

### 2. Load the Extension in Chromium / Chrome / Brave

1. Open your browser and navigate to `chrome://extensions/` (or `brave://extensions/`).
2. Toggle **Developer mode** on (top-right).
3. Click **Load unpacked** and select the `extension/` folder inside this repository.
4. Copy the generated **Extension ID** (e.g. `lmnpgndmioblkjcihjjfejdbgihjghmg`).

### 3. Lock the Host to your Extension ID

Re-run the installer with your Extension ID:

```bash
./scripts/install.sh <EXTENSION_ID>
```

This registers the host manifest with the allowed origin `chrome-extension://<EXTENSION_ID>/` in your browser profile (`~/.config/chromium/NativeMessagingHosts/` etc.).

---

## Usage

1. Open any supported video or media webpage (e.g. YouTube, Vimeo, etc.).
2. Click the **yt-dlp Extension** icon in your toolbar.
3. The extension detects the current tab URL and loads video metadata and available formats.
4. Choose your mode (**Video** or **Audio Only**), resolution, codec, container/format, and click **Download**.
5. Real-time speed and progress will be shown in the popup and persist in the background.

---

## Settings

Click the settings gear icon in the popup header or right-click the extension icon and select **Options**.
Here you can:
- Change the default download directory.
- Set default container and audio bitrates.
- Check backend connectivity and verify installed versions of `yt-dlp` and `FFmpeg`.

---

## Running Tests

The test suite covers binary protocol framing, format normalization, progress parsing, rate limit/cookie sanitization, cross-browser manifests, and mock subprocess execution (38 tests):

```bash
python3 -m unittest discover -s tests -v
```

---

## Uninstallation

To remove the Native Messaging host registrations:

```bash
./scripts/uninstall.sh
```

Then remove the extension from `chrome://extensions/`.

---

## Architecture & Agent Handoff

For detailed technical notes, architecture diagrams, protocol specs, and inter-model collaboration context, see [AGENT_COMMUNICATION.md](AGENT_COMMUNICATION.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
