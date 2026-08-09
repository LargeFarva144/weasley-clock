import json
import sys
from pathlib import Path
import paho.mqtt.client as mqtt

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from clock_engine.clock_manager import ClockManager

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

config = load_config(CONFIG_PATH)

MQTT_BROKER = config["mqtt"].get("broker", "localhost")
MQTT_PORT = config["mqtt"].get("port", 1883)
MQTT_USER = config["mqtt"].get("user")
MQTT_PASSWORD = config["mqtt"].get("password")

LOCATION_ANGLES = config.get("locations", {})
HANDS_CONFIG = {hand["hand_id"]: hand for hand in config.get("hands", [])}
USER_TO_HAND_ID = {hand["ha_user"]: hand["hand_id"] for hand in config.get("hands", []) if "ha_user" in hand}

manager = ClockManager()

for hand_id, hand_info in HANDS_CONFIG.items():
    if hand_info['name'] != "none":
        print(
            f"Registering '{hand_info['name']}' ({hand_id}) on channel {hand_info['servo_channel']}, GPIO {hand_info['feedback_gpio']}..."
        )
        manager.register_hand(
            hand_id=hand_id,
            servo_channel=hand_info["servo_channel"],
            feedback_gpio_pin=hand_info["feedback_gpio"],
        )

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected successfully to MQTT Broker.")
        client.subscribe("weasley_clock/hand/+/set_location")
        print("Subscribed to: weasley_clock/hand/+/set_location")
    else:
        print(f"Failed to connect to MQTT Broker, return code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        ha_user = topic_parts[2]
        location_name = msg.payload.decode("utf-8").strip()

        hand_id = USER_TO_HAND_ID.get(ha_user)

        if not hand_id:
            print(f"Warning: Unknown Home Assistant user '{ha_user}' in MQTT payload.")
            return

        print(f"Received MQTT command for '{hand_id}': Location = '{location_name}'")

        if location_name not in LOCATION_ANGLES:
            print(f"Warning: Location '{location_name}' not defined in config.")
            return

        hand_info = HANDS_CONFIG[hand_id]
        base_angle = LOCATION_ANGLES[location_name]
        offset = hand_info.get("angle_offset", 0.0)

        target_angle = (base_angle + offset) % 360.0

        print(
            f"--> Moving '{hand_info['name']}' to {location_name} (Base: {base_angle}°, Offset: {offset}° -> Target: {target_angle:.1f}°)"
        )
        manager.set_hand_angle(hand_id, target_angle)

    except Exception as e:
        print(f"Error processing MQTT message: {e}")

if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping MQTT daemon...")
    finally:
        client.disconnect()
        manager.shutdown()