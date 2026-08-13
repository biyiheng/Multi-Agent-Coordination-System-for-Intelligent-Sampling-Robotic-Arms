// pages/control/control.js - Manual control page
const api = require('../../utils/api.js');
const util = require('../../utils/util.js');
const app = getApp();

Page({
  data: {
    eePose: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
    servos: [
      { id: 1, label: 'Joint 1 (Base)', min: 500, max: 2500, value: 1500 },
      { id: 2, label: 'Joint 2 (Shoulder)', min: 500, max: 2500, value: 1500 },
      { id: 3, label: 'Joint 3 (Elbow)', min: 500, max: 2500, value: 1500 },
      { id: 4, label: 'Joint 4 (Wrist Rot)', min: 500, max: 2500, value: 1500 },
      { id: 5, label: 'Joint 5 (Wrist Pitch)', min: 500, max: 2500, value: 1500 },
      { id: 6, label: 'Joint 6 (Wrist Roll)', min: 500, max: 2500, value: 1500 },
    ],
    joystickX: 0,
    joystickY: 0,
    gripperForce: 50,
    gripperLoading: false,
    actionLoading: false,
  },

  onLoad() {
    this.loadArmStatus();
  },

  onShow() {
    this.loadArmStatus();
  },

  async loadArmStatus() {
    try {
      const status = await api.getArmStatus();
      const positions = status.joint_positions;
      const servos = this.data.servos.map((servo, i) => ({
        ...servo,
        value: util.angleToPwm(positions[`joint_${i + 1}`] || 0),
      }));
      this.setData({
        eePose: status.ee_pose,
        servos,
        gripperForce: status.gripper_force || 50,
      });
    } catch (err) {
      console.error('Failed to load arm status:', err);
    }
  },

  // Servo slider change handler
  onServoChange: util.debounce(function (e) {
    const { servoId, value } = e.detail;
    const angle = util.pwmToAngle(value);

    // Update local state
    const servos = this.data.servos.map(s => {
      if (s.id === servoId) return { ...s, value };
      return s;
    });
    this.setData({ servos });

    // Send move command
    api.moveJoint(servoId, angle, 1.0).catch(err => {
      console.error(`Failed to move joint ${servoId}:`, err);
    });
  }, 200),

  // Joystick change handler
  onJoystickChange(e) {
    const { x, y, angle, magnitude } = e.detail;
    this.setData({ joystickX: x, joystickY: y });

    const speed = 10; // mm per update
    const dx = Math.cos(angle) * magnitude * speed;
    const dy = Math.sin(angle) * magnitude * speed;

    const newPose = {
      x: this.data.eePose.x + dx,
      y: this.data.eePose.y + dy,
      z: this.data.eePose.z,
      roll: this.data.eePose.roll,
      pitch: this.data.eePose.pitch,
      yaw: this.data.eePose.yaw,
    };

    this.setData({ eePose: newPose });
  },

  // Joystick released
  onJoystickEnd(e) {
    // Send final pose
    api.moveCartesian(this.data.eePose).catch(err => {
      console.error('Failed to move:', err);
    });
  },

  // Gripper controls
  async onOpenGripper() {
    this.setData({ gripperLoading: true });
    try {
      await api.openGripper();
      app.showToast('Gripper opened');
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ gripperLoading: false });
  },

  async onCloseGripper() {
    this.setData({ gripperLoading: true });
    try {
      await api.closeGripper(this.data.gripperForce);
      app.showToast('Gripper closed');
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ gripperLoading: false });
  },

  onGripperForceChange(e) {
    this.setData({ gripperForce: e.detail.value });
  },

  // Action buttons
  async onOrigin() {
    this.setData({ actionLoading: true });
    try {
      await api.returnToOrigin();
      app.showToast('Returning to origin');
      this.loadArmStatus();
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ actionLoading: false });
  },

  async onStop() {
    this.setData({ actionLoading: true });
    try {
      await api.stopArm();
      app.showToast('Arm stopped');
    } catch (err) {
      app.showToast('Failed: ' + err.message);
    }
    this.setData({ actionLoading: false });
  },

  async onEstop() {
    wx.showModal({
      title: 'Emergency Stop',
      content: 'Immediately cut power to the arm?',
      confirmText: 'E-Stop',
      confirmColor: '#FA5151',
      success: async (res) => {
        if (res.confirm) {
          this.setData({ actionLoading: true });
          try {
            await api.estop();
            app.showToast('EMERGENCY STOP activated');
          } catch (err) {
            app.showToast('Failed: ' + err.message);
          }
          this.setData({ actionLoading: false });
        }
      }
    });
  },

  onRefresh() {
    this.loadArmStatus();
    app.showToast('Refreshed');
  },
});