"""
Probe mirato per slot DX11/DX (165-170) per capire perche'
GetDX11Device e GetDX11Context tornano lo stesso indirizzo.

Test: chiamiamo slot 169..172 individualmente in subprocess separati e
confrontiamo i puntatori.
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(code: str):
    p = subprocess.run([sys.executable, "-u", "-c", code],
                       capture_output=True, text=True, cwd=str(ROOT))
    print(f"  exit={p.returncode}")
    if p.stdout.strip():
        for l in p.stdout.strip().splitlines():
            print("  out:", l)
    if p.stderr.strip() and p.returncode != 0:
        for l in p.stderr.strip().splitlines()[-3:]:
            print("  err:", l)


print("== Probe slot DX11/DX (chiamato singolarmente, dopo OpenDirectX11) ==")
for slot in range(165, 175):
    print(f"\n--- slot {slot} as void_p() (no args) ---")
    code = f"""
import sys, ctypes
sys.path.insert(0, r'{ROOT}')
from spout import _lib
h = _lib._create_handle()
# Bring-up DirectX
fn1 = _lib._vtbl_fn(h, 165, ctypes.c_bool, [])
fn2 = _lib._vtbl_fn(h, 167, ctypes.c_bool, [ctypes.c_void_p])
fn1(h); fn2(h, None)
fn = _lib._vtbl_fn(h, {slot}, ctypes.c_void_p, [])
v = fn(h)
print('void_p()=', hex(v or 0))
"""
    run(code)
