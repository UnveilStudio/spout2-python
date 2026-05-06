"""
Low-level ctypes interface to SpoutLibrary.dll.

SpoutLibrary exposes a COM-like vtable interface. GetSpout() returns a pointer
to a SPOUTLIBRARY object whose first member is a vtable (array of function
pointers). Each virtual method is dispatched by indexing into that vtable.

Vtable indices are derived from the declaration order in SpoutLibrary.h v2.007.017.
Assumes the DLL was compiled with NTDDI_WIN10_RS4 defined (standard for Win10+),
which adds 6 graphics-preference methods at indices 145-150.
"""
import ctypes
import os
import sys

if sys.platform != "win32":
    raise OSError("Spout is only supported on Windows")

# --------------------------------------------------------------------------- #
# DLL loading
# --------------------------------------------------------------------------- #

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_DLL_PATH = os.path.join(_PKG_DIR, "SpoutLibrary.dll")

if not os.path.exists(_DLL_PATH):
    raise FileNotFoundError(
        f"SpoutLibrary.dll not found at {_DLL_PATH}\n"
        "Download from: https://github.com/leadedge/Spout2/releases"
    )

try:
    _dll = ctypes.WinDLL(_DLL_PATH)
except OSError as exc:
    raise OSError(f"Failed to load SpoutLibrary.dll: {exc}") from exc

# Factory: GetSpout() -> SPOUTHANDLE (opaque void* / vtable object pointer)
_dll.GetSpout.restype = ctypes.c_void_p
_dll.GetSpout.argtypes = []

# --------------------------------------------------------------------------- #
# GL format constants (from SpoutLibrary.h)
# --------------------------------------------------------------------------- #

GL_RGBA     = 0x1908
GL_BGRA_EXT = 0x80E1
GL_BGRA     = 0x80E1

# SpoutLibLogLevel enum
LOG_SILENT  = 0
LOG_VERBOSE = 1
LOG_NOTICE  = 2
LOG_WARNING = 3
LOG_ERROR   = 4
LOG_FATAL   = 5
LOG_NONE    = 6

# --------------------------------------------------------------------------- #
# Vtable dispatch helpers
# --------------------------------------------------------------------------- #

def _create_handle() -> int:
    """Create a new SPOUTLIBRARY instance. Returns a c_void_p integer."""
    h = _dll.GetSpout()
    if not h:
        raise RuntimeError(
            "GetSpout() returned NULL — SpoutLibrary failed to initialize. "
            "Ensure a GPU and DirectX 11 are available."
        )
    return h


_PROTOTYPE_CACHE: dict = {}


def _vtbl_fn(handle: int, index: int, restype, argtypes):
    """
    Return a callable for the virtual method at *index* in the object's vtable.

    handle  : int  (c_void_p value returned by GetSpout)
    index   : int  (0-based vtable slot number)
    restype : ctypes type or None
    argtypes: list of ctypes types for the explicit parameters (excluding 'this')
    """
    # The object layout: [vtable_ptr | data ...]
    # vtable layout:     [fn_ptr_0, fn_ptr_1, ...]
    vtbl_ptr = ctypes.cast(handle, ctypes.POINTER(ctypes.c_void_p))[0]
    fn_ptr   = ctypes.cast(vtbl_ptr, ctypes.POINTER(ctypes.c_void_p))[index]
    # Cache CFUNCTYPE prototypes — building one is non-trivial and this
    # helper is called inside per-frame hot paths (send_image, is_frame_new).
    key = (restype, tuple(argtypes))
    FnType = _PROTOTYPE_CACHE.get(key)
    if FnType is None:
        FnType = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        _PROTOTYPE_CACHE[key] = FnType
    return FnType(fn_ptr)


# --------------------------------------------------------------------------- #
# Vtable slot indices (declaration order from SpoutLibrary.h)
# --------------------------------------------------------------------------- #

# --- Sender ---
V_SET_SENDER_NAME   = 0
V_SET_SENDER_FORMAT = 1
V_RELEASE_SENDER    = 2
V_SEND_FBO          = 3
V_SEND_TEXTURE      = 4
V_SEND_IMAGE        = 5
V_IS_INITIALIZED    = 6
V_GET_NAME          = 7
V_GET_WIDTH         = 8
V_GET_HEIGHT        = 9
V_GET_FPS           = 10
V_GET_FRAME         = 11
V_GET_HANDLE        = 12
V_GET_CPU           = 13
V_GET_GLDX          = 14

