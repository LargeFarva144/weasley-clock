# clock_engine/test_910hz.py
import time
import lgpio

GPIO_PIN = 4
MIN_DC = 0.027  # 2.7%
MAX_DC = 0.971  # 97.1%

# Open GPIO Chip 0 (Pi 5 default)
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_input(h, GPIO_PIN)

t_rise_ns = 0
t_fall_ns = 0
duty_cycle = 0.0
last_update = 0.0


def edge_callback(chip, gpio, level, timestamp):
    global t_rise_ns, t_fall_ns, duty_cycle, last_update

    if level == 1:  # Rising edge
        if t_rise_ns > 0 and t_fall_ns > t_rise_ns:
            period = timestamp - t_rise_ns
            high_time = t_fall_ns - t_rise_ns
            if period > 0:
                dc = high_time / period
                if 0.01 <= dc <= 0.99:
                    duty_cycle = dc
                    last_update = time.time()
        t_rise_ns = timestamp
    elif level == 0:  # Falling edge
        t_fall_ns = timestamp


# Attach hardware alert callback
cb_id = lgpio.callback(h, GPIO_PIN, lgpio.BOTH_EDGES, edge_callback)

print("Reading 910Hz Servo Feedback (Press Ctrl+C to stop)...")
try:
    for _ in range(20):
        time.sleep(0.2)
        if time.time() - last_update < 0.5:
            angle = (duty_cycle - MIN_DC) * 360.0 / (MAX_DC - MIN_DC)
            angle = max(0.0, min(360.0, angle))
            print(
                f"Duty Cycle: {duty_cycle*100:.2f}%  --->  Angle: {angle:.1f}°"
            )
        else:
            print("Waiting for signal...")
finally:
    cb_id.cancel()
    lgpio.gpiochip_close(h)
