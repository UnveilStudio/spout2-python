"""
Probe slot 98 della DLL v2.007.017 — il claim e' che e' un metodo extra
non documentato che shifta il resto della vtable di +1 fino a slot ~105.

Strategia: confronto comportamento di slot 98..107 con DLL e con header.
Se il claim e' giusto:
  98 = ??? (extra)
  99 = GetSDKversion (header pos 98)
  100 = IsLaptop (header pos 99)
  101 = GetCurrentModule (header pos 100)
  102 = GetExeVersion (header pos 101)
  103 = GetExePath (header pos 102)
  104 = GetExeName (header pos 103)
  105 = GetPath OR GetName (header pos 104 o 105 — uno rimosso)
  106 = StartTiming (header pos 106 — riallineato)
  107 = EndTiming (header pos 107)
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe_slot(slot: int, restype: str, argstr: str = "[]", call_args: str = "h"):
    """Chiama slot con un determinato restype e argstr in subprocess fresco."""
    code = f"""
import sys, ctypes
sys.path.insert(0, r'{ROOT}')
from spout import _lib
h = _lib._create_handle()
fn = _lib._vtbl_fn(h, {slot}, {restype}, {argstr})
v = fn({call_args})
print('result=', repr(v))
"""
    p = subprocess.run([sys.executable, "-u", "-c", code],
                       capture_output=True, text=True, cwd=str(ROOT))
    out = p.stdout.strip()
    err_tail = p.stderr.strip().splitlines()[-1:] if p.stderr.strip() else []
    return p.returncode, out, err_tail


print("== Probe slot 98..108 con vari restype ==\n")

for slot in range(98, 109):
    print(f"--- slot {slot} ---")
    # void()
    rc, out, err = probe_slot(slot, "None")
    print(f"  void():       exit={rc:>11d}  {out}")
    # bool()
    rc, out, err = probe_slot(slot, "ctypes.c_bool")
    print(f"  bool():       exit={rc:>11d}  {out}")
    # int()
    rc, out, err = probe_slot(slot, "ctypes.c_int")
    print(f"  int():        exit={rc:>11d}  {out}")
    # void_p() (handle/string ptr)
    rc, out, err = probe_slot(slot, "ctypes.c_void_p")
    print(f"  void_p():     exit={rc:>11d}  {out}")
    # double() with args (bool, bool) - matches EndTiming
    rc, out, err = probe_slot(
        slot, "ctypes.c_double",
        "[ctypes.c_bool, ctypes.c_bool]",
        "h, False, False"
    )
    print(f"  double(b,b):  exit={rc:>11d}  {out}")
    print()
