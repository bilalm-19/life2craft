"""Step 4: write the .schem file (the format WorldEdit and Litematica load)."""
from pathlib import Path

import mcschematic


def save_schem(out_dir, name, coords, blocks, version="JE_1_20_1"):
    """coords: (n, 3) x, y, z of every block.  blocks: n block names like 'minecraft:stone'."""
    schem = mcschematic.MCSchematic()
    for (x, y, z), block in zip(coords, blocks):
        schem.setBlock((int(x), int(y), int(z)), block)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schem.save(str(out_dir), name, getattr(mcschematic.Version, version))
    return out_dir / f"{name}.schem"