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
from ._base import _SpoutBase


class SpoutReceiver(_SpoutBase):
    """
    Wraps the Spout receiver side of SpoutLibrary.

    Parameters
    ----------
    sender_name : str
        Connect only to this specific sender. If ``""`` (default) the receiver
        connects to the active sender automatically.
    """

    def __init__(self, sender_name: str = ""):
        super().__init__()
        if sender_name:
            self._set_receiver_name(sender_name)

    def _set_receiver_name(self, name: str):
        fn = self._fn(_lib.V_SET_RECEIVER_NAME, None, [ctypes.c_char_p])
        fn(self._h, name.encode())

    def _release_resource(self):
        fn = self._fn(_lib.V_RELEASE_RECEIVER, None, [])
        fn(self._h)

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
        buffer : bytearray | memoryview | ctypes array
            Pre-allocated *writable* output buffer of ``width * height * 4``
            bytes for GL_RGBA. ``bytes`` is rejected because it is immutable.
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
        if isinstance(buffer, bytes):
            raise TypeError("receive_image needs a writable buffer; pass a bytearray instead of bytes")
        if isinstance(buffer, (bytearray, memoryview)):
            buf = (ctypes.c_ubyte * len(buffer)).from_buffer(buffer)
        else:
            buf = buffer

        fn = self._fn(
            _lib.V_RECEIVE_IMAGE,
            ctypes.c_bool,
            [ctypes.c_void_p, ctypes.c_uint, ctypes.c_bool, ctypes.c_uint],
        )
        return bool(fn(self._h, buf, gl_format, invert, 0))

    # ------------------------------------------------------------------ #
    # Status properties
    # ------------------------------------------------------------------ #

    @property
    def is_connected(self) -> bool:
        """True if currently connected to an active sender."""
        return self._call(_lib.V_IS_CONNECTED, ctypes.c_bool, bool)

    @property
    def is_updated(self) -> bool:
        """True if the sender dimensions changed since the last receive call."""
        return self._call(_lib.V_IS_UPDATED, ctypes.c_bool, bool)

    @property
    def is_frame_new(self) -> bool:
        """True if the sender produced a new frame since the last receive."""
        return self._call(_lib.V_IS_FRAME_NEW, ctypes.c_bool, bool)

    @property
    def sender_name(self) -> str:
        """Name of the currently connected sender (``""`` if not connected)."""
        # Slot V_GET_SENDER_NAME crashes when the receiver is not connected.
        if not self.is_connected:
            return ""
        fn = self._fn(_lib.V_GET_SENDER_NAME, ctypes.c_char_p, [])
        result = fn(self._h)
        return result.decode() if result else ""

    @property
    def sender_width(self) -> int:
        return self._call(_lib.V_GET_SENDER_WIDTH, ctypes.c_uint)

    @property
    def sender_height(self) -> int:
        return self._call(_lib.V_GET_SENDER_HEIGHT, ctypes.c_uint)

    @property
    def sender_fps(self) -> float:
        """Frame rate of the connected sender."""
        return self._call(_lib.V_GET_SENDER_FPS, ctypes.c_double)

    @property
    def sender_frame(self) -> int:
        """Frame number of the connected sender."""
        return self._call(_lib.V_GET_SENDER_FRAME, ctypes.c_long)

    @property
    def sender_cpu(self) -> bool:
        """True if the connected sender uses CPU sharing."""
        return self._call(_lib.V_GET_SENDER_CPU, ctypes.c_bool, bool)

    @property
    def sender_gldx(self) -> bool:
        """True if the connected sender has GL/DX interop."""
        return self._call(_lib.V_GET_SENDER_GLDX, ctypes.c_bool, bool)

    def __repr__(self):
        if self.is_connected:
            return (
                f"<SpoutReceiver connected={self.sender_name!r} "
                f"{self.sender_width}x{self.sender_height}>"
            )
        return "<SpoutReceiver disconnected>"