# --- Receiver ---
V_SET_RECEIVER_NAME = 15
V_GET_RECEIVER_NAME = 16
V_RELEASE_RECEIVER  = 17
V_RECEIVE_TEXTURE   = 18
V_RECEIVE_IMAGE     = 19
V_IS_UPDATED        = 20
V_IS_CONNECTED      = 21
V_IS_FRAME_NEW      = 22
V_GET_SENDER_NAME   = 23
V_GET_SENDER_WIDTH  = 24
V_GET_SENDER_HEIGHT = 25
V_GET_SENDER_FORMAT = 26
V_GET_SENDER_FPS    = 27
V_GET_SENDER_FRAME  = 28
V_GET_SENDER_HANDLE = 29
V_GET_SENDER_TEX    = 30   # ID3D11Texture2D* — advanced use only
V_GET_SENDER_CPU    = 31
V_GET_SENDER_GLDX   = 32
V_GET_HOST_PATH     = 33
V_GET_SENDER_LIST   = 34   # std::vector<std::string> — DO NOT CALL
V_SELECT_SENDER     = 35
V_SELECT_SENDER_PANEL = 36

# --- Frame count / sync ---
V_SET_FRAME_COUNT        = 37
V_DISABLE_FRAME_COUNT    = 38
V_IS_FRAME_COUNT_ENABLED = 39
V_HOLD_FPS               = 40
V_GET_REFRESH_RATE       = 41
V_SET_FRAME_SYNC         = 42
V_WAIT_FRAME_SYNC        = 43
V_ENABLE_FRAME_SYNC      = 44
V_CLOSE_FRAME_SYNC       = 45
V_IS_FRAME_SYNC_ENABLED  = 46
V_GET_VERTICAL_SYNC      = 47
V_SET_VERTICAL_SYNC      = 48

# --- Memory buffer ---
V_WRITE_MEM_BUFFER   = 49
V_READ_MEM_BUFFER    = 50
V_CREATE_MEM_BUFFER  = 51
V_DELETE_MEM_BUFFER  = 52
V_GET_MEM_BUF_SIZE   = 53

# --- Logging ---
V_OPEN_CONSOLE    = 54
V_CLOSE_CONSOLE   = 55
V_ENABLE_LOG      = 56
V_ENABLE_LOG_FILE = 57
V_DISABLE_LOG_FILE = 58
V_REMOVE_LOG_FILE = 59
V_DISABLE_LOG     = 60
V_DISABLE_LOGS    = 61
V_ENABLE_LOGS     = 62
V_LOGS_ENABLED    = 63
V_LOG_FILE_ENABLED = 64
V_GET_LOG_PATH    = 65   # -> std::string — DO NOT CALL
V_GET_SPOUT_LOG   = 66   # -> std::string — DO NOT CALL
V_SHOW_LOGS       = 67
V_SET_LOG_LEVEL   = 68
# 69-74: SpoutLog* variadic — DO NOT CALL

# --- SpoutMessageBox (7 overloads + 7 helpers) = 14 slots: 75-88 ---
V_MSG_BOX_0      = 75   # (const char*, DWORD)
# 76-81: variadic / std::string overloads — DO NOT CALL
V_MSG_BOX_ICON_0 = 82   # (HICON)
# 83: std::string overload — skip
V_MSG_BOX_BUTTON   = 84
V_MSG_BOX_MODELESS = 85
V_MSG_BOX_WINDOW   = 86
V_MSG_BOX_POSITION = 87
V_COPY_CLIPBOARD   = 88
V_OPEN_LOGS        = 89

# --- Registry (90-97) ---
V_READ_DWORD   = 90
V_WRITE_DWORD  = 91
V_READ_PATH    = 92
V_WRITE_PATH   = 93
V_WRITE_BINARY = 94
V_REMOVE_PATH  = 95
V_REMOVE_SUBKEY = 96
V_FIND_SUBKEY  = 97

