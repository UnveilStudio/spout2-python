"""
preview_example.py — Connect to any active Spout sender and show it in OpenCV.

⚠️ Requires an external Spout sender that owns a *real* GPU rendering
context — for example **TouchDesigner** with a "Spout Out" TOP, OBS, Notch,
Resolume, vMix, Unreal/Unity, or anything else that draws via GPU. The
pure-Python `examples/send_example.py` does NOT drive a real GL/DX texture
(it uses Spout's memory-share fallback) and the cross-process GL/DX interop
cannot be set up reliably from a pure-Python receiver. For a fully-Python
loopback demo, use NDI instead (https://github.com/UnveilStudio/NDIForPython).

Press 'q' or ESC in the preview window to quit.

Usage:
    python examples/preview_example.py                  # auto-pick active sender
    python examples/preview_example.py "MySender"       # connect to a specific one

Requirements:
    pip install opencv-python numpy
    pip install git+https://github.com/UnveilStudio/SPOUT2ForPython.git
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spout import SpoutReceiver, SpoutUtils, GL_RGBA

WINDOW = "SPOUT2ForPython preview"


def wait_for_sender(utils: SpoutUtils, requested: str, timeout_s: float = 30.0) -> str:
    """Block until a Spout sender becomes available, then return its name."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if requested:
            if utils.find_sender(requested):
                return requested
        else:
            active = utils.get_active_sender()
            if active:
                return active
        time.sleep(0.2)
    raise TimeoutError(
        f"No Spout sender {'named ' + repr(requested) if requested else ''} "
        f"appeared within {timeout_s:.0f}s. Make sure a Spout-enabled "
        f"application (TouchDesigner, OBS, Resolume, …) is publishing."
    )


def main() -> int:
    requested = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"Looking for {'sender ' + repr(requested) if requested else 'any active sender'}...")

    with SpoutUtils() as utils:
        target = wait_for_sender(utils, requested)
        info = utils.get_sender_info(target)
        if info is None:
            print(f"Sender {target!r} disappeared before connection.")
            return 1
        width, height = info[0], info[1]
        print(f"Connected to {target!r}  {width}x{height}")

        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        buf = bytearray(width * height * 4)
        bgr = np.empty((height, width, 3), dtype=np.uint8)
        last_log = time.perf_counter()
        frame_count = 0

        with SpoutReceiver(target) as rx:
            print("Press 'q' or ESC in the window to quit.\n")
            while True:
                # Detect resolution changes via SpoutUtils — works on the
                # memory-share path without an OpenGL context.
                info = utils.get_sender_info(target)
                if info is None:
                    print(f"\nSender {target!r} closed.")
                    break
                w, h = info[0], info[1]
                if w != width or h != height:
                    width, height = w, h
                    buf = bytearray(width * height * 4)
                    bgr = np.empty((height, width, 3), dtype=np.uint8)
                    print(f"\n  resolution change: {width}x{height}")

                rx.receive()
                ok = rx.receive_image(buf, width, height, GL_RGBA, invert=True)
                if not ok:
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
                        f"\r  {width}x{height}  recv={fps:5.1f} fps  "
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
