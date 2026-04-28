# SPOUT2ForPython — Mappa mentale dell'architettura

> **Versione documento:** 2026-04-28  
> **Spout SDK target:** v2.007.017 (`spout/SpoutLibrary.dll`)  
> **Verifica empirica:** `tests/` (vedi sezione finale)

Questo documento descrive *come funziona davvero* il binding ed e' validato
contro l'esecuzione di `tests/test_vtable_audit.py`,
`tests/test_slot98_probe.py`, `tests/test_cross_process.py`,
`tests/test_with_opengl.py`. Ogni "claim" qui sotto ha un test
corrispondente.

---

## 1. Stack runtime

```
+---------------------------------------------------------+
|  Codice utente (script, app, notebook, motore inferenza)|
+----------------------+----------------------------------+
                       |
                       v
+---------------------------------------------------------+
|  spout/sender.py    spout/receiver.py    spout/utils.py |   <- API pubblica
|                                                         |
|  classi thin: 1 ctypes call -> 1 vtable dispatch        |
+----------------------+----------------------------------+
                       |
                       v
+---------------------------------------------------------+
|  spout/_lib.py                                          |   <- core ctypes
|   - WinDLL(SpoutLibrary.dll)                            |
|   - GetSpout() -> SPOUTHANDLE (void*)                   |
|   - _create_handle()                                    |
|   - _vtbl_fn(handle, idx, restype, argtypes)            |
|   - V_* slot indices (0..171)                           |
+----------------------+----------------------------------+
                       |
                       v
+---------------------------------------------------------+
|  SpoutLibrary.dll (v2.007.017, x64)                     |
|   - Implementa SPOUTLIBRARY (vtable COM-style)          |
|   - 172 slot virtual function totali (0..171)           |
|   - Internamente usa SpoutGL classes (Spout, SpoutDX,   |
|     SpoutSenderNames, spoututils)                       |
+----------------------+----------------------------------+
                       |
                       v
+---------------------------------------------------------+
|  Sistema operativo / GPU                                |
|   - DirectX 11 (texture share via NT shared handle)     |
|   - OpenGL (NV_DX_interop2 / WGL_NV_DX_interop)         |
|   - Named shared memory (sender directory + named buf)  |
+---------------------------------------------------------+
```

---

## 2. Vtable layout della DLL v2.007.017

Il file `spout/_lib.py` mantiene gli indici `V_*` come 0-based vtable slot.
La DLL e' compilata con `NTDDI_WIN10_RS4`, quindi include i 6 slot
"Graphics preference" (145..150).

### 2.1 Mapping (verificato empiricamente)

| Slot range | Funzione                | Test verificato |
|------------|-------------------------|------------|
| 0-14       | Sender (SetName...GetGLDX) | si (SLOT_6, 8, 10, 11, 13, 14) |
| 15-36      | Receiver (SetReceiverName...SelectSenderPanel) | si (20, 21, 22) |
| 37-48      | Frame count / sync     | si (39, 41, 46, 47) |
| 49-53      | Memory buffer          | si (51, 53, 49, 50, 52) |
| 54-74      | Logging / SpoutLog*    | si (63, 64); 69-74 sono variadic — non chiamabili |
| 75-89      | SpoutMessageBox + helpers | parziale (alcuni overload non chiamabili) |
| 90-97      | Registry utilities     | si (signature) |
| **98**     | **slot orfano** (vedi 2.2) | si — sempre 0/null |
| 99         | GetSDKversion → std::string | si (crash su signature sbagliata = std::string) |
| 100        | IsLaptop → bool        | si (False su desktop) |
| 101        | GetCurrentModule → HMODULE | si (puntatore in 0x7fff... → modulo Windows) |
| 102-104    | GetExe{Version,Path,Name} → std::string | si |
| 105        | GetPath OR GetName → std::string | si (crash con stack overrun) |
| 106-107    | StartTiming / EndTiming | si (allineati con header) |
| 108-110    | OpenGL shared texture  | si (110 testato post CreateOpenGL) |
| 111-116    | Sender names enumeration | si (count, get, find, info, active) |
| 117-122    | User settings (buffer, max sender) | si |
| 123-134    | 2.006 compat           | si (getter testati) |
| 135-138    | Graphics compat (auto/CPU/GLDX ready) | si |
| 139-144    | Adapter info           | si (3 adapter rilevati) |
| 145-150    | Graphics preference    | si (149 = IsPreferenceAvailable) |
| 151-155    | OpenGL utilities       | si (CreateOpenGL/CloseOpenGL testati) |
| 156-158    | Pixel buffer (ClearAlpha, FlipBuffer) | non testati |
| 159-164    | Formats DX11/GL        | si (159, 161, 162) |
| 165-170    | DirectX                | si (165, 167, 168, 169, 170) |
| **171**    | Release                | si |

