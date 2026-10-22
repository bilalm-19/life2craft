"""Cut the subject out of photos by removing the background with `rembg`.

Saves `photo.jpg` as a transparent PNG, `<out>/photo_cutout.png` (default folder: data/crop_outputs).

    python cutout.py photo.jpg
    python cutout.py a.jpg b.png --out my_cutouts
"""

import argparse
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

DEFAULT_OUT = "data/crop_outputs"


def get_subject_img(paths, out_dir=DEFAULT_OUT, model="u2net"):
    """Cut the subject out of each photo using `rembg`.
    Saves in_example.jpg as out_dir/in_example_cutout.png (PNG, to keep the transparency) and returns the cutouts.
    """
    session = new_session(model)                     # load the model once, not once per photo
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)       # also creates any missing parent folders

    outputs = []
    for path in paths:
        path = Path(path)
        img = Image.open(path).convert("RGB")        # raises a clear error if the file is missing; RGB handles odd file types
        cutout = remove(img, session=session)        # a Pillow image with transparency (RGBA)
        save_path = out_dir / f"{path.stem}_cutout.png"
        cutout.save(save_path)
        print(f"saved {save_path}")
        outputs.append(cutout)
    return outputs


def main():
    ap = argparse.ArgumentParser(description="Cut the subject out of one or more photos (writes a transparent PNG for each)")
    ap.add_argument("paths", nargs="+", help="path(s) of the photo(s) to cut the subject out of")
    ap.add_argument("--out", default=DEFAULT_OUT, help=f"folder to save the cutouts in (default: {DEFAULT_OUT})")
    args = ap.parse_args()                           # keep the result: the values are on `args`, not on `ap`

    get_subject_img(args.paths, out_dir=args.out)


if __name__ == "__main__":                           # only run main() when this file is started directly, not when imported
    main()