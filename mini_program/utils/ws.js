// utils/ws.js - WebSocket client for real-time telemetry
const app = getApp();

const WS_URL = app ? app.globalData.wsUrl : 'ws://192.168.1.100:8000/ws/telemetry';

let socketTask = null;
let connected = false;
let reconnectTimer = null;
let messageCallback = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000; // 30 seconds

/**
 * Establish WebSocket connection
 */
function connect(url, onMessage) {
  if (connected) {
    console.log('WebSocket already connected');
    return;
  }

  const wsUrl = url || WS_URL;
  messageCallback = onMessage;

  console.log('Connecting WebSocket to:', wsUrl);

  socketTask = wx.connectSocket({
    url: wsUrl,
    success() {
      console.log('WebSocket connection request sent');
    },
    fail(err) {
      console.error('WebSocket connection failed:', err);
      scheduleReconnect();
    }
  });

  socketTask.onOpen(() => {
    console.log('WebSocket connected');
    connected = true;
    reconnectAttempts = 0;
  });

  socketTask.onMessage((res) => {
    try {
      const data = JSON.parse(res.data);
      if (messageCallback) {
        messageCallback(data);
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  });

  socketTask.onClose((res) => {
    console.log('WebSocket closed:', res.code, res.reason);
    connected = false;
    scheduleReconnect();
  });

  socketTask.onError((err) => {
    console.error('WebSocket error:', err);
    connected = false;
  });
}

/**
 * Close WebSocket connection
 */
function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (socketTask) {
    socketTask.close({
      success() {
        console.log('WebSocket disconnected');
      }
    });
    socketTask = null;
  }

  connected = false;
  reconnectAttempts = 0;
}

/**
 * Send data over WebSocket
 */
function send(data) {
  if (!connected || !socketTask) {
    console.warn('WebSocket not connected, cannot send');
    return false;
  }

  const payload = typeof data === 'string' ? data : JSON.stringify(data);

  socketTask.send({
    data: payload,
    success() {
      // Message sent
    },
    fail(err) {
      console.error('Failed to send WebSocket message:', err);
    }
  });

  return true;
}

/**
 * Check if WebSocket is connected
 */
function isConnected() {
  return connected;
}

/**
 * Register message handler
 */
function onMessage(callback) {
  messageCallback = callback;
}

/**
 * Schedule reconnection with exponential backoff
 */
function scheduleReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.warn('Max reconnect attempts reached');
    return;
  }

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
  }

  const delay = Math.min(
    BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
    MAX_RECONNECT_DELAY
  );

  console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`);

  reconnectTimer = setTimeout(() => {
    reconnectAttempts++;
    connect(WS_URL, messageCallback);
  }, delay);
}

/**
 * Send ping to keep connection alive
 */
function sendPing() {
  if (connected) {
    send('ping');
  }
}

module.exports = {
  connect,
  disconnect,
  send,
  isConnected,
  onMessage,
  sendPing,
};