"""
share_image.py — Load an image and share it to TouchDesigner via Spout.

Usage:
    python examples/share_image.py                      # uses assets/unveil_logo.png
    python examples/share_image.py path/to/image.jpg
    python examples/share_image.py path/to/image.png    (also .bmp, .tiff, …)

In TouchDesigner: add a "Spout In" TOP and it will receive "PythonImage".

Requirements:
    pip install Pillow
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from spout import SpoutSender, GL_RGBA

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_IMAGE = os.path.join(os.path.dirname(_HERE), "assets", "unveil_logo.png")

if len(sys.argv) > 1:
    image_path = sys.argv[1]
elif os.path.exists(_DEFAULT_IMAGE):
    image_path = _DEFAULT_IMAGE
    print(f"No image given — using default demo asset: {image_path}")
else:
    image_path = input("Image path: ").strip().strip('"')

if not os.path.exists(image_path):
    print(f"File not found: {image_path}")
    sys.exit(1)

print(f"Loading: {image_path}")
img = Image.open(image_path).convert("RGBA")
width, height = img.size
pixels = img.tobytes()  # raw RGBA bytes, top-to-bottom
print(f"Image size: {width}x{height}  ({len(pixels)} bytes)")

with SpoutSender("PythonImage") as sender:
    if not sender.create_opengl():
        print("WARNING: create_opengl() failed — send_image may not work without a GL context.")
        print("         Try running from inside an OpenGL-capable application.")
    else:
        print("OpenGL context created OK")

    print("\nSending to TouchDesigner as 'PythonImage'")
    print("In TouchDesigner: add a Spout In TOP -> it should appear immediately.")
    print("Press Ctrl+C to stop.\n")

    frame = 0
    try:
        while True:
            ok = sender.send_image(pixels, width, height, GL_RGBA, invert=True)
            if frame % 30 == 0:
                print(f"Frame {frame:5d}  send={'OK' if ok else 'FAILED'}")
            frame += 1
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sender.close_opengl()
        print("Cleaned up.")
