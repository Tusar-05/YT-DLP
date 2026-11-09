# Project: YT-DLP Browser Extension

Act as a senior full-stack developer specializing in browser extension development, Python automation, Linux integration, and modern UI/UX design.

Build a complete, production-quality browser extension that uses **yt-dlp as its local downloading backend** to download video and audio from supported websites.

The project must run locally on my Omarchy Linux system (Arch Linux-based).

## 1. Core Architecture

Use the following architecture:

- Frontend: HTML, CSS, JavaScript.
- Browser extension: Manifest V3.
- Backend: Python 3.
- Downloader: yt-dlp.
- Media processing: FFmpeg.
- Extension/backend communication: Native Messaging API.
- Metadata exchange: JSON.

Do not implement a cloud backend. All downloads must be processed locally on the user's computer.

## 2. Browser Compatibility

Initially target Chromium-based browsers:
- Google Chrome
- Brave
- Chromium
- Microsoft Edge

Keep the architecture modular enough to support Firefox later.

## 3. Extension Interface

Create a modern, polished, minimal dark-themed interface.

Design requirements:
- Dark charcoal background.
- Modern typography.
- Rounded cards and buttons.
- Subtle animations and hover effects.
- Clear visual hierarchy.
- Responsive popup layout.
- Professional download dashboard.

The extension popup should contain:

1. Video thumbnail.
2. Video title.
3. Channel name.
4. Video duration.
5. Detected video URL.
6. Video/audio mode selector.
7. Format selector.
8. Resolution selector.
9. Download button.
10. Download progress indicator.

## 4. Video Download Features

Allow users to download videos in available resolutions:

- 144p
- 240p
- 360p
- 480p
- 720p
- 1080p
- 1440p
- 2160p (4K)

Only display formats actually available for the selected video.

Allow selection of:
- MP4
- WebM
- H.264
- H.265/HEVC
- VP9
- AV1

Use yt-dlp format discovery to retrieve actual available formats.

Prefer compatible format combinations and use FFmpeg for merging separate video and audio streams.

## 5. Audio Download Features

Provide an audio-only download mode.

Supported output formats:
- MP3
- M4A
- OPUS
- WAV
- FLAC

Allow bitrate selection where supported:
- 64 kbps
- 128 kbps
- 192 kbps
- 256 kbps
- 320 kbps

Use yt-dlp audio extraction and FFmpeg conversion.

Clearly distinguish source quality from transcoded output quality.

## 6. Metadata Extraction

When a user opens a supported video page, retrieve:

- Video title
- Thumbnail
- Duration
- Channel name
- Available formats
- Resolution
- File extension
- Video codec
- Audio codec
- Approximate file size when available

Use yt-dlp JSON output for metadata extraction.

Display loading indicators while retrieving metadata.

## 7. Download Manager

Implement a download management interface.

Features:
- Real-time download progress.
- Download percentage.
- Download speed.
- Estimated remaining time.
- Download queue.
- Pause/resume where supported.
- Cancel downloads.
- Multiple download handling.
- Completed downloads list.
- Failed download notifications.

Use yt-dlp progress hooks and structured communication between Python and the browser extension.

Do not fake progress values.

## 8. Playlist Support

Support playlist detection.

Allow users to:
- Download an individual video.
- Download an entire playlist.
- Select individual videos from a playlist.
- Choose a common output format and quality.
- View playlist download progress.

## 9. Additional Features

Implement:
- Subtitle downloading.
- Automatic subtitle language selection.
- Thumbnail downloading.
- Custom download directory.
- Configurable default quality.
- Configurable default audio format.
- Download history.
- Error logging.
- yt-dlp version checking and updating instructions.

Default download directory:

~/Videos/Downloads

## 10. Backend Implementation

Create a Python Native Messaging host.

Requirements:
- Communicate using the Native Messaging JSON protocol.
- Correctly implement message length headers.
- Never print debugging messages to stdout.
- Send diagnostic messages to stderr.
- Validate all incoming messages.
- Handle malformed JSON.
- Handle concurrent download requests safely.
- Manage yt-dlp subprocesses.
- Stream download progress to the extension.
- Support cancellation.
- Handle missing dependencies.
- Handle network errors.
- Handle unsupported URLs.
- Never execute arbitrary shell commands from extension input.

Use subprocess argument arrays rather than shell command strings.

## 11. Security

Implement:
- Strict URL validation.
- Restrict downloads to supported URLs.
- Avoid arbitrary command execution.
- Validate output paths.
- Prevent path traversal.
- Do not expose local filesystem contents to webpages.
- Use minimum browser permissions.
- Do not collect user browsing history.
- Do not transmit user data to external servers.
- Restrict Native Messaging access to the intended extension ID.

Only support downloads the user owns or is authorized to download, and respect applicable copyright laws and website terms.

## 12. Project Structure

Organize the code cleanly:

yt-dlp-extension/
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   ├── popup.js
│   ├── background.js
│   ├── options.html
│   ├── options.js
│   └── icons/
│
├── native-host/
│   ├── host.py
│   ├── downloader.py
│   ├── formats.py
│   ├── config.py
│   └── native-host-manifest.json
│
├── scripts/
│   ├── install.sh
│   └── uninstall.sh
│
├── tests/
│
├── README.md
└── LICENSE

You may modify this structure if a better architecture is justified.

## 13. Omarchy Linux Integration

Provide installation scripts for Arch Linux / Omarchy.

The installer should:
- Check for Python 3.
- Check for yt-dlp.
- Check for FFmpeg.
- Install missing dependencies where appropriate.
- Register the Native Messaging host.
- Configure the extension's allowed origin.
- Create the download directory.
- Set executable permissions.
- Provide clear installation instructions.

Do not require root privileges for normal downloads.

Support both system-installed and user-installed yt-dlp where practical.

## 14. Testing

Test:
- Metadata retrieval.
- Video format discovery.
- Audio format discovery.
- MP4 downloads.
- WebM downloads.
- Audio extraction.
- FFmpeg conversion.
- Download cancellation.
- Progress reporting.
- Playlist handling.
- Invalid URLs.
- Missing dependencies.
- Native Messaging communication.

Use mock tests where external network access is unavailable.

## 15. Development Instructions

Follow these rules:

1. Inspect the development environment before implementing.
2. Create the complete project structure.
3. Implement the backend first.
4. Test the Native Messaging host independently.
5. Implement the browser extension.
6. Integrate the extension and backend.
7. Test the complete workflow.
8. Fix errors rather than leaving TODO placeholders.
9. Keep the code modular and maintainable.
10. Document every installation and configuration step.

Do not generate a superficial demo or a nonfunctional UI.

The final result must be an actual working browser extension with a functional local yt-dlp backend.

Start by inspecting the environment and creating an implementation plan. Then proceed with implementation and testing.
