"""
Verifica empirica: con un GL context reale (pyglet) il receiver Python
ottiene davvero pixel non-zero?
"""
from __future__ import annotations
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pyglet
from pyglet import gl

from spout import SpoutReceiver, SpoutUtils, GL_RGBA

# 1. Avvio sender in subprocess
unique = f"PygletTest_{secrets.token_hex(3)}"
W, H = 320, 240

sender_code = (
    f"import sys; sys.path.insert(0, r'{ROOT}')\n"
    "import time, ctypes, numpy as np\n"
    "import pyglet\n"
    "win = pyglet.window.Window(64, 64, 'snd', visible=False)\n"
    "win.switch_to()\n"
    "from spout import SpoutSender, GL_RGBA\n"
    f"W, H = {W}, {H}\n"
    f"s = SpoutSender('{unique}')\n"
    "rgba = np.zeros((H, W, 4), dtype=np.uint8)\n"
    "rgba[..., 1] = 200; rgba[..., 3] = 255\n"
    "i = 0\n"
    "while True:\n"
    "    win.dispatch_events()\n"
    "    rgba[..., 0] = (i*2) & 0xFF  # red anima\n"
    "    ok = s.send_image(rgba.tobytes(), W, H, GL_RGBA)\n"
    "    if i == 0: print(f'first send ok={ok} init={s.is_initialized} gldx={s.gldx_compatible} cpu={s.cpu_share}', flush=True)\n"
    "    i += 1\n"
    "    time.sleep(1/30)\n"
)
print(f"Lancio sender '{unique}' in subprocess...")
proc = subprocess.Popen([sys.executable, "-u", "-c", sender_code],
                        cwd=str(ROOT), stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)
time.sleep(2.5)

try:
    # 2. Crea pyglet window -> GL context reale
    print("Creo pyglet window per GL context reale...")
    win = pyglet.window.Window(W, H, "test", visible=False)
    win.switch_to()  # make context current
    print(f"  GL_VERSION  = {gl.gl_info.get_version_string()}")
    print(f"  GL_RENDERER = {gl.gl_info.get_renderer()}")
    print(f"  GL_VENDOR   = {gl.gl_info.get_vendor()}")

    # 3. Inizializza SpoutReceiver
    print("\nApro SpoutReceiver...")
    rcv = SpoutReceiver(unique)

    # 4. Loop ricezione
    buf = bytearray(W * H * 4)
    nonzero = 0
    ok_count = 0
    samples = []
    for i in range(60):
        win.dispatch_events()  # tieni vivo il GL context
        if rcv.receive():
            ok = rcv.receive_image(buf, W, H, GL_RGBA)
            if ok:
                ok_count += 1
                if any(b != 0 for b in buf[::1024]):
                    nonzero += 1
                    if len(samples) < 2:
                        samples.append(bytes(buf[:16]).hex())
        time.sleep(0.03)

    print(f"\nrx_image True: {ok_count}/60   non-zero buffer: {nonzero}")
    print(f"is_connected = {rcv.is_connected}")
    print(f"sender_cpu   = {rcv.sender_cpu}")
    print(f"sender_gldx  = {rcv.sender_gldx}")
    if samples:
        print(f"campioni     : {samples}")

    if nonzero > 0:
        print("\n>>> SUCCESSO: GL context reale -> pixel transfer funzionante!")
    else:
        print("\n>>> ANCORA buffer zero — il GL context da solo non basta")

    rcv.release()
    win.close()

finally:
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=3)
        print("\n=== sender stdout ===")
        for line in (out or "").strip().splitlines()[-6:]:
            print(f"  {line}")
    except subprocess.TimeoutExpired:
        proc.kill()
