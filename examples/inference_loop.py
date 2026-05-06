"""
inference_loop.py — Real-time Spout ↔ model inference round-trip.

Data flow:
    [Spout sender, e.g. TouchDesigner / OBS]
        ↓  receive_image  (zero-copy into numpy buffer)
    [preprocess]  → float32 CHW tensor
        ↓  model()
    [postprocess] → uint8 RGBA numpy array
        ↓  send_image  (zero-copy via ctypes alias)
    [Spout receiver, e.g. TouchDesigner / resolume]

The model slot is a stub — drop in StreamDiffusion, ControlNet, or any
torch model that accepts (1, 3, H, W) float32 in [0, 1].

Requirements: torch, numpy
"""
import sys, os, ctypes, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import torch.nn as nn
from spout import SpoutSender, SpoutReceiver, GL_RGBA


# ---------------------------------------------------------------------------
# Model placeholder — replace with your actual pipeline
# ---------------------------------------------------------------------------

class IdentityModel(nn.Module):
    """Pass-through model. Replace with StreamDiffusion / ControlNet / etc."""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x  # (1, 3, H, W) → (1, 3, H, W)


# ---------------------------------------------------------------------------
# Buffer helpers (shared between send and receive sides)
# ---------------------------------------------------------------------------

def _make_recv_buffer(w: int, h: int):
    arr = np.empty(h * w * 4, dtype=np.uint8)
    return arr, (ctypes.c_ubyte * arr.size).from_buffer(arr)


def recv_buf_to_model_input(arr: np.ndarray, h: int, w: int, device) -> torch.Tensor:
    """
    bytearray DLL output → float32 (1, 3, H, W) tensor on *device*.
    Drops the alpha channel. One allocation (the float tensor).
    """
    hwc_u8 = torch.from_numpy(arr.reshape(h, w, 4))           # uint8, no copy
    chw_f  = hwc_u8[..., :3].permute(2, 0, 1).float() / 255  # float, new tensor
    return chw_f.unsqueeze(0).to(device)                       # (1, 3, H, W)


def model_output_to_send_buf(output: torch.Tensor):
    """
    float32 (1, 3, H, W) [0, 1] → contiguous RGBA uint8 numpy array + ctypes alias.
    """
    chw = output.squeeze(0).detach().cpu().clamp(0, 1)         # (3, H, W)
    hwc = chw.permute(1, 2, 0).numpy()                        # (H, W, 3) float
    h, w = hwc.shape[:2]

    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = (hwc * 255).astype(np.uint8)
    rgba[...,  3] = 255

    rgba = np.ascontiguousarray(rgba)
    return rgba, (ctypes.c_ubyte * rgba.size).from_buffer(rgba), w, h


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    model = IdentityModel().to(device).eval()
    # ── StreamDiffusion example (uncomment & adapt) ──────────────────────
    # from streamdiffusion import StreamDiffusion
    # from streamdiffusion.image_utils import postprocess_image
    # pipe = StreamDiffusion(...)
    # pipe.prepare("your prompt")
    # model = pipe
    # ---------------------------------------------------------------------

    IN_SENDER  = "InputSender"   # the Spout sender feeding frames in
    OUT_SENDER = "InferenceOut"  # we publish results here

    print(f"Receiving from '{IN_SENDER}', sending to '{OUT_SENDER}'")
    print("Press Ctrl+C to stop.\n")

    with SpoutReceiver(IN_SENDER) as rx, SpoutSender(OUT_SENDER) as tx:
        recv_arr = recv_ctypes = None
        w = h = 0
        frame_count = 0
        t_last_report = time.perf_counter()

        while True:
            # ── 1. receive ───────────────────────────────────────────────
            if not rx.receive():
                time.sleep(0.2)
                continue

            if rx.is_updated or recv_arr is None:
                w, h = rx.sender_width, rx.sender_height
                recv_arr, recv_ctypes = _make_recv_buffer(w, h)
                print(f"Input: '{rx.sender_name}'  {w}x{h}")

            if not rx.is_frame_new:
                time.sleep(1 / 240)
                continue

            rx.receive_image(recv_ctypes, w, h, GL_RGBA)

            # ── 2. preprocess ─────────────────────────────────────────────
            x = recv_buf_to_model_input(recv_arr, h, w, device)  # (1, 3, H, W)

            # ── 3. inference ──────────────────────────────────────────────
            with torch.inference_mode():
                y = model(x)                                      # (1, 3, H, W)

            # ── 4. postprocess & send ─────────────────────────────────────
            rgba, send_ctypes, out_w, out_h = model_output_to_send_buf(y)
            tx.send_image(send_ctypes, out_w, out_h, GL_RGBA)

            frame_count += 1
            now = time.perf_counter()
            if now - t_last_report >= 2.0:
                print(
                    f"frames={frame_count:6d}  "
                    f"rx_fps={rx.sender_fps:.1f}  "
                    f"tx_fps={tx.fps:.1f}"
                )
                t_last_report = now


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
