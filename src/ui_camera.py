"""Camera start / stop / selection for the main window. Mixed into MainWindow, which owns the widgets and the worker."""
import logging

from PySide6.QtGui import QPixmap

from .camera import list_cameras
from .worker import CameraOpener

log = logging.getLogger(__name__)


class CameraLifecycle:
    def _refresh_cameras(self):
        if self.worker is not None or self.opener is not None:
            self.message = "Stop the camera before refreshing the camera list."
            return
        current = self.camera_box.currentData()
        self.camera_box.clear()
        found = list_cameras()
        for i, w, h in found:
            self.camera_box.addItem(f"Camera {i} ({w}x{h})", i)
        if current is not None:
            row = self.camera_box.findData(current)
            self.camera_box.setCurrentIndex(max(row, 0))
        if found:
            self.camera_unavailable = False
            self.message = f"Found {len(found)} camera(s)."
        else:
            self.camera_unavailable = True
            self.message = "No camera found. Check the USB cable/port, then press Refresh."

    def _on_camera_selected(self, _row: int):
        """Switch to the newly selected camera immediately if one is already running."""
        if self.worker is not None and self.opener is None:
            self._stop_worker()  # the opener closes the old camera in the background
            self._start_camera()

    def _toggle_camera(self):
        if self.opener is not None:
            return
        if self.worker is not None:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        index = self.camera_box.currentData()
        if index is None:
            self.message = "No camera selected. Connect the USB camera and press Refresh."
            return
        self.camera_unavailable = False
        self.message = f"Opening camera {index}…"
        self._set_busy(True)
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Opening camera…")
        self.opener = CameraOpener(self.camera, index)
        self.opener.opened.connect(self._on_opened)
        self.opener.failed.connect(self._on_open_failed)
        self.opener.start()

    def _set_busy(self, busy: bool):
        self.start_btn.setEnabled(not busy)
        self.camera_box.setEnabled(not busy)
        self.status.setText("Opening camera…" if busy else self.status.text())

    def _finish_open(self):
        self.opener.wait()
        self.opener = None
        self._set_busy(False)

    def _on_open_failed(self, msg: str):
        log.error("%s", msg)
        self._finish_open()
        self.camera_unavailable = True
        self.message = msg
        self.start_btn.setText("Start Camera")

    def _stop_camera(self):
        self._stop_worker()
        self.camera.close()
