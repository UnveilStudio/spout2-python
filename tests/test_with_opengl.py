"""
Sender + Receiver con CreateOpenGL() esplicito (vtable slot 151)
prima di send/receive.
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

W, H = 320, 240
NAME = f"GL_{secrets.token_hex(2)}"

print(f"=== Test con CreateOpenGL() forzato, '{NAME}' ===\n")

sender = SpoutSender(NAME)

# Bring-up GL context
fn_create = _lib._vtbl_fn(sender._h, _lib.V_CREATE_OPENGL, ctypes.c_bool, [ctypes.c_void_p])
gl_ok = bool(fn_create(sender._h, None))
print(f"  CreateOpenGL  : {gl_ok}")
print(f"  IsGLDXready   : {_lib._vtbl_fn(sender._h, _lib.V_IS_GLDX_READY, ctypes.c_bool, [])(sender._h)}")

rgba = np.zeros((H, W, 4), dtype=np.uint8)
rgba[..., 0] = 200
rgba[..., 1] = 100
rgba[..., 3] = 255

for i in range(8):
    ok = sender.send_image(rgba.tobytes(), W, H, GL_RGBA)
    if i == 0:
        print(f"  primo send -> {ok}")
        print(f"  is_initialized={sender.is_initialized}")
        print(f"  gldx_compatible={sender.gldx_compatible}")
        print(f"  cpu_share={sender.cpu_share}")
    time.sleep(0.05)

# Receiver
print("\n-- Receiver --")
recv = SpoutReceiver(NAME)
fn_create2 = _lib._vtbl_fn(recv._h, _lib.V_CREATE_OPENGL, ctypes.c_bool, [ctypes.c_void_p])
print(f"  CreateOpenGL  : {bool(fn_create2(recv._h, None))}")

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
    time.sleep(0.03)

print(f"\n  receive_image True : {ok_count}")
print(f"  buffer non-zero    : {nonzero}")
print(f"  primi 16 byte      : {bytes(buf[:16]).hex()}")
print(f"  recv.is_connected  : {recv.is_connected}")
print(f"  recv.sender_cpu    : {recv.sender_cpu}")
print(f"  recv.sender_gldx   : {recv.sender_gldx}")

# Cleanup OpenGL
fn_close = _lib._vtbl_fn(sender._h, _lib.V_CLOSE_OPENGL, ctypes.c_bool, [])
fn_close(sender._h)
recv.release()
sender.release()
