import hashlib
from pathlib import Path
import geopandas as gpd

NRCAN_DIR = Path("data/raw/nrcan_900a")
GDB_PATH = NRCAN_DIR / "900A.gdb"
ZIP_PATH = NRCAN_DIR / "900A.gdb.zip"

def get_file_checksum(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_nrcan_raw():
    """Load raw layers from NRCan 900A geodatabase."""
    if not GDB_PATH.exists():
        raise FileNotFoundError(f"NRCan 900A GDB not found at {GDB_PATH}")

    layers = gpd.list_layers(GDB_PATH)
    layer_names = layers["name"].tolist()

    data = {}
    for layer in ["ProducingMines", "MetalWorks", "Top100Exp"]:
        if layer in layer_names:
            gdf = gpd.read_file(GDB_PATH, layer=layer)
            data[layer] = gdf

    checksum = get_file_checksum(ZIP_PATH) if ZIP_PATH.exists() else ""
    return data, checksum
