"""User-triggered download of the official MediaPipe Hand Landmarker model (float16, ~7.5 MB).

Model card / license: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
Run from the project root: python scripts/download_model.py
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402


def main() -> int:
    dest = config.MODEL_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {config.MODEL_URL}\n  -> {dest}")
    tmp = dest.with_suffix(".part")
    try:
        urllib.request.urlretrieve(config.MODEL_URL, tmp)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    tmp.replace(dest)
    print(f"Done ({dest.stat().st_size / 1e6:.1f} MB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
