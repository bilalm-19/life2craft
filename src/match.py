"""Step 3: choose a Minecraft block for every cell of the colour grid."""
import collections

import numpy as np
from sklearn.cluster import KMeans
from skimage.color import deltaE_ciede2000, rgb2lab


def to_lab(rgb255):
    """(n, 3) RGB values 0-255 -> (n, 3) Lab values."""
    return rgb2lab(np.asarray(rgb255, float).reshape(-1, 1, 3) / 255.0).reshape(-1, 3)


def brighten(rgb, gain):
    """Multiply colours by gain. If a channel would pass 255, scale all three down together
    so the hue is kept (cream stays cream instead of clipping toward white)."""
    t = np.asarray(rgb, float) * gain
    return t / np.maximum(1.0, t.max(axis=-1, keepdims=True) / 255.0)


def match_cells(colour, solid, palette, k=12, gain=1.4):
    """Pick a Minecraft block for every cell.

    colour:  (H, W, 3) RGB of each cell (from resample_dominant).
    solid:   (H, W) True where the cell gets a block.
    palette: {block name: (R, G, B)}.
    k:       number of colour groups (materials). Fewer = cleaner, more = more detail.
    gain:    brightening. Minecraft darkens faces by about 0.7 on average, so a literal match looks too dark.
    Returns an (H, W) array of block names ("" where a cell is empty).
    """
    if not solid.any():
        raise ValueError("no solid cells to match")
    cells = colour[solid]                      # (n, 3): the colours of the solid cells only, as a flat list
    k = min(k, len(cells))                     # can't make more groups than there are cells

    # Step 1: group similar colours, so a wall of near-identical shades ends up as one material.
    # KMeans sorts the colours into k groups and gives each cell a group number (labels).
    # It's done in Lab, so "similar" means similar to the eye. n_init=8 tries 8 starting guesses, keeps the best.
    labels = KMeans(n_clusters=k, n_init=8, random_state=0).fit(to_lab(cells)).labels_
    # Each group's colour is the average RGB of the cells in it
    centres = np.array([cells[labels == i].mean(axis=0) for i in range(k)])

    # Step 2: for each group's colour, find the palette block that looks closest.
    # Brighten first to make up for Minecraft's face shading, then convert to Lab to compare.
    names = list(palette)                                    # block names, in a fixed order
    palette_lab = to_lab([palette[n] for n in names])        # every block's colour, in Lab
    # deltaE_ciede2000 scores how different two colours look (0 = identical, 40+ = very different).
    # np.repeat copies one group colour so it can be compared against every block at once.
    # Result: a table, one row per group, one column per block.
    diff = np.stack([deltaE_ciede2000(np.repeat(t[None], len(names), 0), palette_lab)
                     for t in to_lab(brighten(centres, gain))])
    pick = diff.argmin(axis=1)                               # per group, the column (block) with the lowest score

    # Step 3: every solid cell takes the block picked for its group.
    # Empty cells stay "" because nothing should ask for them.
    grid = np.full(solid.shape, "", dtype=object)
    grid[solid] = [names[pick[g]] for g in labels]           # labels[i] = group of solid cell i; pick[group] = its block name
    return grid


def summarise(blocks):
    """Print the block types used and their share."""
    counts = collections.Counter(blocks)
    top = ", ".join(f"{n.split(':')[1]} {c / len(blocks):.0%}" for n, c in counts.most_common(6))
    print(f"{len(counts)} block types: {top}")