"""
Forzo memory-share mode (legacy 2.006) tramite SetMemoryShareMode (slot 130).
"""
from __future__ import annotations
import ctypes, secrets, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from spout import SpoutSender, SpoutReceiver, SpoutUtils, GL_RGBA, _lib

W, H = 320, 240
NAME = f"MemShare_{secrets.token_hex(2)}"

print(f"=== Memory-share mode forzato, '{NAME}' ===\n")

# Sender
s = SpoutSender(NAME)
# slot 130 = SetMemoryShareMode(bool)
fn = _lib._vtbl_fn(s._h, _lib.V_SET_MEM_SHARE, ctypes.c_bool, [ctypes.c_bool])
print(f"  SetMemoryShareMode(True) -> {bool(fn(s._h, True))}")
# slot 134 = SetShareMode(int)  0=tex, 1=mem, 2=cpu
fn2 = _lib._vtbl_fn(s._h, _lib.V_SET_SHARE_MODE, None, [ctypes.c_int])
fn2(s._h, 1)
print(f"  SetShareMode(1) called")
# verifica
gsm = _lib._vtbl_fn(s._h, _lib.V_GET_SHARE_MODE, ctypes.c_int, [])(s._h)
gms = _lib._vtbl_fn(s._h, _lib.V_GET_MEM_SHARE, ctypes.c_bool, [])(s._h)
print(f"  GetShareMode={gsm}  GetMemoryShareMode={bool(gms)}")

rgba = np.zeros((H, W, 4), dtype=np.uint8)
rgba[..., 0] = 200; rgba[..., 3] = 255
ok = s.send_image(rgba.tobytes(), W, H, GL_RGBA)
print(f"  send_image -> {ok}  init={s.is_initialized} gldx={s.gldx_compatible} cpu={s.cpu_share}")

for _ in range(5):
    s.send_image(rgba.tobytes(), W, H, GL_RGBA)
    time.sleep(0.05)

# Receiver
print("\n-- Receiver --")
r = SpoutReceiver(NAME)
fn = _lib._vtbl_fn(r._h, _lib.V_SET_MEM_SHARE, ctypes.c_bool, [ctypes.c_bool])
fn(r._h, True)
fn2 = _lib._vtbl_fn(r._h, _lib.V_SET_SHARE_MODE, None, [ctypes.c_int])
fn2(r._h, 1)

buf = bytearray(W * H * 4)
nz = 0; ok_count = 0
for i in range(40):
    s.send_image(rgba.tobytes(), W, H, GL_RGBA)
    if r.receive():
        ok = r.receive_image(buf, W, H, GL_RGBA)
        if ok:
            ok_count += 1
            if any(b != 0 for b in buf[::1024]):
                nz += 1
    time.sleep(0.03)

print(f"  receive_image True: {ok_count}/40   non-zero: {nz}")
print(f"  primi 16 byte     : {bytes(buf[:16]).hex()}")

r.release()
s.release()
