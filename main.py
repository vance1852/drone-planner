import sys

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("无人机航线规划与禁飞区检测系统")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