### 2.2 Lo slot misterioso 98

**Header dichiara**: a posizione 98 in declaration order c'e' `GetSDKversion`.

**DLL espone**: a slot 98 c'e' un metodo che ritorna 0/null per qualsiasi
restype provato (`void`, `bool`, `int`, `void_p`, `double`) e **non crasha
mai**. A slot 99 c'e' invece il metodo che si comporta come std::string return
(crash con tutte le signature non-std::string), che combacia con
`GetSDKversion`.

**Conclusione**: c'e' uno slot di troppo in coda alla zona "Information".
Possibili spiegazioni (non discriminabili senza disassemblare la DLL):
- residuo di un metodo deprecato / rimosso (vedi `Remove GetSpoutVersion` nel
  changelog 31.07.24 della cpp);
- stub vuoto inserito dal compilatore;
- mismatch fra un header intermedio usato per buildare la DLL e l'header
  pubblico v2.007.017 nel repo.

**Effetto pratico**: lo shift di +1 da slot 98 in poi viene riassorbito a
slot 105 perche' UNO fra `GetPath`/`GetName` (entrambi `std::string` per
valore in input) e' stato rimosso. Da slot 106 (`StartTiming`) in poi i
numeri tornano a coincidere col declaration order dell'header.

**Regola operativa**: non riordinare i `V_*` di `_lib.py`. Lo slot 98 va
trattato come `DO NOT CALL`.

### 2.3 Slot pericolosi (segfault o stack corruption)

Documentato in `_lib.py` con commento "DO NOT CALL". Verificato:

| Slot | Motivo |
|------|--------|
| 7 (V_GET_NAME) | crash se sender NON inizializzato (deref di un pointer interno mai settato) |
| 23 (V_GET_SENDER_NAME) | crash se receiver NON connesso |
| 30 (V_GET_SENDER_TEX) | ritorna `ID3D11Texture2D*` — sicuro solo se chi chiama ha device DX11 |
| 34 (V_GET_SENDER_LIST) | ritorna `std::vector<std::string>` — ABI MSVC non portabile |
| 65, 66 (V_GET_LOG_PATH, V_GET_SPOUT_LOG) | ritorno std::string |
| 69-74 | SpoutLog* variadic, signature variabile |
| 76-81 | SpoutMessageBox overload variadic / std::string |
| 83 | SpoutMessageBoxIcon(std::string) |
| 99, 102-105 | std::string return / arg |
| 164 | GLformatName → std::string |

Tecnica che usiamo per std::string return su MSVC x64: il chiamante
**deve** passare come primo argomento esplicito un puntatore al buffer
output prima di "this". Non lo facciamo: nessun helper Python lo gestisce.
Per leggerli si dovrebbe usare la C-API parallela esposta dall'eseguibile
SpoutSettings.exe o disassemblare la DLL.

---

## 3. Modelli di sharing supportati da Spout2

Spout2 ha **tre** path interni di trasferimento texture:

1. **GL/DX interop** (path veloce): la DLL apre una texture DX11 condivisa,
   poi tramite `WGL_NV_DX_interop2` la "wrappa" in un GL texture object.
   Sender e receiver fanno copia GPU-side. Richiede:
   - GPU NVIDIA o AMD recente con driver che esponga `NV_DX_interop2`
   - **un OpenGL context valido nel processo chiamante**
   - hardware compatibile (`IsGLDXready()` = True)

2. **CPU share** (fallback): la DLL alloca uno staging buffer in system
   memory, copia DX11 staging texture -> RAM lato sender, poi copia
   RAM -> DX11 staging -> texture lato receiver. Lento ma funzionante anche
   senza interop hardware.

