/**
 * popup.js — yt-dlp Extension popup controller.
 *
 * Talks to the Python Native Messaging host (com.yt-dlp-extension.host) via a
 * connected Port so we can stream download progress in real time. Each request
 * carries a req_id; responses are matched back by req_id.
 */

(function () {
  const HOST_NAME = "com.yt-dlp-extension.host";

  // DOM refs
  const els = {
    urlInput: document.getElementById("urlInput"),
    detectBtn: document.getElementById("detectBtn"),
    loadingSpinner: document.getElementById("loadingSpinner"),
    metaContainer: document.getElementById("metaContainer"),
    thumbImg: document.getElementById("thumbImg"),
    titleText: document.getElementById("titleText"),
    channelText: document.getElementById("channelText"),
    durationText: document.getElementById("durationText"),
    urlText: document.getElementById("urlText"),
    optionsCard: document.getElementById("optionsCard"),
    modeSeg: document.getElementById("modeSeg"),
    videoFields: document.getElementById("videoFields"),
    audioFields: document.getElementById("audioFields"),
    containerFields: document.getElementById("containerFields"),
    resolutionSelect: document.getElementById("resolutionSelect"),
    containerSelect: document.getElementById("containerSelect"),
    audioFormatSelect: document.getElementById("audioFormatSelect"),
    audioBitrateSelect: document.getElementById("audioBitrateSelect"),
    subtitlesCb: document.getElementById("subtitlesCb"),
    thumbnailCb: document.getElementById("thumbnailCb"),
    downloadDir: document.getElementById("downloadDir"),
    browseDirBtn: document.getElementById("browseDirBtn"),
    downloadBtn: document.getElementById("downloadBtn"),
    progressContainer: document.getElementById("progressContainer"),
    progressFill: document.getElementById("progressFill"),
    progressText: document.getElementById("progressText"),
    progressMeta: document.getElementById("progressMeta"),
    status: document.getElementById("status"),
  };

  // State
  let port = null;
  let pending = new Map(); // req_id => { resolve, reject, type }
  let currentUrl = "";
  let currentFormats = { video: [], audio: [], title: "" };
  let currentMode = "video";
  let activeDownloadId = null;

  // ---------- Native Messaging client ----------

  function connectNative() {
    if (port) return port;
    try {
      port = chrome.runtime.connectNative(HOST_NAME);
    } catch (e) {
      setStatus("Native Messaging host not available. Install the host first.", true);
      throw e;
    }
    port.onMessage.addListener(onNativeMessage);
    port.onDisconnect.addListener(() => {
      port = null;
    });
    return port;
  }

  function sendNativeMessage(msg) {
    if (!port) connectNative();
    return new Promise((resolve, reject) => {
      const reqId = crypto.randomUUID?.() || Math.random().toString(36).slice(2);
      msg.req_id = reqId;
      pending.set(reqId, { resolve, reject, type: msg.type });
      try {
        port.postMessage(msg);
      } catch (e) {
        pending.delete(reqId);
        reject(e);
      }
    });
  }

  function onNativeMessage(message) {
    const { req_id, type } = message;
    const waiter = req_id ? pending.get(req_id) : null;

    // Streaming / unsolicited messages (no req_id match)
    if (!waiter) {
      handleStreamMessage(message);
      return;
    }

    pending.delete(req_id);
    if (message.type.endsWith("_result") || message.type === "pong") {
      waiter.resolve(message);
    } else if (message.type === "error" || message.type.includes("failed")) {
      waiter.reject(new Error(message.message || message.error || "Request failed"));
    } else {
      waiter.resolve(message);
    }
  }

  function handleStreamMessage(message) {
    switch (message.type) {
      case "progress":
        renderProgress(message);
        break;
      case "download_complete":
        renderProgress({ type: "download_complete", ...message });
        setStatus("Download complete!", false);
        activeDownloadId = null;
        setDownloadButtonState(false);
        break;
      case "download_failed":
        setStatus("Download failed: " + (message.error || "unknown"), true);
        activeDownloadId = null;
        setDownloadButtonState(false);
        break;
      default:
        // ignore unknown stream messages
        break;
    }
  }

  // ---------- Helpers ----------

  function setStatus(text, isError) {
    const s = els.status;
    s.textContent = text;
    s.className = isError ? "err" : "ok";
  }

  function clearStatus() {
    els.status.textContent = "";
    els.status.className = "";
  }

  function setDownloadButtonState(enabled) {
    els.downloadBtn.disabled = !enabled;
  }

  function fmtDuration(seconds) {
    if (!seconds && seconds !== 0) return "";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  }

  function formatBytes(bytes) {
    if (!bytes) return "";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  }

  function renderProgress(message) {
    if (message.type === "progress") {
      const pct = message.percent || 0;
      els.progressContainer.style.display = "block";
      els.progressFill.style.width = pct + "%";
      els.progressText.textContent = pct.toFixed(1) + "%";
      const parts = [];
      if (message.speed_str) parts.push(message.speed_str);
      if (message.eta_str) parts.push("ETA " + message.eta_str);
      els.progressMeta.textContent = parts.join("  ·  ");
    }
  }

  function resetProgress() {
    els.progressContainer.style.display = "none";
    els.progressFill.style.width = "0%";
    els.progressText.textContent = "0%";
    els.progressMeta.textContent = "";
  }

  // ---------- URL detection from active tab ----------

  async function detectCurrentTab() {
    setStatus("Detecting current tab…", false);
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.url) {
        setStatus("Could not read current tab URL.", true);
        return;
      }
      currentUrl = tab.url;
      els.urlInput.value = currentUrl;
      els.detectBtn.textContent = "Using current tab";
      setStatus("URL detected.", false);
      loadMetadata(currentUrl);
    } catch (e) {
      setStatus("Tab access denied. Paste a URL manually.", true);
    }
  }

  // ---------- Metadata / formats ----------

  async function loadMetadata(url) {
    currentUrl = url;
    clearStatus();
    resetProgress();
    setLoading(true);
    els.metaContainer.style.display = "none";
    els.optionsCard.style.display = "none";
    setDownloadButtonState(false);

    try {
      const res = await sendNativeMessage({ type: "metadata", url });
      if (!res.ok) throw new Error(res.error || "Metadata failed");
      const d = res.data || {};
      els.titleText.textContent = d.title || "Unknown title";
      els.channelText.textContent = d.channel ? d.channel : "";
      els.durationText.textContent = d.duration ? fmtDuration(d.duration) : "";
      els.urlText.textContent = d.webpage_url || url;
      if (d.thumbnail) {
        els.thumbImg.src = d.thumbnail;
        els.thumbImg.onerror = () => { els.thumbImg.src = ""; };
      } else {
        els.thumbImg.src = "";
      }
      els.metaContainer.style.display = "flex";

      // Now fetch formats
      await loadFormats(url);
    } catch (e) {
      setStatus("Metadata error: " + e.message, true);
    } finally {
      setLoading(false);
    }
  }

  async function loadFormats(url) {
    try {
      const res = await sendNativeMessage({ type: "formats", url });
      if (!res.ok) throw new Error(res.error || "Formats failed");
      currentFormats = res.data || { video: [], audio: [], title: "" };
      renderOptions(currentFormats);
      els.optionsCard.style.display = "block";
      setDownloadButtonState(true);
    } catch (e) {
      setStatus("Format error: " + e.message, true);
      // Still show options with defaults
      renderOptions({ video: [], audio: [], title: "" });
      els.optionsCard.style.display = "block";
      setDownloadButtonState(true);
    }
  }

  function setLoading(loading) {
    els.loadingSpinner.style.display = loading ? "inline-flex" : "none";
    els.urlInput.disabled = loading;
    els.detectBtn.disabled = loading;
  }

  // ---------- Render options (resolution / format selectors) ----------

  function renderOptions(formats) {
    const resSel = els.resolutionSelect;
    resSel.innerHTML = "";

    // Determine available heights from video formats
    const heights = new Set();
    for (const f of (formats.video || [])) {
      if (f.height) heights.add(f.height);
    }
    const sortedHeights = [...heights].sort((a, b) => b - a);

    const targetResolutions = [2160, 1440, 1080, 720, 480, 360, 240, 144];
    const shown = new Set();
    for (const h of targetResolutions) {
      if (heights.has(h) && !shown.has(h)) {
        const opt = document.createElement("option");
        opt.value = String(h);
        opt.textContent = h + "p";
        resSel.appendChild(opt);
        shown.add(h);
      }
    }
    // Add any remaining detected heights not in target list
    for (const h of sortedHeights) {
      if (!shown.has(h)) {
        const opt = document.createElement("option");
        opt.value = String(h);
        opt.textContent = h + "p";
        resSel.appendChild(opt);
        shown.add(h);
      }
    }
    if (resSel.options.length === 0) {
      const opt = document.createElement("option");
      opt.value = "best";
      opt.textContent = "Best available";
      resSel.appendChild(opt);
    }

    // Audio mode toggles visibility
    updateModeVisibility();
  }

  function updateModeVisibility() {
    const isAudio = currentMode === "audio";
    els.videoFields.style.display = isAudio ? "none" : "block";
    els.containerFields.style.display = isAudio ? "none" : "block";
    els.audioFields.style.display = isAudio ? "block" : "none";
    // Update segment active styling
    for (const b of els.modeSeg.querySelectorAll(".seg")) {
      b.classList.toggle("active", b.dataset.mode === currentMode);
    }
  }

  // ---------- Mode switching ----------

  els.modeSeg.addEventListener("click", (e) => {
    const btn = e.target.closest(".seg");
    if (!btn) return;
    currentMode = btn.dataset.mode;
    updateModeVisibility();
  });

  // ---------- Download ----------

  async function startDownload() {
    const url = els.urlInput.value.trim() || currentUrl;
    if (!url) {
      setStatus("Please enter a video URL.", true);
      return;
    }

    const downloadDir = els.downloadDir.value.trim() || null;
    const mode = currentMode;
    const params = {
      type: "download",
      url,
      mode,
      download_dir: downloadDir || undefined,
      subtitles: els.subtitlesCb.checked,
      thumbnail: els.thumbnailCb.checked,
    };

    if (mode === "audio") {
      params.audio_format = els.audioFormatSelect.value;
      params.audio_quality = els.audioBitrateSelect.value;
    } else {
      params.format_id = els.resolutionSelect.value === "best" ? "best" : `bestvideo[height<=${els.resolutionSelect.value}]+bestaudio/best[height<=${els.resolutionSelect.value}]`;
      params.container = els.containerSelect.value;
      params.quality = els.resolutionSelect.value;
    }

    clearStatus();
    resetProgress();
    setDownloadButtonState(false);
    els.downloadBtn.textContent = "Downloading…";

    try {
      const res = await sendNativeMessage(params);
      if (!res.ok) throw new Error(res.error || "Download failed");
      activeDownloadId = res.download_id;
      setStatus("Download started.", false);
    } catch (e) {
      setStatus("Download error: " + e.message, true);
      setDownloadButtonState(true);
      els.downloadBtn.textContent = "Download";
    }
  }

  // ---------- Event wiring ----------

  els.detectBtn.addEventListener("click", detectCurrentTab);

  els.urlInput.addEventListener("input", () => {
    currentUrl = els.urlInput.value.trim();
    setDownloadButtonState(false);
    els.metaContainer.style.display = "none";
    els.optionsCard.style.display = "none";
    resetProgress();
    clearStatus();
  });

  els.urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (currentUrl) loadMetadata(currentUrl);
    }
  });

  els.downloadBtn.addEventListener("click", startDownload);

  // Directory selection via native host config + fallback to default
  els.browseDirBtn.addEventListener("click", async () => {
    try {
      const res = await sendNativeMessage({ type: "config", action: "get" });
      if (res.ok) {
        els.downloadDir.value = res.data.download_dir || "";
      }
    } catch (e) {
      // ignore
    }
    // Chrome extensions can't open a folder picker directly; user edits the path.
    els.downloadDir.readOnly = false;
    els.downloadDir.focus();
    els.downloadDir.select();
  });

  // Initialize: try to detect current tab on open
  detectCurrentTab();

})();
