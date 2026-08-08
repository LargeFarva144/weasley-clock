import time
from adafruit_servokit import ServoKit
from gpiozero import DigitalInputDevice

# Setup hardware
kit = ServoKit(channels=16)
servo = kit.continuous_servo[0]
sensor = DigitalInputDevice(4)

# Simple pulse measurement using high-res timestamp
def read_raw_duty_cycle(samples=5):
    cycles = []
    for _ in range(samples):
        # Measure 1 pulse
        while sensor.value == 1: pass
        while sensor.value == 0: pass
        t_start = time.perf_counter()
        while sensor.value == 1: pass
        t_high = time.perf_counter()
        while sensor.value == 0: pass
        t_end = time.perf_counter()
        
        tot = t_end - t_start
        if tot > 0:
            cycles.append((t_high - t_start) / tot)
        time.sleep(0.005)
    
    avg_dc = sum(cycles) / len(cycles)
    # Map duty cycle (0.029 - 0.971) to 0-360 deg
    return (360 - 1) - ((avg_dc - 0.029) * 360) / (0.971 - 0.029)

print("--- SERVO DIAGNOSTIC TEST ---")
start_angle = read_raw_duty_cycle()
print(f"1. Starting Angle: {start_angle:.1f}°")

print("2. Applying +0.052 throttle for 1.5 seconds...")
servo.throttle = 0.052
time.sleep(1.5)
servo.throttle = 0.0
time.sleep(0.5)

end_angle = read_raw_duty_cycle()
print(f"3. Ending Angle:   {end_angle:.1f}°")

diff = end_angle - start_angle
print(f"\nRESULT: +0.15 Throttle changed angle by {diff:+.1f}°")
if diff > 0:
    print("--> POSITIVE THROTTLE INCREASES ANGLE (Clockwise)")
else:
    print("--> POSITIVE THROTTLE DECREASES ANGLE (Counter-Clockwise)")