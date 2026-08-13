// components/camera-view/camera-view.js - Camera view component
Component({
  properties: {
    serverUrl: {
      type: String,
      value: 'http://192.168.1.100:8000',
    },
    refreshInterval: {
      type: Number,
      value: 1000, // ms
    },
  },

  data: {
    snapshotUrl: '',
    autoRefresh: true,
    fps: '--',
    resolution: '640x480',
    _refreshTimer: null,
  },

  lifetimes: {
    attached() {
      this.refreshSnapshot();
      this.startAutoRefresh();
    },
    detached() {
      this.stopAutoRefresh();
    },
  },

  pageLifetimes: {
    show() {
      this.startAutoRefresh();
    },
    hide() {
      this.stopAutoRefresh();
    },
  },

  methods: {
    refreshSnapshot() {
      const url = `${this.properties.serverUrl}/api/v1/vision/snapshot?t=${Date.now()}`;
      this.setData({ snapshotUrl: url });

      // In production, this would fetch the actual image
      // For now, we use a placeholder
      this.setData({ fps: '30' });
    },

    startAutoRefresh() {
      this.stopAutoRefresh();
      if (this.data.autoRefresh) {
        this.data._refreshTimer = setInterval(() => {
          this.refreshSnapshot();
        }, this.properties.refreshInterval);
      }
    },

    stopAutoRefresh() {
      if (this.data._refreshTimer) {
        clearInterval(this.data._refreshTimer);
        this.data._refreshTimer = null;
      }
    },

    onRefresh() {
      this.refreshSnapshot();
    },

    onAutoRefresh() {
      const autoRefresh = !this.data.autoRefresh;
      this.setData({ autoRefresh });

      if (autoRefresh) {
        this.startAutoRefresh();
      } else {
        this.stopAutoRefresh();
      }
    },

    onTap(e) {
      // Tap to inspect: get coordinates relative to image
      const { x, y } = e.detail;
      this.triggerEvent('inspect', { x, y });
    },

    onImageError() {
      console.warn('Camera snapshot failed to load');
      // Use placeholder
      this.setData({
        snapshotUrl: '',
      });
    },
  },
});