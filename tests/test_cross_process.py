"""
Test cross-process: sender Python in un processo, receiver Python in un altro.

Verifica empiricamente:
  1. Il receiver vede il sender nella lista (shared-memory directory IPC)
  2. SpoutUtils.get_sender_info() ritorna dimensioni corrette
  3. SpoutReceiver.receive() torna True (handshake metadata)
  4. SpoutReceiver.receive_image() copia davvero i pixel oppure no?
     (verifichiamo che il buffer non sia tutto zero)

Risultato atteso secondo README: il transfer pixel CROSS-PROCESS Python<->Python
NON funziona perche' SpoutLibrary's GL/DX shared-texture handshake non e' esposto
a ctypes / contesti OpenGL standalone (gldx_compatible = False) e il fallback
CPU-share droppa silenziosamente i frame.

Vogliamo confermare con dati effettivi.
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Avvia sender in subprocess con nome univoco per evitare collisioni con
    # entry stale nella shared mem directory.
    import secrets
    unique_name = f"PyTest_{secrets.token_hex(4)}"

    sender_inline = (
        f"import sys; sys.path.insert(0, r'{ROOT}')\n"
        "import time, numpy as np\n"
        "from spout import SpoutSender, GL_RGBA\n"
        "W, H = 320, 240\n"
        f"with SpoutSender('{unique_name}') as s:\n"
        "    rgba = np.zeros((H, W, 4), dtype=np.uint8)\n"
        "    rgba[..., 0] = 255  # solid red\n"
        "    rgba[..., 3] = 255\n"
        "    while True:\n"
        "        s.send_image(rgba.tobytes(), W, H, GL_RGBA)\n"
        "        time.sleep(1/30)\n"
    )
    print(f"== Lancio sender '{unique_name}' ==\n")
    sender_proc = subprocess.Popen(
        [sys.executable, "-u", "-c", sender_inline],
        cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )

    # Lascio tempo al sender per registrarsi nella shared mem directory
    time.sleep(3.0)

    try:
        sys.path.insert(0, str(ROOT))
        from spout import SpoutReceiver, SpoutUtils, GL_RGBA

        # ----- Step 1: verifico che il sender e' visibile via shared mem dir
        with SpoutUtils() as utils:
            senders = utils.get_all_senders()
            print(f"Senders attivi: {senders}")
            print(f"Sender attivo : {utils.get_active_sender()!r}")
            print(f"# adapters    : {utils.get_num_adapters()}")
            print(f"GL/DX ready   : {utils.is_gldx_ready()}")
            info = utils.get_sender_info(unique_name)
            print(f"sender_info({unique_name}) = {info}")

        if not info:
            print("[FAIL] Sender non visibile via shared memory directory!")
            return

        w, h, share_handle, fmt = info
        print(f"\n  W x H        = {w} x {h}")
        print(f"  share handle = 0x{share_handle:016x}" if share_handle else "  share handle = 0")
        print(f"  DXGI format  = {fmt}")

        # ----- Step 1.5: stato del sender lato Python (seconda istanza)
        print("\n== Stato sender Python (introspezione) ==")
        try:
            from spout import SpoutSender
            # NON creo un nuovo sender — solo controllo la prima istanza esiste gia'
            # Lo introspetto leggendo via shared memory tramite SpoutUtils
            with SpoutUtils() as u2:
                print(f"  active = {u2.get_active_sender()!r}")
                print(f"  count  = {u2.get_sender_count()}")
        except Exception as e:
            print(f"  errore introspezione: {e!r}")

        # ----- Step 2: provo SpoutReceiver e analizzo il pixel buffer
        print("\n== SpoutReceiver test ==")
        with SpoutReceiver(unique_name) as rcv:
            buf = bytearray(w * h * 4)
            success_frames = 0
            zero_frames = 0
            nonzero_frames = 0
            connected_count = 0
            samples = []

            for i in range(40):
                connected = rcv.receive()
                if connected:
                    connected_count += 1
                    if rcv.is_updated or i == 0:
                        new_w = rcv.sender_width
                        new_h = rcv.sender_height
                        if new_w * new_h * 4 != len(buf):
                            buf = bytearray(new_w * new_h * 4)
                            w, h = new_w, new_h

                    ok = rcv.receive_image(buf, w, h, GL_RGBA)
                    if ok:
                        success_frames += 1
                        nonzero = sum(1 for b in buf[::1024] if b != 0)  # campiono ogni 1024 byte
                        if nonzero > 0:
                            nonzero_frames += 1
                            if len(samples) < 3:
                                # primi 16 byte come campione
                                samples.append(bytes(buf[:16]).hex())
                        else:
                            zero_frames += 1
                time.sleep(0.05)

            print(f"\n  poll iterazioni        : 40")
            print(f"  receive() True         : {connected_count}")
            print(f"  receive_image() True   : {success_frames}")
            print(f"  buffer non-zero        : {nonzero_frames}")
            print(f"  buffer tutto zero      : {zero_frames}")
            if samples:
                print(f"  campioni primi 16 byte : {samples}")

            # Diagnostica (protetta: alcuni getter segfaltano su disconnessione)
            print("\n  -- diagnostica receiver --")
            try:
                print(f"  rcv.is_connected     = {rcv.is_connected}")
            except Exception as e:
                print(f"  is_connected ERR    : {e!r}")
            try:
                print(f"  rcv.sender_width     = {rcv.sender_width}")
                print(f"  rcv.sender_height    = {rcv.sender_height}")
            except Exception as e:
                print(f"  width/height ERR    : {e!r}")
            try:
                print(f"  rcv.sender_cpu       = {rcv.sender_cpu}")
                print(f"  rcv.sender_gldx      = {rcv.sender_gldx}")
            except Exception as e:
                print(f"  cpu/gldx ERR        : {e!r}")

        # ----- Verdetto
        print("\n== VERDETTO ==")
        if nonzero_frames == 0:
            print("CONFERMATA la limitazione: receive_image NON copia pixel reali")
            print("(buffer sempre zero) malgrado handshake metadata funzioni.")
        else:
            print("SORPRESA: alcuni frame sono arrivati con dati! Le note erano sbagliate.")

    finally:
        print("\n== Stoppo sender ==")
        sender_proc.terminate()
        try:
            out, _ = sender_proc.communicate(timeout=3)
            print("ultime righe sender stdout:")
            for line in (out or "").strip().splitlines()[-5:]:
                print(f"  > {line}")
        except subprocess.TimeoutExpired:
            sender_proc.kill()


if __name__ == "__main__":
    main()
