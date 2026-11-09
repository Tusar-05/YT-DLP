/**
 * options.js — Settings page controller.
 * Reads/writes user config and displays backend tool status via native messaging.
 */

(function () {
  const HOST_NAME = "com.yt-dlp-extension.host";

  const els = {
    downloadDir: document.getElementById("downloadDir"),
    saveDirBtn: document.getElementById("saveDirBtn"),
    audioFormatSelect: document.getElementById("audioFormatSelect"),
    audioBitrateSelect: document.getElementById("audioBitrateSelect"),
    videoContainerSelect: document.getElementById("videoContainerSelect"),
    defaultQualitySelect: document.getElementById("defaultQualitySelect"),
    checkHostBtn: document.getElementById("checkHostBtn"),
    hostStatus: document.getElementById("hostStatus"),
    saveStatus: document.getElementById("saveStatus"),
    hostPath: document.getElementById("hostPath"),
    ytdlpVersion: document.getElementById("ytdlpVersion"),
    ffmpegVersion: document.getElementById("ffmpegVersion"),
    pythonVersion: document.getElementById("pythonVersion"),
    updateInfo: document.getElementById("updateInfo"),
    updateCmd: document.getElementById("updateCmd"),
  };

  let port = null;
  const pending = new Map();

  function getPort() {
    if (port) return port;
    try {
      port = chrome.runtime.connectNative(HOST_NAME);
    } catch (e) {
      port = null;
      throw e;
    }

    port.onMessage.addListener((msg) => {
      const reqId = msg.req_id;
      if (reqId && pending.has(reqId)) {
        const waiter = pending.get(reqId);
        pending.delete(reqId);
        if (msg.type === "error" || msg.ok === false) {
          waiter.reject(new Error(msg.message || msg.error || "Operation failed"));
        } else {
          waiter.resolve(msg);
        }
      }
    });

    port.onDisconnect.addListener(() => {
      const err = chrome.runtime.lastError?.message || "Host disconnected";
      port = null;
      for (const waiter of pending.values()) {
        waiter.reject(new Error(err));
      }
      pending.clear();
    });

    return port;
  }

  function sendNative(payload) {
    let p;
    try {
      p = getPort();
    } catch (err) {
      return Promise.reject(err);
    }

    return new Promise((resolve, reject) => {
      const reqId = payload.req_id || crypto.randomUUID?.() || Math.random().toString(36).slice(2);
      payload.req_id = reqId;
      pending.set(reqId, { resolve, reject });
      try {
        p.postMessage(payload);
      } catch (e) {
        pending.delete(reqId);
        reject(e);
      }
    });
  }

  function setStatus(el, text, isError) {
    el.textContent = text;
    el.className = isError ? "status err" : "status ok";
  }

  async function loadConfig() {
    try {
      const res = await sendNative({ type: "config", action: "get" });
      if (res && res.data) {
        const d = res.data;
        if (d.download_dir) els.downloadDir.value = d.download_dir;
        if (d.default_audio_format) els.audioFormatSelect.value = d.default_audio_format;
        if (d.default_audio_quality) els.audioBitrateSelect.value = String(d.default_audio_quality);
        if (d.default_video_container) els.videoContainerSelect.value = d.default_video_container;
        if (d.default_video_quality) els.defaultQualitySelect.value = d.default_video_quality;
      }
    } catch (e) {
      setStatus(els.saveStatus, "Could not load config: " + e.message, true);
    }
  }

  async function loadVersionInfo() {
    try {
      const res = await sendNative({ type: "version" });
      if (res && res.data) {
        const d = res.data;
        els.hostPath.textContent = d.host_path || "configured";
        els.ytdlpVersion.textContent = d.ytdlp_version || "unknown";
        els.ffmpegVersion.textContent = d.ffmpeg_version ? d.ffmpeg_version.split(" ")[2] || d.ffmpeg_version : "unknown";
        els.pythonVersion.textContent = d.python_version || "unknown";
        if (d.update_command) {
          els.updateCmd.textContent = d.update_command;
          els.updateInfo.style.display = "block";
        }
      }
    } catch (e) {
      els.hostPath.textContent = "error connecting to host";
      els.ytdlpVersion.textContent = "unavailable";
      els.ffmpegVersion.textContent = "unavailable";
      els.pythonVersion.textContent = "unavailable";
    }
  }

  async function saveConfig() {
    const cfg = {
      download_dir: els.downloadDir.value.trim() || "~/Videos/Downloads",
      default_audio_format: els.audioFormatSelect.value,
      default_audio_quality: els.audioBitrateSelect.value,
      default_video_container: els.videoContainerSelect.value,
      default_video_quality: els.defaultQualitySelect.value,
    };
    try {
      const res = await sendNative({ type: "config", action: "set", config: cfg });
      if (res && res.ok) {
        setStatus(els.saveStatus, "Settings saved.", false);
        setTimeout(() => {
          if (els.saveStatus.textContent === "Settings saved.") {
            els.saveStatus.textContent = "";
          }
        }, 3000);
      } else {
        setStatus(els.saveStatus, "Save failed: " + (res?.error || "unknown"), true);
      }
    } catch (e) {
      setStatus(els.saveStatus, "Save error: " + e.message, true);
    }
  }

  async function checkHost() {
    els.hostStatus.textContent = "Pinging…";
    els.hostStatus.className = "hint";
    try {
      const res = await sendNative({ type: "ping" });
      if (res && res.ok) {
        setStatus(els.hostStatus, "Host connected successfully.", false);
        loadVersionInfo();
      } else {
        setStatus(els.hostStatus, "Host error: " + (res?.error || "unknown"), true);
      }
    } catch (e) {
      setStatus(els.hostStatus, "Host unreachable: " + e.message, true);
    }
  }

  els.saveDirBtn.addEventListener("click", saveConfig);
  els.checkHostBtn.addEventListener("click", checkHost);

  // Auto-save on change
  for (const el of [els.audioFormatSelect, els.audioBitrateSelect, els.videoContainerSelect, els.defaultQualitySelect]) {
    el.addEventListener("change", saveConfig);
  }
  els.downloadDir.addEventListener("blur", saveConfig);

  loadConfig();
  loadVersionInfo();
})();
