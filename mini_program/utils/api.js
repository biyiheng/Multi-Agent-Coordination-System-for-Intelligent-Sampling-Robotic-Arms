// utils/api.js - API communication module
const app = getApp();

const BASE_URL = app ? app.globalData.serverUrl : 'http://192.168.1.100:8000';

/**
 * Wrapped request with authentication and error handling
 */
function request(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const url = `${BASE_URL}${path}`;

    wx.request({
      url,
      method: method,
      data: data,
      header: {
        'Content-Type': 'application/json',
      },
      timeout: 10000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject({
            statusCode: res.statusCode,
            message: res.data?.detail || `Request failed with status ${res.statusCode}`,
            data: res.data
          });
        }
      },
      fail(err) {
        reject({
          message: 'Network error',
          error: err
        });
      }
    });
  });
}

// ===== Arm Control API =====

function getArmStatus() {
  return request('GET', '/api/v1/arm/status');
}

function getArmPosition() {
  return request('GET', '/api/v1/arm/position');
}

function getArmPose() {
  return request('GET', '/api/v1/arm/pose');
}

function moveJoint(jointId, position, time = 1.0) {
  return request('POST', '/api/v1/arm/move/joint', {
    joint_id: jointId,
    position: position,
    time: time
  });
}

function moveCartesian(pose) {
  return request('POST', '/api/v1/arm/move/cartesian', pose);
}

function moveAllJoints(positions, time = 1.0) {
  return request('POST', '/api/v1/arm/move/all', {
    positions: positions,
    time: time
  });
}

function stopArm() {
  return request('POST', '/api/v1/arm/stop');
}

function estop() {
  return request('POST', '/api/v1/arm/estop');
}

function returnToOrigin() {
  return request('POST', '/api/v1/arm/origin');
}

function openGripper() {
  return request('POST', '/api/v1/arm/gripper/open');
}

function closeGripper(force = 50) {
  return request('POST', '/api/v1/arm/gripper/close', { force });
}

function getWorkspace() {
  return request('GET', '/api/v1/arm/workspace');
}

// ===== Vision API =====

function getVisionStatus() {
  return request('GET', '/api/v1/vision/status');
}

function detectColor(colorName) {
  return request('POST', '/api/v1/vision/detect/color', { color_name: colorName });
}

function detectAprilTag() {
  return request('POST', '/api/v1/vision/detect/apriltag', {});
}

function classifyObject() {
  return request('POST', '/api/v1/vision/classify', {});
}

function qualityInspection() {
  return request('POST', '/api/v1/vision/inspect', {});
}

function getSnapshot() {
  return request('GET', '/api/v1/vision/snapshot');
}

function setColorThreshold(color, threshold) {
  return request('POST', '/api/v1/vision/threshold', { color, threshold });
}

// ===== Task API =====

function createTask(taskData) {
  return request('POST', '/api/v1/task/create', taskData);
}

function getTasks(status = null, limit = 50, offset = 0) {
  let path = `/api/v1/task/list?limit=${limit}&offset=${offset}`;
  if (status) {
    path += `&status=${status}`;
  }
  return request('GET', path);
}

function getTask(taskId) {
  return request('GET', `/api/v1/task/${taskId}`);
}

function startTask(taskId) {
  return request('POST', `/api/v1/task/${taskId}/start`);
}

function pauseTask(taskId) {
  return request('POST', `/api/v1/task/${taskId}/pause`);
}

function resumeTask(taskId) {
  return request('POST', `/api/v1/task/${taskId}/resume`);
}

function cancelTask(taskId) {
  return request('POST', `/api/v1/task/${taskId}/cancel`);
}

function getTaskProgress(taskId) {
  return request('GET', `/api/v1/task/${taskId}/progress`);
}

function deleteTask(taskId) {
  return request('DELETE', `/api/v1/task/${taskId}`);
}

// ===== Monitor API =====

function getSystemStatus() {
  return request('GET', '/api/v1/monitor/status');
}

function getSensors() {
  return request('GET', '/api/v1/monitor/sensors');
}

function getSafetyStatus() {
  return request('GET', '/api/v1/monitor/safety');
}

function getLogs(limit = 100, type = null) {
  let path = `/api/v1/monitor/logs?limit=${limit}`;
  if (type) {
    path += `&action_type=${type}`;
  }
  return request('GET', path);
}

function getStatistics() {
  return request('GET', '/api/v1/monitor/statistics');
}

function healthCheck() {
  return request('GET', '/api/v1/monitor/health');
}

module.exports = {
  request,
  getArmStatus,
  getArmPosition,
  getArmPose,
  moveJoint,
  moveCartesian,
  moveAllJoints,
  stopArm,
  estop,
  returnToOrigin,
  openGripper,
  closeGripper,
  getWorkspace,
  getVisionStatus,
  detectColor,
  detectAprilTag,
  classifyObject,
  qualityInspection,
  getSnapshot,
  setColorThreshold,
  createTask,
  getTasks,
  getTask,
  startTask,
  pauseTask,
  resumeTask,
  cancelTask,
  getTaskProgress,
  deleteTask,
  getSystemStatus,
  getSensors,
  getSafetyStatus,
  getLogs,
  getStatistics,
  healthCheck,
};