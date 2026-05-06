"""
Shared base class for the three public wrappers.

Holds the SPOUTLIBRARY handle, the context-manager protocol, the per-frame
``_fn`` / ``_call`` vtable helpers, and a ``release`` template that calls a
subclass hook before tearing down the library handle.
"""
import ctypes
from . import _lib

# Spout's documented maximum sender / adapter name length.
SPOUT_NAME_MAX = 256


class _SpoutBase:
    """Common SPOUTLIBRARY lifecycle and vtable dispatch."""

    def __init__(self):
        self._h = _lib._create_handle()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    def __del__(self):
        # Guard against partial init (if _create_handle raised, _h is unset)
        # and against interpreter shutdown where ctypes/_lib may be partly torn down.
        if getattr(self, "_h", None) is not None:
            try:
                self.release()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Vtable helpers
    # ------------------------------------------------------------------ #

    def _fn(self, index, restype, argtypes):
        """Return a callable for vtable slot *index* (cached prototype)."""
        return _lib._vtbl_fn(self._h, index, restype, argtypes)

    def _call(self, index, restype, cast=None):
        """Dispatch a no-arg vtable method, optionally casting the result."""
        fn = self._fn(index, restype, [])
        result = fn(self._h)
        return cast(result) if cast else result

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def _release_resource(self):
        """Override to release type-specific resources before V_RELEASE."""

    def release(self):
        """Tear down the SPOUTLIBRARY instance."""
        if self._h:
            self._release_resource()
            fn = self._fn(_lib.V_RELEASE, None, [])
            fn(self._h)
            self._h = None

    # ------------------------------------------------------------------ #
    # Shared utilities (state-free SDK functions usable from any handle)
    # ------------------------------------------------------------------ #

    def hold_fps(self, fps: int):
        """Sleep to maintain the target frame rate *fps*."""
        fn = self._fn(_lib.V_HOLD_FPS, None, [ctypes.c_int])
        fn(self._h, fps)
