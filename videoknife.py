import sys, os
from glob import glob
from mimetypes import guess_type
import PySide2.QtGui
from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox, QPushButton, QFileDialog, QMessageBox, QComboBox
from PySide2.QtGui import QImage, QPixmap, QPainter, QColor, QBrush
from PySide2 import QtCore
import numpy as np
import cv2
from database import Album


MAX_WIDTH = 1200
MAX_HEIGHT = 1000


def cv2_to_pixmap(img: np.ndarray) -> QPixmap:
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = img.shape
    image = QImage(img.data, w, h, QImage.Format_RGB888)
    return QPixmap.fromImage(image)


class Canvas(QWidget):
    def __init__(self, win: "MainWindow"):
        super(Canvas, self).__init__()
        self.win = win
        self.setMouseTracking(True)
        self.h = 0
        self.w = 0
        self.scale = 1.0
        self.pix = None
        self.area = None
        self.pressed = False

    def paintEvent(self, event):
        if self.pix is None:
            return
        self.resize(self.w, self.h)
        p = QPainter(self)
        p.drawPixmap(0, 0, self.w, self.h, self.pix, 0, 0, self.sw, self.sh)
        if self.area is not None:
            p.setPen(QColor(0, 0, 255))
            brush = QBrush(QtCore.Qt.BDiagPattern)
            p.setBrush(brush)
            x, y, w, h = self.area[0], self.area[1], self.area[2] - self.area[0], self.area[3] - self.area[1]
            x, y, w, h = int(self.scale * x), int(self.scale * y), int(self.scale * w), int(self.scale * h)
            p.drawRect(x, y, w, h)

    def set_img(self, img: np.ndarray):
        self.sh, self.sw, _ = img.shape
        scale = min(MAX_HEIGHT / self.sh, MAX_WIDTH / self.sw)
        if scale >= 1.0:
            self.h = self.sh
            self.w = self.sw
            self.scale = 1.0
        else:
            self.h = round(scale * self.sh)
            self.w = round(scale * self.sw)
            self.scale = scale
        # self.h, self.w, _ = img.shape
        self.pix = cv2_to_pixmap(img)
        self.update()

    def mousePressEvent(self, event: PySide2.QtGui.QMouseEvent) -> None:
        pos = event.pos()
        x, y = pos.x(), pos.y()
        x = int(x / self.scale)
        y = int(y / self.scale)
        self.area = [x, y, x, y]
        self.pressed = True
        self.update()
        self.win.update_area()

    def mouseMoveEvent(self, event: PySide2.QtGui.QMouseEvent) -> None:
        if self.pressed and self.area is not None:
            pos = event.pos()
            x, y = pos.x(), pos.y()
            x = int(x / self.scale)
            y = int(y / self.scale)
            self.area[2] = x
            self.area[3] = y
        self.update()
        self.win.update_area()

    def mouseReleaseEvent(self, event: PySide2.QtGui.QMouseEvent) -> None:
        pos = event.pos()
        x, y = pos.x(), pos.y()
        x = int(x / self.scale)
        y = int(y / self.scale)
        if self.area[0] == x and self.area[1] == y:
            self.area = None
        else:
            self.area[2] = x
            self.area[3] = y
        self.pressed = False
        self.update()
        self.win.update_area()


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("VideoKnife")

        self.widget1 = QWidget()
        self.layout_h = QHBoxLayout(self.widget1)
        self.widget1.setLayout(self.layout_h)

        self.canvas = Canvas(self)
        self.layout_h.addWidget(self.canvas)

        self.widget2 = QWidget()
        self.widget2.setMaximumWidth(200)
        self.layout_h.addWidget(self.widget2)
        self.layout_v = QVBoxLayout(self.widget2)
        self.layout_v.addStretch(0)
        self.widget2.setLayout(self.layout_v)

        self.label_name_album = QLabel("album: ")
        self.layout_v.addWidget(self.label_name_album)

        self.button_create_album = QPushButton("create album...")
        self.button_create_album.clicked.connect(self.on_click_create_album)
        self.layout_v.addWidget(self.button_create_album)

        self.button_open_album = QPushButton("open album...")
        self.button_open_album.clicked.connect(self.on_click_open_album)
        self.layout_v.addWidget(self.button_open_album)

        self.list_video = QComboBox()
        self.list_video_id = []
        self.list_video.currentIndexChanged.connect(self.update_video)
        self.layout_v.addWidget(self.list_video)

        self.button_add_video = QPushButton("add video...")
        self.button_add_video.clicked.connect(self.on_click_add_video)
        self.layout_v.addWidget(self.button_add_video)

        self.button_add_videos = QPushButton("add videos...")
        self.button_add_videos.clicked.connect(self.on_click_add_videos)
        self.layout_v.addWidget(self.button_add_videos)

        self.button_delete_video = QPushButton("delete video")
        self.button_delete_video.clicked.connect(self.on_click_delete_video)
        self.layout_v.addWidget(self.button_delete_video)

        self.label_fps = QLabel("fps: ")
        self.layout_v.addWidget(self.label_fps)
        self.label_frame_width = QLabel("width: ")
        self.layout_v.addWidget(self.label_frame_width)
        self.label_frame_height = QLabel("height: ")
        self.layout_v.addWidget(self.label_frame_height)
        self.label_frame_count = QLabel("count: ")
        self.layout_v.addWidget(self.label_frame_count)
        self.label_pos_frame = QLabel("pos frame")
        self.layout_v.addWidget(self.label_pos_frame)
        self.spin = QSpinBox()
        self.spin.setSingleStep(1)
        self.spin.valueChanged.connect(self.value_changed)
        self.layout_v.addWidget(self.spin)
        self.label_area = QLabel("area: ")
        self.layout_v.addWidget(self.label_area)

        self.label_definition = QLabel("crop definition")
        self.layout_v.addWidget(self.label_definition)
        self.list_definition = QComboBox()
        self.list_definition.currentIndexChanged.connect(self.update_definition)
        self.layout_v.addWidget(self.list_definition)

        self.label_start = QLabel("start frame")
        self.layout_v.addWidget(self.label_start)
        self.spin_start = QSpinBox()
        self.layout_v.addWidget(self.spin_start)
        self.spin_start.setMinimum(0)
        self.spin_start.setMaximum(0)
        self.spin_start.setValue(0)

        self.label_end = QLabel("end frame")
        self.layout_v.addWidget(self.label_end)
        self.spin_end = QSpinBox()
        self.layout_v.addWidget(self.spin_end)
        self.spin_end.setMinimum(0)
        self.spin_end.setMaximum(0)
        self.spin_end.setValue(0)

        self.label_step = QLabel("step frame")
        self.layout_v.addWidget(self.label_step)
        self.spin_step = QSpinBox()
        self.layout_v.addWidget(self.spin_step)
        self.spin_step.setMinimum(1)
        self.spin_step.setMaximum(1)
        self.spin_step.setValue(1)

        self.button_add_definition = QPushButton("add definition")
        self.button_add_definition.clicked.connect(self.add_definition)
        self.layout_v.addWidget(self.button_add_definition)

        self.button_delete_definition = QPushButton("delete definition")
        self.button_delete_definition.clicked.connect(self.delete_definition)
        self.layout_v.addWidget(self.button_delete_definition)

        self.button_crop = QPushButton("CROP!")
        self.button_crop.clicked.connect(self.crop)
        self.layout_v.addWidget(self.button_crop)

        self.setCentralWidget(self.widget1)

        self.path_album = ""
        self.name_album = ""
        self.path_video = ""
        self.fps = 0
        self.frame_count = 0
        self.pos_frames = 0
        self.frame_width = 0
        self.frame_height = 0
        self.cap = None

        self.album = None

    def on_click_create_album(self):
        path, _ = QFileDialog.getSaveFileName(self, 'create album', os.path.dirname(os.path.abspath(__file__)))
        if path == "":
            return
        if os.path.exists(path):
            QMessageBox.warning(self, "warning", f"already exists {os.path.basename(path)}")
            return

        if not self.open_album(path):
            QMessageBox.warning(self, "warning", f"couldn't create {os.path.basename(path)}")

    def on_click_open_album(self):
        path = QFileDialog.getExistingDirectory(self, 'Open album', os.path.dirname(os.path.abspath(__file__)))
        if path == "":
            return
        if not self.open_album(path):
            QMessageBox.warning(self, "warning", f"couldn't open {os.path.basename(path)}")

    def open_album(self, path: str) -> bool:
        self.album = Album(path)
        self.path_album = path
        self.label_name_album.setText(f"album: {os.path.basename(path)}")
        self.update_video_list()
        return True

    def update_video_list(self):
        idx = self.list_video.currentIndex()
        self.list_video.clear()
        if self.album is None:
            return
        df = self.album.get_all_video()
        self.list_video_id = df["id_video"].values.tolist()
        names = df["name_video"].values.tolist()
        self.list_video.addItems(names)
        self.list_video.setCurrentIndex(max(0, min(idx, len(names) - 1)))
        self.update_video()

    def update_video(self):
        idx = self.list_video.currentIndex()
        if idx < 0:
            # crear screen
            self.canvas.pix = None
            self.canvas.update()
            return
        name_video = self.list_video.currentText()
        path_video = os.path.join(self.path_album, "video", name_video)
        if self.path_video == path_video:
            return

        self.path_video = path_video
        self.cap = cv2.VideoCapture(self.path_video)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.label_fps.setText(f"fps: {self.fps:>.2f}")
        self.label_frame_width.setText(f"width: {self.frame_width}")
        self.label_frame_height.setText(f"height: {self.frame_height}")
        self.label_frame_count.setText(f"count: {self.frame_count}")

        self.spin.setMinimum(0)
        self.spin.setMaximum(max(0, self.frame_count - 1))

        self.spin_start.setMinimum(0)
        self.spin_start.setMaximum(max(0, self.frame_count - 1))

        self.spin_end.setMinimum(0)
        self.spin_end.setMaximum(max(0, self.frame_count - 1))

        self.spin_step.setMinimum(1)
        self.spin_step.setMaximum(max(1, self.frame_count - 1))

        self.spin.setValue(0)
        self.value_changed(0)

        self.update_definition_list()

    def value_changed(self, i: int):
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        success, img = self.cap.read()
        if not success:
            return
        self.canvas.set_img(img)
        self.canvas.update()

    def update_definition_list(self):
        self.list_definition.clear()
        if self.album is None:
            return
        idx = self.list_video.currentIndex()
        if idx < 0:
            return
        id_video = self.list_video_id[idx]
        df = self.album.get_crop_definitions(id_video)
        ids_definition = df["id_definition"].values.tolist()
        ids_definition = [str(e) for e in ids_definition]
        self.list_definition.addItems(ids_definition)

        self.update_definition()

    def update_definition(self):
        if self.album is None:
            return
        idx = self.list_definition.currentIndex()
        if idx < 0:
            return
        id_definition = int(self.list_definition.currentText())
        df = self.album.get_crop_definition(id_definition)
        start = int(df["index_start"].iloc[0])
        end = int(df["index_end"].iloc[0])
        step = int(df["step_index"].iloc[0])
        if df["pixel_left"].iloc[0] is None:
            area = None
        else:
            area = [
                int(df["pixel_left"].iloc[0]),
                int(df["pixel_top"].iloc[0]),
                int(df["pixel_right"].iloc[0]),
                int(df["pixel_bottom"].iloc[0]),
            ]

        self.spin_start.setValue(start)
        self.spin_end.setValue(end)
        self.spin_step.setValue(step)
        self.canvas.area = area
        self.canvas.update()

    def add_definition(self):
        if self.album is None:
            return
        idx = self.list_video.currentIndex()
        if idx < 0:
            return
        id_video = self.list_video_id[idx]
        start_frame = self.spin_start.value()
        end_frame = self.spin_end.value()
        step = self.spin_step.value()
        area = self.canvas.area
        area = None if area is None else tuple(area)
        self.album.add_crop_definition(id_video, (start_frame, end_frame, step), area)

        self.update_definition_list()

    def delete_definition(self):
        if self.album is None:
            return
        idx = self.list_definition.currentIndex()
        if idx < 0:
            return
        id_definition = int(self.list_definition.currentText())

        ret = QMessageBox.warning(self, "DELETE", "delete?\nAll relevant information will be deleted.", QMessageBox.Yes, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.album.remove_crop_definition(id_definition)
            self.update_definition_list()

    def on_click_add_video(self):
        if self.album is None:
            QMessageBox.warning(self, "warning", "album is not set")
            return
        path, _ = QFileDialog.getOpenFileName(self, "add video", os.path.dirname(os.path.abspath(__file__)))
        t = guess_type(path)[0]
        if t is None or not t.startswith("video/"):
            QMessageBox.warning(self, "warning", f"NOT VIDEO: {os.path.basename(path)}")
            return
        self.album.add_video(path)
        self.update_video_list()

    def on_click_add_videos(self):
        if self.album is None:
            QMessageBox.warning(self, "warning", "album is not set")
            return
        dir_video = QFileDialog.getExistingDirectory(self, "add videos", os.path.dirname(os.path.abspath(__file__)))
        paths = glob(os.path.join(dir_video, "*"))
        paths.sort()
        for path in paths:
            t = guess_type(path)[0]
            if t is None or not t.startswith("video/"):
                continue
            self.album.add_video(path)
        self.update_video_list()

    def on_click_delete_video(self):
        if self.album is None:
            QMessageBox.warning(self, "warning", "album is not set")
            return
        idx = self.list_video.currentIndex()
        if idx < 0:
            return
        id_video = self.list_video_id[idx]
        name_video = self.list_video.currentText()

        ret = QMessageBox.warning(self, "DELETE", f"delete?\nAll relevant information will be deleted.\nfile: {name_video}", QMessageBox.Yes, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.album.remove_video(id_video)
            self.update_video_list()

    def crop(self):
        if self.album is None:
            QMessageBox.warning(self, "warning", "album is not set")
            return

        self.album.do_crop_all()

    def update_area(self):
        area = self.canvas.area
        self.label_area.setText(f"area: " if area is None else f"area: ({area[0]}, {area[1]}, {area[2]}, {area[3]})")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    desktop = app.desktop()
    window = MainWindow()
    window.resize(desktop.width(), desktop.height())
    window.show()
    app.exec_()
