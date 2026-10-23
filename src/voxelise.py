"""Step 2: turn the silhouette into a 3D block grid.
 
A single photo has no depth, so the depth is a guess. Two guesses are offered:
  revolve  a round tower: spin the silhouette around its vertical axis
  extrude  anything else: push the silhouette straight back by --depth metres
 
Conventions used everywhere (getting these wrong flips or rotates the build):
  * x runs left to right across the photo, y is up (row 0 is the ground), and depth runs along z
  * in Minecraft +x is east and +z is south, so after pasting, the photo's left-right axis lies east-west
"""


import numpy as np
from scipy import ndimage
from skimage.color import rgb2lab 

MC_BLOCK_DIMS = 1 # minecraft blocks are 1m x 1m x 1m

def grid_size(mask, height_m = None, width_m = None, pitch = MC_BLOCK_DIMS):
    """How many blocks tall (H) and wide (W). pitch = metres per block."""
   
    if height_m is None and width_m is None:
            raise ValueError("You must provide either a height_m or a width_m.")

    # Calculate the image's original aspect ratio (width / height)
    aspect_ratio = mask.shape[1] / mask.shape[0] # so we can infer the missing dimension using one of the dimensions

    # Calculate Height/Width
    if height_m is not None:
        H_blocks = round(height_m / pitch)
    if width_m is not None:
        W_blocks = round(width_m / pitch)
    if height_m is None:                        # only the width was given: infer the height
        H_blocks = round(W_blocks / aspect_ratio)
    if width_m is None:                         # only the height was given: infer the width
        W_blocks = round(H_blocks * aspect_ratio)

    return H_blocks, W_blocks


def resample_dominant(rgb, mask, H, W, threshold=12.0, min_pixels=4):
    """Downsample the photo to an H x W grid of cells (one per block). Returns (solid, colour), rows flipped so row 0 is the ground.
    mask: True/False per photo pixel (True = subject), made as `alpha > 128`.
    solid:  (H, W) True where over half the cell is subject.
    colour: (H, W, 3) RGB per cell, averaged over only the pixels close to the cell's dominant shade.
    """
    h, w = mask.shape                      # photo size in pixels (lowercase); the grid size is H, W (uppercase)
    lab = rgb2lab(rgb / 255.0)             # whole photo in Lab, once: distances there roughly match how different colours look

    # Where each grid cell's patch of photo pixels begins: grid row r covers photo rows ys[r]:ys[r+1],
    # and grid column c covers photo columns xs[c]:xs[c+1]
    ys = np.linspace(0, h, H + 1).astype(int)
    xs = np.linspace(0, w, W + 1).astype(int)

    solid = np.zeros((H, W), bool)         # starts all False: "no block anywhere"
    colour = np.zeros((H, W, 3))           # starts all black; only solid cells get a real colour

    for r in range(H):
        for c in range(W):
            # This cell's patch of the mask: one True/False per photo pixel the cell covers
            m = mask[ys[r]:ys[r + 1], xs[c]:xs[c + 1]]
            if m.sum() <= m.size / 2:      # at most half the patch is subject: leave the cell empty
                continue
            solid[r, c] = True

            # Only the subject pixels of this patch, as a list of colours, shape (n, 3). Background pixels are dropped.
            px_rgb = rgb[ys[r]:ys[r + 1], xs[c]:xs[c + 1]][m]      # used for averaging
            px_lab = lab[ys[r]:ys[r + 1], xs[c]:xs[c + 1]][m]      # used for judging similarity

            # The middle value of each of L, a and b: the shade most of the pixels agree on
            dominant = np.median(px_lab, axis=0)
            # True for each pixel whose Lab distance from the dominant shade is under the threshold
            near = np.linalg.norm(px_lab - dominant, axis=1) < threshold

            if near.sum() >= min_pixels and near.mean() >= 0.5:    # a clear majority: average only the similar pixels
                colour[r, c] = px_rgb[near].mean(axis=0)
            else:                                                  # no clear dominant shade: plain average of all subject pixels
                colour[r, c] = px_rgb.mean(axis=0)

    return solid[::-1], colour[::-1]       # flip the rows so row 0 is the ground


