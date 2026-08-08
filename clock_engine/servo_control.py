import time
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

    def motor_position_control(
            self,
            target_angle_degrees: float,
            tolerance_degrees: float = 0.25,
            timeout_sec: float = 10.0
        ):
        """
        Sets servo to desired angular position
        """
        target_angle_degrees = target_angle_degrees % 360.0
        t_start = time.time()

        print(f"Moving servo to target angle: {target_angle_degrees:.1f} degrees...")

        while True:
            try:
                current_angle_degrees = self.feedback.get_angle_degrees()
            except RuntimeError as e:
                self.servo.throttle = 0.0
                print(f"Error reading position: {e}")
                break

            error = self._get_shortest_path_error(target_angle_degrees, current_angle_degrees)

            if abs(error) <= tolerance_degrees:
                self.servo.throttle = 0.0
                print("Target reached!")
                break

            if (time.time() - t_start) > timeout_sec:
                self.servo.throttle = 0.0
                print("Timeout reached.")
                break

            calculated_speed = abs(error) * self.kp
            speed = max(self.min_throttle, min(self.max_throttle, calculated_speed))

            if error < 0:
                speed = -speed

            self.servo.throttle = speed
            time.sleep(0.050)

if __name__ == "__main__":
    kit = ServoKit(channels=16)

    hand_0 = ClockHandController(
        servo_kit=kit,
        servo_channel=0,
        feedback_gpio_pin=4,
        kp=0.001
    )

    print("Starting position test for hand_0...")
    hand_0.motor_position_control(target_angle_degrees=90)
    time.sleep(2)
    hand_0.motor_position_control(target_angle_degrees=270)
    time.sleep(2)
    hand_0.motor_position_control(target_angle_degrees=0)
    print("Test complete.")
