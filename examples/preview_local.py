"""
preview_local.py - Demo end-to-end full Python: sender + receiver visivo.

Pattern:
  1. Un subprocess "sender" pubblica frame animati su Spout (per TouchDesigner/
     OBS/etc) e in parallelo li scrive in una shared memory standard di
     Python (multiprocessing.shared_memory).
  2. Il main process apre quella shared memory, legge i frame come numpy view
     e li mostra con cv2.imshow().

Perche' due canali invece che solo Spout?
  Il fallback CPU-share di SpoutLibrary, l'unico modo di trasferire pixel
  senza un GL/DX-interop hardware compatibile, NON funziona fra due istanze
  Python (testato in tests/test_with_opengl.py: receiver buffer rimane sempre
  zero anche con CreateOpenGL su entrambi i lati). La shared memory di Python
  e' invece nativa, semplice, zero-copy e abbastanza veloce per qualsiasi
  risoluzione realistica (8 MB/frame @1080p RGBA).

Esegui:
  python examples/preview_local.py
  -> finestra cv2 con il logo Unveil che pulsa.
  Premi 'q' per chiudere.
"""
from __future__ import annotations

import multiprocessing.shared_memory as smm
import os
import secrets
import struct
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

W, H = 640, 480
FPS = 30
SHM_HEADER = 16  # 4 uint32: magic, frame_no, w, h
MAGIC = 0x53504F55  # "SPOU"


