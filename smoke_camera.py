"""Hardware smoke test for lerobot_camera_paxini, no lerobot env needed.

Connects to the real high-speed adapter, streams 6 s per render mode, keeps
the frame with the strongest signal (not the last one, which is usually a
rest frame), saves one PNG per mode. Run on the bench:

    python3 smoke_camera.py /dev/ttyACM1 14

Pass: distinct fps near the board push rate (80-91), heatmap peak frame
max well above 0, vector_rgb peak frame straying far from 128 both ways,
and a blob in the PNGs where the finger pressed.
"""
import sys, time
import numpy as np

from lerobot_camera_paxini import PaxiniCamera, PaxiniCameraConfig

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM1"
module = int(sys.argv[2]) if len(sys.argv) > 2 else 14

for render in ("heatmap", "vector_rgb"):
    cfg = PaxiniCameraConfig(port=port, module_index=module, render=render,
                             fps=30, width=240, height=320)
    cam = PaxiniCamera(cfg)
    cam.connect()
    print(f"{render}: connected, PRESS THE SLOT-{module} FINGERTIP NOW, 6 s")
    best, best_score, distinct, prev = None, -1.0, 0, None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 6:
        img = cam.async_read(timeout_ms=500)
        if prev is None or not np.array_equal(img, prev):
            distinct += 1
            prev = img
            ref = 128 if render == "vector_rgb" else 0
            score = float(np.abs(img.astype(np.int16) - ref).sum())
            if score > best_score:
                best_score, best = score, img
        time.sleep(0.005)
    cam.disconnect()
    out = f"/tmp/smoke_{render}.png"
    try:
        import cv2; cv2.imwrite(out, best[:, :, ::-1])
    except ImportError:
        from PIL import Image; Image.fromarray(best).save(out)
    print(f"{render}: {distinct/6:.0f} distinct fps, peak frame min {best.min()} "
          f"max {best.max()} -> {out}")
