"""
Test loopback in-process: sender e receiver nello stesso processo Python.

Spout in genere e' progettato per cross-process via DX shared texture.
Loopback in-process potrebbe funzionare o fallire diversamente — verifichiamo.
"""
from __future__ import annotations
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from spout import SpoutSender, SpoutReceiver, GL_RGBA  # noqa: E402

W, H = 256, 192
NAME = f"InProc_{secrets.token_hex(3)}"

print(f"Sender + receiver IN-PROCESS, name='{NAME}', {W}x{H}\n")

rgba = np.zeros((H, W, 4), dtype=np.uint8)
rgba[..., 1] = 255  # solid green
rgba[..., 3] = 255

sender = SpoutSender(NAME)
print(f"sender.gldx_compatible = {sender.gldx_compatible}")
print(f"sender.cpu_share       = {sender.cpu_share}")

# Push qualche frame
for i in range(5):
    ok = sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
    if i == 0:
        print(f"primo send_image -> {ok}")
        print(f"sender.is_initialized  = {sender.is_initialized}")
        print(f"sender.gldx_compatible = {sender.gldx_compatible}")
        print(f"sender.cpu_share       = {sender.cpu_share}")
    time.sleep(1/30)

# Apro receiver
print("\n-- Receiver --")
receiver = SpoutReceiver(NAME)
buf = bytearray(W * H * 4)
nonzero = 0
ok_count = 0
conn = 0

for i in range(20):
    sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
    if receiver.receive():
        conn += 1
        ok = receiver.receive_image(buf, W, H, GL_RGBA)
        if ok:
            ok_count += 1
            if any(b != 0 for b in buf[::1024]):
                nonzero += 1
    time.sleep(1/30)

print(f"\npoll iter         : 20")
print(f"receive() True    : {conn}")
print(f"receive_image True: {ok_count}")
print(f"buffer non-zero   : {nonzero}")
print(f"primi 16 byte buf : {bytes(buf[:16]).hex()}")

receiver.release()
sender.release()
