// app.js - App entry point for Intelligent Sampling Robotic Arm Mini Program
const ws = require('./utils/ws.js');
const api = require('./utils/api.js');

App({
  globalData: {
    systemInfo: null,
    userInfo: null,
    serverUrl: 'http://192.168.1.100:8000',
    wsUrl: 'ws://192.168.1.100:8000/ws/telemetry',
    connected: false,
    armStatus: {
      joint_positions: { joint_1: 0, joint_2: 0, joint_3: 0, joint_4: 0, joint_5: 0, joint_6: 0 },
      ee_pose: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
      is_moving: false,
      gripper_state: 'unknown',
      safety_status: { level: 'normal', emergency_stop: false }
    },
    sensorData: {
      temperature: 25.0,
      humidity: 50.0,
      distance: 0,
      voltage: 12.0
    },
    telemetryCallbacks: []
  },

  onLaunch(options) {
    const that = this;

    // Get system info
    wx.getSystemInfo({
      success(res) {
        that.globalData.systemInfo = res;
        console.log('System info:', res);
      }
    });

    // Initialize WebSocket connection
    this.connectWebSocket();

    // Check for updates
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) {
        updateManager.onUpdateReady(() => {
          wx.showModal({
            title: 'Update Available',
            content: 'A new version is available. Restart to update?',
            success(res) {
              if (res.confirm) {
                updateManager.applyUpdate();
              }
            }
          });
        });
      }
    });
  },

  onShow() {
    // Reconnect WebSocket when app comes to foreground
    if (!ws.isConnected()) {
      this.connectWebSocket();
    }
  },

  onHide() {
    // Keep WebSocket connection alive in background
  },

  connectWebSocket() {
    ws.connect(this.globalData.wsUrl, (message) => {
      this.handleTelemetryMessage(message);
    });
  },

  handleTelemetryMessage(message) {
    const data = message.data || message;

    switch (data.type) {
      case 'arm_status':
        this.globalData.armStatus = data.data;
        break;
      case 'sensor_data':
        this.globalData.sensorData = data.data;
        break;
      case 'task_progress':
        // Forward to task page
        break;
      case 'safety_alert':
        this.showSafetyAlert(data.alerts);
        break;
      case 'pong':
        break;
      default:
        console.log('Unknown telemetry type:', data.type);
    }

    // Notify all registered callbacks
    this.globalData.telemetryCallbacks.forEach(cb => {
      try {
        cb(message);
      } catch (e) {
        console.error('Telemetry callback error:', e);
      }
    });
  },

  showSafetyAlert(alerts) {
    if (!alerts || alerts.length === 0) return;
    const alert = alerts[0];
    wx.showToast({
      title: `Safety: ${alert.level || 'warning'}`,
      icon: 'none',
      duration: 3000
    });
  },

  // Global methods
  request(options) {
    return api.request(options.method || 'GET', options.url, options.data);
  },

  wsSend(data) {
    ws.send(data);
  },

  showToast(title, icon = 'none') {
    wx.showToast({ title, icon, duration: 2000 });
  },

  showLoading(title = 'Loading...') {
    wx.showLoading({ title, mask: true });
  },

  hideLoading() {
    wx.hideLoading();
  },

  // Register telemetry callback
  onTelemetry(callback) {
    this.globalData.telemetryCallbacks.push(callback);
    return () => {
      const idx = this.globalData.telemetryCallbacks.indexOf(callback);
      if (idx > -1) {
        this.globalData.telemetryCallbacks.splice(idx, 1);
      }
    };
  }
});