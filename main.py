"""
main.py
Точка входа приложения STRG.
Инициализирует графическое окружение PyQt6 и открывает главное окно.
"""

import os
import sys

# Гарантируем, что Python видит все файлы в папке проекта
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from PyQt6.QtWidgets import QApplication
from gui_window import MainWindow
from theme import GLOBAL_STYLESHEET


def main():
    app = QApplication(sys.argv)

    # Применяем глобальный стиль темы из theme.py
    app.setStyleSheet(GLOBAL_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
