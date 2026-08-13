// components/joystick/joystick.js - Virtual joystick component
Component({
  properties: {
    size: {
      type: Number,
      value: 280
    },
    knobSize: {
      type: Number,
      value: 80
    }
  },

  data: {
    knobX: 0,
    knobY: 0,
    baseCenterX: 0,
    baseCenterY: 0,
    baseRadius: 0,
    active: false,
    lastX: 0,
    lastY: 0,
    lastAngle: 0,
    lastMagnitude: 0,
  },

  methods: {
    onTouchStart(e) {
      const touch = e.touches[0];
      const query = this.createSelectorQuery();

      query.select('.joystick-base').boundingClientRect((rect) => {
        if (!rect) return;

        const baseCenterX = rect.left + rect.width / 2;
        const baseCenterY = rect.top + rect.height / 2;
        const baseRadius = rect.width / 2 - this.properties.knobSize / 2;

        this.setData({
          active: true,
          baseCenterX,
          baseCenterY,
          baseRadius,
        });

        this.updateKnobPosition(touch.clientX, touch.clientY);
      }).exec();
    },

    onTouchMove(e) {
      if (!this.data.active) return;
      const touch = e.touches[0];
      this.updateKnobPosition(touch.clientX, touch.clientY);
    },

    onTouchEnd() {
      this.setData({
        active: false,
        knobX: 0,
        knobY: 0,
      });

      this.triggerEvent('end', {
        x: 0,
        y: 0,
        angle: 0,
        magnitude: 0,
      });
    },

    updateKnobPosition(clientX, clientY) {
      const { baseCenterX, baseCenterY, baseRadius } = this.data;

      let dx = clientX - baseCenterX;
      let dy = clientY - baseCenterY;
      const distance = Math.sqrt(dx * dx + dy * dy);

      // Clamp to radius
      if (distance > baseRadius) {
        dx = (dx / distance) * baseRadius;
        dy = (dy / distance) * baseRadius;
      }

      const magnitude = Math.min(distance / baseRadius, 1.0);
      const angle = Math.atan2(dy, dx);

      this.setData({
        knobX: dx,
        knobY: dy,
        lastX: dx / baseRadius,
        lastY: dy / baseRadius,
        lastAngle: angle,
        lastMagnitude: magnitude,
      });

      this.triggerEvent('change', {
        x: dx / baseRadius,
        y: -dy / baseRadius, // Invert Y for intuitive control
        angle,
        magnitude,
      });
    },
  },
});