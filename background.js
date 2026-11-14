// YT-DLP Downloader - Background Service Worker
// Handles API calls, download management, and popup communication

// Extension identifier (generated on install)
let extensionId = null;

// Current download state
const downloadState = {
  downloading: false,
  progress: 0,
  videoID: null,
  streams: [],
  subtitleUrls: {}
};

// API configuration
const API_CONFIG = {
  externalApi: 'https://yt-dl-api.com', // External API service (no backend needed)
  localBackend: 'http://localhost:8000', // Local Python backend (optional)
  youtubeApiBase: 'https://www.youtube.com/youtubei/v1/player'
};

// Handle extension installation/activation
chrome.runtime.onInstalled.addListener((details) => {
  console.log('YT-DLP Extension installed or updated');
  
  if (details.reason === 'install') {
    // Generate a key for Chrome Web Store compatibility
    const crypto = window.crypto;
    const keyMaterial = crypto.getRandomValues(new Uint8Array(32));
    const keyBytes = new Uint8Array(keyMaterial);
    
    extensionId = btoa(String.fromCharCode(...keyBytes)).replace(/[^a-zA-Z0-9=]/g, '');
    chrome.storage.local.set({ extensionId });
    
    console.log('YT-DLP: Extension ID generated (placeholder for now)');
  }
});

// Listen for messages from content scripts and popups
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  
  // Handle popup open requests from YouTube page
  if (request.action === 'openPopup') {
    return handleOpenPopup(request.videoID, request.pageUrl).then(response => sendResponse(response));
  }

  // Get available streams for selected video
  if (request.action === 'getStreams') {
    return getVideoStreams(request.url || request.pageUrl)
      .then(data => {
        downloadState.streams = data.formats;
        downloadState.videoInfo = data.info;
        sendResponse({ 
          streams: data.formats, 
          videoInfo: data.info,
          apiUsed: request.source === 'local' ? 'local-backend' : 'external-api'
        });
      })
      .catch(error => {
        console.error('YT-DLP: Error getting streams:', error);
        sendResponse({ error: error.message, streams: [], videoInfo: null });
      });
  }

  // Get subtitle URLs for a video
  if (request.action === 'getSubtitles') {
    return getSubtitles(request.videoID, request.url).then(subs => 
      sendResponse({ subtitles: subs })
    );
  }

  // Cancel current download
  if (request.action === 'cancelDownload') {
    chrome.downloads.erase({ id: downloadState.downloading });
    downloadState.downloading = false;
    downloadState.progress = 0;
    sendResponse({ success: true, message: 'Download cancelled' });
  }

  // Get current download status
  if (request.action === 'getStatus') {
    chrome.downloads.getDownloadPaths([downloadState.downloading], pathData => {
      chrome.downloads.query({ id: downloadState.downloading }, [item => 
        sendResponse({ item: item, path: pathData[0] })
      ]);
    });
  }

  return true; // Keep channel open for async response
});

// Initialize on extension start
chrome.runtime.onStartup.addListener(() => {
  console.log('YT-DLP: Extension started');
});

// Handle updates
chrome.runtime.onUpdateAvailable.addListener(() => {
  console.log('YT-DLP: Update available');
});

// Main functions
async function handleOpenPopup(videoID, pageUrl) {
  try {
    // Check if YouTube is loaded
    const ytFrame = document.getElementById('movie_player') || 
                   document.querySelector('ytd-player video');
    
    if (!ytFrame) {
      console.log('YT-DLP: Waiting for YouTube to load...');
      return { status: 'loading' };
    }

    // Extract video info from page URL or fetch it
    const videoInfo = await extractVideoInfo(pageUrl);
    
    sendPageMessage({
      type: 'status',
      message: `Found video: ${videoInfo?.title || videoID}`,
      videoID: videoID
    });

    return { 
      status: 'ready', 
      videoID: videoID,
      title: videoInfo?.title || 'Video' 
    };

  } catch (error) {
    console.error('YT-DLP: Error opening popup:', error);
    sendPageMessage({
      type: 'error',
      message: 'Could not detect YouTube video page'
    });
    return { status: 'error', error: error.message };
  }
}

