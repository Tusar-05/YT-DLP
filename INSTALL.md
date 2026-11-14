# 📦 Installation Guide - YT-DLP Browser Extension

## 🚀 Quick Start (Choose One Method)

### Method 1: Chrome Web Store (Easiest for Regular Users) ⭐ RECOMMENDED

1. Click the **[Install from Chrome Web Store](https://chrome.google.com/webstore/category/extensions)** button
2. Review permissions and click **"Add to Chrome"**
3. Extension is ready! Go to YouTube and test it out.

**Pros:** One-click install, auto-updates  
**Cons:** Limited customization

---

### Method 2: Open Source Installation (For Developers) 🔧

Follow these steps for full control and offline capability:

#### Step 1: Download the Repository

```bash
# Option A: Clone from GitHub
git clone https://github.com/Tusar-05/YT-DLP.git
cd YT-DLP

# Option B: Download ZIP (if not using Git)
# Right-click repository → Download ZIP → Extract
```

#### Step 2: Load in Chrome Browser

1. **Open Chrome browser**
2. Type `chrome://extensions` in address bar and press Enter
3. Enable **"Developer mode"** (toggle switch in top-right corner)
4. Click **"Load unpacked"** button
5. Navigate to your YT-DLP folder
6. Select the entire `YT-DLP` folder (not files inside)
7. Extension loads with name "YT-DLP Downloader"

#### Step 3: Test It!

1. Go to any YouTube video page (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ)
2. You should see a download icon/button appear
3. Click it and select your desired quality
4. File downloads to Chrome's Downloads folder

**Success!** 🎉

---

## 🔍 Troubleshooting

### "Extension doesn't show download button"

**Solution:** Refresh YouTube page → `Ctrl+Shift+R` (hard reload)

### "Load Unpacked" shows errors

**Check these:**
1. Make sure you selected the folder, not files inside it
2. Ensure manifest.json is at root level of folder
3. Chrome version must be 86+ (Manifest V3 support)

### "Extension requests permission but says 'blocked'"

This is normal for first-time install. Click **"Allow"** in prompt.

---

## 🛠️ Advanced Setup

### Using Local Backend (Full Control & Privacy)

If you want to run yt-dlp locally on your machine:

#### Prerequisites:
```bash
# Install Python (if not already installed)
python --version  # Should show Python 3.8+

# Install dependencies
pip install flask yt_dlp

# Download yt-dlp executable
pip install -U yt-dlp
yt-dlp --version  # Verify installation
```

#### Run Local Server:
```bash
cd YT-DLP/backend
python app.py
```

The extension will now use `http://localhost:8000` for downloads.

---

## 📱 Supported Browsers

| Browser | Status | Notes |
|---------|--------|-------|
| **Chrome** (Windows/Mac/Linux) | ✅ Full Support | Manifest V3 |
| **Edge** (Windows/Mac) | ✅ Full Support | Same as Chrome |
| **Firefox** | 🟡 Partial | Requires Firefox-specific build |
| **Safari** | ⚠️ Limited | No traditional extensions |

---

## 🔒 Privacy Notes

When using this extension:

- **Client-Side Only Mode:** All API calls go to external services (yt-dl-api.com)
- **Local Backend Mode:** Downloads processed on your machine only

See [SECURITY.md](../README.md#privacy-and-security) for details.

---

## 📖 Next Steps After Installation

1. Explore extension popup features
2. Try different video qualities
3. Download audio-only streams
4. Check subtitle support
5. Review privacy settings in options menu

---

## 🆘 Need Help?

Having trouble? Check these resources:

- [Common Issues FAQ](../FAQ.md)
- [GitHub Issues](https://github.com/Tusar-05/YT-DLP/issues)
- [Documentation](../API.md) for advanced usage

<div align="center">
  <strong>Happy downloading! 🎬</strong><br>
  Made with ❤️ by the open-source community
</div>
