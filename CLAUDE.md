# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python bindings for [Spout2](https://spout.zeal.co/) — a Windows-only GPU texture-sharing system. Spout allows applications to share frames via GPU memory (similar to Syphon on macOS). This library wraps `SpoutLibrary.dll` using `ctypes` with COM-style vtable dispatch.

**Windows x64 only.** The DLL will fail to load on any other platform.

## Running Examples

```bash
python examples/send_example.py             # Animated gradient sender at 640x480 @30fps
python examples/receive_example.py          # Connects to active sender and polls frames
python examples/share_image.py path/to/image  # Shares a static image (requires Pillow)
```

The project is installable via `pip install .` (or `pip install git+https://github.com/UnveilStudio/SPOUT2ForPython.git`). `SpoutLibrary.dll` is bundled as `package-data` and shipped inside the installed `spout` package.

## Architecture

```
Application
    ↓
spout/sender.py | spout/receiver.py | spout/utils.py   ← thin Python wrappers
    ↓
spout/_lib.py                                           ← ctypes + vtable dispatch
    ↓
SpoutLibrary.dll (v2.007.017)                          ← C++ GPU texture sharing
```

### Vtable Dispatch Pattern (`_lib.py`)

`SpoutLibrary.dll` exposes a COM-style interface. The DLL exports a single `GetSpout()` factory that returns a pointer to a `SPOUTLIBRARY` object whose first member is a vtable pointer.

- `_create_handle()` calls `GetSpout()` and returns the opaque object pointer
- `_vtbl_fn(handle, index, restype, argtypes)` dereferences `handle→vtable[index]` and returns a bound callable
- All `V_*` constants in `_lib.py` are vtable slot indices matching the order in `SpoutLibrary.h`

**Important:** The compiled DLL (v2.007.017) contains one undocumented extra method at vtable index 98 that is absent from the public header. This was discovered empirically — `V_IS_LAPTOP` at index 100 returned the correct result, confirming the offset. Do not reorder `V_*` constants without verifying against the DLL headers in `Spout2-SDK/`.

The actual integrated/dedicated GPU switching API is at indices 145–150 (`V_GET_PERF_PREF` … `V_IS_APP_PATH`). These wrap the Windows Graphics Performance Preference registry setting and require Windows 10 April 2018 Update (NTDDI_WIN10_RS4) or later.

### Three Public Classes

| Class | File | Purpose |
|---|---|---|
| `SpoutSender` | `sender.py` | Publish RGBA/BGRA pixel frames to a named sender |
| `SpoutReceiver` | `receiver.py` | Subscribe to a sender and poll for new frames |
| `SpoutUtils` | `utils.py` | Enumerate senders, frame sync, shared memory IPC, GPU adapter info |

All three classes call `_create_handle()` on init and call `ReleaseLibrary` (vtable teardown) on `__del__` or context manager exit. `SpoutSender` supports `with` statements.

### Pixel Buffer Convention

- Pixel data is passed as `bytes`, `bytearray`, or a ctypes array
- Format constants (`GL_RGBA`, `GL_BGRA_EXT`, `GL_BGRA`) are defined in `_lib.py`
- `invert=True` flips vertically (OpenGL origin is bottom-left)

### Receiver Poll Model

`receive()` checks connection state without copying data. `receive_image(buffer, ...)` copies pixels into a caller-provided buffer. Check `is_updated` after `receive()` returns `True` to detect resolution changes from the sender side.
