"""
spout — Python bindings for Spout2 GPU texture sharing (Windows only).

Quick start::

    from spout import SpoutSender, SpoutReceiver, SpoutUtils

Spout2 SDK version: 2.007.017
Binding method: ctypes vtable dispatch against SpoutLibrary.dll
Platform: Windows x64 only
"""
from .sender   import SpoutSender
from .receiver import SpoutReceiver
from .utils    import SpoutUtils
from ._lib import (
    GL_RGBA,
    GL_BGRA,
    GL_BGRA_EXT,
    LOG_SILENT,
    LOG_VERBOSE,
    LOG_NOTICE,
    LOG_WARNING,
    LOG_ERROR,
    LOG_FATAL,
    LOG_NONE,
)

__all__ = [
    "SpoutSender",
    "SpoutReceiver",
    "SpoutUtils",
    "GL_RGBA",
    "GL_BGRA",
    "GL_BGRA_EXT",
    "LOG_SILENT",
    "LOG_VERBOSE",
    "LOG_NOTICE",
    "LOG_WARNING",
    "LOG_ERROR",
    "LOG_FATAL",
    "LOG_NONE",
]
