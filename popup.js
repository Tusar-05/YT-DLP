// YT-DLP Downloader - Popup Script (Complete Version)
// Handles popup UI, API communication, and download actions

(function() {
  'use strict';

  const Popup = {
    init: function() {
      this.showLoading();
      this.bindEvents();
      
      // Listen for messages from content script
      chrome.runtime.onMessage.addListener((message) => {
        if (message.type === 'status') {
          this.handleStatusUpdate(message);
        } else if (message.type === 'streams') {
          this.handleStreamsReady(message.streams, message.videoInfo);
        }
      });
    },

    showLoading: function() {
      document.getElementById('loading-container').classList.remove('hidden');
    },

    showError: function(error) {
      document.getElementById('error-container').classList.remove('hidden');
      console.error('YT-DLP Popup Error:', error);
    }
  };

  // Bind all button and input events
  Popup.bindEvents = function() {
    const downloadBtn = document.getElementById('download-btn');
    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => this.handleDownload());
    }

    // Cancel download
    const cancelBtn = document.getElementById('cancel-download');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => this.cancelDownload());
    }

    // Audio only checkbox
    const audioOnlyCheckbox = document.getElementById('audio-only-checkbox');
    if (audioOnlyCheckbox) {
      audioOnlyCheckbox.addEventListener('change', (e) => {
        this.toggleAudioOnly(e.target.checked);
      });
    }

    // Include subtitles checkbox
    const subtitlesCheckbox = document.getElementById('include-subtitles');
    if (subtitlesCheckbox) {
      subtitlesCheckbox.addEventListener('change', (e) => {
        console.log('YT-DLP: Subtitles selected:', e.target.checked);
      });
    }
  };

  Popup.handleStatusUpdate = function(message) {
    const loadingContainer = document.getElementById('loading-container');
    const mainContainer = document.getElementById('main-container');
    
    if (message.status === 'ready') {
      this.showReady(message.title);
    } else if (message.status === 'error') {
      this.showError(message.error || message.message);
    }
  };

  Popup.handleStreamsReady = function(streams, videoInfo) {
    // Switch from loading to ready view
    document.getElementById('loading-container').classList.add('hidden');
    document.getElementById('main-container').classList.remove('hidden');
    
    // Populate video info
    this.populateVideoInfo(videoInfo);
    
    // Add format options
    this.populateFormatOptions(streams);
    
    // Add subtitle list if available
    if (videoInfo.subtitles) {
      const subtitleSection = document.getElementById('subtitle-section');
      if (subtitleSection) {
        subtitleSection.classList.remove('hidden');
      }
    }

    console.log('YT-DLP: Streams ready', { count: streams.length });
  };

  Popup.populateVideoInfo = function(videoInfo) {
    const titleEl = document.getElementById('video-title');
    const uploaderEl = document.getElementById('uploader-name');
    const durationEl = document.getElementById('video-duration');
    const viewsEl = document.getElementById('view-count');
    
    if (titleEl && videoInfo.title) {
      titleEl.textContent = videoInfo.title;
    }

    if (uploaderEl && videoInfo.uploader) {
      uploaderEl.textContent = videoInfo.uploader;
    } else if (uploaderEl) {
      uploaderEl.textContent = 'Unknown Channel';
    }

    if (durationEl && videoInfo.duration_seconds) {
      const durationMins = Math.floor(videoInfo.duration_seconds / 60);
      const durationSecs = videoInfo.duration_seconds % 60;
      durationEl.textContent = `${durationMins}:${String(durationSecs).padStart(2, '0')}`;
    }

    if (viewsEl && videoInfo.view_count) {
      viewsEl.textContent = `• ${this.formatNumber(videoInfo.view_count)}`;
    } else if (viewsEl) {
      viewsEl.textContent = '• Views available';
    }
  };

  Popup.populateFormatOptions = function(streams) {
    const formatOptions = document.getElementById('format-options');
    if (!formatOptions || streams.length === 0) return;

    let highestQuality = 0;

    streams.forEach((stream, index) => {
      const qualityNum = parseInt(stream.resolution.replace('p', '')) || 0;
      const fps = stream.fps || 0;
      if (qualityNum > highestQuality) {
        highestQuality = qualityNum;
      }

      const btn = document.createElement('div');
      btn.className = 'format-option-small';
      
      let label = '';
      if (stream.resolution) {
        label = `${qualityNum}p @ ${fps}fps`;
      } else if (stream.quality_label) {
        label = stream.quality_label;
      }

      btn.dataset.label = label || 'Best Quality';
      btn.dataset.url = stream.url || '';
      btn.dataset.itag = stream.itag || '';
      btn.dataset.codec = `${stream.vcodec || 'n/a'}/${stream.acodec || 'n/a'}`;
      
      btn.textContent = label;

      btn.addEventListener('click', () => {
        this.selectFormat(btn, formatOptions);
      });

      formatOptions.appendChild(btn);
    });

    const allBtns = formatOptions.querySelectorAll('.format-option-small');
    if (allBtns.length > 0) {
      allBtns[0].click();
    }
  };

  Popup.selectFormat = function(selectedBtn, container) {
    const buttons = container.querySelectorAll('.format-option-small');
    buttons.forEach(btn => btn.classList.remove('selected'));
    
    selectedBtn.classList.add('selected');
  };

  Popup.toggleAudioOnly = function(enabled) {
    const audioSection = document.getElementById('audio-only-section');
    if (audioSection) {
      audioSection.classList.toggle('hidden', !enabled);
    }
  };

})();

// Download handler (attached to window for content script access)
window.popupScript = {
  handleDownload: async function() {
    try {
      const selectedBtn = document.querySelector('.format-option-small.selected');
      if (!selectedBtn) throw new Error('No format selected');

      let url = selectedBtn.dataset.url;
      
      if (!url) {
        throw new Error('Invalid stream URL');
      }

      console.log(`YT-DLP: Starting download of ${selectedBtn.dataset.label}`);

      this.showProgressUI();

      const fileName = `yt-dlp_${selectedBtn.dataset.label || 'video'}.mp4`;
      
      chrome.downloads.download({
        url: url,
        filename: fileName,
        saveAs: true
      });

    } catch (error) {
      console.error('YT-DLP Download Error:', error);
      alert(`Download failed: ${error.message}`);
    }
  },

  showProgressUI: function() {
    const formatSection = document.querySelector('.format-section');
    if (formatSection) formatSection.style.opacity = '0.3';
    
    this.progressInterval = setInterval(() => this.updateDownloadProgress(), 1000);
  },

  updateDownloadProgress: async function() {
    // Note: Chrome API doesn't expose real-time progress for external URLs
    try {
      // Polling approach - would need backend integration for real progress
      const response = await fetch(chrome.runtime.getURL('/icons/icon128.png'));
      this.hideProgressUI();
    } catch (error) {
      clearInterval(this.progressInterval);
      this.hideProgressUI();
    }
  },

  hideProgressUI: function() {
    if (!this.progressInterval) return;
    clearInterval(this.progressInterval);
    
    const formatSection = document.querySelector('.format-section');
    if (formatSection) formatSection.style.opacity = '1';
  },

  cancelDownload: async function() {
    try {
      const pending = await chrome.downloads.query({ state: ['in_progress'] });
      if (pending.length > 0) {
        const itemId = pending[0].id;
        await chrome.downloads.erase({ id: itemId });
        alert('Download cancelled');
      }
    } catch (error) {
      console.error('YT-DLP: Cancel failed:', error);
      alert('Could not cancel download');
    }
  },

  formatNumber: function(num) {
    if (!num) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
};
