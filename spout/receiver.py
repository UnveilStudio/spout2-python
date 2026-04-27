"""
SpoutReceiver — receive pixel data from any Spout sender.

Usage::

    from spout.receiver import SpoutReceiver
    from spout._lib import GL_RGBA

    with SpoutReceiver() as receiver:
        while receiver.is_connected:
            if receiver.receive():
                w, h = receiver.sender_width, receiver.sender_height
                buf = bytearray(w * h * 4)
                receiver.receive_image(buf, w, h)
                process(buf)
"""
import ctypes
from . import _lib


class SpoutReceiver:
    """
    Wraps the Spout receiver side of SpoutLibrary.

    Parameters
    ----------
    sender_name : str
        Connect only to this specific sender. If ``""`` (default) the receiver
        connects to the active sender automatically.
    """

    def __init__(self, sender_name: str = ""):
        self._h = _lib._create_handle()
        if sender_name:
            fn = _lib._vtbl_fn(
                self._h, _lib.V_SET_RECEIVER_NAME, None, [ctypes.c_char_p]
            )
            fn(self._h, sender_name.encode())

    # ------------------------------------------------------------------ #
    # Context manager
    # ------------------------------------------------------------------ #

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()

    def __del__(self):
        self.release()

    # ------------------------------------------------------------------ #
    # Private vtable helper
    # ------------------------------------------------------------------ #

    def _fn(self, index, restype, argtypes):
        return _lib._vtbl_fn(self._h, index, restype, argtypes)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def receive(self) -> bool:
        """
        Poll for a new frame from the connected sender.

        Returns True if successfully connected (even without a new frame).
        Call ``is_updated`` afterwards to check if dimensions changed.
        Call ``receive_image`` to copy pixel data.
        """
        fn = self._fn(
            _lib.V_RECEIVE_TEXTURE,
            ctypes.c_bool,
            [ctypes.c_uint, ctypes.c_uint, ctypes.c_bool, ctypes.c_uint],
        )
        return bool(fn(self._h, 0, 0, False, 0))

    def receive_image(
        self,
        buffer,
        width: int,
        height: int,
        gl_format: int = _lib.GL_RGBA,
        invert: bool = False,
    ) -> bool:
        """
        Copy the current sender frame into *buffer*.

        Parameters
        ----------
        buffer : bytearray | ctypes array
            Pre-allocated output buffer. Must be ``width * height * 4`` bytes
            for GL_RGBA.
        width, height : int
            Expected frame dimensions. Must match the sender's current size.
        gl_format : int
            GL_RGBA (default) or GL_BGRA_EXT.
        invert : bool
            Flip the received image vertically.

        Returns
        -------
        bool
            True on success.
        """
        if isinstance(buffer, (bytearray, memoryview)):
            buf = (ctypes.c_ubyte * len(buffer)).from_buffer(buffer)
        else:
            buf = buffer

        fn = self._fn(
            _lib.V_RECEIVE_IMAGE,
            ctypes.c_bool,
            [ctypes.c_char_p, ctypes.c_uint, ctypes.c_bool, ctypes.c_uint],
        )
        return bool(fn(self._h, buf, gl_format, invert, 0))

    def release(self):
        """Disconnect from the sender and free resources."""
        if self._h:
            fn = self._fn(_lib.V_RELEASE_RECEIVER, None, [])
            fn(self._h)
            fn2 = self._fn(_lib.V_RELEASE, None, [])
            fn2(self._h)
            self._h = None

    # ------------------------------------------------------------------ #
    # Status properties
    # ------------------------------------------------------------------ #

    @property
    def is_connected(self) -> bool:
        """True if currently connected to an active sender."""
        fn = self._fn(_lib.V_IS_CONNECTED, ctypes.c_bool, [])
        return bool(fn(self._h))

    @property
    def is_updated(self) -> bool:
        """True if the sender dimensions changed since the last receive call."""
        fn = self._fn(_lib.V_IS_UPDATED, ctypes.c_bool, [])
        return bool(fn(self._h))

    @property
    def is_frame_new(self) -> bool:
        """True if the sender produced a new frame since the last receive."""
        fn = self._fn(_lib.V_IS_FRAME_NEW, ctypes.c_bool, [])
        return bool(fn(self._h))

    @property
    def sender_name(self) -> str:
        """Name of the currently connected sender."""
        fn = self._fn(_lib.V_GET_SENDER_NAME, ctypes.c_char_p, [])
        result = fn(self._h)
        return result.decode() if result else ""

    @property
    def sender_width(self) -> int:
        fn = self._fn(_lib.V_GET_SENDER_WIDTH, ctypes.c_uint, [])
        return fn(self._h)

    @property
    def sender_height(self) -> int:
        fn = self._fn(_lib.V_GET_SENDER_HEIGHT, ctypes.c_uint, [])
        return fn(self._h)

    @property
    def sender_fps(self) -> float:
        """Frame rate of the connected sender."""
        fn = self._fn(_lib.V_GET_SENDER_FPS, ctypes.c_double, [])
        return fn(self._h)

    @property
    def sender_frame(self) -> int:
        """Frame number of the connected sender."""
        fn = self._fn(_lib.V_GET_SENDER_FRAME, ctypes.c_long, [])
        return fn(self._h)

    @property
    def sender_cpu(self) -> bool:
        """True if the connected sender uses CPU sharing."""
        fn = self._fn(_lib.V_GET_SENDER_CPU, ctypes.c_bool, [])
        return bool(fn(self._h))

    @property
    def sender_gldx(self) -> bool:
        """True if the connected sender has GL/DX interop."""
        fn = self._fn(_lib.V_GET_SENDER_GLDX, ctypes.c_bool, [])
        return bool(fn(self._h))

    def __repr__(self):
        if self.is_connected:
            return (
                f"<SpoutReceiver connected={self.sender_name!r} "
                f"{self.sender_width}x{self.sender_height}>"
            )
        return "<SpoutReceiver disconnected>"