3. **Memory share** (legacy 2.006): named shared memory direct, niente DX.
   Esiste ancora ma non e' la modalita' default.

**Auto-share** (`GET_AUTO_SHARE = True` di default) significa: prova GL/DX
interop, se fallisce passa a CPU share.

### 3.1 Cosa funziona da Python (verificato)

| Caso | sender | receiver | Risultato |
|------|--------|----------|-----------|
| Python -> TouchDesigner / OBS / Resolume / vMix | OK | OK | **funziona pienamente** |
| Python sender, **NESSUN** GL context, qualsiasi receiver | FAIL | -- | `send_image` ritorna False, `is_initialized` resta False |
| Python sender con `CreateOpenGL()`, receiver Python | OK (cpu_share=True) | connesso ma buffer ZERO | **non funziona** |
| Python sender via `CreateOpenGL()`, receiver TouchDesigner | OK | OK | funziona (testato in passato) |
| Python sender + Python receiver same-process | FAIL | FAIL | come sopra |

### 3.2 Perche' Python ↔ Python non funziona

Empiricamente:
- Senza GL context, sender non si inizializza affatto (`send_image -> False`)
- Con `CreateOpenGL()`, sender si inizializza ma `gldx_compatible` resta False
  → Spout cade su CPU share (`cpu_share = True`)
- Il receiver Python con `CreateOpenGL()` si connette (`is_connected = True`,
  metadata corretti), `receive_image()` ritorna True, ma il **buffer rimane
  sempre composto da zeri**
- La directory shared-memory (lista sender, dimensioni, share handle, formato
  DXGI) viene popolata correttamente da entrambe le parti

Causa probabile (ipotesi): il fallback CPU-share dentro la DLL richiede
che la copia DX11 staging texture -> RAM avvenga *quando il sender ha appena
finito di scrivere*, sincronizzata con un evento. La nostra `CreateOpenGL`
crea un contesto offscreen senza render loop, quindi la sincronizzazione non
scatta nel modo previsto, oppure la texture DX11 staging non viene mai
popolata da pixel reali (Spout fa flush implicito tramite la pipeline GL).

**Verdetto operativo**: usa un'app Spout-aware nativa (TouchDesigner, OBS,
Resolume, vMix, Notch, ffmpeg con plugin Spout) come receiver. Il sender
Python e' ok.

### 3.3 Workaround per demo full-Python: shared memory parallela

Per i casi in cui serve un preview puramente Python (CI, smoke test,
sviluppo offline) `examples/preview_local.py` realizza un canale
parallelo:

- il sender Python pubblica i frame su Spout (per TD/OBS/etc) **e**
  contemporaneamente li scrive in una `multiprocessing.shared_memory`
  region;
- il main process apre la stessa shared memory, ricostruisce il numpy
  array e mostra il frame con `cv2.imshow`.

Questo bypassa completamente il pixel transfer di Spout — Spout viene
usato solo come "registry" per esporre il sender alle app native, ma il
preview locale non dipende dal suo CPU-share. Funziona in modo
deterministico ed e' verificato via `tests/test_preview_local_e2e.py`
(salva un PNG su disco e controlla che contenga contenuto reale).

Costi: una copia CPU per frame (8 MB/s a 1080p RGBA @60fps — banale
su DDR5).

---

## 4. Ciclo di vita di un handle

```
GetSpout() -> SPOUTLIBRARY*
   |
   v
[ vtable_ptr | spout (Spout*) | ... internal state ... ]
   |
   v (vtbl[idx] = function pointer)
chiamata nativa con "this" = handle

Cleanup:
- ReleaseSender(0)  / ReleaseReceiver()
- Release()         <- slot 171: distrugge l'oggetto SPOUTImpl

Tutte e tre le classi Python (SpoutSender, SpoutReceiver, SpoutUtils)
seguono il pattern:

  __init__   -> _create_handle()
  release()  -> ReleaseSender/Receiver + Release(171)
  __exit__   -> release()
  __del__    -> release()
```

