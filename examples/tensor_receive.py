"""
tensor_receive.py — Receive Spout frames directly into PyTorch tensors.

The pixel buffer is pre-allocated as a numpy array and shared with ctypes so
the DLL writes into it with no extra copy. The numpy array is then wrapped as
a torch tensor (also zero-copy via from_numpy).

Requirements: torch, numpy
"""
import sys, os, ctypes, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from spout import SpoutReceiver, GL_RGBA


def make_recv_buffer(w: int, h: int):
    """
    Allocate a C-contiguous uint8 RGBA numpy array and a ctypes view into it.
    The ctypes view is what we hand to receive_image(); numpy sees the same memory.
    """
    arr = np.empty(h * w * 4, dtype=np.uint8)
    ctypes_buf = (ctypes.c_ubyte * arr.size).from_buffer(arr)
    return arr, ctypes_buf


def buf_to_tensor_hwc(arr: np.ndarray, h: int, w: int) -> torch.Tensor:
    """Return an (H, W, 4) uint8 tensor sharing the numpy buffer (no copy)."""
    return torch.from_numpy(arr.reshape(h, w, 4))


def buf_to_tensor_chw(arr: np.ndarray, h: int, w: int, drop_alpha: bool = True) -> torch.Tensor:
    """
    Return a float32 (C, H, W) tensor in [0, 1] — the typical format expected
    by torchvision transforms and most diffusion model encoders.

    drop_alpha=True  → shape (3, H, W)  RGB
    drop_alpha=False → shape (4, H, W)  RGBA
    """
    hwc = torch.from_numpy(arr.reshape(h, w, 4))      # uint8, shared memory
    chw = hwc.permute(2, 0, 1).float() / 255.0        # float32, new tensor
    return chw[:3] if drop_alpha else chw


def process_frame(tensor: torch.Tensor):
    """Placeholder — plug your inference / analysis here."""
    mean = tensor.mean().item()
    print(f"  frame tensor  shape={tuple(tensor.shape)}  dtype={tensor.dtype}  mean={mean:.3f}")


def main():
    print("Waiting for a Spout sender named 'TensorSender' (or any active sender)…")
    print("Press Ctrl+C to stop.\n")

    with SpoutReceiver("TensorSender") as receiver:
        arr, ctypes_buf = None, None
        w = h = 0
        frame_count = 0

        while True:
            connected = receiver.receive()

            if not connected:
                time.sleep(0.2)
                continue

            # Reallocate buffers whenever sender resolution changes
            if receiver.is_updated or arr is None:
                w = receiver.sender_width
                h = receiver.sender_height
                arr, ctypes_buf = make_recv_buffer(w, h)
                print(f"Connected: '{receiver.sender_name}'  {w}x{h}")

            if not receiver.is_frame_new:
                time.sleep(1 / 120)
                continue

            # DLL writes directly into the numpy-backed buffer
            receiver.receive_image(ctypes_buf, w, h, GL_RGBA)

            # Zero-copy tensor view (uint8 HWC) — safe to read until next receive_image
            frame_hwc = buf_to_tensor_hwc(arr, h, w)

            # Float CHW tensor for model input — this allocates a new tensor
            frame_chw = buf_to_tensor_chw(arr, h, w, drop_alpha=True)

            frame_count += 1
            if frame_count % 60 == 0:
                process_frame(frame_chw)

            time.sleep(1 / 120)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
