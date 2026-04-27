# AGENTS.md — Guida rapida per agenti AI

Questo file aiuta un agente (Claude Code, Cursor, Copilot, ecc.) a usare
`spout2-python` correttamente al primo colpo, senza dover leggere tutto il
codice sorgente.

## TL;DR

- `spout2-python` espone tre classi: `SpoutSender`, `SpoutReceiver`, `SpoutUtils`.
- È un wrapper `ctypes` su `SpoutLibrary.dll` (Spout2 v2.007.017).
- **Solo Windows x64.** Su altri OS l'import fallisce subito con `OSError`.
- I pixel viaggiano come buffer `bytes` / `bytearray` / `ctypes` array, in
  formato `GL_RGBA` (default) o `GL_BGRA` / `GL_BGRA_EXT`.
- Origine OpenGL = bottom-left. Se i tuoi pixel sono top-down (PIL, numpy,
  PyTorch standard) passa `invert=True` su `send_image` e `receive_image`.

## Installazione

```bash
pip install git+https://github.com/UnveilStudio/spout2-python.git
# opzionali:
pip install "git+https://github.com/UnveilStudio/spout2-python.git#egg=spout2-python[torch]"
pip install "git+https://github.com/UnveilStudio/spout2-python.git#egg=spout2-python[image]"
```

Niente da configurare: `SpoutLibrary.dll` è bundled e caricata automaticamente
da `spout/_lib.py`.

## Pattern di uso

### Sender — ciclo standard

```python
from spout import SpoutSender, GL_RGBA

W, H = 640, 480
with SpoutSender("MySender") as sender:
    while running:
        rgba_bytes = produce_frame(W, H)        # len == W*H*4
        sender.send_image(rgba_bytes, W, H, GL_RGBA, invert=False)
```

Note:
- `send_image` richiede un OpenGL context. Se la tua app non ne ha uno
  (es. script CLI puro), guarda `examples/share_image.py` che chiama
  `CreateOpenGL()` via vtable.
- Riusa lo stesso buffer fra i frame quando possibile (allocazione zero).

### Receiver — poll loop

```python
from spout import SpoutReceiver, GL_RGBA

with SpoutReceiver("MySender") as receiver:
    buf = None
    while running:
        if not receiver.receive():
            continue                               # nessun frame nuovo
        if receiver.is_updated or buf is None:
            W, H = receiver.sender_width, receiver.sender_height
            buf  = bytearray(W * H * 4)
        receiver.receive_image(buf, W, H, GL_RGBA)
        process(buf, W, H)
```

Note:
- `receive()` non copia pixel — è solo un check di stato.
- `receive_image(buffer, ...)` copia i pixel nel buffer del chiamante.
- Controlla `receiver.is_updated` dopo `receive()` per ri-allocare quando il
  sender cambia risoluzione.

### Tensor / inference (PyTorch)

Vedi `examples/tensor_send.py`, `examples/tensor_receive.py` e
`examples/inference_loop.py` per il loop completo Spout → modello → Spout.
Pattern chiave: `np.ascontiguousarray` + `(ctypes.c_ubyte * size).from_buffer(arr)`
per ottenere zero-copy in entrambe le direzioni.

## Cose da NON fare

- **Non riordinare i `V_*` in `spout/_lib.py`.** Sono indici vtable della DLL
  e devono matchare l'ordine di dichiarazione in `SpoutLibrary.h`. Lo slot 98
  nella DLL v2.007.017 è un metodo non documentato — riordinare significa
  rompere tutto silenziosamente.
- **Non importare `spout` su Linux/macOS** sperando che funzioni: `_lib.py`
  controlla `sys.platform == "win32"` e solleva `OSError`.
- **Non passare buffer più piccoli di `W*H*4`** a `send_image` /
  `receive_image`: la DLL non valida la lunghezza e leggerà out-of-bounds.
- **Non chiamare `SpoutSender` / `SpoutReceiver` senza chiudere**: usa
  `with` o `__del__` farà il cleanup, ma context manager è più sicuro.

## Riferimenti

- Spout2 upstream: https://github.com/leadedge/Spout2
- Header originale (per indici vtable): `Spout2-SDK/SPOUTSDK/SpoutLibrary/SpoutLibrary.h`
- Note dettagliate sul vtable dispatch: `CLAUDE.md`
