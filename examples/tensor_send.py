"""
tensor_send.py — Send a PyTorch tensor as a Spout frame.

Converts a float32 CHW tensor [0, 1] (typical model output) to RGBA uint8
and shares it with zero extra copy by letting ctypes alias the numpy buffer.

Requirements: torch, numpy
"""
import sys, os, ctypes, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from spout import SpoutSender, GL_RGBA

WIDTH  = 512
HEIGHT = 512
FPS    = 30


def tensor_to_spout_buf(tensor: torch.Tensor) -> tuple[np.ndarray, int, int]:
    """
    Convert a float32 CHW or HWC tensor [0, 1] to a C-contiguous RGBA uint8
    numpy array. Returns (rgba_array, width, height).

    Supports:
        (C, H, W)  — typical diffusion model output (1 or 3 channels)
        (H, W, C)  — typical torchvision / PIL layout
        (H, W)     — grayscale
    """
    t = tensor.detach().cpu().float().clamp(0, 1)

    if t.ndim == 2:                       # (H, W) → grayscale
        t = t.unsqueeze(-1).expand(-1, -1, 3)   # → (H, W, 3)
    elif t.ndim == 3 and t.shape[0] in (1, 3, 4):  # (C, H, W) → (H, W, C)
        t = t.permute(1, 2, 0)
        if t.shape[2] == 1:
            t = t.expand(-1, -1, 3)

    h, w, c = t.shape
    arr_rgb = (t.numpy() * 255).astype(np.uint8)   # (H, W, C) uint8

    # Build RGBA — add alpha channel if not already there
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :min(c, 3)] = arr_rgb[..., :3]
    rgba[..., 3] = 255  # fully opaque

    return np.ascontiguousarray(rgba), w, h


def make_test_tensor(frame_num: int) -> torch.Tensor:
    """Synthetic animated frame — replace with your model output."""
    t = frame_num / FPS
    x = torch.linspace(0, 1, WIDTH).unsqueeze(0).expand(HEIGHT, -1)
    y = torch.linspace(0, 1, HEIGHT).unsqueeze(1).expand(-1, WIDTH)
    r = (torch.sin(2 * torch.pi * (x + t)) * 0.5 + 0.5)
    g = (torch.sin(2 * torch.pi * (y + t * 1.3)) * 0.5 + 0.5)
    b = (torch.cos(2 * torch.pi * (x - t * 0.7)) * 0.5 + 0.5)
    return torch.stack([r, g, b])  # (3, H, W)


def main():
    print(f"Sending tensors as Spout frames  {WIDTH}x{HEIGHT} @ {FPS} fps")
    print("Press Ctrl+C to stop.\n")

    with SpoutSender("TensorSender") as sender:
        frame_num = 0
        interval  = 1.0 / FPS

        while True:
            t0 = time.perf_counter()

            # --- your model output goes here ---
            tensor = make_test_tensor(frame_num)       # (3, H, W) float [0,1]

            rgba, w, h = tensor_to_spout_buf(tensor)

            # Zero-copy: alias the numpy array as a ctypes buffer
            ctypes_buf = (ctypes.c_ubyte * rgba.size).from_buffer(rgba)
            sender.send_image(ctypes_buf, w, h, GL_RGBA)

            if frame_num % FPS == 0:
                print(f"frame={frame_num:6d}  fps={sender.fps:.1f}")

            frame_num += 1
            time.sleep(max(0.0, interval - (time.perf_counter() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSender stopped.")
