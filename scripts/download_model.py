"""User-triggered download of the official MediaPipe models: Hand Landmarker (float16, ~7.5 MB) and Pose Landmarker
(lite, float16, ~5.8 MB, used by the Mirror dance).

Model card / license: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
Run from the project root: python scripts/download_model.py
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}\n  -> {dest}")
    tmp = dest.with_suffix(".part")
    try:
        urllib.request.urlretrieve(url, tmp)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        print(f"Download failed: {exc}", file=sys.stderr)
        return False
    tmp.replace(dest)
    print(f"Done ({dest.stat().st_size / 1e6:.1f} MB).")
    return True


def main() -> int:
    ok = [download(config.MODEL_URL, config.MODEL_PATH), download(config.POSE_MODEL_URL, config.POSE_MODEL_PATH)]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
