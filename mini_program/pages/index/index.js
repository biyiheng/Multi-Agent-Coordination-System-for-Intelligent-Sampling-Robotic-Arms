// pages/index/index.js - Home/Dashboard page
const api = require('../../utils/api.js');
const util = require('../../utils/util.js');
const app = getApp();

Page({
  data: {
    connected: false,
    loading: false,
    uptime: '--',
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
    safetyStatus: {
      level: 'normal',
      warnings: [],
      errors: [],
      emergency_stop: false
    },
    recentTasks: []
  },

  onLoad() {
    this.loadData();
  },

  onShow() {
    this.loadData();
    this.startStatusPolling();
  },

  onHide() {
    this.stopStatusPolling();
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  startStatusPolling() {
    this.stopStatusPolling();
    this._statusTimer = setInterval(() => {
      this.loadStatus();
    }, 3000);
  },

  stopStatusPolling() {
    if (this._statusTimer) {
      clearInterval(this._statusTimer);
      this._statusTimer = null;
    }
  },

  async loadData() {
    await Promise.all([
      this.loadStatus(),
      this.loadRecentTasks()
    ]);
  },

  async loadStatus() {
    try {
      const status = await api.getSystemStatus();
      this.setData({
        connected: true,
        armStatus: status.arm || this.data.armStatus,
        sensorData: status.sensors || this.data.sensorData,
        safetyStatus: status.safety || this.data.safetyStatus,
        uptime: util.formatDuration((status.uptime || 0) * 1000),
      });
    } catch (err) {
      console.error('Failed to load status:', err);
      this.setData({ connected: false });
    }
  },

  async loadRecentTasks() {
    try {
      const tasks = await api.getTasks(null, 5, 0);
      const formatted = tasks.map(task => ({
        ...task,
        created_at: util.formatRelativeTime(task.created_at),
        status: task.status
      }));
      this.setData({ recentTasks: formatted });
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  },

  // Quick actions
  async onOrigin() {
    this.setData({ loading: true });
    try {
      await api.returnToOrigin();
      app.showToast('Returning to origin');
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ loading: false });
  },

  async onStop() {
    this.setData({ loading: true });
    try {
      await api.stopArm();
      app.showToast('Arm stopped');
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ loading: false });
  },

  async onEstop() {
    wx.showModal({
      title: 'Emergency Stop',
      content: 'This will immediately cut power to the arm. Continue?',
      confirmText: 'E-Stop',
      confirmColor: '#FA5151',
      success: async (res) => {
        if (res.confirm) {
          this.setData({ loading: true });
          try {
            await api.estop();
            app.showToast('EMERGENCY STOP activated');
          } catch (err) {
            app.showToast('Failed: ' + err.message);
          }
          this.setData({ loading: false });
        }
      }
    });
  },

  onNavigateToTasks() {
    wx.switchTab({ url: '/pages/task/task' });
  },

  onTaskDetail(e) {
    const taskId = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/task/task?id=${taskId}` });
  }
});