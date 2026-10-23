# 🧱 life2craft

📸 ➜ ⛏️ Turns a photo of an object into a Minecraft schematic (`.schem`, for WorldEdit and Litematica). The object can be
anything with a clear outline: a tower, a building, a statue, a bridge.

`📸 photo` ➜ `✂️ cutout` ➜ `🔲 grid` ➜ `🧊 3D` ➜ `🎨 blocks` ➜ `💾 .schem`

## ✨ How it works

1. **✂️ Cutout** (`cutout.py`): `rembg` removes the background and saves a transparent PNG. Its alpha channel
   (0 = transparent, 255 = solid) becomes a **mask**: `alpha > 128` is True where a pixel is the subject.
   The mask and photo are then trimmed to the subject's bounding box.
2. **🔲 Grid** (`voxelise.py`): `grid_size` works out how many blocks tall and wide from the real size and the block
   size (`--pitch`). `resample_dominant` then shrinks the photo to one cell per block, giving:
   - `solid`: True where a cell gets a block (more than half of its pixels are subject).
   - `colour`: an RGB colour per cell. **The median** is used here: the median of a cell's pixels (in Lab colour,
     where distance roughly matches how different colours look) finds its dominant shade, and only pixels within
     `threshold` of it are averaged. A few stray pixels, such as blue edge pixels among grey ones, do not tint the
     cell. If there is no clear majority, all the subject pixels are averaged.
3. **🧊 3D** (`voxelise.py`): `extrude`, `revolve` or `carve` turns the 2D grid into 3D (see "Choosing a shape").
   `hollow` then keeps only the blocks that touch air, which makes the file much smaller.
4. **🎨 Blocks** (`match.py`): `match_cells` picks a block for each cell. **K-means** groups the cells' colours into
   `k` groups, so near-identical shades share one material instead of becoming a patchwork. Each group's average
   colour is brightened by `--gain` (Minecraft darkens block faces), then matched to the closest palette block with
   CIEDE2000, a colour-difference measure that matches what the eye sees. Median works inside one cell, and
   k-means works across all the cells.
5. **💾 Export** (`export.py`): writes the `.schem`.

Conventions: x runs left to right across the photo, y is up (row 0 is the ground), and depth runs along z.
In Minecraft, +x is east and +z is south.

## 📐 Choosing a shape

One photo has no depth, so the depth is a guess. The shape flag chooses how to guess it.

| Flag | What it does | Good for |
|---|---|---|
| none (`extrude`) | pushes the silhouette straight back by `--depth`, so every height is equally deep | houses, signs, bridges, anything flat or boxy |
| `--round` (`revolve`) | makes each row a filled circle as wide as the silhouette there | round objects: water towers, columns, vases, tree trunks |
| `--carve` | keeps a block only where the front and side silhouettes are both solid, with the side taken as a copy of the front | square objects that taper and look the same from the side: the Eiffel Tower, pylons, pyramids |

`--carve` makes depth shrink with width, so the front face slopes back going up, gaps in the silhouette (such as
between the Eiffel Tower's legs) stay open, and all four faces show the photo. `--round` fills gaps, because each
circle is solid across its full width.

## 🚀 Usage

Run from the project root. The file names below are illustrative.

```
# a round object
python src/main.py data/inputs/telstra_tower.jpg --height 195 --round

# a square tapering tower
python src/main.py data/inputs/eiffel_tower.jpg --height 330 --carve

# a boxy building, with its depth given
python src/main.py data/inputs/house.jpg --height 5.5 --depth 14 --pitch 0.25

# giving the width instead of the height
python src/main.py data/inputs/eiffel_tower.jpg --width 125 --carve
```

`main.py` builds one photo per run. To cut out several photos at once (transparent PNGs only, no schematics), use
the cutout script directly:

```
python src/cutout.py data/inputs/a.jpg data/inputs/b.jpg --out my_cutouts
```

The schematic is written to `output/<name>.schem`, and the cutout to `data/crop_outputs/`.
In game: copy the `.schem` into the WorldEdit `schematics` folder, then run `//schem load <name>` and `//paste`.

## ⚙️ Options

| Option | Point | Default |
|---|---|---|
| `photo` | the photo to build from. Positional (no dashes) and goes first | required |
| `--height`, `--width` | real size in metres; this sets the scale. Give one or both; the other is worked out from the photo's proportions | one is required |
| `--depth` | metres front to back, for `extrude` and `--carve` (ignored with `--round`) | as wide as the grid |
| `--round` | spin the silhouette into a round object | off |
| `--carve` | square object with the same silhouette on all four sides (not with `--round`) | off |
| `--pitch` | metres per block. Smaller means more detail and a much bigger build | 1 |
| `--colours` | `k` for k-means: the number of colour groups. Fewer is cleaner, more keeps detail | 12 |
| `--gain` | brightening to make up for Minecraft's face shading (about 0.7 on average). Raise it if a build looks too dark in game | 1.4 |
| `--solid` | fill the inside | hollow shell |
| `--version` | Minecraft Java version of the file, e.g. `JE_1_20_1` | `JE_1_20_1` |
| `--name` | schematic name | the photo's file name |
| `--out` | output folder | `output` |

## 🛠️ Setup

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

The first run downloads the cutout model (about 176 MB). Windows and Linux install the GPU build of onnxruntime,
which falls back to the CPU if no GPU is set up. macOS installs the CPU build.

## 📁 Layout

```
src/cutout.py       rembg cutout (one or several photos)
src/voxelise.py     grid size, resampling (median), extrude / revolve / carve / hollow
src/match.py        k-means grouping and block matching
src/export.py       .schem writer
src/main.py         command line, one photo per run
data/palette.json   block name -> average RGB (46 blocks; all exist in every version since 1.16)
data/inputs/        source photos
```

Add a block by adding `"minecraft:name": [r, g, b]` to `palette.json`.

## ⚠️ Limits

- Depth comes from `--depth`, not the photo; if omitted it defaults to the grid's width. `--carve` also assumes the
  side silhouette is the same as the front.
- One photo per object: there are no side or back views, and `main.py` builds one photo per run.
- The cutout model picks the most noticeable object, so it can pick the wrong one in a cluttered photo, and it can
  count background seen through gaps (such as the Eiffel Tower's arch) as part of the subject.
- No windows or glass, and no sloped roofs.
