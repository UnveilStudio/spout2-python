"""
SpoutUtils — enumerate senders, query system state, manage memory buffers,
and control frame synchronisation.

All utilities share a single SPOUTLIBRARY instance obtained via GetSpout().
"""
import ctypes
from . import _lib


class SpoutUtils:
    """
    Miscellaneous Spout utilities: sender enumeration, frame sync, and
    shared-memory data buffers.
    """

    def __init__(self):
        self._h = _lib._create_handle()

    # ------------------------------------------------------------------ #
    # Context manager
    # ------------------------------------------------------------------ #

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    def __del__(self):
        self.release()

    def _fn(self, index, restype, argtypes):
        return _lib._vtbl_fn(self._h, index, restype, argtypes)

    def release(self):
        if self._h:
            fn = self._fn(_lib.V_RELEASE, None, [])
            fn(self._h)
            self._h = None

    # ------------------------------------------------------------------ #
    # Sender enumeration
    # ------------------------------------------------------------------ #

    def get_sender_count(self) -> int:
        """Return the number of active Spout senders on this system."""
        fn = self._fn(_lib.V_GET_SENDER_COUNT, ctypes.c_int, [])
        return fn(self._h)

    def get_sender(self, index: int) -> str:
        """
        Return the name of the sender at *index* in the sender list.

        Parameters
        ----------
        index : int
            0-based index, must be < ``get_sender_count()``.
        """
        buf = ctypes.create_string_buffer(256)
        fn = self._fn(
            _lib.V_GET_SENDER,
            ctypes.c_bool,
            [ctypes.c_int, ctypes.c_char_p, ctypes.c_int],
        )
        ok = fn(self._h, index, buf, 256)
        return buf.value.decode() if ok else ""

    def get_all_senders(self) -> list:
        """Return a list of all active sender names."""
        return [self.get_sender(i) for i in range(self.get_sender_count())]

    def find_sender(self, name: str) -> bool:
        """Return True if a sender named *name* exists."""
        fn = self._fn(_lib.V_FIND_SENDER_NAME, ctypes.c_bool, [ctypes.c_char_p])
        return bool(fn(self._h, name.encode()))

    def get_active_sender(self) -> str:
        """Return the name of the currently active sender."""
        buf = ctypes.create_string_buffer(256)
        fn = self._fn(_lib.V_GET_ACTIVE_SENDER, ctypes.c_bool, [ctypes.c_char_p])
        ok = fn(self._h, buf)
        return buf.value.decode() if ok else ""

    def get_sender_info(self, name: str):
        """
        Return ``(width, height, share_handle, dxgi_format)`` for the sender
        named *name*, or ``None`` if no such sender exists.

        Works without an OpenGL context — useful to learn a sender's
        dimensions before allocating a receive buffer when running on a pure
        memory-share path (e.g. headless Python scripts).
        """
        width  = ctypes.c_uint(0)
        height = ctypes.c_uint(0)
        handle = ctypes.c_void_p(0)
        fmt    = ctypes.c_ulong(0)
        fn = self._fn(
            _lib.V_GET_SENDER_INFO,
            ctypes.c_bool,
            [ctypes.c_char_p,
             ctypes.POINTER(ctypes.c_uint),
             ctypes.POINTER(ctypes.c_uint),
             ctypes.POINTER(ctypes.c_void_p),
             ctypes.POINTER(ctypes.c_ulong)],
        )
        ok = fn(self._h, name.encode(),
                ctypes.byref(width), ctypes.byref(height),
                ctypes.byref(handle), ctypes.byref(fmt))
        if not ok:
            return None
        return (width.value, height.value, handle.value, fmt.value)

    def set_active_sender(self, name: str) -> bool:
        """Set *name* as the active sender."""
        fn = self._fn(_lib.V_SET_ACTIVE_SENDER, ctypes.c_bool, [ctypes.c_char_p])
        return bool(fn(self._h, name.encode()))

    # ------------------------------------------------------------------ #
    # Frame synchronisation
    # ------------------------------------------------------------------ #

    def enable_frame_sync(self, enable: bool = True):
        """Enable or disable frame synchronisation globally."""
        fn = self._fn(_lib.V_ENABLE_FRAME_SYNC, None, [ctypes.c_bool])
        fn(self._h, enable)

    def set_frame_sync(self, sender_name: str):
        """Signal a sync event for *sender_name*."""
        fn = self._fn(_lib.V_SET_FRAME_SYNC, None, [ctypes.c_char_p])
        fn(self._h, sender_name.encode())

    def wait_frame_sync(self, sender_name: str, timeout_ms: int = 0) -> bool:
        """
        Wait for a sync event from *sender_name*.

        Parameters
        ----------
        timeout_ms : int
            Timeout in milliseconds. 0 = return immediately (test-only).
        """
        fn = self._fn(
            _lib.V_WAIT_FRAME_SYNC,
            ctypes.c_bool,
            [ctypes.c_char_p, ctypes.c_ulong],
        )
        return bool(fn(self._h, sender_name.encode(), timeout_ms))

    def is_frame_sync_enabled(self) -> bool:
        fn = self._fn(_lib.V_IS_FRAME_SYNC_ENABLED, ctypes.c_bool, [])
        return bool(fn(self._h))

    def hold_fps(self, fps: int):
        """Sleep to maintain the target frame rate *fps*."""
        fn = self._fn(_lib.V_HOLD_FPS, None, [ctypes.c_int])
        fn(self._h, fps)

    def get_refresh_rate(self) -> float:
        """Return the system monitor refresh rate (Hz)."""
        fn = self._fn(_lib.V_GET_REFRESH_RATE, ctypes.c_double, [])
        return fn(self._h)

    # ------------------------------------------------------------------ #
    # Shared memory data buffers
    # ------------------------------------------------------------------ #

    def create_memory_buffer(self, name: str, length: int) -> bool:
        """
        Create a named shared-memory buffer of *length* bytes.

        Use this to share arbitrary data (not textures) between processes.
        """
        fn = self._fn(
            _lib.V_CREATE_MEM_BUFFER,
            ctypes.c_bool,
            [ctypes.c_char_p, ctypes.c_int],
        )
        return bool(fn(self._h, name.encode(), length))

    def write_memory_buffer(self, name: str, data: bytes) -> bool:
        """Write *data* into a previously created shared-memory buffer."""
        fn = self._fn(
            _lib.V_WRITE_MEM_BUFFER,
            ctypes.c_bool,
            [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int],
        )
        return bool(fn(self._h, name.encode(), data, len(data)))

    def read_memory_buffer(self, name: str, max_length: int = 4096) -> bytes:
        """
        Read data from a shared-memory buffer.

        Returns the bytes read (up to *max_length*), or ``b""`` on failure.
        """
        buf = ctypes.create_string_buffer(max_length)
        fn = self._fn(
            _lib.V_READ_MEM_BUFFER,
            ctypes.c_int,
            [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int],
        )
        n = fn(self._h, name.encode(), buf, max_length)
        return bytes(buf.raw[:n]) if n > 0 else b""

    def delete_memory_buffer(self) -> bool:
        """Delete the shared-memory buffer created by this instance."""
        fn = self._fn(_lib.V_DELETE_MEM_BUFFER, ctypes.c_bool, [])
        return bool(fn(self._h))

    def get_memory_buffer_size(self, name: str) -> int:
        """Return the size (bytes) of the named shared-memory buffer."""
        fn = self._fn(_lib.V_GET_MEM_BUF_SIZE, ctypes.c_int, [ctypes.c_char_p])
        return fn(self._h, name.encode())

    # ------------------------------------------------------------------ #
    # Logging helpers
    # ------------------------------------------------------------------ #

    def open_console(self):
        """Open a debug console window (useful for debugging in GUI apps)."""
        fn = self._fn(_lib.V_OPEN_CONSOLE, None, [])
        fn(self._h)

    def enable_log(self):
        """Enable Spout logging to the console."""
        fn = self._fn(_lib.V_ENABLE_LOG, None, [])
        fn(self._h)

    def disable_log(self):
        """Disable all Spout logging."""
        fn = self._fn(_lib.V_DISABLE_LOG, None, [])
        fn(self._h)

    def set_log_level(self, level: int):
        """
        Set the Spout log verbosity.

        Use the ``LOG_*`` constants from ``spout._lib``:
        ``LOG_SILENT``, ``LOG_VERBOSE``, ``LOG_NOTICE``,
        ``LOG_WARNING``, ``LOG_ERROR``, ``LOG_FATAL``, ``LOG_NONE``.
        """
        fn = self._fn(_lib.V_SET_LOG_LEVEL, None, [ctypes.c_int])
        fn(self._h, level)

    # ------------------------------------------------------------------ #
    # Adapter info
    # ------------------------------------------------------------------ #

    def get_num_adapters(self) -> int:
        """Return the number of GPU adapters on this system."""
        fn = self._fn(_lib.V_GET_NUM_ADAPTERS, ctypes.c_int, [])
        return fn(self._h)

    def get_adapter_name(self, index: int) -> str:
        """Return the name of the GPU adapter at *index*."""
        buf = ctypes.create_string_buffer(256)
        fn = self._fn(
            _lib.V_GET_ADAPTER_NAME,
            ctypes.c_bool,
            [ctypes.c_int, ctypes.c_char_p, ctypes.c_int],
        )
        ok = fn(self._h, index, buf, 256)
        return buf.value.decode() if ok else ""

    def get_all_adapter_names(self) -> list:
        """Return names of all GPU adapters."""
        return [self.get_adapter_name(i) for i in range(self.get_num_adapters())]

    def is_gldx_ready(self) -> bool:
        """True if OpenGL/DirectX interop is supported on this machine."""
        fn = self._fn(_lib.V_IS_GLDX_READY, ctypes.c_bool, [])
        return bool(fn(self._h))

    def is_laptop(self) -> bool:
        """True if running on a laptop."""
        fn = self._fn(_lib.V_IS_LAPTOP, ctypes.c_bool, [])
        return bool(fn(self._h))
