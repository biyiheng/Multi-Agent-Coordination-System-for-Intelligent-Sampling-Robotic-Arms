// pages/history/history.js - History page
const api = require('../../utils/api.js');
const util = require('../../utils/util.js');
const app = getApp();

Page({
  data: {
    samples: [],
    taskOptions: ['All Tasks'],
    filters: {
      date: '',
      taskIndex: 0,
      minQuality: 0,
    },
    taskList: [],
  },

  onLoad() {
    this.loadTasks();
    this.loadSamples();
  },

  onShow() {
    this.loadSamples();
  },

  async loadTasks() {
    try {
      const tasks = await api.getTasks(null, 100, 0);
      this.setData({
        taskList: tasks,
        taskOptions: ['All Tasks', ...tasks.map(t => t.name)],
      });
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  },

  async loadSamples() {
    try {
      // Build filter params
      const params = { limit: 100, offset: 0 };
      const { filters, taskList } = this.data;

      if (filters.taskIndex > 0 && taskList[filters.taskIndex - 1]) {
        params.task_id = taskList[filters.taskIndex - 1].id;
      }
      if (filters.minQuality > 0) {
        params.quality_min = filters.minQuality / 100;
      }

      // For now, get system status which includes sample info
      const status = await api.getSystemStatus();

      // Mock sample data for display
      const mockSamples = this.generateMockSamples();
      this.setData({ samples: mockSamples });
    } catch (err) {
      console.error('Failed to load samples:', err);
    }
  },

  generateMockSamples() {
    const samples = [];
    const positions = [
      { x: 0, y: 0, z: 10 }, { x: 50, y: 0, z: 10 }, { x: 100, y: 0, z: 10 },
      { x: 0, y: 50, z: 10 }, { x: 50, y: 50, z: 10 }, { x: 100, y: 50, z: 10 },
    ];

    for (let i = 0; i < positions.length; i++) {
      const quality = 0.75 + Math.random() * 0.25;
      samples.push({
        id: `SAMPLE-${String(i + 1).padStart(4, '0')}`,
        task_id: 'task-001',
        position: positions[i],
        quality_score: quality,
        passed: quality >= 0.8,
        status: quality >= 0.8 ? 'passed' : 'failed',
        timestamp: util.formatRelativeTime(new Date(Date.now() - i * 3600000)),
        type: 'sample',
      });
    }

    return samples;
  },

  onDateChange(e) {
    this.setData({ 'filters.date': e.detail.value });
  },

  onTaskFilterChange(e) {
    this.setData({ 'filters.taskIndex': parseInt(e.detail.value) });
  },

  onQualityFilterChange(e) {
    this.setData({ 'filters.minQuality': e.detail.value });
  },

  onApplyFilter() {
    this.loadSamples();
    app.showToast('Filters applied');
  },

  onRefresh() {
    this.loadSamples();
    app.showToast('Refreshed');
  },

  onExport() {
    wx.showModal({
      title: 'Export Data',
      content: 'Export sample data as CSV?',
      success: (res) => {
        if (res.confirm) {
          const csv = this.generateCSV();
          this.shareCSV(csv);
        }
      }
    });
  },

  generateCSV() {
    const { samples } = this.data;
    let csv = 'ID,Task ID,X,Y,Z,Quality,Passed,Timestamp\n';
    samples.forEach(s => {
      csv += `${s.id},${s.task_id},${s.position.x},${s.position.y},${s.position.z},${s.quality_score},${s.passed},${s.timestamp}\n`;
    });
    return csv;
  },

  shareCSV(csv) {
    wx.setClipboardData({
      data: csv,
      success() {
        app.showToast('Data copied to clipboard');
      }
    });
  },

  onSampleDetail(e) {
    const sampleId = e.currentTarget.dataset.id;
    console.log('Sample detail:', sampleId);
    // Could navigate to a detail page
  },
});