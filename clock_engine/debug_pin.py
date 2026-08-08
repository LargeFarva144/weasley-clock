import time
import lgpio

GPIO_PIN = 17 # BCM GPIO 4 (Physical Pin 7)

h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_input(h, GPIO_PIN)

edge_count = 0

def raw_callback(chip, gpio, level, timestamp):
    global edge_count
    edge_count += 1

cb = lgpio.callback(h, GPIO_PIN, lgpio.BOTH_EDGES, raw_callback)

print("Testing BCM GPIO 4 for hardware edges...")
for i in range(5):
    time.sleep(1)
    current_state = lgpio.gpio_read(h, GPIO_PIN)
    print(f"Second {i+1}: Pin State = {'HIGH' if current_state else 'LOW '}, Total Edges Detected = {edge_count}")

cb.cancel()
lgpio.gpiochip_close(h)
