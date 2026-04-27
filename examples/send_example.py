"""
send_example.py — Create a Spout sender and publish synthetic RGBA frames.

Run this alongside receive_example.py (or any Spout-aware application) to see
the texture shared in real time.

NOTE: SendImage() requires an active OpenGL context. If your application
already has one (e.g. via PyOpenGL, pygame, moderngl) this will work directly.
If not, uncomment the CreateOpenGL() block below to create a hidden window.
"""
import sys
import os
import ctypes
import time
import math

# Make sure the project root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spout import SpoutSender, GL_RGBA

WIDTH  = 640
HEIGHT = 480
FPS    = 30


def make_frame(frame_num: int, width: int, height: int) -> bytearray:
    """Generate a simple animated gradient frame (RGBA)."""
    buf = bytearray(width * height * 4)
    t = frame_num / FPS
    for y in range(height):
        for x in range(width):
            r = int(128 + 127 * math.sin(2 * math.pi * (x / width + t)))
            g = int(128 + 127 * math.sin(2 * math.pi * (y / height + t * 1.3)))
            b = int(128 + 127 * math.cos(2 * math.pi * (x / width - t * 0.7)))
            i = (y * width + x) * 4
            buf[i]     = r
            buf[i + 1] = g
            buf[i + 2] = b
            buf[i + 3] = 255  # fully opaque
    return buf


def main():
    print(f"Creating Spout sender 'PythonSender' at {WIDTH}x{HEIGHT} @ {FPS} fps")
    print("Press Ctrl+C to stop.\n")

    with SpoutSender("PythonSender") as sender:
        frame = 0
        interval = 1.0 / FPS

        while True:
            t0 = time.perf_counter()

            pixels = make_frame(frame, WIDTH, HEIGHT)
            ok = sender.send_image(pixels, WIDTH, HEIGHT, GL_RGBA)

            if frame % FPS == 0:
                status = "OK" if ok else "FAILED"
                print(
                    f"Frame {frame:6d}  send={status}  "
                    f"fps={sender.fps:.1f}  "
                    f"initialized={sender.is_initialized}"
                )

            frame += 1
            elapsed = time.perf_counter() - t0
            sleep = max(0.0, interval - elapsed)
            time.sleep(sleep)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSender stopped.")
