"""
Audit esaustivo della vtable di SpoutLibrary.dll v2.007.017.

Strategia: ogni call vtable potenzialmente pericolosa gira in un subprocess
separato, così un segfault nativo non distrugge il report.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_in_subprocess(code: str, timeout: float = 10.0) -> dict:
    """Esegue *code* in un python -c child. Ritorna {ok, exit, stdout, stderr}."""
    proc = subprocess.run(
        [sys.executable, "-u", "-c", code],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(ROOT),
    )
    return {
        "exit": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "ok": proc.returncode == 0,
    }


def probe(label: str, body: str, expect_print: bool = True) -> dict:
    """Esegue body in subprocess. Body deve usare _lib + stampare il risultato."""
    code = (
        "import sys, ctypes\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        "from spout import _lib\n"
        "h = _lib._create_handle()\n"
        f"{body}\n"
    )
    r = run_in_subprocess(code)
    out = {"label": label, **r}
    print(f"[{ 'OK ' if r['ok'] else 'CRASH'}] exit={r['exit']:>4d}  {label}")
    if r["stdout"]:
        for line in r["stdout"].splitlines():
            print(f"     stdout: {line}")
    if r["stderr"] and not r["ok"]:
        # Solo le ultime 3 righe di stderr per non inquinare
        for line in r["stderr"].splitlines()[-3:]:
            print(f"     stderr: {line}")
    return out


def main():
    REPORT = []

    print(f"== DLL: {ROOT / 'spout' / 'SpoutLibrary.dll'} ==\n")

    # ----- BLOCCO 1: getter stateless che NON richiedono init ------------
    print("=== BLOCCO 1: getter stateless ===")

    blocco1 = [
        ("V_IS_INITIALIZED(6)",     "fn=_lib._vtbl_fn(h,6,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_UPDATED(20)",        "fn=_lib._vtbl_fn(h,20,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_CONNECTED(21)",      "fn=_lib._vtbl_fn(h,21,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_FRAME_NEW(22)",      "fn=_lib._vtbl_fn(h,22,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_FRAME_COUNT_ENABLED(39)", "fn=_lib._vtbl_fn(h,39,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_REFRESH_RATE(41)",  "fn=_lib._vtbl_fn(h,41,ctypes.c_double,[]); print(fn(h))"),
        ("V_IS_FRAME_SYNC_ENABLED(46)", "fn=_lib._vtbl_fn(h,46,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_VERTICAL_SYNC(47)", "fn=_lib._vtbl_fn(h,47,ctypes.c_int,[]); print(fn(h))"),
        ("V_LOGS_ENABLED(63)",      "fn=_lib._vtbl_fn(h,63,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_LOG_FILE_ENABLED(64)",  "fn=_lib._vtbl_fn(h,64,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_LAPTOP(100)",        "fn=_lib._vtbl_fn(h,100,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_CURR_MODULE(101)",  "fn=_lib._vtbl_fn(h,101,ctypes.c_void_p,[]); print(hex(fn(h) or 0))"),
        ("V_GET_SENDER_COUNT(111)", "fn=_lib._vtbl_fn(h,111,ctypes.c_int,[]); print(fn(h))"),
        ("V_GET_BUFFER_MODE(117)",  "fn=_lib._vtbl_fn(h,117,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_BUFFERS(119)",      "fn=_lib._vtbl_fn(h,119,ctypes.c_int,[]); print(fn(h))"),
        ("V_GET_MAX_SENDERS(121)",  "fn=_lib._vtbl_fn(h,121,ctypes.c_int,[]); print(fn(h))"),
        ("V_GET_DX9(127)",          "fn=_lib._vtbl_fn(h,127,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_MEM_SHARE(129)",    "fn=_lib._vtbl_fn(h,129,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_CPU_MODE(131)",     "fn=_lib._vtbl_fn(h,131,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_SHARE_MODE(133)",   "fn=_lib._vtbl_fn(h,133,ctypes.c_int,[]); print(fn(h))"),
        ("V_GET_AUTO_SHARE(135)",   "fn=_lib._vtbl_fn(h,135,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_IS_GLDX_READY(138)",    "fn=_lib._vtbl_fn(h,138,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_NUM_ADAPTERS(139)", "fn=_lib._vtbl_fn(h,139,ctypes.c_int,[]); print(fn(h))"),
        ("V_GET_ADAPTER(142)",      "fn=_lib._vtbl_fn(h,142,ctypes.c_int,[]); print(fn(h))"),
        ("V_IS_PREF_AVAIL(149)",    "fn=_lib._vtbl_fn(h,149,ctypes.c_bool,[]); print(bool(fn(h)))"),
        ("V_GET_DX11_FORMAT(159)",  "fn=_lib._vtbl_fn(h,159,ctypes.c_int,[]); print(fn(h))"),
    ]

    for label, body in blocco1:
        REPORT.append(probe(label, body))

    # ----- BLOCCO 2: slot 98 — claim "extra undocumented" ----------------
    print("\n=== BLOCCO 2: claim slot 98 extra ===")

    # Se il claim è vero, slot 98 è uno slot non documentato (probabilmente bool/void)
    # e GetSDKversion (header pos 98) sta a slot 99.
    # Test: se chiamiamo slot 99 come std::string method (passando un buffer
    # output), può crashare. Ma chiamarlo come "void()" dovrebbe essere safe.
    # Slot 100 = IsLaptop (header 99) — dovrebbe ritornare bool ragionevole.

    REPORT.append(probe(
        "SLOT_98 chiamato come bool()",
        "fn=_lib._vtbl_fn(h,98,ctypes.c_bool,[]); print('result=',bool(fn(h)))",
    ))

    # Verifico che 100 = IsLaptop dia un risultato bool sensato
    REPORT.append(probe(
        "SLOT_100 (claim: IsLaptop)",
        "fn=_lib._vtbl_fn(h,100,ctypes.c_bool,[]); print('IsLaptop=',bool(fn(h)))",
    ))

    # Verifico che 106/107 = StartTiming/EndTiming (allineati, no shift)
    REPORT.append(probe(
        "SLOT_106 (StartTiming) -> SLOT_107 (EndTiming)",
        ("fn1=_lib._vtbl_fn(h,106,None,[]); fn1(h);"
         " fn2=_lib._vtbl_fn(h,107,ctypes.c_double,[ctypes.c_bool,ctypes.c_bool]);"
         " v=fn2(h,False,False); print('elapsed_us=',v)"),
    ))

    # ----- BLOCCO 3: GL/DX context bringup -------------------------------
    print("\n=== BLOCCO 3: bring-up OpenGL ===")

    # Prova ciclo CreateOpenGL -> IsGLDXready -> GetGLDX -> CloseOpenGL
    REPORT.append(probe(
        "CreateOpenGL -> IsGLDXready -> CloseOpenGL",
        (
            "fn=_lib._vtbl_fn(h,151,ctypes.c_bool,[ctypes.c_void_p])\n"
            "ok=bool(fn(h,None)); print('CreateOpenGL=',ok)\n"
            "ready=_lib._vtbl_fn(h,138,ctypes.c_bool,[]); print('IsGLDXready=',bool(ready(h)))\n"
            "gldx=_lib._vtbl_fn(h,14,ctypes.c_bool,[]); print('GetGLDX=',bool(gldx(h)))\n"
            "cpu=_lib._vtbl_fn(h,13,ctypes.c_bool,[]); print('GetCPU=',bool(cpu(h)))\n"
            "tex=_lib._vtbl_fn(h,110,ctypes.c_uint,[]); print('GetSharedTextureID=',tex(h))\n"
            "fnc=_lib._vtbl_fn(h,152,ctypes.c_bool,[]); print('CloseOpenGL=',bool(fnc(h)))"
        ),
    ))

    # ----- BLOCCO 4: DirectX bringup -------------------------------------
    print("\n=== BLOCCO 4: bring-up DirectX 11 ===")

    REPORT.append(probe(
        "OpenDirectX -> OpenDirectX11 -> GetDX11Device/Context -> CloseDirectX11",
        (
            "fn1=_lib._vtbl_fn(h,165,ctypes.c_bool,[]); print('OpenDirectX=',bool(fn1(h)))\n"
            "fn2=_lib._vtbl_fn(h,167,ctypes.c_bool,[ctypes.c_void_p]); print('OpenDirectX11=',bool(fn2(h,None)))\n"
            "fn3=_lib._vtbl_fn(h,169,ctypes.c_void_p,[]); d=fn3(h); print('DX11Device=',hex(d or 0))\n"
            "fn4=_lib._vtbl_fn(h,170,ctypes.c_void_p,[]); c=fn4(h); print('DX11Context=',hex(c or 0))\n"
            "fn5=_lib._vtbl_fn(h,168,None,[]); fn5(h); print('CloseDirectX11=ok')"
        ),
    ))

    # ----- BLOCCO 5: enumerazione sender (richiede sender attivo) --------
    print("\n=== BLOCCO 5: enumerazione sender ===")

    REPORT.append(probe(
        "GetSenderCount + iterazione GetSender",
        (
            "fn=_lib._vtbl_fn(h,111,ctypes.c_int,[]); n=fn(h); print('count=',n)\n"
            "fn2=_lib._vtbl_fn(h,112,ctypes.c_bool,[ctypes.c_int,ctypes.c_char_p,ctypes.c_int])\n"
            "import ctypes as C\n"
            "for i in range(n):\n"
            "    b=C.create_string_buffer(256)\n"
            "    ok=fn2(h,i,b,256); print(f'  [{i}] ok={bool(ok)} name={b.value!r}')"
        ),
    ))

    REPORT.append(probe(
        "GetActiveSender",
        (
            "import ctypes as C; b=C.create_string_buffer(256)\n"
            "fn=_lib._vtbl_fn(h,115,ctypes.c_bool,[ctypes.c_char_p]); ok=fn(h,b)\n"
            "print('ok=',bool(ok),'name=',b.value)"
        ),
    ))

    # ----- BLOCCO 6: adapter info ----------------------------------------
    print("\n=== BLOCCO 6: adapter info ===")

    REPORT.append(probe(
        "GetNumAdapters + iterazione GetAdapterName",
        (
            "fn=_lib._vtbl_fn(h,139,ctypes.c_int,[]); n=fn(h); print('num_adapters=',n)\n"
            "fn2=_lib._vtbl_fn(h,140,ctypes.c_bool,[ctypes.c_int,ctypes.c_char_p,ctypes.c_int])\n"
            "import ctypes as C\n"
            "for i in range(n):\n"
            "    b=C.create_string_buffer(256)\n"
            "    ok=fn2(h,i,b,256); print(f'  [{i}] ok={bool(ok)} name={b.value!r}')\n"
            "cur=_lib._vtbl_fn(h,141,ctypes.c_char_p,[])\n"
            "print('AdapterName(current)=',cur(h))"
        ),
    ))

    # ----- BLOCCO 7: shared memory buffer --------------------------------
    print("\n=== BLOCCO 7: shared memory buffer ===")

    REPORT.append(probe(
        "Create/Write/Read/Delete memory buffer",
        (
            "import ctypes as C\n"
            "fnC=_lib._vtbl_fn(h,51,ctypes.c_bool,[ctypes.c_char_p,ctypes.c_int])\n"
            "print('Create=',bool(fnC(h,b'audit_buf',64)))\n"
            "fnSize=_lib._vtbl_fn(h,53,ctypes.c_int,[ctypes.c_char_p])\n"
            "print('Size=',fnSize(h,b'audit_buf'))\n"
            "fnW=_lib._vtbl_fn(h,49,ctypes.c_bool,[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int])\n"
            "print('Write=',bool(fnW(h,b'audit_buf',b'spout-test',10)))\n"
            "rb=C.create_string_buffer(64)\n"
            "fnR=_lib._vtbl_fn(h,50,ctypes.c_int,[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int])\n"
            "n=fnR(h,b'audit_buf',rb,64); print('Read=',n,'data=',rb.raw[:n])\n"
            "fnD=_lib._vtbl_fn(h,52,ctypes.c_bool,[])\n"
            "print('Delete=',bool(fnD(h)))"
        ),
    ))

    # ----- BLOCCO 8: getter problematici (uninit getter -> garbage) ------
    print("\n=== BLOCCO 8: getter problematici (con/senza init) ===")

    # GetName (slot 7) - SEGFAULT NOTO se non inizializzato. Lo lanciamo lo stesso
    # in subprocess per documentarlo.
    REPORT.append(probe(
        "V_GET_NAME(7) UNINIT",
        "fn=_lib._vtbl_fn(h,7,ctypes.c_char_p,[]); print('name=',fn(h))",
    ))
    REPORT.append(probe(
        "V_GET_SENDER_NAME(23) UNINIT",
        "fn=_lib._vtbl_fn(h,23,ctypes.c_char_p,[]); print('sender_name=',fn(h))",
    ))

    # ----- Salva report --------------------------------------------------
    out = ROOT / "tests" / "vtable_audit_report.json"
    out.write_text(json.dumps(REPORT, indent=2))

    ok = sum(1 for r in REPORT if r["ok"])
    crash = sum(1 for r in REPORT if not r["ok"])
    print(f"\n=== TOTALI ===  ok={ok}  crash={crash}  report={out.name}")


if __name__ == "__main__":
    main()
