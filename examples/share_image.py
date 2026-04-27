"""
share_image.py — Load any image and share it to TouchDesigner via Spout.

Usage:
    python examples/share_image.py path/to/image.jpg
    python examples/share_image.py path/to/image.png   (also works with .bmp, .tiff, etc.)

In TouchDesigner: add a "Spout In" TOP and it will receive "PythonImage".

Requirements:
    pip install Pillow
"""
import sys
import os
import ctypes
import time

# Resolve image path from args or prompt
if len(sys.argv) > 1:
    image_path = sys.argv[1]
else:
    image_path = input("Image path: ").strip().strip('"')

if not os.path.exists(image_path):
    print(f"File not found: {image_path}")
    sys.exit(1)

# Make sure the project root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from spout._lib import _create_handle, _vtbl_fn, GL_RGBA, V_CREATE_OPENGL, V_CLOSE_OPENGL, V_RELEASE

# Load image and convert to RGBA bytes
print(f"Loading: {image_path}")
img = Image.open(image_path).convert("RGBA")
width, height = img.size
pixels = img.tobytes()  # raw RGBA bytes, top-to-bottom
print(f"Image size: {width}x{height}  ({len(pixels)} bytes)")

# Create a SPOUTLIBRARY handle
h = _create_handle()

# CreateOpenGL() — creates a hidden window + OpenGL context for us
fn_create_gl = _vtbl_fn(h, V_CREATE_OPENGL, ctypes.c_bool, [ctypes.c_void_p])
ok = fn_create_gl(h, None)
if not ok:
    print("WARNING: CreateOpenGL() failed — SendImage may not work without a GL context.")
    print("         Try running from inside an OpenGL-capable application.")
else:
    print("OpenGL context created OK")

# Set sender name
fn_name = _vtbl_fn(h, 0, None, [ctypes.c_char_p])  # SetSenderName
fn_name(h, b"PythonImage")

# SendImage — pixels must be c_void_p (pointer to unsigned char buffer)
fn_send = _vtbl_fn(h, 5, ctypes.c_bool, [
    ctypes.c_void_p,    # const unsigned char* pixels
    ctypes.c_uint,      # width
    ctypes.c_uint,      # height
    ctypes.c_uint,      # glFormat
    ctypes.c_bool,      # bInvert — True flips vertically (TD expects bottom-up)
])

buf = (ctypes.c_ubyte * len(pixels)).from_buffer_copy(pixels)

print("\nSending to TouchDesigner as 'PythonImage'")
print("In TouchDesigner: add a Spout In TOP → it should appear immediately.")
print("Press Ctrl+C to stop.\n")

frame = 0
try:
    while True:
        ok = fn_send(h, ctypes.addressof(buf), width, height, GL_RGBA, True)  # invert=True for TD
        if frame % 30 == 0:
            print(f"Frame {frame:5d}  send={'OK' if ok else 'FAILED'}")
        frame += 1
        time.sleep(1 / 30)  # 30 fps

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    # CloseOpenGL and Release
    fn_close_gl = _vtbl_fn(h, V_CLOSE_OPENGL, ctypes.c_bool, [])
    fn_close_gl(h)
    fn_release = _vtbl_fn(h, V_RELEASE, None, [])
    fn_release(h)
    h = None
    print("Cleaned up.")
