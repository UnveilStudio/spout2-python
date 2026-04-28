"""
Forzo CPU-share mode esplicitamente. Vediamo se loopback funziona cosi'.
"""
from __future__ import annotations
import ctypes
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from spout import SpoutSender, SpoutReceiver, GL_RGBA
from spout import _lib

W, H = 256, 192
NAME = f"CPUTest_{secrets.token_hex(2)}"

print(f"Sender+Receiver in-process con CPU share forzato, '{NAME}'\n")

# --- Sender ---
sender = SpoutSender(NAME)
# Force CPU share via vtable slot 137 (V_SET_CPU_SHARE)
fn = _lib._vtbl_fn(sender._h, _lib.V_SET_CPU_SHARE, None, [ctypes.c_bool])
fn(sender._h, True)
print(f"  set_cpu_share(True) called")

rgba = np.zeros((H, W, 4), dtype=np.uint8)
rgba[..., 2] = 255  # solid blue
rgba[..., 3] = 255
ok = sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
print(f"  send_image -> {ok}")
print(f"  sender.is_initialized = {sender.is_initialized}")
print(f"  sender.gldx_compatible = {sender.gldx_compatible}")
print(f"  sender.cpu_share       = {sender.cpu_share}")

for _ in range(5):
    sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
    time.sleep(1/30)

# --- Receiver ---
print("\n-- Receiver --")
recv = SpoutReceiver(NAME)
fn2 = _lib._vtbl_fn(recv._h, _lib.V_SET_CPU_SHARE, None, [ctypes.c_bool])
fn2(recv._h, True)

buf = bytearray(W * H * 4)
nonzero = 0
ok_count = 0
for i in range(30):
    sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
    if recv.receive():
        ok = recv.receive_image(buf, W, H, GL_RGBA)
        if ok:
            ok_count += 1
            if any(b != 0 for b in buf[::1024]):
                nonzero += 1
    time.sleep(1/30)

print(f"  receive_image True : {ok_count}")
print(f"  buffer non-zero    : {nonzero}")
print(f"  primi 16 byte      : {bytes(buf[:16]).hex()}")

recv.release()
sender.release()
