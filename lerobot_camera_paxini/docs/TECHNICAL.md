# Technical notes: lerobot_camera_paxini

For maintainers and reviewers. The user guide covers usage, this covers how and why.

## Design goal

One plugin for every GEN3 variant, structured after the existing community camera plugins (lerobot-camera-xense and the hexfellow suite): empty runtime dependencies, the vendor SDK as an optional extra, config registered with `@CameraConfig.register_subclass("paxini")`, and the full Camera ABC including the static `find_cameras`.

## Variant genericity

Nothing in the package knows a taxel count. Three sources combine at connect time:

1. The board reports the point count (high-speed board register read) or the part code implies it (serial board, from config).
2. `paxini_sdk.sensor_registry` maps count or part code to a variant. Twelve variants are bundled, 9 to 239 points.
3. `sensor_registry.load_points(variant)` returns per-taxel (x, y, z) millimeter coordinates from the vendor data files.

If both a part code and a board count are available they are cross-checked, and a mismatch raises rather than rendering a wrong layout. An unknown count fails with an instruction to pass the part code, which keeps new variants usable before the registry catches up.

## The rasterizer

`TaxelRasterizer` precomputes everything shape-dependent once at connect, then every frame is two matrix products.

Construction: taxel (x, y) coordinates are fit into the image with equal scaling on both axes and an 8 px margin, y flipped so sensor +y points up. A splat weight matrix W of shape (H*W, P) holds a Gaussian of `splat_sigma_px` around each taxel's pixel position, truncated below 1e-3, normalized so every taxel peaks at exactly 1.0. A per-pixel normalizer makes overlapping splats average instead of add, so two adjacent taxels at 1 N do not render as 2 N.

Per frame: `W @ forces` splats a (P, 3) array to (H*W, 3), then either encoding maps to uint8. Cost at the largest variant (239 taxels, 240 x 320) is a 76800 x 239 by 239 x 3 product, well under a millisecond in numpy.

`splat_sigma_px = 0` degenerates to nearest-pixel assignment, one lit pixel per taxel.

## The vector_rgb encoding

`img = clip(force / force_max_n, -1, 1) * 127 + 128`, per channel. Chosen over a magnitude colormap as the default because it is invertible: a policy or a later analysis can recover the signed 3-axis force field from the image up to quantization. Quantization step is `force_max_n / 127`, about 0.04 N at the 5 N default, which sits below the sensor's own noise floor.

The heatmap mode is a fixed four-stop ramp (green, yellow, orange, red) on force magnitude with a dark-at-zero correction, matching what users know from the vendor host app. It is not invertible and exists for humans.

## Threading model

One daemon thread per camera, two shapes depending on the board:

1. Serial board: a poll loop calling `read_distributed_force()` at `fps`, converting counts to newtons, publishing through a lock plus event. Transient read errors log a warning and retry after 100 ms, the loop never dies on one bad frame.
2. High-speed board: the SDK's `stream_auto_push` generator is consumed as fast as the board pushes (about 91 Hz), frames for the configured module are rendered, the rest ignored. `fps` does not throttle this path, lerobot's own recording loop samples at dataset rate.

`async_read` returns a copy of the latest rendered frame, `read` is an alias with a 1 s timeout. Rendering happens on the reader thread, not the caller, so a slow consumer never backs up the serial port.

## Failure semantics

Connect-time errors raise: no active modules, unknown part code, count mismatch. Run-time read errors on the serial path retry forever with warnings. A dying push stream logs an exception and leaves the last frame in place, so recording continues with a frozen tactile image rather than crashing mid dataset. Whether freezing is preferable to crashing during a long recording is a judgment call, the current choice favors not losing the session.

## Tests

`tests/test_rasterize.py` renders the smallest, the reference, and the largest variant (9, 52, 239 taxels) from the real bundled coordinates, checks zero force gives uniform neutral gray, a single loaded taxel deflects the correct channels in the correct directions, shape mismatches raise, and the `paxini` type registers with `CameraConfig`. No hardware, runs in 3 s.

## Known limitations

1. uint8 quantization bounds force resolution at `force_max_n / 127`. Use the robot plugin for float precision.
2. One camera instance per module. Two fingertips on one high-speed board means two camera entries opening the same port, which the shared-board handling in paxini-sdk must arbitrate. Verified single-module only so far.
3. The video codec path smears per-taxel values (chroma subsampling plus lossy compression). Documented in the user guide, PNG mode is the workaround.
4. `find_cameras` lists all serial ports, it cannot yet fingerprint which ones are Paxini boards without opening them.
