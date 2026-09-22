"""Synthetic RAW bursts with exact ground truth.

Real bursts have no noise-free reference, so merge quality is measured here on
bursts synthesised from a known scene:

1. a band-limited camera-linear RGB scene (procedural chart or a supplied image),
   rendered at 2x and area-downsampled to mimic pixel integration;
2. per-frame hand-shake (random sub-pixel translation + small rotation) and an
   optional independently moving textured object;
3. Bayer mosaicking (BGGR, like the HDR+ Pixel data);
4. Poisson shot noise and Gaussian read noise with an ISO-like gain ``k``:
   ``S = S0 * k``, ``O = O0 * k**2`` (S0, O0 default to the NoiseProfile of a real
   ISO-51 Pixel frame from the HDR+ dataset);
5. 10-bit quantisation with a 64 DN black level and clipping at white.

Frame 0 is the reference; ground truth is its noise-free mosaic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..noise import NoiseModel
from ..raw import CaptureMetadata, RawFrame, to_planes
from ..raw.bayer import plane_offsets

PATTERN = "BGGR"


@dataclass(frozen=True)
class SyntheticScene:
    name: str
    n_frames: int = 8
    exposure: float = 0.6  # scene scale in units of sensor white
    iso_gain: float = 1.0
    shot0: float = 1.184e-4
    read0: float = 2.0e-6
    shake_px: float = 2.0  # std of per-frame translation, full-resolution pixels
    rotation_deg: float = 0.15
    moving_object: bool = False
    object_speed_px: float = 10.0  # full-resolution pixels per frame
    seed: int = 0
    chart_seed: int = 0
    size: tuple[int, int] = (768, 1024)  # full-resolution (H, W); must be even


@dataclass
class SyntheticBurst:
    frames: list[RawFrame]
    gt_planes: np.ndarray  # (H/2, W/2, 4) noise-free reference in normalised units
    motion_mask: np.ndarray  # (H/2, W/2) bool — where scene motion occurs in reference coordinates
    noise: NoiseModel
    scene: SyntheticScene
    info: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------- scene content
def make_chart(h: int, w: int, seed: int = 0) -> np.ndarray:
    """Procedural camera-linear RGB test scene in [0, 1] with varied frequency content."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = xx / w, yy / h
    img = np.stack([0.25 + 0.35 * u, 0.30 + 0.25 * v, 0.45 - 0.25 * u * v], axis=-1)  # smooth gradients

    # multi-scale texture ("foliage/fabric")
    tex = np.zeros((h, w), np.float32)
    for scale, amp in ((64, 0.5), (16, 0.3), (4, 0.2), (2, 0.15)):
        small = rng.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
        tex += amp * cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    region = (u > 0.55) & (v > 0.5)
    img[region] *= (0.4 + 0.9 * tex[region])[:, None]

    # Siemens star (fine radial detail up to Nyquist)
    cy, cx, r0 = 0.3 * h, 0.25 * w, 0.22 * min(h, w)
    ang = np.arctan2(yy - cy, xx - cx)
    rad = np.hypot(yy - cy, xx - cx)
    star = rad < r0
    img[star] = (0.08 + 0.75 * (np.sin(36 * ang[star]) > 0))[:, None]

    # "text": thin dark strokes on a light panel
    y0, y1, x0, x1 = int(0.62 * h), int(0.92 * h), int(0.05 * w), int(0.48 * w)
    img[y0:y1, x0:x1] = 0.8
    for _ in range(60):
        ry, rx = rng.integers(y0 + 4, y1 - 12), rng.integers(x0 + 4, x1 - 30)
        if rng.random() < 0.5:
            img[ry : ry + rng.integers(6, 12), rx : rx + 2] = 0.05
        else:
            img[ry : ry + 2, rx : rx + rng.integers(8, 28)] = 0.05

    # colour patches, a deep shadow patch with faint detail, and a near-white highlight
    colors = rng.uniform(0.05, 0.85, size=(12, 3)).astype(np.float32)
    ph, pw = int(0.07 * h), int(0.06 * w)
    for i, c in enumerate(colors):
        py, px = int(0.06 * h) + (i // 6) * (ph + 4), int(0.55 * w) + (i % 6) * (pw + 4)
        img[py : py + ph, px : px + pw] = c
    sy, sx = int(0.25 * h), int(0.55 * w)
    img[sy : sy + ph * 2, sx : sx + pw * 3] = (0.01 + 0.012 * (tex[sy : sy + ph * 2, sx : sx + pw * 3] > 0.55))[..., None]
    img[sy : sy + ph, sx + pw * 3 + 8 : sx + pw * 5] = 0.97
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def _object_texture(radius: int, rng: np.random.Generator) -> np.ndarray:
    d = 2 * radius + 1
    base = rng.uniform(0.1, 0.9, 3).astype(np.float32)
    stripes = (np.sin(np.arange(d)[:, None] * 0.6 + np.arange(d)[None, :] * 0.3) > 0).astype(np.float32)
    return base[None, None, :] * (0.5 + 0.6 * stripes[..., None])


# ---------------------------------------------------------------------------- generation
def _affine(dx: float, dy: float, deg: float, center: tuple[float, float]) -> np.ndarray:
    m = cv2.getRotationMatrix2D(center, deg, 1.0)
    m[:, 2] += (dx, dy)
    return m


def generate_burst(scene: SyntheticScene, source_rgb: np.ndarray | None = None) -> SyntheticBurst:
    rng = np.random.default_rng(scene.seed)
    h, w = scene.size
    ss = 2  # supersampling factor
    hi = source_rgb if source_rgb is not None else make_chart(h * ss, w * ss, scene.chart_seed)
    hi = cv2.resize(hi, (w * ss, h * ss), interpolation=cv2.INTER_AREA) if hi.shape[:2] != (h * ss, w * ss) else hi
    hi = cv2.GaussianBlur(hi, (0, 0), 0.6 * ss)  # optics: band-limit before sampling

    radius = int(0.07 * min(h, w)) * ss
    obj = _object_texture(radius, rng)
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    disk = (xx * xx + yy * yy) <= radius * radius
    obj_start = np.array([0.35 * w, 0.72 * h]) * ss
    obj_dir = np.array([1.0, -0.35]) / np.hypot(1.0, 0.35)

    s = scene.shot0 * scene.iso_gain
    o = scene.read0 * scene.iso_gain**2
    noise = NoiseModel(s, o, source="synthetic_truth")
    center = (w * ss / 2.0, h * ss / 2.0)
    motion_mask = np.zeros((h // 2, w // 2), bool)
    frames: list[RawFrame] = []
    gt_planes = None
    transforms = []
    for i in range(scene.n_frames):
        if i == 0:
            m = _affine(0, 0, 0, center)
        else:
            dx, dy = rng.normal(0, scene.shake_px * ss, 2)
            m = _affine(dx, dy, rng.normal(0, scene.rotation_deg), center)
        transforms.append(m)
        img = cv2.warpAffine(hi, m, (w * ss, h * ss), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if scene.moving_object:
            pos = obj_start + obj_dir * scene.object_speed_px * ss * i
            _paste(img, obj, disk, pos)
            # footprint in reference coordinates: invert this frame's camera motion
            inv = cv2.invertAffineTransform(m)
            ref_pos = inv @ np.array([pos[0], pos[1], 1.0])
            _stamp_mask(motion_mask, ref_pos / (2 * ss), radius / (2 * ss) + 3)
        rgb = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA) * scene.exposure
        cfa = _mosaic(rgb)
        if i == 0:
            gt_planes = to_planes(cfa, PATTERN)
        frames.append(_to_frame(_sense(cfa, s, o, rng), s, o, i))
    return SyntheticBurst(
        frames, gt_planes.astype(np.float32), motion_mask, noise, scene,
        {"transforms": [t.tolist() for t in transforms]},
    )


def _paste(img: np.ndarray, obj: np.ndarray, disk: np.ndarray, pos: np.ndarray) -> None:
    r = disk.shape[0] // 2
    cy, cx = int(round(pos[1])), int(round(pos[0]))
    y0, y1, x0, x1 = cy - r, cy + r + 1, cx - r, cx + r + 1
    H, W = img.shape[:2]
    oy0, ox0 = max(0, -y0), max(0, -x0)
    y0c, x0c, y1c, x1c = max(0, y0), max(0, x0), min(H, y1), min(W, x1)
    if y1c <= y0c or x1c <= x0c:
        return
    sub = img[y0c:y1c, x0c:x1c]
    m = disk[oy0 : oy0 + (y1c - y0c), ox0 : ox0 + (x1c - x0c)]
    sub[m] = obj[oy0 : oy0 + (y1c - y0c), ox0 : ox0 + (x1c - x0c)][m]


def _stamp_mask(mask: np.ndarray, center_xy: np.ndarray, radius: float) -> None:
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    mask |= (xx - center_xy[0]) ** 2 + (yy - center_xy[1]) ** 2 <= radius * radius


def _mosaic(rgb: np.ndarray) -> np.ndarray:
    """Sample an (H, W, 3) image on the BGGR lattice."""
    channel = {"R": 0, "Gr": 1, "Gb": 1, "B": 2}
    cfa = np.empty(rgb.shape[:2], np.float32)
    for name, (r, c) in plane_offsets(PATTERN).items():
        cfa[r::2, c::2] = rgb[r::2, c::2, channel[name]]
    return cfa


def _sense(cfa: np.ndarray, s: float, o: float, rng: np.random.Generator) -> np.ndarray:
    """Poisson-Gaussian sensing + 10-bit quantisation, returned in normalised units."""
    signal = np.clip(cfa, 0.0, None).astype(np.float64)
    shot = rng.poisson(signal / s) * s if s > 0 else signal
    x = shot + rng.normal(0.0, np.sqrt(o), cfa.shape)
    black, white = 64.0, 1023.0
    dn = np.clip(np.rint(x * (white - black) + black), 0, white)
    return ((dn - black) / (white - black)).astype(np.float32)


def _to_frame(cfa: np.ndarray, s: float, o: float, index: int) -> RawFrame:
    meta = CaptureMetadata(
        make="HIE", model="synthetic", iso=100.0, exposure_time=0.01, orientation=1, bits_per_sample=10,
        raw_white_level=1023.0, raw_black_level=[64.0] * 4, as_shot_neutral=np.ones(3),
        noise_profile=np.array([[s, o]] * 3),
    )
    meta.extras["frame_index"] = index
    return RawFrame(cfa=cfa, pattern=PATTERN, meta=meta, source=f"synthetic:{index}")


# ---------------------------------------------------------------------------- scenario sets
def scenarios(split: str = "test") -> list[SyntheticScene]:
    """Named scenarios. ``tune`` and ``test`` use disjoint noise seeds *and* chart seeds."""
    base_seed, chart = (0, 0) if split == "test" else (1000, 7)
    specs = [
        dict(name="daylight_static", exposure=0.6, iso_gain=1.0, shake_px=1.5),
        dict(name="indoor_handheld", exposure=0.15, iso_gain=8.0, shake_px=3.0, rotation_deg=0.25),
        dict(name="night_handheld", exposure=0.03, iso_gain=32.0, shake_px=3.0, rotation_deg=0.25),
        dict(name="night_motion", exposure=0.03, iso_gain=32.0, shake_px=2.0, moving_object=True),
        dict(name="daylight_motion", exposure=0.6, iso_gain=1.0, shake_px=1.5, moving_object=True, object_speed_px=18.0),
        dict(name="large_shake", exposure=0.3, iso_gain=4.0, shake_px=12.0, rotation_deg=0.6),
    ]
    return [SyntheticScene(seed=base_seed + i, chart_seed=chart, **spec) for i, spec in enumerate(specs)]
