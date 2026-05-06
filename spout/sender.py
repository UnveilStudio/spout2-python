"""
SpoutSender — send pixel data (RGBA/BGRA images) to other Spout-aware applications.

Usage::

    from spout.sender import SpoutSender
    from spout._lib import GL_RGBA

    with SpoutSender("MySender") as sender:
        while True:
            pixels = get_frame_bytes()          # bytes/bytearray, width*height*4
            sender.send_image(pixels, 1920, 1080)
"""
import ctypes
from . import _lib
from ._base import _SpoutBase


class SpoutSender(_SpoutBase):
    """
    Wraps the Spout sender side of SpoutLibrary.

    Parameters
    ----------
    name : str
        Sender name visible to other applications. Pass ``""`` or omit to let
        Spout assign a name based on the executable.
    """

    def __init__(self, name: str = ""):
        super().__init__()
        if name:
            self._set_name(name)

    def _set_name(self, name: str):
        fn = self._fn(_lib.V_SET_SENDER_NAME, None, [ctypes.c_char_p])
        fn(self._h, name.encode())

    def _release_resource(self):
        fn = self._fn(_lib.V_RELEASE_SENDER, None, [ctypes.c_ulong])
        fn(self._h, 0)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def send_image(
        self,
        pixels,
        width: int,
        height: int,
        gl_format: int = _lib.GL_RGBA,
        invert: bool = False,
    ) -> bool:
        """
        Share a raw pixel buffer with connected receivers.

        Parameters
        ----------
        pixels : bytes | bytearray | memoryview | ctypes array
            Pixel data. Must be exactly ``width * height * bytes_per_pixel``
            bytes. For GL_RGBA that is ``width * height * 4`` bytes.
            ``bytearray`` / writable ``memoryview`` are aliased zero-copy;
            immutable ``bytes`` is copied once.
        width, height : int
            Frame dimensions in pixels.
        gl_format : int
            GL_RGBA (default) or GL_BGRA_EXT. See ``spout._lib`` constants.
        invert : bool
            Flip the image vertically before sharing (default False).

        Returns
        -------
        bool
            True on success.
        """
        if isinstance(pixels, bytes):
            buf = (ctypes.c_ubyte * len(pixels)).from_buffer_copy(pixels)
        elif isinstance(pixels, (bytearray, memoryview)):
            buf = (ctypes.c_ubyte * len(pixels)).from_buffer(pixels)
        else:
            buf = pixels

        fn = self._fn(
            _lib.V_SEND_IMAGE,
            ctypes.c_bool,
            [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
             ctypes.c_uint, ctypes.c_bool],
        )
        return bool(fn(self._h, buf, width, height, gl_format, invert))

    def create_opengl(self) -> bool:
        """
        Create a hidden window + OpenGL context owned by SpoutLibrary.

        Useful for headless Python scripts that need to call ``send_image``
        without an existing GL context (CLI scripts, image-publishing demos).
        Pair with ``close_opengl()`` on shutdown.
        """
        fn = self._fn(_lib.V_CREATE_OPENGL, ctypes.c_bool, [ctypes.c_void_p])
        return bool(fn(self._h, None))

    def close_opengl(self) -> bool:
        """Close the OpenGL context created by ``create_opengl()``."""
        fn = self._fn(_lib.V_CLOSE_OPENGL, ctypes.c_bool, [])
        return bool(fn(self._h))

    # ------------------------------------------------------------------ #
    # Properties / status
    # ------------------------------------------------------------------ #

    @property
    def is_initialized(self) -> bool:
        """True if the sender has been initialised (first send succeeded)."""
        return self._call(_lib.V_IS_INITIALIZED, ctypes.c_bool, bool)

    @property
    def name(self) -> str:
        """Sender name as registered in the Spout sender list (``""`` if not yet initialised)."""
        # Slot V_GET_NAME crashes if the sender has not been initialised.
        if not self.is_initialized:
            return ""
        fn = self._fn(_lib.V_GET_NAME, ctypes.c_char_p, [])
        result = fn(self._h)
        return result.decode() if result else ""

    @property
    def width(self) -> int:
        return self._call(_lib.V_GET_WIDTH, ctypes.c_uint)

    @property
    def height(self) -> int:
        return self._call(_lib.V_GET_HEIGHT, ctypes.c_uint)

    @property
    def fps(self) -> float:
        """Actual sender frame rate (frames per second)."""
        return self._call(_lib.V_GET_FPS, ctypes.c_double)

    @property
    def frame(self) -> int:
        """Sender frame number (incremented on each send)."""
        return self._call(_lib.V_GET_FRAME, ctypes.c_long)

    @property
    def cpu_share(self) -> bool:
        """True if the sender is using CPU (system-memory) sharing."""
        return self._call(_lib.V_GET_CPU, ctypes.c_bool, bool)

    @property
    def gldx_compatible(self) -> bool:
        """True if OpenGL/DirectX interop hardware support is detected."""
        return self._call(_lib.V_GET_GLDX, ctypes.c_bool, bool)

    def __repr__(self):
        if not self.is_initialized:
            return "<SpoutSender uninitialised>"
        return f"<SpoutSender name={self.name!r} {self.width}x{self.height}>"
