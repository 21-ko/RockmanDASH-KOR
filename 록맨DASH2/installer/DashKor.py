import sys
import os
from bptc import apply_patch
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QProgressBar, QMessageBox,
    QFileDialog, QVBoxLayout, QDialog, QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QPalette, QPixmap, QBrush, QFont, QTransform
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class InstallerThread(QThread):
    progress_update = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    error_message = pyqtSignal(str)

    def __init__(self, original_file, patch_file, output_file):
        super().__init__()
        self.original_file = original_file
        self.patch_file = patch_file
        self.output_file = output_file

    def run(self):
        error_detail = ""
        try:
            for progress in range(1, 6):
                self.sleep(1)
                self.progress_update.emit(progress * 20)

            apply_patch(self.original_file, self.patch_file, self.output_file)
            self.finished.emit(True, "")
        except ValueError as e:
            error_detail = str(e)
            self.error_message.emit(error_detail)
            self.finished.emit(False, error_detail)
        except Exception as e:
            error_detail = f"예상치 못한 오류: {str(e)}"
            self.error_message.emit(error_detail)
            self.finished.emit(False, error_detail)

class PatcherApp(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_patch = "default"
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("설치 마법사")
        self.setFixedSize(600, 400)

        palette = QPalette()
        pixmap_path = resource_path(os.path.join("assets", "header.jpg"))
        pixmap = QPixmap(pixmap_path)
        palette.setBrush(QPalette.Background, QBrush(pixmap))
        self.setPalette(palette)

        font = QFont()
        font.setPointSize(24)

        self.install_button = QPushButton("설치", self)
        self.install_button.setGeometry(20, 20, 200, 50)
        self.install_button.setFont(font)
        self.install_button.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 15px;")
        self.install_button.clicked.connect(self.run_patcher)

        self.exit_button = QPushButton("종료", self)
        self.exit_button.setGeometry(20, 80, 200, 50)
        self.exit_button.setFont(font)
        self.exit_button.setStyleSheet("background-color: #f44336; color: white; border-radius: 15px;")
        self.exit_button.clicked.connect(self.close_application)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(100, 300, 400, 30)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        self.loading_label = QLabel(self)
        self.loading_pixmap = QPixmap(resource_path(os.path.join("assets", "loading.png")))
        self.loading_label.setPixmap(self.loading_pixmap)
        self.loading_label.setFixedSize(64, 64)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.move(518, 318)
        self.loading_label.hide()

        self.timer = QTimer(self)
        self.rotation_angle = 0

    def close_application(self):
        self.close()

    def rotate_loading_image(self):
        rotated_pixmap = self.loading_pixmap.transformed(
            QTransform().rotate(self.rotation_angle), Qt.SmoothTransformation
        )
        self.loading_label.setPixmap(rotated_pixmap)
        self.rotation_angle = (self.rotation_angle + 10) % 360

    def set_loading_error(self):
        self.timer.stop()
        error_pixmap = QPixmap(resource_path(os.path.join("assets", "loading_error.png"))).scaled(64, 64, Qt.KeepAspectRatio)
        self.loading_label.setPixmap(error_pixmap)

    def reset_all(self):
        self.timer.stop()
        self.rotation_angle = 0
        self.loading_label.setPixmap(self.loading_pixmap)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.loading_label.hide()

    def run_patcher(self):
        original_file, _ = QFileDialog.getOpenFileName(self, "이미지 파일 선택", "", "ISO Files (*.iso)")
        if not original_file:
            return

        patch_file = resource_path(os.path.join("assets", "rockman.patch"))

        output_file, _ = QFileDialog.getSaveFileName(self, "결과 파일 저장", "", "ISO Files (*.iso)")
        if not output_file:
            return

        self.reset_all()
        self.progress_bar.show()
        self.loading_label.show()

        self.timer.timeout.connect(self.rotate_loading_image)
        self.timer.start(50)

        self.thread = InstallerThread(original_file, patch_file, output_file)
        self.thread.progress_update.connect(self.progress_bar.setValue)
        self.thread.error_message.connect(self.on_error_message)
        self.thread.finished.connect(self.on_installation_finished)
        self.thread.start()

    def on_error_message(self, message):
        self.error_details = message

    def on_installation_finished(self, success, error_message):
        if success:
            self.timer.stop()
            self.loading_label.hide()
            self.progress_bar.hide()
            QMessageBox.information(self, "성공", "패치가 성공적으로 적용되었습니다!")
        else:
            self.set_loading_error()
            error_box = QMessageBox(self)
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle("오류")
            error_box.setText("패치 적용 중 오류가 발생했습니다!")
            error_box.setDetailedText(self.error_details)
            error_box.exec_()
        self.reset_all()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    patcher = PatcherApp()
    patcher.show()
    sys.exit(app.exec_())
