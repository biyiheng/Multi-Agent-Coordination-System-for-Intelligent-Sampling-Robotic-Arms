// pages/monitor/monitor.js - Real-time monitoring page
const api = require('../../utils/api.js');
const util = require('../../utils/util.js');
const app = getApp();

Page({
  data: {
    serverUrl: 'http://192.168.1.100:8000',
    jointPositions: [0, 0, 0, 0, 0, 0],
    eePose: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
    sensorData: {
      temperature: 25.0,
      humidity: 50.0,
      distance: 0,
      voltage: 12.0,
      current: 0.0
    },
    safetyStatus: {
      level: 'normal',
      warnings: [],
      errors: [],
      emergency_stop: false
    },
    logs: [],
    isMoving: false,
  },

  onLoad() {
    this.setData({ serverUrl: app.globalData.serverUrl });
    this.loadAllData();
    this.startPolling();
  },

  onShow() {
    this.loadAllData();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  startPolling() {
    this.stopPolling();
    this._pollTimer = setInterval(() => {
      this.loadAllData();
    }, 2000);
  },

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  },

  async loadAllData() {
    try {
      const [status, logs] = await Promise.all([
        api.getSystemStatus(),
        api.getLogs(20),
      ]);

      const arm = status.arm || {};
      const positions = arm.joint_positions || {};

      this.setData({
        jointPositions: [
          positions.joint_1 || 0,
          positions.joint_2 || 0,
          positions.joint_3 || 0,
          positions.joint_4 || 0,
          positions.joint_5 || 0,
          positions.joint_6 || 0,
        ],
        eePose: arm.ee_pose || this.data.eePose,
        sensorData: status.sensors || this.data.sensorData,
        safetyStatus: status.safety || this.data.safetyStatus,
        isMoving: arm.is_moving || false,
      });

      if (logs.logs) {
        this.setData({
          logs: logs.logs.map(log => ({
            ...log,
            timestamp: util.formatRelativeTime(log.timestamp),
          }))
        });
      }
    } catch (err) {
      console.error('Failed to load monitoring data:', err);
    }
  },

  onRefreshLogs() {
    this.loadAllData();
  },
});