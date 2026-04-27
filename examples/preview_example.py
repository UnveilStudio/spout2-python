"""
preview_example.py — Connect to any active Spout sender and show it in OpenCV.

Run a Spout-aware sender first (TouchDesigner "Spout Out" TOP, Resolume,
OBS, Notch, …) — or just `python examples/send_example.py` — and then run
this script. The first sender it sees is connected to and displayed.

Press 'q' or ESC in the preview window to quit.

Usage:
    python examples/preview_example.py                  # auto-pick active sender
    python examples/preview_example.py "MySender"       # connect to a specific one

Requirements:
    pip install opencv-python numpy
    pip install git+https://github.com/UnveilStudio/spout2-python.git
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spout import SpoutReceiver, GL_RGBA

WINDOW = "spout2-python preview"


def main() -> int:
    requested = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"Opening Spout receiver{f' for sender {requested!r}' if requested else ''}...")
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)

    last_log = time.perf_counter()
    frame_count = 0
    buf = None
    bgr = None
    width = height = 0

    with SpoutReceiver(requested) as rx:
        print("Waiting for a sender — press 'q' or ESC in the window to quit.\n")
        while True:
            ok = rx.receive()
            if not ok or not rx.is_connected:
                # No active sender — keep the window alive while waiting.
                if cv2.waitKey(50) in (ord("q"), 27):
                    break
                continue

            # (Re)allocate buffer when the sender resolution changes.
            if rx.is_updated or buf is None or width != rx.sender_width or height != rx.sender_height:
                width, height = rx.sender_width, rx.sender_height
                buf = bytearray(width * height * 4)
                bgr = np.empty((height, width, 3), dtype=np.uint8)
                print(f"\nConnected: {rx.sender_name!r}  {width}x{height}  "
                      f"sender_fps={rx.sender_fps:.1f}")

            # OpenGL is bottom-left origin → invert=True so cv2 shows it
            # right-side-up. Format RGBA: convert to BGR for imshow.
            if not rx.receive_image(buf, width, height, GL_RGBA, invert=True):
                if cv2.waitKey(1) in (ord("q"), 27):
                    break
                continue

            rgba = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4)
            cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR, dst=bgr)

            cv2.imshow(WINDOW, bgr)
            key = cv2.waitKey(1)
            if key in (ord("q"), 27):
                break

            frame_count += 1
            now = time.perf_counter()
            if now - last_log >= 1.0:
                fps = frame_count / (now - last_log)
                sys.stdout.write(
                    f"\r  {width}x{height}  "
                    f"recv={fps:5.1f} fps  "
                    f"sender_fps={rx.sender_fps:5.1f} "
                )
                sys.stdout.flush()
                frame_count = 0
                last_log = now

    cv2.destroyAllWindows()
    print("\nClosed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\nStopped by user.")