def revolve(solid):
    """Round tower: turn the 2D silhouette into 3D by making each row a filled disc as wide as the silhouette is in that row.

    Returns three things:
        occ:  (H, W, W) True/False grid, True where a block is. Indexed (y, x, z); y is height.
        idx:  (n, 3) list of every block's position, one row per block, columns (y, x, z). n = number of blocks.
        cell: (n, 2) for each block, the (row, column) of the 2D colour grid that gives its colour.
    """
    H, W = solid.shape
    c = (W - 1) / 2
    xs, zs = np.meshgrid(np.arange(W), np.arange(W), indexing="ij")
    d2 = (xs - c) ** 2 + (zs - c) ** 2
    occ = np.zeros((H, W, W), bool)
    centre = np.full(H, c)
    for r in range(H):
        cols = np.flatnonzero(solid[r])
        if len(cols):
            occ[r] = d2 <= max((cols.max() - cols.min() + 1) / 2, 0.75) ** 2
            centre[r] = (cols.max() + cols.min()) / 2
    idx = np.argwhere(occ)
    y, x, z = idx.T
    col = np.clip(np.round(x - c + centre[y]), 0, W - 1).astype(int)     # the photo is projected straight through the tower
    keep = solid[y, col]                       # False = this block's colour cell is empty: it should not exist
    occ[y[~keep], x[~keep], z[~keep]] = False
    idx, y, col = idx[keep], y[keep], col[keep]

    return occ, idx, np.stack([y, col], 1)
 
 
def extrude(solid, depth_blocks):
    """Anything else: the silhouette pushed straight back. Returns the same three things as revolve()."""
    H, W = solid.shape
    occ = np.repeat(solid[:, :, None], depth_blocks, axis=2)
    idx = np.argwhere(occ)
    return occ, idx, idx[:, :2].copy()           # (row, column) of the photo grid = (y, x)
 
 
def hollow(occ, idx):
    """Keep only the blocks that touch air (the shell). Far fewer blocks, and the file stays small."""
    inner = ndimage.binary_erosion(occ)
    return ~inner[idx[:, 0], idx[:, 1], idx[:, 2]]

def carve(solid, depth_blocks):
    """Square tower: keep a block only where both the front and side silhouettes are solid.

    With one photo, the side silhouette is a copy of the front, so depth at each height equals the width there.
    Layers get shallower as the silhouette narrows (the front face slopes back going up), and gaps in the
    silhouette (between the legs) stay open all the way through. Suits symmetric, tapering towers; use extrude() for a house.

    solid:        (H, W) True where the front photo is subject.
    depth_blocks: depth of the widest layer, in blocks. You choose it; a single photo cannot supply it.
    Returns the same three things as revolve():
        occ:  (H, W, D) True where a block is, indexed (y, x, z)
        idx:  (n, 3) each block's position as (y, x, z)
        cell: (n, 2) each block's (row, column) in the 2D colour grid
    """
    H, W = solid.shape
    D = depth_blocks

    # ---- Shape ----
    # The side silhouette is the front one stretched from W columns to D depth positions.
    # z_to_col[z] is the photo column that depth position z shows.
    # Example: a photo 5 columns wide (columns 0-4) and 10 depth positions (z = 0-9):
    #          z = 0, 1, 2, ..., 9 show photo columns [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    z_to_col = np.minimum(((np.arange(D) + 0.5) * W / D).astype(int), W - 1)
    side = solid[:, z_to_col]                          # (H, D)

    # Keep a block only where BOTH silhouettes are solid (solid[:, :, None] alone would be extrude()).
    # Each layer is then a rectangle, with width and depth both set by the silhouette's width at that height.
    occ = solid[:, :, None] & side[:, None, :]         # (H, W, D)
    idx = np.argwhere(occ)
    y, x, z = idx.T

    # ---- Colour: each face shows the photo, read left to right as seen from outside that face ----
    # Each block uses the face it is nearest to.
    cx, cz = (W - 1) / 2, (D - 1) / 2
    near_side_face = np.abs(x - cx) / max(cx, 1) > np.abs(z - cz) / max(cz, 1)    # nearest a west/east face (else front/back)
    is_east = near_side_face & (x > cx)
    is_back = ~near_side_face & (z < cz)

    # Along a face only one coordinate changes: x on the front/back faces, z on the west/east faces
    # (x runs east, z runs south, the front is +z). Facing a wall, the photo's columns must rise toward your
    # right hand, so some faces use a flipped index.
    # Example of a flip, with a photo 5 columns wide (columns 0-4): the blocks at x = 0, 1, 2, 3, 4
    # show photo columns W-1-x = 4, 3, 2, 1, 0.
    #   front (+z):  x                right hand = east
    #   back  (-z):  W-1-x            right hand = west, so flip x
    #   west  (-x):  z_to_col[z]      right hand = south
    #   east  (+x):  z_to_col[D-1-z]  right hand = north, so flip z
    wanted = np.where(near_side_face,
                      np.where(is_east, z_to_col[D - 1 - z], z_to_col[z]),
                      np.where(is_back, W - 1 - x, x))

    # The unflipped column is always solid; the flipped one only if the silhouette is left-right symmetric.
    # Otherwise fall back to the unflipped column (that face may then be mirrored).
    plain = np.where(near_side_face, z_to_col[z], x)
    col = np.where(solid[y, wanted], wanted, plain)
    return occ, idx, np.stack([y, col], 1)