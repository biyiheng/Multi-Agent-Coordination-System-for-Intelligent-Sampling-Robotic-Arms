// components/status-panel/status-panel.js - Status display panel component
Component({
  properties: {
    armStatus: {
      type: Object,
      value: {
        joint_positions: { joint_1: 0, joint_2: 0, joint_3: 0, joint_4: 0, joint_5: 0, joint_6: 0 },
        ee_pose: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
        is_moving: false,
        gripper_state: 'unknown',
        safety_status: {},
      },
      observer(newVal) {
        this.updateDisplay(newVal);
      },
    },
    sensorData: {
      type: Object,
      value: {
        temperature: 25.0,
        humidity: 50.0,
        distance: 0,
        voltage: 12.0,
      },
    },
    safetyStatus: {
      type: Object,
      value: {
        level: 'normal',
        warnings: [],
        errors: [],
        emergency_stop: false,
      },
    },
  },

  data: {
    jointDisplay: [0, 0, 0, 0, 0, 0],
    eePose: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
  },

  lifetimes: {
    attached() {
      this.updateDisplay(this.properties.armStatus);
    },
  },

  methods: {
    updateDisplay(armStatus) {
      if (!armStatus) return;

      const positions = armStatus.joint_positions || {};
      const pose = armStatus.ee_pose || {};

      this.setData({
        jointDisplay: [
          positions.joint_1 || 0,
          positions.joint_2 || 0,
          positions.joint_3 || 0,
          positions.joint_4 || 0,
          positions.joint_5 || 0,
          positions.joint_6 || 0,
        ],
        eePose: {
          x: pose.x || 0,
          y: pose.y || 0,
          z: pose.z || 0,
          roll: pose.roll || 0,
          pitch: pose.pitch || 0,
          yaw: pose.yaw || 0,
        },
      });
    },
  },
});