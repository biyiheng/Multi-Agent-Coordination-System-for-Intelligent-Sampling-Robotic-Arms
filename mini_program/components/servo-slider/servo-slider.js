// components/servo-slider/servo-slider.js - Servo control slider component
Component({
  properties: {
    servoId: {
      type: Number,
      value: 0,
    },
    label: {
      type: String,
      value: 'Joint',
    },
    min: {
      type: Number,
      value: 500,
    },
    max: {
      type: Number,
      value: 2500,
    },
    value: {
      type: Number,
      value: 1500,
      observer(newVal) {
        this.updateDisplay(newVal);
      },
    },
    step: {
      type: Number,
      value: 1,
    },
  },

  data: {
    displayAngle: 90,
  },

  lifetimes: {
    attached() {
      this.updateDisplay(this.properties.value);
    },
  },

  methods: {
    onSliderChange(e) {
      const value = e.detail.value;
      this.updateDisplay(value);

      this.triggerEvent('change', {
        servoId: this.properties.servoId,
        value: value,
        angle: this.pwmToAngle(value),
      });
    },

    onSliderChanging(e) {
      const value = e.detail.value;
      this.updateDisplay(value);
    },

    updateDisplay(pwm) {
      this.setData({
        displayAngle: this.pwmToAngle(pwm),
      });
    },

    pwmToAngle(pwm) {
      // Convert PWM (500-2500) to angle (0-180)
      if (pwm < 500) pwm = 500;
      if (pwm > 2500) pwm = 2500;
      return Math.round(((pwm - 500) / 2000) * 180);
    },

    angleToPwm(angle) {
      // Convert angle (0-180) to PWM (500-2500)
      if (angle < 0) angle = 0;
      if (angle > 180) angle = 180;
      return Math.round(500 + (angle / 180) * 2000);
    },
  },
});