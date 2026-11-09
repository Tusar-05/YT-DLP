/**
 * background.js — Service worker for the yt-dlp Extension.
 *
 * Registers the Native Messaging host name and handles extension lifecycle.
 * The popup connects to the host directly via chrome.runtime.connectNative;
 * this worker keeps the host registration alive and can surface download
 * completion notifications if desired.
 */

const HOST_NAME = "com.yt-dlp-extension.host";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[yt-dlp Extension] installed; native host:", HOST_NAME);
});

// Keep the Native Messaging channel warm: respond to a lightweight ping so
// the popup can verify the host is available before requesting metadata.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "pingHost") {
    try {
      const port = chrome.runtime.connectNative(HOST_NAME);
      port.postMessage({ type: "ping" });
      port.onMessage.addListener((reply) => {
        port.disconnect();
        sendResponse({ ok: true, pong: reply });
      });
      port.onDisconnect.addListener(() => {
        sendResponse({ ok: false, error: "host disconnected" });
      });
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }
    return true; // async response
  }
  return false;
});
