"""Convert source art into assets/icon.png + assets/icon.ico."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SRC_CANDIDATES = [
    ASSETS / "clip2tube-icon-src.jpg",
    ASSETS / "clip2tube-icon-src.png",
    ASSETS / "clip2tube-icon.jpg",
    ASSETS / "clip2tube-icon.png",
]


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    src_path = next((p for p in SRC_CANDIDATES if p.is_file()), None)
    if src_path is None:
        raise SystemExit("No source icon found in assets/")

    src = Image.open(src_path).convert("RGBA")
    hi = src.resize((512, 512), Image.Resampling.LANCZOS)

    # Knock out near-white canvas + apply rounded-rect alpha
    # (avoids white corner triangles in the sidebar logo)
    px = hi.load()
    for y in range(hi.height):
        for x in range(hi.width):
            r, g, b, a = px[x, y]
            if r > 240 and g > 240 and b > 240:
                px[x, y] = (r, g, b, 0)

    mask = Image.new("L", hi.size, 0)
    draw = ImageDraw.Draw(mask)
    radius = int(hi.width * 0.18)
    draw.rounded_rectangle(
        (0, 0, hi.width - 1, hi.height - 1), radius=radius, fill=255
    )
    r, g, b, a = hi.split()
    a = Image.composite(a, Image.new("L", hi.size, 0), mask)
    hi = Image.merge("RGBA", (r, g, b, a))

    png_path = ASSETS / "icon.png"
    hi.save(png_path, "PNG")

    master = hi.resize((256, 256), Image.Resampling.LANCZOS)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = ASSETS / "icon.ico"
    master.save(ico_path, format="ICO", sizes=ico_sizes)

    print(f"OK {png_path} ({png_path.stat().st_size} bytes)")
    print(f"OK {ico_path} ({ico_path.stat().st_size} bytes)")
    with Image.open(ico_path) as ico:
        print("ICO sizes:", ico.info.get("sizes") or list({ico.size}))


if __name__ == "__main__":
    main()