**Nota**: ogni `SpoutSender(name)` o `SpoutReceiver(name)` crea una **nuova
istanza SPOUTLIBRARY indipendente**. Due istanze nello stesso processo Python
non condividono stato; comunicano solo via shared memory IPC come fossero in
processi separati. Questo e' coerente con i risultati di
`tests/test_with_opengl.py`.

---

## 5. Pixel buffer convention

- `bytes` / `bytearray` / `ctypes` array sono accettati;
  `bytes` viene copiato (`from_buffer_copy`), `bytearray` no
  (`from_buffer` zero-copy).
- Format constants definite in `_lib.py`: `GL_RGBA = 0x1908`,
  `GL_BGRA = GL_BGRA_EXT = 0x80E1`.
- `invert=True` flippa l'asse Y (origine GL = bottom-left, origine
  np/PIL/torch = top-left). Default per `send_image` = False.
- Lunghezza minima richiesta: `width * height * 4` byte. La DLL **non
  controlla** la lunghezza — buffer troppo corti causano out-of-bounds read.
- Per zero-copy con NumPy: `(ctypes.c_ubyte * size).from_buffer(np.ascontiguousarray(arr))`.

---

## 6. Sender directory IPC

Spout mantiene una shared-memory globale (named) chiamata `SpoutSenderNames`
che contiene:
- count (int)
- max-senders (default 255)
- array di entry: `{ name[256], width, height, share_handle, dxgi_format }`
- nome del sender attivo

Verificato in `test_cross_process.py`: anche sender/receiver in processi
diversi vedono la stessa directory. Funziona indipendentemente dalla
disponibilita' di GL/DX interop.

`SpoutUtils.get_sender_info(name)` legge direttamente questa directory
senza richiedere GL/DX context — usabile anche da script CLI puro.

---

## 7. Reproduce / verify

Tutti i test sono in `tests/`. Eseguibili one-shot.

```bash
# Audit completo della vtable (37 sub-test)
python tests/test_vtable_audit.py

# Probe targetto sullo slot 98 e dintorni (98..108 con 5 restype ciascuno)
python tests/test_slot98_probe.py

# Bring-up DX11 (slot 165..174)
python tests/test_vtable_dx_probe.py

# Cross-process Python sender + Python receiver
python tests/test_cross_process.py

# Loopback in-process (no GL)
python tests/test_same_process.py

# Loopback in-process con CreateOpenGL forzato
python tests/test_with_opengl.py

# CPU share forzato
python tests/test_cpu_share.py
```

Output JSON parziale per audit principale:
`tests/vtable_audit_report.json`.

---

## 8. Conferme empiriche claim-per-claim

| Claim documento                 | Test                             | Risultato |
|--------------------------------|----------------------------------|-----------|
| DLL e' v2.007.017               | `_lib.py` carica `SpoutLibrary.dll`; cpp.h dichiara la versione | OK |
| Vtable ha 172 slot              | slot 171 = Release; slot 172+ = access violation | OK (`test_vtable_dx_probe.py`) |
| Slot 98 e' uno slot extra orfano | comportamento opposto a slot 99 (no crash) | OK |
| GetSDKversion → std::string a 99 | crash con signature semplice; allineamento ABI | OK |
| IsLaptop → bool a 100           | False su desktop RTX 4090       | OK |
| GetCurrentModule a 101          | restituisce HMODULE in range Windows-loader | OK |
| StartTiming/EndTiming a 106/107 | EndTiming → micros plausibili    | OK |
| 3 adapter rilevati              | RTX 4090 + AMD Radeon iGPU + RTX 4090 | OK |
| Memory buffer Create→Read       | Create=True, Read del payload    | parziale (signature da verificare per Size > 1) |
| Cross-process metadata IPC      | sender directory visibile fra processi | OK |
| Cross-process pixel transfer    | buffer **sempre zero**           | LIMITAZIONE CONFERMATA |
| In-process senza GL: send fail  | `send_image -> False` se non si chiama prima `CreateOpenGL` | OK |
| In-process con `CreateOpenGL`   | sender ok, gldx=False, cpu_share=True; receiver buffer zero | LIMITAZIONE CONFERMATA |
| Slot 7/23 (GetName/SenderName)  | crash su istanze non inizializzate | OK |
