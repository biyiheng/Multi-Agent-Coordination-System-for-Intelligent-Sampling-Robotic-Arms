// utils/util.js - Utility functions for the mini program

/**
 * Format timestamp to readable string
 */
function formatTime(date) {
  if (!date) return '--';

  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '--';

  const year = d.getFullYear();
  const month = padZero(d.getMonth() + 1);
  const day = padZero(d.getDate());
  const hour = padZero(d.getHours());
  const minute = padZero(d.getMinutes());
  const second = padZero(d.getSeconds());

  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

/**
 * Format date (without time)
 */
function formatDate(date) {
  if (!date) return '--';

  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '--';

  const year = d.getFullYear();
  const month = padZero(d.getMonth() + 1);
  const day = padZero(d.getDate());

  return `${year}-${month}-${day}`;
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(date) {
  if (!date) return '--';

  const d = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '--';

  const now = new Date();
  const diff = now.getTime() - d.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
  if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  return 'Just now';
}

/**
 * Format duration in milliseconds to readable string
 */
function formatDuration(ms) {
  if (!ms || ms < 0) return '--';

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

/**
 * Pad number with leading zero
 */
function padZero(num) {
  return num < 10 ? '0' + num : '' + num;
}

/**
 * Debounce function
 */
function debounce(fn, delay = 300) {
  let timer = null;
  return function (...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      fn.apply(this, args);
      timer = null;
    }, delay);
  };
}

/**
 * Throttle function
 */
function throttle(fn, delay = 300) {
  let lastTime = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastTime >= delay) {
      lastTime = now;
      fn.apply(this, args);
    }
  };
}

/**
 * Deep clone an object
 */
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj.getTime());
  if (obj instanceof Array) return obj.map(item => deepClone(item));

  const cloned = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      cloned[key] = deepClone(obj[key]);
    }
  }
  return cloned;
}

/**
 * Convert PWM value (500-2500) to servo angle (0-180 degrees)
 */
function pwmToAngle(pwm) {
  if (pwm < 500) pwm = 500;
  if (pwm > 2500) pwm = 2500;
  return Math.round(((pwm - 500) / 2000) * 180);
}

/**
 * Convert servo angle (0-180 degrees) to PWM value (500-2500)
 */
function angleToPwm(angle) {
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  return Math.round(500 + (angle / 180) * 2000);
}

/**
 * Round a number to specified decimal places
 */
function roundTo(num, decimals = 2) {
  const factor = Math.pow(10, decimals);
  return Math.round(num * factor) / factor;
}

/**
 * Format a number with unit
 */
function formatNumber(num, unit = '') {
  if (num === null || num === undefined) return '--';
  return `${roundTo(num, 1)}${unit}`;
}

/**
 * Get status display info
 */
function getStatusInfo(status) {
  const statusMap = {
    'idle': { text: 'Idle', class: 'tag-idle', color: '#999999' },
    'planning': { text: 'Planning', class: 'tag-running', color: '#1890FF' },
    'running': { text: 'Running', class: 'tag-running', color: '#1890FF' },
    'paused': { text: 'Paused', class: 'tag-paused', color: '#FA8C16' },
    'completed': { text: 'Completed', class: 'tag-completed', color: '#52C41A' },
    'failed': { text: 'Failed', class: 'tag-failed', color: '#FA5151' },
    'cancelled': { text: 'Cancelled', class: 'tag-cancelled', color: '#999999' },
    'normal': { text: 'Normal', class: 'status-ok', color: '#07C160' },
    'warning': { text: 'Warning', class: 'status-warning', color: '#FFC300' },
    'critical': { text: 'Critical', class: 'status-error', color: '#FA5151' },
  };
  return statusMap[status] || { text: status, class: '', color: '#999999' };
}

/**
 * Generate a simple unique ID
 */
function generateId() {
  return 'id_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Check if an object is empty
 */
function isEmpty(obj) {
  if (!obj) return true;
  if (Array.isArray(obj)) return obj.length === 0;
  if (typeof obj === 'object') return Object.keys(obj).length === 0;
  return !obj;
}

module.exports = {
  formatTime,
  formatDate,
  formatRelativeTime,
  formatDuration,
  padZero,
  debounce,
  throttle,
  deepClone,
  pwmToAngle,
  angleToPwm,
  roundTo,
  formatNumber,
  getStatusInfo,
  generateId,
  isEmpty,
};