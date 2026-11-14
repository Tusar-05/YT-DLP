// YT-DLP Downloader - Content Script
// Injected into YouTube pages to add download functionality

(function() {
  'use strict';

  // Check if already loaded (prevent duplicate injection)
  if (window.YT_DLP_LOADED) return;
  window.YT_DLP_LOADED = true;

  const YT_DLP = {
    version: '1.0.0',
    extensionId: null,
    
    // Extract YouTube video ID from various URL formats
    extractVideoID: function(url) {
      try {
        const pattern = new RegExp('(?:v=|shorts\\./)([a-zA-Z0-9_-]{11})');
        const match = url.match(pattern);
        return match ? match[1] : null;
      } catch (e) {
        return null;
      }
    },

    // Initialize on YouTube video pages
    init: function() {
      const videoContainer = document.querySelector('ytd-watch-metadata');
      if (!videoContainer) return;

      this.setupUI();
      this.detectVideoPage();
    },

    detectVideoPage: function() {
      // Check if we're on a video watch page
      const watchUrl = window.location.pathname.startsWith('/watch');
      
      if (!watchUrl) {
        console.log('YT-DLP: Not on a watch page, waiting...');
        setTimeout(() => this.detectVideoPage(), 2000);
        return;
      }

      // Extract video ID
      const videoID = window.location.search.includes('=') 
        ? new URLSearchParams(window.location.search).get('v')
        : null;

      if (!videoID) {
        console.log('YT-DLP: Could not find video ID');
        return;
      }

      console.log(`YT-DLP: Detected video ${videoID}`);
      
      // Send message to background script
      chrome.runtime.sendMessage({
        action: 'ready',
        pageUrl: window.location.href,
        videoID: videoID
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.warn('YT-DLP: Extension not loaded properly');
        }
      });

      this.injectDownloadUI(videoID);
    },

    // Inject download button and UI
    injectDownloadUI: function(videoID) {
      try {
        const videoElement = document.querySelector('video');
        if (!videoElement) return;

        // Create download container
        const downloadContainer = document.createElement('div');
        downloadContainer.id = 'yt-dlp-download-container';
        downloadContainer.style.cssText = `
          position: fixed;
          bottom: 120px;
          right: 20px;
          z-index: 99999;
          display: flex;
          flex-direction: column;
          gap: 8px;
        `;

        // Create download button
        const downloadBtn = document.createElement('button');
        downloadBtn.id = 'yt-dlp-download-btn';
        downloadBtn.innerHTML = `
          <div style="
            width: 56px; 
            height: 56px; 
            background: linear-gradient(135deg, #FF0000, #CC0000); 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            box-shadow: 0 4px 12px rgba(255,0,0,0.3);
          ">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
              <path d="M19 9h-4V4H9v5H5v7h4v4h5v-4h4v-7z"/>
            </svg>
          </div>
        `;
        downloadBtn.title = 'Download Video';
        
        // Click handler
        downloadBtn.addEventListener('click', () => {
          this.showPopup(videoID);
        });

        downloadContainer.appendChild(downloadBtn);

        // Add to video element
        videoElement.parentNode.appendChild(downloadContainer);

        console.log('YT-DLP: Download button injected successfully');

      } catch (e) {
        console.error('YT-DLP: Error injecting UI:', e);
      }
    },

    // Show extension popup
    showPopup: function(videoID) {
      chrome.runtime.sendMessage({
        action: 'openPopup',
        videoID: videoID,
        pageUrl: window.location.href
      });
    },

    // Setup UI styles and events
    setupUI: function() {
      const style = document.createElement('style');
      style.textContent = `
        #yt-dlp-download-container button {
          cursor: pointer;
          transition: transform 0.2s;
        }
        #yt-dlp-download-container button:hover {
          transform: scale(1.1);
        }
        #yt-dlp-download-container .yt-progress-bar {
          background: linear-gradient(90deg, #FF0000, #CC0000);
          height: 4px;
          border-radius: 2px;
          margin-top: 4px;
          overflow: hidden;
        }
      `;
      document.head.appendChild(style);

      // Listen for messages from background script
      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'status') {
          this.updateStatus(message.status);
        } else if (message.type === 'streams') {
          this.showStreamSelector(message.streams, message.videoInfo);
        }
      });
    },

    updateStatus: function(status) {
      // Can implement progress bar updates here
      console.log('YT-DLP Status:', status);
    },

    showStreamSelector: function(streams, videoInfo) {
      const container = document.querySelector('#yt-dlp-download-container');
      if (!container) return;

      const streamsDiv = document.createElement('div');
      streamsDiv.id = 'yt-dlp-streams';

      // Create format selector dropdown
      const select = document.createElement('select');
      select.id = 'yt-dlp-format-select';
      
      streams.forEach((stream, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = this.formatStreamName(stream);
        option.dataset.url = stream.url || '';
        
        if (stream.resolution === 'best' || stream.quality_label === '1080') {
          option.selected = true;
        }

        select.appendChild(option);
      });

      // Download action button
      const downloadAction = document.createElement('button');
      downloadAction.id = 'yt-dlp-download-action';
      downloadAction.textContent = 'Download Selected';
      
      downloadAction.style.cssText = `
        padding: 10px 20px;
        background: #FF0000;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-weight: bold;
      `;

      downloadAction.onclick = () => {
        const selectedIndex = select.selectedIndex;
        const selectedUrl = select.options[selectedIndex].dataset.url;
        
        // Trigger download via Chrome API
        chrome.downloads.download({
          url: selectedUrl,
          filename: videoInfo?.title || `video_${videoID}.mp4`,
          saveAs: true
        });

        // Cleanup
        container.innerHTML = '';
      };

      streamsDiv.appendChild(select);
      streamsDiv.appendChild(document.createElement('br'));
      streamsDiv.appendChild(downloadAction);

      container.replaceChild(streamsDiv, document.getElementById('yt-dlp-streams') || downloadAction);
    },

    formatStreamName: function(stream) {
      const resolution = stream.resolution || stream.quality_label || 'best';
      return `${resolution}p • ${stream.itag || 'unknown'} • ${this.formatFileSize(stream.file_size)} MB`;
    },

    formatFileSize: function(bytes) {
      if (!bytes) return 'Unknown';
      const mb = bytes / (1024 * 1024);
      return mb.toFixed(1);
    }
  };

  // Listen for YouTube page changes
  window.addEventListener('load', () => {
    setTimeout(() => YT_DLP.init(), 500);
  });

  // Expose globally for debugging
  window.YT_DLP = YT_DLP;

})();
