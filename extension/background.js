/**
 * background.js — Service worker for the yt-dlp Extension.
 *
 * Manages the Native Messaging connection to `com.yt_dlp_extension.host`,
 * routes requests from popup and options pages, persists download history,
 * and maintains download lifecycle so downloads survive popup closure.
 */

const HOST_NAME = "com.yt_dlp_extension.host";

let nativePort = null;
const pendingRequests = new Map(); // req_id -> { resolve, reject, timer }

// In-memory download state
const activeDownloads = new Map(); // download_id -> DownloadRecord
let downloadHistory = []; // list of completed/failed records

// Load saved history on startup
chrome.storage.local.get(["downloadHistory"], (res) => {
  if (Array.isArray(res.downloadHistory)) {
    downloadHistory = res.downloadHistory.slice(0, 50);
  }
});

function saveHistory() {
  chrome.storage.local.set({ downloadHistory: downloadHistory.slice(0, 50) });
}

function addHistoryRecord(record) {
  if (!record || !record.download_id) return;
  downloadHistory = [record, ...downloadHistory.filter((h) => h.download_id !== record.download_id)].slice(0, 50);
  saveHistory();
}

function getNativePort() {
  if (nativePort) return nativePort;

  try {
    nativePort = chrome.runtime.connectNative(HOST_NAME);
  } catch (err) {
    console.error("[background] Failed to connect to native host:", err);
    nativePort = null;
    return null;
  }

  nativePort.onMessage.addListener(onNativeMessage);
  nativePort.onDisconnect.addListener(() => {
    const lastErr = chrome.runtime.lastError?.message || "Host disconnected";
    console.warn("[background] Native host disconnected:", lastErr);
    nativePort = null;

    // Reject all pending requests
    for (const [reqId, waiter] of pendingRequests.entries()) {
      clearTimeout(waiter.timer);
      waiter.reject(new Error(lastErr));
    }
    pendingRequests.clear();
  });

  return nativePort;
}

function sendToNative(msg) {
  const port = getNativePort();
  if (!port) {
    return Promise.reject(new Error("Native Messaging host not available. Run install.sh."));
  }

  return new Promise((resolve, reject) => {
    const reqId = msg.req_id || crypto.randomUUID?.() || Math.random().toString(36).slice(2);
    msg.req_id = reqId;

    const timer = setTimeout(() => {
      pendingRequests.delete(reqId);
      reject(new Error("Native host request timed out"));
    }, 125000); // 125s timeout (yt-dlp metadata extraction can take up to 120s)

    pendingRequests.set(reqId, { resolve, reject, timer });

    try {
      port.postMessage(msg);
    } catch (err) {
      clearTimeout(timer);
      pendingRequests.delete(reqId);
      reject(err);
    }
  });
}

function onNativeMessage(msg) {
  if (!msg || typeof msg !== "object") return;

  const reqId = msg.req_id;
  if (reqId && pendingRequests.has(reqId)) {
    const waiter = pendingRequests.get(reqId);
    clearTimeout(waiter.timer);
    pendingRequests.delete(reqId);

    if (msg.type === "error" || msg.ok === false) {
      waiter.reject(new Error(msg.message || msg.error || "Operation failed"));
    } else {
      waiter.resolve(msg);
    }
    return;
  }

  // Handle streaming / unsolicited messages
  switch (msg.type) {
    case "progress": {
      const id = msg.download_id;
      if (id && activeDownloads.has(id)) {
        const item = activeDownloads.get(id);
        item.percent = msg.percent || 0;
        item.speed_str = msg.speed_str || "";
        item.eta_str = msg.eta_str || "";
        item.status = "running";
      }
      broadcastToExtension({ type: "download_progress", ...msg });
      break;
    }

    case "download_complete": {
      const id = msg.download_id;
      let record = activeDownloads.get(id) || { download_id: id };
      record.status = "completed";
      record.percent = 100;
      record.filepath = msg.filepath || record.filepath;
      record.title = msg.title || record.title || "Download completed";
      record.completedAt = Date.now();

      activeDownloads.delete(id);
      addHistoryRecord(record);

      // Show indicator on extension badge
      chrome.action.setBadgeText({ text: "✓" });
      chrome.action.setBadgeBackgroundColor({ color: "#4ade80" });
      setTimeout(() => chrome.action.setBadgeText({ text: "" }), 6000);

      broadcastToExtension({ type: "download_completed", record });
      break;
    }

    case "download_failed": {
      const id = msg.download_id;
      let record = activeDownloads.get(id) || { download_id: id };
      record.status = msg.status || "failed";
      record.error = msg.error || "Download failed";
      record.failedAt = Date.now();

      activeDownloads.delete(id);

      // If already recorded (e.g. from cancelDownload), update existing record rather than duplicate
      const existing = downloadHistory.find((h) => h.download_id === id);
      if (existing && record.status === "cancelled") {
        existing.error = msg.error || existing.error || "cancelled";
        saveHistory();
      } else {
        addHistoryRecord(record);
      }

      if (record.status !== "cancelled") {
        chrome.action.setBadgeText({ text: "!" });
        chrome.action.setBadgeBackgroundColor({ color: "#cf6679" });
        setTimeout(() => chrome.action.setBadgeText({ text: "" }), 6000);
      }

      broadcastToExtension({ type: "download_failed", record });
      break;
    }

    default:
      broadcastToExtension(msg);
      break;
  }
}

function broadcastToExtension(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {
    // Popup or options page may be closed; ignore delivery failure.
  });
}

// ---------------------------------------------------------------------- //
// Message listener from popup & options
// ---------------------------------------------------------------------- //
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { action, payload } = message || {};

  if (action === "nativeRequest") {
    // Forward directly to native host
    sendToNative(payload)
      .then((res) => sendResponse({ ok: true, data: res }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // async
  }

  if (action === "startDownload") {
    sendToNative(payload)
      .then((res) => {
        const id = res.download_id;
        if (id) {
          activeDownloads.set(id, {
            download_id: id,
            url: payload.url,
            title: payload.title || "Starting download...",
            mode: payload.mode || "video",
            percent: 0,
            speed_str: "",
            eta_str: "",
            status: "starting",
            startedAt: Date.now(),
          });
        }
        sendResponse({ ok: true, download_id: id, data: res });
      })
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  if (action === "cancelDownload") {
    const id = payload?.download_id;
    sendToNative({ type: "cancel", download_id: id })
      .then((res) => {
        if (id && activeDownloads.has(id)) {
          const rec = activeDownloads.get(id);
          rec.status = "cancelled";
          activeDownloads.delete(id);
          addHistoryRecord(rec);
        }
        sendResponse({ ok: true, data: res });
      })
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }

  if (action === "getDownloadsState") {
    sendResponse({
      ok: true,
      active: Array.from(activeDownloads.values()),
      history: downloadHistory.slice(0, 20),
    });
    return false;
  }

  if (action === "clearHistory") {
    downloadHistory = [];
    saveHistory();
    sendResponse({ ok: true });
    return false;
  }

  if (action === "openOptions") {
    chrome.runtime.openOptionsPage();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});
