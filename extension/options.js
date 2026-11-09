/**
 * options.js — Settings page controller.
 * Reads/writes user config via the Native Messaging host and persists defaults.
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
  };

  let port = null;

  function connectNative() {
    if (port) return port;
    port = chrome.runtime.connectNative(HOST_NAME);
    port.onMessage.addListener((msg) => {
      // streaming/unsolicited messages not used on options page
    });
    return port;
  }

  function send(msg) {
    if (!port) connectNative();
    return new Promise((resolve, reject) => {
      const reqId = crypto.randomUUID?.() || Math.random().toString(36).slice(2);
      msg.req_id = reqId;
      const once = (reply) => {
        if (reply && reply.req_id === reqId) {
          port.onMessage.removeListener(once);
          if (reply.type === "error" || reply.type.includes("failed")) reject(new Error(reply.message || reply.error || "failed"));
          else resolve(reply);
        }
      };
      port.onMessage.addListener(once);
      try { port.postMessage(msg); } catch (e) { port.onMessage.removeListener(once); reject(e); }
    });
  }

  function setStatus(el, text, isError) {
    el.textContent = text;
    el.className = isError ? "status err" : "status ok";
  }

  async function loadConfig() {
    try {
      const res = await send({ type: "config", action: "get" });
      if (res.ok && res.data) {
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

  async function saveConfig() {
    const cfg = {
      download_dir: els.downloadDir.value.trim() || "~/Videos/Downloads",
      default_audio_format: els.audioFormatSelect.value,
      default_audio_quality: els.audioBitrateSelect.value,
      default_video_container: els.videoContainerSelect.value,
      default_video_quality: els.defaultQualitySelect.value,
    };
    try {
      const res = await send({ type: "config", action: "set", config: cfg });
      if (res.ok) {
        setStatus(els.saveStatus, "Settings saved.", false);
      } else {
        setStatus(els.saveStatus, "Save failed: " + (res.error || "unknown"), true);
      }
    } catch (e) {
      setStatus(els.saveStatus, "Save error: " + e.message, true);
    }
  }

  async function checkHost() {
    try {
      const res = await send({ type: "ping" });
      setStatus(els.hostStatus, "Host reachable (pong: " + (res.ok ? "ok" : "no") + ").", false);
    } catch (e) {
      setStatus(els.hostStatus, "Host not reachable: " + e.message, true);
    }
  }

  els.saveDirBtn.addEventListener("click", saveConfig);
  els.checkHostBtn.addEventListener("click", checkHost);

  // Auto-save on any change
  for (const el of [els.audioFormatSelect, els.audioBitrateSelect, els.videoContainerSelect, els.defaultQualitySelect]) {
    el.addEventListener("change", saveConfig);
  }
  els.downloadDir.addEventListener("blur", saveConfig);

  loadConfig();

})();