# --- Information ---
# NOTE: The compiled DLL (v2.007.017) has one undocumented extra method at
# index 98, shifting IsLaptop to 100. Everything from 106 onward matches
# the header exactly (confirmed empirically: StartTiming=106, EndTiming=107,
# GetSenderCount=111, GetActiveSender=115, GetNumAdapters=139, etc.).
V_UNDOCUMENTED_98 = 98  # unknown extra method — DO NOT CALL
V_GET_SDK_VER    = 99   # -> std::string — DO NOT CALL
V_IS_LAPTOP      = 100  # confirmed: returns True on laptop
V_GET_CURR_MODULE = 101
V_GET_EXE_VER    = 102  # -> std::string — DO NOT CALL
V_GET_EXE_PATH   = 103  # -> std::string — DO NOT CALL
V_GET_EXE_NAME   = 104  # -> std::string — DO NOT CALL
V_GET_PATH_STR   = 105  # std::string arg — DO NOT CALL (GetPath or GetName; one was removed from DLL)
V_START_TIMING   = 106  # confirmed
V_END_TIMING     = 107  # confirmed

# --- OpenGL shared texture (108-110) ---
V_BIND_SHARED_TEX   = 108
V_UNBIND_SHARED_TEX = 109
V_GET_SHARED_TEX_ID = 110

# --- Sender names (111-116) ---
V_GET_SENDER_COUNT  = 111
V_GET_SENDER        = 112
V_FIND_SENDER_NAME  = 113
V_GET_SENDER_INFO   = 114
V_GET_ACTIVE_SENDER = 115
V_SET_ACTIVE_SENDER = 116

# --- User settings (117-122) ---
V_GET_BUFFER_MODE = 117
V_SET_BUFFER_MODE = 118
V_GET_BUFFERS     = 119
V_SET_BUFFERS     = 120
V_GET_MAX_SENDERS = 121
V_SET_MAX_SENDERS = 122

# --- 2.006 compatibility (123-134) ---
V_CREATE_SENDER    = 123
V_UPDATE_SENDER    = 124
V_CREATE_RECEIVER  = 125
V_CHECK_RECEIVER   = 126
V_GET_DX9          = 127
V_SET_DX9          = 128
V_GET_MEM_SHARE    = 129
V_SET_MEM_SHARE    = 130
V_GET_CPU_MODE     = 131
V_SET_CPU_MODE     = 132
V_GET_SHARE_MODE   = 133
V_SET_SHARE_MODE   = 134

# --- Graphics compatibility (135-138) ---
V_GET_AUTO_SHARE = 135
V_SET_AUTO_SHARE = 136
V_SET_CPU_SHARE  = 137
V_IS_GLDX_READY  = 138

# --- Adapter (139-144) ---
V_GET_NUM_ADAPTERS   = 139
V_GET_ADAPTER_NAME   = 140
V_ADAPTER_NAME       = 141
V_GET_ADAPTER        = 142
V_GET_ADAPTER_INFO_0 = 143
V_GET_ADAPTER_INFO_1 = 144

# --- Graphics preference (145-150, requires NTDDI_WIN10_RS4 — standard on Win10+) ---
V_GET_PERF_PREF    = 145
V_SET_PERF_PREF    = 146
V_GET_PREF_ADAPTER = 147
V_SET_PREF_ADAPTER = 148
V_IS_PREF_AVAIL    = 149
V_IS_APP_PATH      = 150

# --- OpenGL utilities (151-155) ---
V_CREATE_OPENGL  = 151
V_CLOSE_OPENGL   = 152
V_INIT_TEXTURE   = 153
V_COPY_TEXTURE   = 154
V_READ_TEX_DATA  = 155

# --- Pixel buffer (156-158) ---
V_CLEAR_ALPHA    = 156
V_FLIP_BUFFER_0  = 157   # src -> dst
V_FLIP_BUFFER_1  = 158   # in-place

# --- Formats (159-164) ---
V_GET_DX11_FORMAT = 159
V_SET_DX11_FORMAT = 160
V_DX11FORMAT      = 161
V_GLDXFORMAT      = 162
V_GLFORMAT        = 163
V_GLFORMAT_NAME   = 164  # -> std::string — DO NOT CALL

# --- DirectX (165-170) ---
V_OPEN_DX      = 165
V_CLOSE_DX     = 166
V_OPEN_DX11    = 167
V_CLOSE_DX11   = 168
V_GET_DX11_DEV = 169
V_GET_DX11_CTX = 170

# --- Library release (171) ---
V_RELEASE = 171
