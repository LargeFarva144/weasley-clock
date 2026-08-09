import time
import queue
import threading
from typing import Dict, Optional
from adafruit_servokit import ServoKit

from clock_engine.servo_control import ClockHandController

class ClockManager:
    """
    Manages multiple clock hands concurrently using background threads and queues.
    """

    def __init__(self, kit: Optional[ServoKit] = None, channels: int = 16):
        self.kit = kit or ServoKit(channels=channels)
        self.hands: Dict[str, ClockHandController] = {}
        self.queues: Dict[str, queue.Queue] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.current_targets: Dict[str, float] = {}
        self.running = True

    def register_hand(
        self,
        hand_id: str,
        servo_channel: int,
        feedback_gpio_pin: int,
    ):
        """
        Registers a new hand, creates its controller, and starts its dedicated worker thread.
        """
        controller = ClockHandController(
            servo_kit=self.kit,
            servo_channel=servo_channel,
            feedback_gpio_pin=feedback_gpio_pin,
        )

        self.hands[hand_id] = controller
        self.queues[hand_id] = queue.Queue()
        self.current_targets[hand_id] = 0.0

        worker = threading.Thread(
            target=self._hand_worker_loop,
            args=(hand_id,),
            name=f"Worker-{hand_id}",
            daemon=True,
        )
        self.threads[hand_id] = worker
        worker.start()
        print(f"Registered and started thread for hand: '{hand_id}'")

    def _hand_worker_loop(self, hand_id: str):
        """Worker loop executing sequentially queued targets for a single hand."""
        controller = self.hands[hand_id]
        q = self.queues[hand_id]

        while self.running:
            try:
                command = q.get(timeout=1.0)
            except queue.Empty:
                continue

            if command is None:
                q.task_done()
                break

            if isinstance(command, (int, float)):
                controller.motor_position_control(command)

            elif isinstance(command, tuple):
                cmd_type, value = command

                if cmd_type == "THROTTLE":
                    controller.motor_throttle_control(value)

                elif cmd_type == "POSITION":
                    controller.motor_position_control(value)

            q.task_done()

    def set_hand_throttle(self, hand_id: str, throttle: float, override_pending: bool = True):
        """
        Commands a hand to move at a target throttle asynchronously.
        If override_pending is True, drops older unprocessed commands in queue.
        """
        if hand_id not in self.hands:
            raise KeyError(f"Hand '{hand_id}' is not registered with ClockManager.")
        
        q = self.queues[hand_id]
        
        if override_pending:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break

        q.put(("THROTTLE", throttle))
            

    def set_hand_angle(self, hand_id: str, target_angle: float, override_pending: bool = True):
        """
        Commands a hand to move to a target angle asynchronously.
        If override_pending is True, drops older unprocessed target commands in queue.
        """
        if hand_id not in self.hands:
            raise KeyError(f"Hand '{hand_id}' is not registered with ClockManager.")

        q = self.queues[hand_id]

        if override_pending:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break

        q.put(("POSITION", target_angle % 360.0))

    def stop_all_hands(self):
        """Stops all hand motors immediately."""
        for hand_id in self.hands:
            q = self.queues[hand_id]
            
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break
            
            q.put(("THROTTLE", 0.0))
            

    def get_current_angle(self, hand_id: str) -> Optional[float]:
        """
        Reads real-time physical angle from feedback sensor without stopping movement.
        """
        if hand_id in self.hands:
            try:
                return self.hands[hand_id].feedback.get_angle_degrees()
            except Exception as e:
                print(f"[{hand_id}] Error reading angle: {e}")
                return None
        return None

    def shutdown(self):
        """
        Gracefully stops all worker threads and releases GPIO resources.
        """
        print("Shutting down ClockManager...")
        self.running = False

        for hand_id, q in self.queues.items():
            q.put(None)

        for hand_id, thread in self.threads.items():
            thread.join(timeout=3.0)

        for hand_id, controller in self.hands.items():
            controller.feedback.cleanup()

        print("ClockManager shutdown complete.")
