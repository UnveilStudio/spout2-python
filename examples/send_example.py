"""
send_example.py — Create a Spout sender and publish synthetic RGBA frames.

Run this alongside receive_example.py / preview_example.py / TouchDesigner /
any other Spout-aware application to see the texture shared in real time.
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spout import SpoutSender, GL_RGBA

WIDTH  = 1280
HEIGHT = 720
FPS    = 60


def main() -> None:
    print(f"Creating Spout sender 'PythonSender' at {WIDTH}x{HEIGHT} @ {FPS} fps")
    print("Press Ctrl+C to stop.\n")

    # Vectorised gradient bases — computed once, reused every frame.
    xs = np.arange(WIDTH,  dtype=np.uint16)
    ys = np.arange(HEIGHT, dtype=np.uint16)[:, None]

    rgba = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    rgba[..., 3] = 255                              # alpha opaque

    with SpoutSender("PythonSender") as sender:
        frame = 0
        interval = 1.0 / FPS
        t_start = time.perf_counter()

        while True:
            t0 = time.perf_counter()
            t = frame / FPS

            r_off = int((np.sin(t)         * 0.5 + 0.5) * 255)
            g_off = int((np.sin(t * 1.3)   * 0.5 + 0.5) * 255)
            b_off = int((np.cos(t * 0.7)   * 0.5 + 0.5) * 255)

            rgba[..., 0] = (xs + r_off) & 0xFF                # R
            rgba[..., 1] = (ys + g_off) & 0xFF                # G
            rgba[..., 2] = ((xs ^ ys) + b_off) & 0xFF         # B

            ok = sender.send_image(rgba.tobytes(), WIDTH, HEIGHT, GL_RGBA)

            if frame % FPS == 0:
                status = "OK" if ok else "FAILED"
                print(
                    f"Frame {frame:6d}  send={status}  "
                    f"fps={sender.fps:5.1f}  "
                    f"wall={(time.perf_counter() - t_start):6.2f}s  "
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
