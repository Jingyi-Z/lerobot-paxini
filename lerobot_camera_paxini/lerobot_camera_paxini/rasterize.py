"""Rasterize a Paxini taxel cloud into an image. Pure numpy, no hardware.

Works for any GEN3 variant: the (x, y) taxel coordinates come in as arguments
(from paxini_sdk.sensor_registry.load_points), so nothing here depends on the
taxel count. All arrays are float32 in, uint8 (H, W, 3) out.
"""

from __future__ import annotations

import numpy as np


class TaxelRasterizer:
    """Precomputes the pixel mapping for one sensor variant, then renders
    each (P, 3) force frame with two matmuls. Cheap enough for 30 fps at any
    variant size (P <= 239)."""

    def __init__(
        self,
        points_mm: np.ndarray,  # (P, >=2) taxel coordinates, mm; only x, y used
        width: int,
        height: int,
        splat_sigma_px: float = 3.0,
        margin_px: int = 8,
    ):
        pts = np.asarray(points_mm, dtype=np.float32)[:, :2]
        self.n_points = pts.shape[0]
        self.width, self.height = int(width), int(height)

        # Fit the taxel cloud into the image with equal scaling on both axes.
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        span = np.maximum(hi - lo, 1e-6)
        scale = min(
            (self.width - 2 * margin_px) / span[0],
            (self.height - 2 * margin_px) / span[1],
        )
        center_px = np.array([self.width, self.height], np.float32) / 2
        center_mm = (lo + hi) / 2
        # y flipped so +y in sensor coords points up in the image.
        xy = (pts - center_mm) * np.array([scale, -scale], np.float32) + center_px

        # Per-taxel splat weights over the pixel grid: (H*W, P), normalized so
        # each taxel contributes 1.0 total at its own footprint. With sigma=0
        # each taxel owns exactly its nearest pixel.
        gy, gx = np.mgrid[0 : self.height, 0 : self.width]
        grid = np.stack([gx.ravel(), gy.ravel()], axis=1).astype(np.float32)
        d2 = ((grid[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2)  # (H*W, P)
        if splat_sigma_px > 0:
            w = np.exp(-d2 / (2 * splat_sigma_px**2))
            w[w < 1e-3] = 0.0
        else:
            w = np.zeros_like(d2)
            w[d2.argmin(axis=0), np.arange(self.n_points)] = 1.0
        col_max = w.max(axis=0, keepdims=True)
        col_max[col_max == 0] = 1.0
        self._weights = (w / col_max).astype(np.float32)  # peak 1.0 per taxel
        # Pixel-wise normalizer so overlapping splats average instead of sum.
        self._wsum = self._weights.sum(axis=1, keepdims=True)
        self._wsum[self._wsum == 0] = 1.0

    def vector_rgb(self, forces: np.ndarray, force_max_n: float) -> np.ndarray:
        """(P, 3) newtons -> (H, W, 3) uint8; Fx, Fy, Fz to R, G, B around 128."""
        f = np.asarray(forces, dtype=np.float32)
        if f.shape != (self.n_points, 3):
            raise ValueError(f"expected ({self.n_points}, 3), got {f.shape}")
        px = (self._weights @ f) / self._wsum  # (H*W, 3), splat-averaged
        img = np.clip(px / force_max_n, -1.0, 1.0) * 127.0 + 128.0
        return img.reshape(self.height, self.width, 3).astype(np.uint8)

    def heatmap(self, forces: np.ndarray, force_max_n: float) -> np.ndarray:
        """(P, 3) newtons -> (H, W, 3) uint8 magnitude colormap
        (green -> yellow -> orange -> red, vendor-app style)."""
        f = np.asarray(forces, dtype=np.float32)
        mag = np.linalg.norm(f, axis=1)  # (P,)
        px = ((self._weights @ mag[:, None]) / self._wsum).ravel()
        t = np.clip(px / force_max_n, 0.0, 1.0)
        stops_t = np.array([0.0, 0.4, 0.7, 1.0], np.float32)
        stops_c = np.array(
            [[0, 180, 40], [235, 235, 0], [245, 140, 0], [220, 0, 0]], np.float32
        )
        img = np.empty((t.size, 3), np.float32)
        for c in range(3):
            img[:, c] = np.interp(t, stops_t, stops_c[:, c])
        # Zero-force pixels stay dark instead of resting green.
        img *= np.clip(t / max(0.02, stops_t[1] * 0.05), 0, 1)[:, None] ** 0.5
        return img.reshape(self.height, self.width, 3).astype(np.uint8)
