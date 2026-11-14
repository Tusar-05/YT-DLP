# YT-DLP Browser Extension 🔽⬇️

Download YouTube videos directly in your browser using `yt-dlp` power! 
Extract videos in multiple qualities, audio-only streams, and even subtitles.

[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-green.svg)](https://chrome.google.com/webstore/category/extensions)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-blue.svg)](manifest.json)

## ✨ Features

- ⚡ **Fast Downloads** - Leverage yt-dlp's powerful video extraction
- 🎬 **Multiple Qualities** - Choose from 360p to 4K resolutions
- 🎵 **Audio-Only** - Extract audio streams easily
- 📝 **Subtitles Support** - Download and manage subtitle files
- 📋 **Playlist Downloads** - Batch download entire playlists
- 🔒 **Privacy First** - Local backend option (no data sent externally)

## 🚀 Quick Start

### Option 1: Install from Chrome Web Store (Recommended for General Users)

1. Click [Install](https://chrome.google.com/webstore/category/extensions) button above
2. Accept permissions and install
3. Browse YouTube → click download button on videos

### Option 2: Open Source Installation (Developer Friendly)

#### From GitHub (Current Method)

```bash
# Clone the repository
git clone https://github.com/Tusar-05/YT-DLP.git
cd YT-DLP

# Install and load in Chrome
echo "Installation complete! See INSTALL.md for next steps"
```

#### Steps to Load:

1. Go to [chrome://extensions](chrome://extensions)
2. Enable **Developer mode** (toggle in top-right)
3. Click **"Load unpacked"**
4. Select the `YT-DLP` folder you just downloaded
5. Extension is ready to use!

### 📋 Prerequisites

- Chrome browser v86+ (Manifest V3 support)
- OR Firefox (requires separate build - see [BUILD.md](BUILD.md))

## 🎯 How It Works

```
┌─────────────┐    ┌───────────────┐    ┌──────────────┐
│   YouTube   │───▶│  Extension    │───▶│ yt-dlp API   │
│   Page      │◀────│   (Browser)   │◀────│  or Local   │
│             │     │              │     │  Backend      │
└─────────────┘     └───────────────┘     └─────────────┘
                               ↓
                    Save to Chrome Downloads folder
```

### Architecture Options:

1. **Client-Side Only** - Uses existing yt-dlp wrapper APIs (fastest setup)
2. **Local Backend** - Runs on your machine with full control and privacy
3. **Hybrid** - Choose based on your needs!

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed breakdown.

## 🔧 Configuration

### Using External API (Default):

```json
// Uses yt-dl-api.com service
{
  "api_url": "https://yt-dl-api.com"
}
```

### Using Local Backend:

1. Install Python dependencies:
   ```bash
   pip install flask yt_dlp
   ```

2. Run local server:
   ```bash
   python app.py
   ```

3. Extension will connect to `http://localhost:8000`

## 📂 Project Structure

```
YT-DLP/
├── manifest.json          # Manifest V3 configuration
├── content.js            # YouTube page injection script
├── background.js         # Service worker (API calls)
├── popup.html            # Extension popup UI
├── popup.css             # Popup styling
├── popup.js              # Popup interactions
├── README.md             # This file!
├── INSTALL.md            # Detailed installation guide
├── LICENSE               # MIT License
└── icons/                # Extension icon images
```

## 🛠️ Development Setup

### Clone & Test Locally:

```bash
git clone https://github.com/Tusar-05/YT-DLP.git
cd YT-DLP

# Install browser (recommended)
pip install google-chrome-cli  # or firefox on Linux

# Or use Chrome directly:
# Go to chrome://extensions → Developer mode → Load unpacked
```

### Build for Different Browsers:

See [BUILD.md](BUILD.md) for platform-specific builds.

## 📖 API Reference

### Content Script Messages:

```javascript
// Fetch available streams
chrome.runtime.sendMessage('YT-DLP', {
  action: 'getStreams',
  url: 'https://www.youtube.com/watch?v=VIDEO_ID'
});
```

### Background Service Worker:

- `'getStreams'` → Fetch stream data
- `'getSubtitleUrls'` → Get subtitle URLs
- `'cancelDownload'` → Cancel current download
- `'getStatus'` → Download progress

See [API.md](API.md) for complete reference.

## 🔒 Privacy & Security

- **No Tracking** - We don't track your browsing habits
- **Local Processing** - Option to run backend locally
- **Minimal Permissions** - Only request what's needed
- **MIT License** - Open source and freely distributable

See [SECURITY.md](SECURITY.md) for security best practices.

## 🤝 Contributing

Contributions welcome! Here's how to help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🐛 Reporting Issues

Found a bug or have a feature request? [Open an issue](https://github.com/Tusar-05/YT-DLP/issues)!

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/ptfityzhao/yt-dlp) - The powerful download tool
- [Chrome Extensions API](https://developer.chrome.com/docs/extensions)
- Manifest V3 authors

## 📞 Support

For questions or support:
- Open an issue on GitHub
- Check [FAQ.md](FAQ.md) for common problems
- Join our community discussions

---

<div align="center">
  <strong>Made with ❤️ by Tusar Kanta Marei</strong><br>
  <em>Proudly open source, MIT licensed</em>
</div>
