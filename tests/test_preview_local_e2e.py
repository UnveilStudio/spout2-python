"""
E2E test per preview_local.py:
1. Lancia preview_local in subprocess
2. Apre la SHM stessa
3. Aspetta qualche frame, salva l'immagine ricevuta su disk
4. Verifica che il PNG salvato non sia tutto zero (= contiene il logo)
"""
from __future__ import annotations
import multiprocessing.shared_memory as smm
import secrets
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Per il test usiamo direttamente la funzione sender_main, senza UI cv2
sys.path.insert(0, str(ROOT))
from examples.preview_local import sender_main, SHM_HEADER, MAGIC, W, H

SHM_NAME = f"e2etest_{secrets.token_hex(4)}"
SPOUT_NAME = f"E2EPreview_{secrets.token_hex(2)}"
SIZE = SHM_HEADER + W * H * 4

print(f"E2E preview_local — shm='{SHM_NAME}'\n")
shm = smm.SharedMemory(name=SHM_NAME, create=True, size=SIZE)
header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf[:SHM_HEADER])
pixels = np.ndarray((H, W, 4), dtype=np.uint8,
                    buffer=shm.buf[SHM_HEADER:SHM_HEADER + H * W * 4])

# Lancia sender in subprocess
sender_proc = subprocess.Popen(
    [sys.executable, "-u", "-c",
     f"import sys; sys.path.insert(0, r'{ROOT}'); "
     f"from examples.preview_local import sender_main; "
     f"sender_main(r'{SHM_NAME}', r'{SPOUT_NAME}', {W}, {H})"],
    cwd=str(ROOT),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

# Aspetta MAGIC
deadline = time.time() + 8.0
while time.time() < deadline and header[0] != MAGIC:
    time.sleep(0.05)
if header[0] != MAGIC:
    print("FAIL: sender non si e' avviato")
    sender_proc.terminate()
    sys.exit(1)

print(f"sender attivo. magic=0x{int(header[0]):08x}  res={header[2]}x{header[3]}")

# Aspetta che arrivino almeno 5 frame
deadline = time.time() + 5.0
while time.time() < deadline and header[1] < 5:
    time.sleep(0.05)

frame_no = int(header[1])
print(f"frame ricevuti: {frame_no}")

# Salvo il frame corrente
out = ROOT / "tests" / "e2e_frame.png"
bgr = cv2.cvtColor(pixels, cv2.COLOR_RGBA2BGR)
cv2.imwrite(str(out), bgr)
nonzero = int(np.count_nonzero(bgr))
total = bgr.size
print(f"frame salvato: {out}  (non-zero pixels: {nonzero}/{total} = {nonzero/total*100:.1f}%)")

# Verifica: il logo deve avere contenuto != 0
if nonzero > total * 0.05:
    print("\n>>> SUCCESSO: il frame contiene contenuto reale (>5% non-zero)")
    rc = 0
else:
    print("\n>>> FAIL: frame quasi tutto zero")
    rc = 1

# Cleanup
sender_proc.terminate()
try:
    sender_proc.wait(timeout=3)
except subprocess.TimeoutExpired:
    sender_proc.kill()
shm.close()
shm.unlink()
sys.exit(rc)
