import time
import lgpio
from gpiozero import DigitalInputDevice

GPIO_PIN = 4  # BCM 4 / Header Pin 7

print("--- RASPBERRY PI 5 GPIO CHIP SCANNER ---")

# 1. Scan raw lgpio chips (0 through 5)
found_edges = False
for chip_num in range(6):
    try:
        h = lgpio.gpiochip_open(chip_num)
        # Check chip label if available
        lgpio.gpio_claim_input(h, GPIO_PIN)
        
        edges = 0
        def scan_cb(chip, gpio, level, timestamp):
            global edges
            edges += 1
            
        cb = lgpio.callback(h, GPIO_PIN, lgpio.BOTH_EDGES, scan_cb)
        time.sleep(0.5)
        
        state = lgpio.gpio_read(h, GPIO_PIN)
        cb.cancel()
        lgpio.gpiochip_close(h)
        
        print(f"gpiochip {chip_num}: Initial State = {'HIGH' if state else 'LOW '}, Edges in 0.5s = {edges}")
        if edges > 100:
            print(f"  ==> SUCCESS! The 910Hz signal is running on gpiochip {chip_num}!")
            found_edges = True
            break
    except Exception as e:
        # Skip chips that cannot be opened or don't have pin 4
        pass

# 2. If raw lgpio missed it, test via gpiozero (which auto-detects RP1 on Pi 5)
if not found_edges:
    print("\nTesting via gpiozero (RP1 Auto-Detector)...")
    sensor = DigitalInputDevice(GPIO_PIN)
    gz_edges = 0
    def gz_cb():
        global gz_edges
        gz_edges += 1
    sensor.when_activated = gz_cb
    sensor.when_deactivated = gz_cb
    time.sleep(1.0)
    print(f"gpiozero detected {gz_edges} edges on GPIO 4!")