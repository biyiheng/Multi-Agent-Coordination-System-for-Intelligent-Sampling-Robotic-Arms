// pages/task/task.js - Task management page
const api = require('../../utils/api.js');
const util = require('../../utils/util.js');
const app = getApp();

Page({
  data: {
    creating: false,
    filterIndex: 0,
    statusFilters: ['All', 'idle', 'running', 'paused', 'completed', 'failed', 'cancelled'],
    strategies: ['grid', 'random', 'spiral', 'adaptive'],
    newTask: {
      name: '',
      strategyIndex: 0,
      bounds: { x_min: '0', x_max: '100', y_min: '0', y_max: '100', z: '10' },
      params: { step: '50' },
      priority: 5,
    },
    tasks: [],
  },

  onLoad() {
    this.loadTasks();
  },

  onShow() {
    this.loadTasks();
  },

  async loadTasks() {
    try {
      const filter = this.data.filterIndex > 0 ? this.data.statusFilters[this.data.filterIndex] : null;
      const tasks = await api.getTasks(filter, 50, 0);

      const formatted = tasks.map(task => ({
        ...task,
        created_at: util.formatRelativeTime(task.created_at),
        updated_at: util.formatRelativeTime(task.updated_at),
      }));

      this.setData({ tasks: formatted });
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  },

  // Form handlers
  onNameInput(e) {
    this.setData({ 'newTask.name': e.detail.value });
  },

  onStrategyChange(e) {
    this.setData({ 'newTask.strategyIndex': parseInt(e.detail.value) });
  },

  onBoundsInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`newTask.bounds.${field}`]: e.detail.value });
  },

  onParamInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`newTask.params.${field}`]: e.detail.value });
  },

  onPriorityChange(e) {
    this.setData({ 'newTask.priority': e.detail.value });
  },

  onFilterChange(e) {
    this.setData({ filterIndex: parseInt(e.detail.value) });
    this.loadTasks();
  },

  // Create task
  async onCreateTask() {
    const { newTask } = this.data;

    if (!newTask.name.trim()) {
      app.showToast('Please enter a task name');
      return;
    }

    this.setData({ creating: true });

    try {
      const taskData = {
        name: newTask.name.trim(),
        strategy: this.data.strategies[newTask.strategyIndex],
        bounds: {
          x_min: parseFloat(newTask.bounds.x_min) || 0,
          x_max: parseFloat(newTask.bounds.x_max) || 100,
          y_min: parseFloat(newTask.bounds.y_min) || 0,
          y_max: parseFloat(newTask.bounds.y_max) || 100,
          z: parseFloat(newTask.bounds.z) || 10,
        },
        parameters: {
          step: parseFloat(newTask.params.step) || 50,
        },
        priority: newTask.priority,
      };

      await api.createTask(taskData);
      app.showToast('Task created');

      // Reset form
      this.setData({
        'newTask.name': '',
        'newTask.bounds': { x_min: '0', x_max: '100', y_min: '0', y_max: '100', z: '10' },
        'newTask.params': { step: '50' },
      });

      this.loadTasks();
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }

    this.setData({ creating: false });
  },

  // Task actions
  async doTaskAction(taskId, action, actionName) {
    try {
      const actionMap = {
        start: api.startTask,
        pause: api.pauseTask,
        resume: api.resumeTask,
        cancel: api.cancelTask,
      };

      const fn = actionMap[action];
      if (!fn) return;

      await fn(taskId);
      app.showToast(`Task ${actionName}`);
      this.loadTasks();
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
  },

  onStartTask(e) {
    const taskId = e.currentTarget.dataset.id;
    this.doTaskAction(taskId, 'start', 'started');
  },

  onPauseTask(e) {
    const taskId = e.currentTarget.dataset.id;
    this.doTaskAction(taskId, 'pause', 'paused');
  },

  onResumeTask(e) {
    const taskId = e.currentTarget.dataset.id;
    this.doTaskAction(taskId, 'resume', 'resumed');
  },

  onCancelTask(e) {
    const taskId = e.currentTarget.dataset.id;
    wx.showModal({
      title: 'Cancel Task',
      content: 'Are you sure you want to cancel this task?',
      success: (res) => {
        if (res.confirm) {
          this.doTaskAction(taskId, 'cancel', 'cancelled');
        }
      }
    });
  },

  onDeleteTask(e) {
    const taskId = e.currentTarget.dataset.id;
    wx.showModal({
      title: 'Delete Task',
      content: 'This will permanently delete the task and all its data.',
      confirmColor: '#FA5151',
      success: async (res) => {
        if (res.confirm) {
          try {
            await api.deleteTask(taskId);
            app.showToast('Task deleted');
            this.loadTasks();
          } catch (err) {
            app.showToast('Failed: ' + err.message);
          }
        }
      }
    });
  },

  onTaskTap(e) {
    const taskId = e.currentTarget.dataset.id;
    // Navigate to task detail (could be a separate page)
    console.log('Task tapped:', taskId);
  },
});