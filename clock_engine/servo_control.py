import time
import lgpio
from adafruit_servokit import ServoKit
from gpiozero import DigitalInputDevice


class DutyCycleFeedback:
    def __init__(self, gpio_pin: int):
        self.gpio = gpio_pin
        self.sensor = DigitalInputDevice(self.gpio)

        self.min_dc = 0.029
        self.max_dc = 0.971

        self._t_rise = 0.0
        self._t_fall = 0.0
        self.duty_cycle = 0.0

    def get_angle_degrees(self) -> float:
        """
        Returns current servo angle position in degrees.
        """
        while True:
            while self.sensor.value == 1:
                pass
            while self.sensor.value == 0:
                pass
            t_start = time.perf_counter()
            while self.sensor.value == 1:
                pass
            t_cycle_high = time.perf_counter()
            while self.sensor.value == 0:
                pass
            t_end = time.perf_counter()

            t_high = t_cycle_high - t_start
            t_cycle = t_end - t_start
            duty_cycle = t_high / t_cycle

            angle = 360 - ((duty_cycle - self.min_dc) * 360) / (self.max_dc - self.min_dc)
            return angle

    def _on_rising_edge(self):
        now = time.perf_counter()
        
        # Calculate period and duty cycle if we have a valid previous cycle
        if self._t_rise > 0 and self._t_fall > self._t_rise:
            period = now - self._t_rise
            high_time = self._t_fall - self._t_rise
            
            if period > 0:
                dc = high_time / period
                if 0.01 <= dc <= 0.99:  # Filter out physical noise/glitches
                    self.duty_cycle = dc

        self._t_rise = now

    def _on_falling_edge(self):
        self._t_fall = time.perf_counter()

    def test_sensor_high(self, duration_sec: int = 5):
        for i in range(duration_sec):
            time.sleep(1)
            # self._get_duty_cycle()

    def test_duty_cycle(self, duration_sec: int = 5):
        """Prints the calculated duty cycle percentage every second."""
        print(f"Measuring duty cycle on GPIO {self.gpio}...")
        for i in range(duration_sec):
            time.sleep(1)
            print(f"Second {i+1}: Duty Cycle = {self.duty_cycle:.6f}%")

    def cleanup(self):
        """Safely releases the pin."""
        self.sensor.close()


class ClockHandController:
    """Combines PCA9685 continuous servo output with 910Hz PWM feedback to drive

    a clock hand to a target angle (0 - 360 degrees).
    """

    def __init__(
        self,
        servo_kit: ServoKit,
        servo_channel: int,
        feedback_gpio_pin: int,
        positive_increases_angle: bool = True,
        kp: float = 0.005,
        min_throttle: float = 0.06,
        max_throttle: float = 0.22,
    ):
        self.servo = servo_kit.continuous_servo[servo_channel]
        self.feedback = DutyCycleFeedback(gpio_pin=feedback_gpio_pin)
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

    def motor_throttle_control(self, throttle: int):
        """
        Sets servo to desired throttle value.
        """
        self.servo.throttle = throttle


if __name__ == "__main__":
    kit = ServoKit(channels=16)

    # Initialize Clock Hand #0 (Servo Channel 0, Feedback on GPIO 4 / RP1 chip)
    # hand_0 = ClockHandController(
    #     servo_kit=kit,
    #     servo_channel=0,
    #     feedback_gpio_pin=4,
    # )

    feedback = DutyCycleFeedback(gpio_pin=4)

    try:
        feedback.get_angle_degrees()
    finally:
        feedback.cleanup()

    # hand_0.motor_throttle_control(0.052)
    # time.sleep(2)
    # hand_0.motor_throttle_control(0.0)
    # time.sleep(2)
    # hand_0.motor_throttle_control(-0.052)
    # time.sleep(2)
    # hand_0.motor_throttle_control(0.0)
