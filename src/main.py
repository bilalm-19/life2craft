"""Photo -> Minecraft .schem.

    python src/main.py data/inputs/eiffel_tower.jpg --height 330 --round --pitch 1.5
    python src/main.py data/inputs/house.jpg --height 5.5 --depth 14 --pitch 0.25
"""
import argparse
import json
from pathlib import Path

import numpy as np

from cutout import get_subject_img
from export import save_schem
from match import match_cells, summarise
from voxelise import MC_BLOCK_DIMS, extrude, grid_size, hollow, resample_dominant, revolve

PALETTE_PATH = Path(__file__).resolve().parent.parent / "data" / "palette.json"    # src/main.py -> project root -> data/
with open(PALETTE_PATH) as f:
    PALETTE = {name: tuple(rgb) for name, rgb in json.load(f).items()}            # {block name: (R, G, B)}

def cutout_to_arrays(cutout):
    """RGBA cutout image -> rgb (h, w, 3) and mask (h, w), both trimmed to the subject's bounding box."""
    rgba = np.asarray(cutout)
    rgb = rgba[..., :3].astype(float)
    mask = rgba[..., 3] > 128                        # True = subject (alpha runs 0-255, so 128 is about halfway)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        raise SystemExit("No subject found in the cutout.")
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    return rgb[box], mask[box]


def main():
    ap = argparse.ArgumentParser(description="Photo of a building or tower -> Minecraft .schem")
    ap.add_argument("photo")
    ap.add_argument("--height", type=float, help="real height in metres (give height, width, or both)")
    ap.add_argument("--width", type=float, help="real width in metres")
    ap.add_argument("--depth", type=float, help="metres front to back, if not round (default: as wide as it is)")
    ap.add_argument("--round", action="store_true", help="a round tower: spin the silhouette around its axis")
    ap.add_argument("--pitch", type=float, default=MC_BLOCK_DIMS, help="metres per block")
    ap.add_argument("--colours", type=int, default=12, help="number of colour groups (materials)")
    ap.add_argument("--gain", type=float, default=1.4, help="brightening to make up for Minecraft's face shading")
    ap.add_argument("--solid", action="store_true", help="fill the inside (default: hollow shell)")
    ap.add_argument("--version", default="JE_1_20_1", help="Minecraft version, e.g. JE_1_20_1")
    ap.add_argument("--name", help="schematic name (default: the photo's file name)")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    # 1. Cutout (also saved as a PNG by get_subject_img)
    cutout = get_subject_img([args.photo])[0]
    rgb, mask = cutout_to_arrays(cutout)

    # 2. 2D grid, then 3D
    H, W = grid_size(mask, args.height, args.width, args.pitch)
    print(f"grid: {W} wide x {H} tall blocks ({args.pitch:g} m per block)")
    solid, colour = resample_dominant(rgb, mask, H, W)
    if args.round:
        occ, idx, cell = revolve(solid)
    else:
        depth_blocks = max(1, round((args.depth if args.depth else W * args.pitch) / args.pitch))
        occ, idx, cell = extrude(solid, depth_blocks)
    print(f"{len(idx):,} blocks before hollowing")

    # 3. Blocks
    grid = match_cells(colour, solid, PALETTE, k=args.colours, gain=args.gain)
    blocks = grid[cell[:, 0], cell[:, 1]]            # each block looks up its colour cell's block name

    if not args.solid:
        keep = hollow(occ, idx)
        idx, blocks = idx[keep], blocks[keep]
    summarise(blocks)

    # 4. Export. idx is (y, x, z); the schematic wants (x, y, z)
    name = args.name or Path(args.photo).stem
    path = save_schem(args.out, name, idx[:, [1, 0, 2]], blocks, args.version)
    print(f"saved {path} ({len(blocks):,} blocks)   in game: //schem load {name}   then   //paste")


if __name__ == "__main__":
    main()