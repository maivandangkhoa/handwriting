"""Camera preview label that reports clicks, and the conversion of a click to camera-view pixels."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel

from . import config


class PreviewLabel(QLabel):
    """Camera preview that reports clicks (position in label coordinates)."""
    clicked = Signal(float, float)

    def mousePressEvent(self, event):
        self.clicked.emit(event.position().x(), event.position().y())


def preview_to_view(x: float, y: float, label: QLabel, frame_width: int) -> tuple[float, float] | None:
    """Camera-view pixel (mirror/flip already applied, as shown) under label position (x, y); None outside the image."""
    pm = label.pixmap()
    if pm is None or pm.isNull():
        return None
    px = x - (label.width() - pm.width()) / 2
    py = y - (label.height() - pm.height()) / 2
    if not (0 <= px < pm.width() and 0 <= py < pm.height()):
        return None
    scale = config.PREVIEW_WIDTH / frame_width
    return (px / scale, py / scale)