async function getVideoStreams(url) {
  try {
    // Try local backend first if configured
    let streams = null;
    
    if (API_CONFIG.localBackend && window.location.hostname === 'localhost') {
      try {
        const response = await fetch(`${API_CONFIG.localBackend}/api/extract`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
        
        if (response.ok) {
          const data = await response.json();
          streams = data.streams;
          console.log('YT-DLP: Using local backend');
        }
      } catch (e) {
        console.log('YT-DLP: Local backend unavailable, using external API');
      }
    }

    // Fallback to external API service
    if (!streams) {
      const apiUrl = API_CONFIG.externalApi;
      const encodedUrl = encodeURIComponent(url);
      
      try {
        const response = await fetch(`${apiUrl}?url=${encodedUrl}`);
        const data = await response.json();
        streams = data.formats || [];
        
        // Map yt-dlp format info to our structure
        const formattedStreams = streams.map((s, i) => ({
          url: s.url,
          resolution: s.resolution || s.quality_label,
          itag: s.itag,
          quality_label: s.quality_label,
          fps: s.fps,
          vcodec: s.vcodec,
          acodec: s.acodec,
          size_bytes: s.size_bytes
        }));

        return {
          formats: formattedStreams,
          info: {
            title: data.title || url,
            thumbnail: data.thumbnail_url || null,
            uploader: data.author || 'Unknown'
          }
        };
      } catch (apiError) {
        console.error('YT-DLP: External API failed:', apiError);
        
        // Try YouTube's public player API as fallback
        return await getFromYouTubePlayerAPI(url);
      }
    }

  } catch (error) {
    console.error('YT-DLP: Stream fetch failed:', error);
    throw new Error('Could not fetch video streams');
  }

  return { formats: [], info: {} };
}

async function getSubtitles(videoID, url) {
  try {
    const apiUrl = API_CONFIG.externalApi;
    const encodedUrl = encodeURIComponent(url);
    
    const response = await fetch(`${apiUrl}?url=${encodedUrl}&subtitles=all`);
    const data = await response.json();
    
    // Extract subtitle URLs from response
    const subs = Object.entries(data.subtitles || {}).map(([lang, urls]) => {
      return { lang, urls };
    });

  } catch (error) {
    console.error('YT-DLP: Subtitle fetch failed:', error);
  }
}

async function extractVideoInfo(url) {
  // Extract from URL parameters or DOM
  try {
    const videoId = new URL(url).searchParams.get('v');
    if (videoId) return { title: 'YouTube Video', videoID: videoId };
    
    // Try to get from page DOM
    const ytVideoContainer = document.querySelector('.ytd-video-secondary-info-renderer');
    if (ytVideoContainer) {
      const titleEl = ytVideoContainer.querySelector('[itemprop="name"]');
      return {
        title: titleEl?.textContent || 'YouTube Video',
        videoID: videoId || null
      };
    }
  } catch (e) {}
  
  return { title: 'Unknown', videoID: null };
}

function sendPageMessage(message) {
  if (window.postMessage) {
    window.parent.postMessage(
      JSON.stringify({ 
        type: 'YT-DLP', 
        data: message, 
        source: chrome.runtime.id 
      }), 
      '*'
    );
  }
}

// Handle page visibility changes - pause background tasks when tab is hidden
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    console.log('YT-DLP: Tab hidden, pausing');
  } else {
    console.log('YT-DLP: Tab visible, resuming');
  }
});

// Log available APIs and features
console.log('YT-DLP Downloader v1.0.0');
console.log(`API Config: ${API_CONFIG.localBackend || 'External API: ' + API_CONFIG.externalApi}`);
