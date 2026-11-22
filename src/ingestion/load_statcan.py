import hashlib
from pathlib import Path
import pandas as pd

STATCAN_DIR = Path("data/raw/statcan")
CSV_PATH = STATCAN_DIR / "16100019.csv"
ALT_CSV_PATH = STATCAN_DIR / "1610001901.csv"
ZIP_PATH = STATCAN_DIR / "16100019-eng.zip"

def get_file_checksum(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_statcan_raw():
    """Load raw Statistics Canada table 16-10-0019-01 CSV."""
    target_path = CSV_PATH if CSV_PATH.exists() else ALT_CSV_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Statistics Canada CSV not found at {target_path}")

    df = pd.read_csv(target_path, dtype=str, keep_default_na=False)
    checksum = get_file_checksum(ZIP_PATH) if ZIP_PATH.exists() else get_file_checksum(target_path)
    return df, checksum
