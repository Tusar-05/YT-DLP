/**
 * popup.js — yt-dlp Extension popup controller.
 *
 * Coordinates with background.js to detect media, fetch metadata and formats,
 * trigger downloads, stream real-time progress, and display download history.
 */

(function () {
  // DOM references
  const els = {
    settingsBtn: document.getElementById("settingsBtn"),
    activeDownloadCard: document.getElementById("activeDownloadCard"),
    activeTitle: document.getElementById("activeTitle"),
    cancelActiveBtn: document.getElementById("cancelActiveBtn"),
    activeProgressFill: document.getElementById("activeProgressFill"),
    activeProgressText: document.getElementById("activeProgressText"),
    activeProgressMeta: document.getElementById("activeProgressMeta"),

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
    resolutionSelect: document.getElementById("resolutionSelect"),
    codecSelect: document.getElementById("codecSelect"),
    containerSelect: document.getElementById("containerSelect"),
    audioFormatSelect: document.getElementById("audioFormatSelect"),
    audioBitrateSelect: document.getElementById("audioBitrateSelect"),
    playlistRow: document.getElementById("playlistRow"),
    playlistCb: document.getElementById("playlistCb"),
    playlistLabel: document.getElementById("playlistLabel"),
    subtitlesCb: document.getElementById("subtitlesCb"),
    thumbnailCb: document.getElementById("thumbnailCb"),
    downloadDir: document.getElementById("downloadDir"),
    browseDirBtn: document.getElementById("browseDirBtn"),

    downloadBtn: document.getElementById("downloadBtn"),
    status: document.getElementById("status"),
    historyList: document.getElementById("historyList"),
    clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  };

  // State
  let currentUrl = "";
  let currentMediaData = null;
  let currentMode = "video";
  let activeDownloadId = null;

  // ------------------------------------------------------------------ //
  // Communication via background service worker
  // ------------------------------------------------------------------ //
  function sendMsg(action, payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action, payload }, (response) => {
        if (chrome.runtime.lastError) {
          return reject(new Error(chrome.runtime.lastError.message));
        }
        if (!response) {
          return reject(new Error("No response from background worker"));
        }
        if (!response.ok) {
          return reject(new Error(response.error || "Operation failed"));
        }
        resolve(response);
      });
    });
  }

  // Listen to background worker broadcast events
  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || typeof msg !== "object") return;

    if (msg.type === "download_progress") {
      activeDownloadId = msg.download_id;
      renderActiveProgress(msg);
    } else if (msg.type === "download_completed") {
      setStatus("Download complete!", false);
      hideActiveDownload();
      refreshState();
    } else if (msg.type === "download_failed") {
      const err = msg.record?.error || "Download failed";
      setStatus(msg.record?.status === "cancelled" ? "Download cancelled." : "Download failed: " + err, true);
      hideActiveDownload();
      refreshState();
    }
  });

  // ------------------------------------------------------------------ //
  // UI Helpers
  // ------------------------------------------------------------------ //
  function setStatus(text, isError) {
    els.status.textContent = text;
    els.status.className = isError ? "status err" : "status ok";
  }

  function clearStatus() {
    els.status.textContent = "";
    els.status.className = "status";
  }

  function fmtDuration(seconds) {
    if (!seconds && seconds !== 0) return "";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  }

  function renderActiveProgress(data) {
    els.activeDownloadCard.style.display = "block";
    if (data.title) els.activeTitle.textContent = data.title;
    const pct = typeof data.percent === "number" ? data.percent : 0;
    els.activeProgressFill.style.width = pct + "%";
    els.activeProgressText.textContent = pct.toFixed(1) + "%";

    const parts = [];
    if (data.speed_str) parts.push(data.speed_str);
    if (data.eta_str) parts.push("ETA " + data.eta_str);
    els.activeProgressMeta.textContent = parts.join("  ·  ");
  }

  function hideActiveDownload() {
    els.activeDownloadCard.style.display = "none";
    activeDownloadId = null;
    els.downloadBtn.disabled = !currentMediaData;
    els.downloadBtn.textContent = "Download";
  }

  function renderHistory(list) {
    const container = els.historyList;
    container.innerHTML = "";

    if (!list || list.length === 0) {
      container.innerHTML = '<div class="empty-hint">No recent downloads</div>';
      return;
    }

    list.slice(0, 10).forEach((item) => {
      const row = document.createElement("div");
      row.className = "history-item";

      const title = document.createElement("div");
      title.className = "history-item-title";
      title.textContent = item.title || item.filepath || item.url || "Media";
      title.title = item.filepath || item.url || "";

      const badge = document.createElement("span");
      const st = item.status || "completed";
      badge.className = `history-badge ${st}`;
      badge.textContent = st;

      row.appendChild(title);
      row.appendChild(badge);
      container.appendChild(row);
    });
  }

  // ------------------------------------------------------------------ //
  // State Initialization
  // ------------------------------------------------------------------ //
  async function refreshState() {
    try {
      const res = await sendMsg("getDownloadsState");
      if (res.active && res.active.length > 0) {
        const top = res.active[0];
        activeDownloadId = top.download_id;
        renderActiveProgress(top);
      }
      renderHistory(res.history || []);
    } catch {
      // background not ready yet
    }
  }

  async function loadDefaultConfig() {
    try {
      const res = await sendMsg("nativeRequest", { type: "config", action: "get" });
      if (res.ok && res.data?.data) {
        const cfg = res.data.data;
        if (cfg.download_dir) {
          els.downloadDir.placeholder = cfg.download_dir;
          if (!els.downloadDir.value) els.downloadDir.value = cfg.download_dir;
        }
        if (cfg.default_video_container) els.containerSelect.value = cfg.default_video_container;
        if (cfg.default_audio_format) els.audioFormatSelect.value = cfg.default_audio_format;
        if (cfg.default_audio_quality) els.audioBitrateSelect.value = String(cfg.default_audio_quality);
      }
    } catch {
      // ignore
    }
  }

  // ------------------------------------------------------------------ //
  // URL Detection & Metadata
  // ------------------------------------------------------------------ //
  async function detectCurrentTab() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.url) return;
      const url = tab.url.trim();

      // Ignore browser internal schemes
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        return;
      }

      currentUrl = url;
      els.urlInput.value = currentUrl;
      loadMediaInfo(currentUrl);
    } catch (e) {
      console.warn("Could not query tab URL:", e);
    }
  }

  async function loadMediaInfo(url) {
    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      setStatus("Please enter a valid http(s) URL", true);
      return;
    }

    currentUrl = url;
    clearStatus();
    els.loadingSpinner.style.display = "flex";
    els.metaContainer.style.display = "none";
    els.optionsCard.style.display = "none";
    els.downloadBtn.disabled = true;

    try {
      // Single call to get both metadata and available formats!
      const res = await sendMsg("nativeRequest", { type: "media_info", url });
      const data = res.data?.data;
      if (!data) throw new Error("No media information returned");

      currentMediaData = data;

      // Render metadata preview
      els.titleText.textContent = data.title || "Untitled";
      els.channelText.textContent = data.channel ? `Channel: ${data.channel}` : "";
      els.durationText.textContent = data.duration ? `Duration: ${fmtDuration(data.duration)}` : "";
      els.urlText.textContent = data.webpage_url || url;

      if (data.thumbnail) {
        els.thumbImg.src = data.thumbnail;
        els.thumbImg.style.display = "block";
        els.thumbImg.onerror = () => { els.thumbImg.style.display = "none"; };
      } else {
        els.thumbImg.style.display = "none";
      }
      els.metaContainer.style.display = "flex";

      // Playlist indicator
      if (data.is_playlist) {
        els.playlistRow.style.display = "inline-flex";
        els.playlistLabel.textContent = data.playlist_count
          ? `Download entire playlist (${data.playlist_count} videos)`
          : "Download entire playlist";
        els.playlistCb.checked = true;
      } else {
        els.playlistRow.style.display = "none";
        els.playlistCb.checked = false;
      }

      // Populate resolutions
      renderResolutionOptions(data.formats?.video || []);

      // Populate codecs
      const codecs = data.formats?.codecs || [];
      updateCodecOptions(codecs);

      els.optionsCard.style.display = "block";
      els.downloadBtn.disabled = false;
    } catch (err) {
      setStatus("Failed to load info: " + err.message, true);
    } finally {
      els.loadingSpinner.style.display = "none";
    }
  }

  function renderResolutionOptions(videoFormats) {
    const sel = els.resolutionSelect;
    sel.innerHTML = "";

    const heights = new Set();
    for (const f of videoFormats) {
      if (f.height) heights.add(f.height);
    }

    const priority = [2160, 1440, 1080, 720, 480, 360, 240, 144];
    const added = new Set();

    // Default "Best"
    const bestOpt = document.createElement("option");
    bestOpt.value = "best";
    bestOpt.textContent = "Best Available Quality";
    sel.appendChild(bestOpt);

    for (const h of priority) {
      if (heights.has(h)) {
        const opt = document.createElement("option");
        opt.value = String(h);
        opt.textContent = `${h}p` + (h >= 2160 ? " (4K)" : h >= 1080 ? " (HD)" : "");
        sel.appendChild(opt);
        added.add(h);
      }
    }

    // Add any remaining heights
    const remaining = [...heights].filter(h => !added.has(h)).sort((a, b) => b - a);
    for (const h of remaining) {
      const opt = document.createElement("option");
      opt.value = String(h);
      opt.textContent = `${h}p`;
      sel.appendChild(opt);
    }
  }

  function updateCodecOptions(availableCodecs) {
    const sel = els.codecSelect;
    for (const opt of sel.options) {
      if (!opt.value) continue;
      const isAvailable = availableCodecs.includes(opt.value);
      opt.textContent = opt.value + (isAvailable ? " (Available)" : "");
    }
  }

  // ------------------------------------------------------------------ //
  // Mode Switching
  // ------------------------------------------------------------------ //
  els.modeSeg.addEventListener("click", (e) => {
    const btn = e.target.closest(".seg");
    if (!btn) return;
    currentMode = btn.dataset.mode;
    const isAudio = currentMode === "audio";

    els.videoFields.style.display = isAudio ? "none" : "block";
    els.audioFields.style.display = isAudio ? "block" : "none";

    for (const b of els.modeSeg.querySelectorAll(".seg")) {
      b.classList.toggle("active", b.dataset.mode === currentMode);
    }
  });

  // ------------------------------------------------------------------ //
  // Download Action
  // ------------------------------------------------------------------ //
  async function startDownload() {
    const url = els.urlInput.value.trim() || currentUrl;
    if (!url) {
      setStatus("Please enter a video URL.", true);
      return;
    }

    const mode = currentMode;
    const downloadDir = els.downloadDir.value.trim() || undefined;

    const params = {
      type: "download",
      url,
      title: currentMediaData?.title || "Media download",
      mode,
      download_dir: downloadDir,
      subtitles: els.subtitlesCb.checked,
      thumbnail: els.thumbnailCb.checked,
      playlist: els.playlistCb.checked,
    };

    if (mode === "audio") {
      params.audio_format = els.audioFormatSelect.value;
      params.audio_quality = els.audioBitrateSelect.value;
    } else {
      params.quality = els.resolutionSelect.value;
      params.codec = els.codecSelect.value || undefined;
      params.container = els.containerSelect.value;
    }

    clearStatus();
    els.downloadBtn.disabled = true;
    els.downloadBtn.textContent = "Starting…";

    try {
      const res = await sendMsg("startDownload", params);
      activeDownloadId = res.download_id;
      renderActiveProgress({
        title: params.title,
        percent: 0,
        speed_str: "Connecting...",
        eta_str: "",
      });
      setStatus("Download started.", false);
    } catch (err) {
      setStatus("Start error: " + err.message, true);
      els.downloadBtn.disabled = false;
      els.downloadBtn.textContent = "Download";
    }
  }

  async function cancelActiveDownload() {
    if (!activeDownloadId) return;
    els.cancelActiveBtn.disabled = true;
    els.cancelActiveBtn.textContent = "Cancelling…";

    try {
      await sendMsg("cancelDownload", { download_id: activeDownloadId });
      setStatus("Download cancelled.", false);
      hideActiveDownload();
      refreshState();
    } catch (err) {
      setStatus("Cancel error: " + err.message, true);
    } finally {
      els.cancelActiveBtn.disabled = false;
      els.cancelActiveBtn.textContent = "Cancel";
    }
  }

  // ------------------------------------------------------------------ //
  // Event Bindings
  // ------------------------------------------------------------------ //
  els.detectBtn.addEventListener("click", detectCurrentTab);

  els.urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      loadMediaInfo(els.urlInput.value.trim());
    }
  });

  els.downloadBtn.addEventListener("click", startDownload);
  els.cancelActiveBtn.addEventListener("click", cancelActiveDownload);

  els.settingsBtn.addEventListener("click", () => {
    sendMsg("openOptions");
  });

  els.clearHistoryBtn.addEventListener("click", async () => {
    await sendMsg("clearHistory");
    renderHistory([]);
  });

  els.browseDirBtn.addEventListener("click", () => {
    loadDefaultConfig();
    els.downloadDir.focus();
    els.downloadDir.select();
  });

  // ------------------------------------------------------------------ //
  // Initialization
  // ------------------------------------------------------------------ //
  refreshState();
  loadDefaultConfig();
  detectCurrentTab();
})();
