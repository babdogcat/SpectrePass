import cv2
import numpy as np
from PIL import Image
import os

def process_image(input_path: str, output_path: str, quality: int = 92) -> None:
    """
    Simple, image-safe AI artifact scrubber.
    Uses only techniques that preserve visual quality.
    """
    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")

    has_alpha = img.shape[2] == 4 if len(img.shape) == 3 else False
    if has_alpha:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
    else:
        bgr = img.copy()

    h, w, c = bgr.shape
    work = bgr.copy()
    tmp_path = output_path + ".tmp.jpg"

    # 1. Subtle color channel micro-shift
    work_float = work.astype(np.float32)
    shift = np.random.uniform(-2, 2)
    M_color = np.float32([[1, 0, shift], [0, 1, 0]])
    work_float[:, :, 0] = cv2.warpAffine(work_float[:, :, 0], M_color, (w, h))

    # 2. Very light Gaussian noise
    noise = np.random.normal(0, 2.3, (h, w, c)).astype(np.float32)
    work_float = np.clip(work_float + noise, 0, 255)

    # 3. Film grain (luminance-dependent)
    lum = cv2.cvtColor(work_float.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    for ch in range(c):
        grain_sigma = 3.0 * (0.4 + lum * 0.6)
        grain = np.random.normal(0, 1, (h, w)).astype(np.float32) * grain_sigma
        work_float[:, :, ch] += grain
    work_float = np.clip(work_float, 0, 255)

    # 4. Bilateral filter (edge-preserving)
    work = cv2.bilateralFilter(work_float.astype(np.uint8), 5, 30, 30)

    # 4. Unsharp mask (gentle)
    work_f = work.astype(np.float32)
    blurred = cv2.GaussianBlur(work_f, (0, 0), 2)
    work_f = cv2.addWeighted(work_f, 1.2, blurred, -0.2, 0)
    work = np.clip(work_f, 0, 255).astype(np.uint8)

    # 5. JPEG recompress
    cv2.imwrite(tmp_path, work, [cv2.IMWRITE_JPEG_QUALITY, 85])
    work = cv2.imread(tmp_path)

    # 6. Light denoise
    work = cv2.fastNlMeansDenoisingColored(work, None, 2, 2, 7, 21)

    # 7. Restore dims
    if work.shape[:2] != (h, w):
        work = cv2.resize(work, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # Save
    cv2.imwrite(output_path, work, [cv2.IMWRITE_JPEG_QUALITY, quality, cv2.IMWRITE_JPEG_OPTIMIZE, 1])

    # Strip metadata
    with Image.open(output_path) as pil_img:
        clean = Image.new(pil_img.mode, pil_img.size)
        clean.putdata(list(pil_img.getdata()))
        out_fmt = "PNG" if output_path.lower().endswith(".png") else "JPEG"
        clean.save(output_path, out_fmt, quality=quality, optimize=True)

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

if __name__ == "__main__":
    import sys
    inp = sys.argv[1] if len(sys.argv) > 1 else "input.jpg"
    out = sys.argv[2] if len(sys.argv) > 2 else "output.jpg"
    process_image(inp, out)