def sender_main(shm_name: str, spout_name: str, w: int, h: int):
    """Eseguito in subprocess: pubblica su Spout + scrive in shared memory."""
    sys.path.insert(0, str(ROOT))
    from spout import SpoutSender, GL_RGBA  # noqa: E402

    # Apri shm condivisa (creata dal main)
    shm = smm.SharedMemory(name=shm_name)
    header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf[:SHM_HEADER])
    pixels = np.ndarray((h, w, 4), dtype=np.uint8,
                        buffer=shm.buf[SHM_HEADER:SHM_HEADER + h * w * 4])
    header[0] = MAGIC
    header[2] = w
    header[3] = h

    # Carica logo bundled e fai fit
    logo_path = ROOT / "assets" / "unveil_logo.png"
    if logo_path.exists():
        img = cv2.imread(str(logo_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            img = np.full((h, w, 4), 64, dtype=np.uint8)
        # Il logo bundled e' un PNG 16-bit (uint16). Riportalo a 8-bit prima
        # di qualsiasi altra operazione, altrimenti BGR2RGBA + resize generano
        # pattern moire' visibili.
        if img.dtype == np.uint16:
            img = (img >> 8).astype(np.uint8)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        # Fit inside w x h preservando aspect
        ih, iw = img.shape[:2]
        scale = min(w / iw, h / ih) * 0.85
        nw, nh = int(iw * scale), int(ih * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        bg = np.zeros((h, w, 4), dtype=np.uint8)
        ox, oy = (w - nw) // 2, (h - nh) // 2
        bg[oy:oy + nh, ox:ox + nw] = resized
        # Convert BGRA -> RGBA per uniformita'
        base = cv2.cvtColor(bg, cv2.COLOR_BGRA2RGBA)
    else:
        base = np.zeros((h, w, 4), dtype=np.uint8)
        base[..., 1] = 200
    base[..., 3] = 255

    print(f"[sender] avviato. Spout='{spout_name}'  shm='{shm_name}'  {w}x{h} @ {FPS}fps", flush=True)

    sender = SpoutSender(spout_name)
    interval = 1.0 / FPS
    frame_no = 0

    # Pre-calcolo coordinate per overlay barra di scansione animata
    xs = np.arange(w)
    try:
        while True:
            t0 = time.perf_counter()

            # Logo statico a piena luminosita'
            frame = base.copy()

            # Overlay: barra orizzontale che scorre alto-basso (dimostra fps live)
            phase = (frame_no / FPS) % 2.0
            y_band = int((np.sin(phase * np.pi) * 0.5 + 0.5) * (h - 1))
            band_h = 6
            y0, y1 = max(0, y_band - band_h), min(h, y_band + band_h)
            # blend additivo ciano semitrasparente
            frame[y0:y1, :, 0] = np.minimum(255, frame[y0:y1, :, 0].astype(np.uint16) +  20)
            frame[y0:y1, :, 1] = np.minimum(255, frame[y0:y1, :, 1].astype(np.uint16) + 120)
            frame[y0:y1, :, 2] = np.minimum(255, frame[y0:y1, :, 2].astype(np.uint16) + 180)
            frame[..., 3] = 255

            # 1) Pubblica su Spout (verra' visto da TD/OBS/etc)
            sender.send_image(frame.tobytes(), w, h, GL_RGBA)

            # 2) Scrivi nella shared memory locale per il receiver Python
            pixels[...] = frame
            header[1] = frame_no  # frame counter (segnala "nuovo frame")

            frame_no += 1
            elapsed = time.perf_counter() - t0
            time.sleep(max(0.0, interval - elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        sender.release()
        shm.close()
        print("[sender] chiuso.", flush=True)


def main():
    shm_name = f"sp2py_{secrets.token_hex(4)}"
    spout_name = f"PythonPreview_{os.getpid()}"
    size = SHM_HEADER + W * H * 4

    print(f"== preview_local ==")
    print(f"  Spout sender    : '{spout_name}'  (apri TouchDesigner/OBS per riceverlo)")
    print(f"  Shared memory   : '{shm_name}'  ({size} byte)")
    print(f"  Risoluzione     : {W}x{H} @ {FPS} fps")
    print(f"  Premi 'q' nella finestra preview per chiudere.\n")

    # Crea shared memory
    shm = smm.SharedMemory(name=shm_name, create=True, size=size)
    header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf[:SHM_HEADER])
    pixels = np.ndarray((H, W, 4), dtype=np.uint8,
                        buffer=shm.buf[SHM_HEADER:SHM_HEADER + H * W * 4])
    header[0] = 0  # magic non ancora settato

    # Lancia sender in subprocess
    sender_proc = subprocess.Popen(
        [sys.executable, "-u", "-c",
         f"import sys; sys.path.insert(0, r'{ROOT}'); "
         f"from examples.preview_local import sender_main; "
         f"sender_main(r'{shm_name}', r'{spout_name}', {W}, {H})"],
        cwd=str(ROOT),
    )

    # Attendi inizializzazione del sender (header magic = MAGIC)
    deadline = time.time() + 5.0
    while time.time() < deadline and header[0] != MAGIC:
        time.sleep(0.05)
    if header[0] != MAGIC:
        print("[main] sender non si e' avviato in tempo", file=sys.stderr)
        sender_proc.terminate()
        shm.close()
        shm.unlink()
        return 1

    print("[main] sender attivo. Apertura finestra preview...\n")

    cv2.namedWindow("Spout preview (Python)", cv2.WINDOW_AUTOSIZE)
    last_frame = -1
    fps_timer = time.perf_counter()
    fps_count = 0
    fps_text = ""

    try:
        while True:
            cur_frame = int(header[1])
            if cur_frame != last_frame:
                last_frame = cur_frame
                # numpy view RGBA -> BGR per cv2
                bgr = cv2.cvtColor(pixels, cv2.COLOR_RGBA2BGR)
                # Overlay info FPS
                if fps_text:
                    cv2.putText(bgr, fps_text, (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("Spout preview (Python)", bgr)
                fps_count += 1
                if time.perf_counter() - fps_timer >= 1.0:
                    fps_text = f"frame {cur_frame}  rx_fps {fps_count}"
                    fps_count = 0
                    fps_timer = time.perf_counter()

            # Esci se l'utente preme 'q' oppure chiude la finestra
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if cv2.getWindowProperty("Spout preview (Python)",
                                     cv2.WND_PROP_VISIBLE) < 1:
                break
            if sender_proc.poll() is not None:
                print("[main] sender e' uscito.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        sender_proc.terminate()
        try:
            sender_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sender_proc.kill()
        shm.close()
        shm.unlink()
        print("[main] cleanup completo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
