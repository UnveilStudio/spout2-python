"""
receive_example.py — Connect to an active Spout sender and receive frames.

Run this while a Spout sender (e.g. send_example.py) is active.

NOTE: ReceiveImage() requires an active OpenGL context in the calling process.
If you only need to detect a sender's presence / metadata you can call
receiver.receive() alone, which works without an OpenGL context.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spout import SpoutReceiver, SpoutUtils, GL_RGBA


def print_senders():
    """List all currently active Spout senders."""
    with SpoutUtils() as utils:
        senders = utils.get_all_senders()
        if senders:
            print(f"Active senders ({len(senders)}):")
            for name in senders:
                print(f"  • {name}")
            active = utils.get_active_sender()
            if active:
                print(f"  → Active: {active}")
        else:
            print("No active Spout senders found.")
        print()


def main():
    print_senders()

    print("Connecting to active sender (or 'PythonSender' if available)…")
    print("Press Ctrl+C to stop.\n")

    with SpoutReceiver("PythonSender") as receiver:
        frame_count = 0
        buf = None

        while True:
            connected = receiver.receive()  # poll / connect

            if not connected:
                print("Waiting for sender…")
                time.sleep(0.5)
                continue

            if receiver.is_updated or buf is None:
                w = receiver.sender_width
                h = receiver.sender_height
                buf = bytearray(w * h * 4)
                print(
                    f"Connected to '{receiver.sender_name}'  "
                    f"{w}x{h}  "
                    f"cpu={receiver.sender_cpu}"
                )

            if receiver.is_frame_new:
                receiver.receive_image(buf, receiver.sender_width, receiver.sender_height)
                frame_count += 1

            if frame_count % 60 == 0 and frame_count > 0:
                print(
                    f"Received frame {frame_count:6d}  "
                    f"sender_fps={receiver.sender_fps:.1f}  "
                    f"frame_num={receiver.sender_frame}"
                )

            time.sleep(1 / 120)  # ~120 Hz poll


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
