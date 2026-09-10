"""Hardware-free tests over several GEN3 variants using the bundled registry."""

import numpy as np
import pytest
from paxini_sdk import sensor_registry

from lerobot_camera_paxini.rasterize import TaxelRasterizer

VARIANTS = ["PXSR-STDMC03A", "PXSR-STDDP03G", "PXSR-STDCP03A"]  # 9, 52, 239 taxels


@pytest.mark.parametrize("code", VARIANTS)
def test_all_variants_render(code):
    variant = sensor_registry.find_by_part_code(code)
    pts = np.asarray(sensor_registry.load_points(variant), np.float32)
    r = TaxelRasterizer(pts, 240, 320, splat_sigma_px=3.0)
    forces = np.zeros((variant.n_points, 3), np.float32)
    img = r.vector_rgb(forces, 5.0)
    assert img.shape == (320, 240, 3) and img.dtype == np.uint8
    assert np.all(img == 128)  # zero force = neutral gray everywhere splats reach

    forces[0] = [5.0, -5.0, 2.5]
    img = r.vector_rgb(forces, 5.0)
    assert img[..., 0].max() == 255 and img[..., 1].min() == 1  # +Fx red up, -Fy green down

    hm = r.heatmap(forces, 5.0)
    assert hm.shape == (320, 240, 3) and hm.max() > 0


def test_wrong_point_count_raises():
    variant = sensor_registry.find_by_part_code("PXSR-STDDP03G")
    pts = np.asarray(sensor_registry.load_points(variant), np.float32)
    r = TaxelRasterizer(pts, 100, 100)
    with pytest.raises(ValueError):
        r.vector_rgb(np.zeros((10, 3), np.float32), 5.0)


def test_plugin_registers_camera_type():
    import lerobot_camera_paxini  # noqa: F401
    from lerobot.cameras.configs import CameraConfig

    assert "paxini" in CameraConfig.get_known_choices()
