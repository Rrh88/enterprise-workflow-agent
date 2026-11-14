"""Make a harder test set: render each invoice PDF to an image, then degrade it
(rotation, blur, contrast loss, noise, JPEG compression) at three severity levels."""
import json
import random
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageEnhance, ImageFilter

SRC = Path("data/invoices")
DST = Path("data/hard")
DST.mkdir(exist_ok=True)

# rotation (deg), blur radius, noise std, jpeg quality, contrast
LEVELS = {
    "mild": (1.5, 0.6, 6, 70, 0.9),
    "medium": (3.0, 1.1, 12, 45, 0.75),
    "severe": (5.0, 1.4, 16, 35, 0.65),
}
NAMES = list(LEVELS)

rng = random.Random(11)
np.random.seed(11)
levels = {}

for i, pdf in enumerate(sorted(SRC.glob("*.pdf"))):
    level = NAMES[i % 3]
    rot, blur, noise, quality, contrast = LEVELS[level]
    pix = pymupdf.open(pdf)[0].get_pixmap(dpi=110)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = img.rotate(rng.uniform(-rot, rot), expand=True, fillcolor=(255, 255, 255))
    img = img.filter(ImageFilter.GaussianBlur(blur))
    img = ImageEnhance.Contrast(img).enhance(contrast)
    arr = np.asarray(img).astype(np.float32)
    arr += np.random.normal(0, noise, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    img.save(DST / f"{pdf.stem}.jpg", quality=quality)
    levels[pdf.stem] = level
    print(pdf.stem, level)

(DST / "levels.json").write_text(json.dumps(levels, indent=2))
print(f"made {len(levels)} degraded images in {DST}")