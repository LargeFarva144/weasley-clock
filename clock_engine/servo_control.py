import time
import lgpio
from adafruit_servokit import ServoKit


class HighFreqPWMFeedback:
    """Reads high-frequency digital PWM feedback (e.g. 910 Hz Parallax 360 servos)

    using nanosecond hardware timestamps from the Pi 5's RP1 GPIO chip.
    """

    def __init__(
        self,
        gpio_pin: int,
        chip: int = 4,  # RP1 GPIO chip on Raspberry Pi 5
        min_dc: float = 0.027,  # ~2.7% duty cycle @ 0 deg
        max_dc: float = 0.971,  # ~97.1% duty cycle @ 360 deg
    ):
        self.gpio = gpio_pin
        self.min_dc = min_dc
        self.max_dc = max_dc

        self._t_rise_ns = 0
        self._t_fall_ns = 0
        self._duty_cycle = 0.0
        self._last_update = 0.0

        # Open RP1 GPIO chip on Pi 5 and claim the input pin
        self._h = lgpio.gpiochip_open(chip)
        lgpio.gpio_claim_input(self._h, self.gpio)

        # Attach hardware edge callback
        self._cb_id = lgpio.callback(
            self._h, self.gpio, lgpio.BOTH_EDGES, self._edge_cb
        )

    def _edge_cb(self, chip, gpio, level, timestamp_ns):
        if level == 1:  # Rising edge
            if self._t_rise_ns > 0 and self._t_fall_ns > self._t_rise_ns:
                period = timestamp_ns - self._t_rise_ns
                high_time = self._t_fall_ns - self._t_rise_ns
                if period > 0:
                    dc = high_time / period
                    if 0.01 <= dc <= 0.99:  # Filter out noise / disconnects
                        self._duty_cycle = dc
                        self._last_update = time.time()
            self._t_rise_ns = timestamp_ns
        elif level == 0:  # Falling edge
            self._t_fall_ns = timestamp_ns

    def get_angle(self, max_stale_sec: float = 0.5) -> float:
        """Returns current angle in degrees (0.0 to 360.0)."""
        if (
            self._last_update == 0
            or (time.time() - self._last_update) > max_stale_sec
        ):
            raise RuntimeError(
                "Feedback signal stale or disconnected! Check physical wire on GPIO pin."
            )

        angle = (self._duty_cycle - self.min_dc) * 360.0 / (
            self.max_dc - self.min_dc
        )
        return max(0.0, min(360.0, angle))

    def cleanup(self):
        """Releases GPIO resources cleanly."""
        if hasattr(self, "_cb_id") and self._cb_id:
            self._cb_id.cancel()
        if hasattr(self, "_h") and self._h >= 0:
            lgpio.gpiochip_close(self._h)


class ClockHandController:
    """Combines PCA9685 continuous servo output with 910Hz PWM feedback to drive

    a clock hand to a target angle (0 - 360 degrees).
    """

    def __init__(
        self,
        kit: ServoKit,
        servo_channel: int,
        feedback_gpio_pin: int,
        gpio_chip: int = 4,
        positive_increases_angle: bool = True,
        kp: float = 0.005,
        min_throttle: float = 0.06,
        max_throttle: float = 0.22,
    ):
        self.servo = kit.continuous_servo[servo_channel]
        self.feedback = HighFreqPWMFeedback(
            gpio_pin=feedback_gpio_pin, chip=gpio_chip
        )
        self.positive_increases_angle = positive_increases_angle
        self.kp = kp
        self.min_throttle = min_throttle
        self.max_throttle = max_throttle

    @staticmethod
    def _get_shortest_path_error(target: float, current: float) -> float:
        """Calculates signed shortest distance [-180, 180] degrees."""
        error = target - current
        while error > 180.0:
            error -= 360.0
        while error < -180.0:
            error += 360.0
        return error

    def move_to_angle(
        self,
        target_angle: float,
        tolerance: float = 2.0,
        timeout_sec: float = 10.0,
    ):
        """Drives the hand to target_angle using closed-loop proportional feedback."""
        target_angle = target_angle % 360.0
        start_time = time.time()

        # Brief delay to collect initial background pulse signals
        time.sleep(0.15)

        print(f"Moving servo to target angle: {target_angle:.1f}°...")

        while True:
            try:
                current_angle = self.feedback.get_angle()
            except RuntimeError as e:
                self.servo.throttle = 0.0
                print(f"Error reading position: {e}")
                break

            error = self._get_shortest_path_error(
                target_angle, current_angle
            )

            # 1. Target Reached
            if abs(error) <= tolerance:
                self.servo.throttle = 0.0
                print(
                    f"Target reached! Final angle: {current_angle:.1f}° (Error: {error:.2f}°)"
                )
                break

            # 2. Safety Timeout
            if (time.time() - start_time) > timeout_sec:
                self.servo.throttle = 0.0
                print(
                    f"Timeout reached! Stopped at {current_angle:.1f}° (Error: {error:.2f}°)"
                )
                break

            # 3. Proportional Throttle Calculation
            speed_mag = max(
                self.min_throttle,
                min(self.max_throttle, abs(error) * self.kp),
            )

            # Apply directional polarity
            if self.positive_increases_angle:
                throttle = speed_mag if error > 0 else -speed_mag
            else:
                throttle = -speed_mag if error > 0 else speed_mag

            self.servo.throttle = throttle
            time.sleep(0.015)

    def close(self):
        """Safely stops the motor and releases GPIO callbacks."""
        self.servo.throttle = 0.0
        self.feedback.cleanup()


# --- Main Test Script ---
if __name__ == "__main__":
    # Initialize PCA9685 HAT (16 Channels)
    kit = ServoKit(channels=16)

    # Initialize Clock Hand #0 (Servo Channel 0, Feedback on GPIO 4 / RP1 chip)
    hand_0 = ClockHandController(
        kit=kit,
        servo_channel=0,
        feedback_gpio_pin=4,
        gpio_chip=4,  # Pi 5 RP1 Chip
        positive_increases_angle=True,  # Confirmed
    )

    try:
        # Move to 180 degrees
        hand_0.move_to_angle(180.0)

        time.sleep(2)

        # Move to 90 degrees
        hand_0.move_to_angle(90.0)

    finally:
        hand_0.close()