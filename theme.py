"""
theme.py
Файл визуальной темы приложения STRG (Строгий стиль QUIK).
Прямоугольные кнопки (0px), тонкие рамки 1px, системные шрифты Tahoma (11px).
"""

import os

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons").replace("\\", "/")

# ============================================================
# 1. ЦВЕТОВАЯ ПАЛИТРА ГРАФИКА
# ============================================================
CHART_BG            = "#111111"  # Фон графика (строгий темный графит)
CHART_GRID          = "#202020"  # Цвет линий сетки
CHART_AXIS_TEXT     = "#777777"  # Цвет текста на шкалах (цена и время)

# Свечи (классический стиль QUIK)
CANDLE_UP_BODY      = "#c0c0c0"  # Тело растущей (белой) свечи
CANDLE_DOWN_BODY    = "#353535"  # Тело падающей (серой) свечи
CANDLE_WICK         = "#777777"  # Цвет фитилей (теней)

# Фракталы и сигналы
FRACTAL_UP          = "#26a69a"  # Треугольник вверх ▲ (зеленый)
FRACTAL_DOWN        = "#ef5350"  # Треугольник вниз ▼ (красный)
PLATEAU_HIGH_LINE   = "#00e676"  # Ярко-зеленая линия плато High (вверх)
PLATEAU_LOW_LINE    = "#ff7700"  # Ярко-оранжевая линия плато Low (вниз)
CORRIDOR_UPPER      = "#00e676"  # Верхняя граница коридора сигналов (ярко-зеленый)
CORRIDOR_LOWER      = "#ff5252"  # Нижняя граница коридора сигналов (красный)

# Цвета каналов (4 разновидности)
# Канал 0: Фракталы и плато (Оранжевый)
CH0_ORANGE_UPPER    = "#ff9800"  # Верхняя граница (янтарно-оранжевый)
CH0_ORANGE_LOWER    = "#ff9800"  # Нижняя граница (янтарно-оранжевый)
CH0_ORANGE_FILL     = (255, 152, 0, 14)  # Деликатная прозрачная оранжевая заливка

# Канал 1: Классика Вильямса (Зеленый)
CH1_GREEN_UPPER     = "#00e676"  # Верхняя граница (ярко-зеленый)
CH1_GREEN_LOWER     = "#00e676"  # Нижняя граница (ярко-зеленый)
CH1_GREEN_FILL      = (0, 230, 118, 14)  # Деликатная прозрачная зелень

# Канал 2: Диапазонный (Фиолетовый)
CH2_PURPLE_UPPER    = "#ba68c8"  # Верхняя граница (светло-фиолетовый)
CH2_PURPLE_LOWER    = "#ba68c8"  # Нижняя граница (светло-фиолетовый)
CH2_PURPLE_FILL     = (186, 104, 200, 14)  # Деликатная прозрачная фиолетовая заливка

# Канал 3: Структурный (Синий)
CH3_BLUE_UPPER      = "#2979ff"  # Верхняя граница (ярко-синий)
CH3_BLUE_LOWER      = "#2979ff"  # Нижняя граница (ярко-синий)
CH3_BLUE_FILL       = (41, 121, 255, 14)  # Деликатная прозрачная синева

# Канал 4: Вильямс с расширением плато (Бирюзовый)
CH4_CYAN_UPPER      = "#00e5ff"  # Верхняя граница (ярко-бирюзовый)
CH4_CYAN_LOWER      = "#00e5ff"  # Нижняя граница (ярко-бирюзовый)
CH4_CYAN_FILL       = (0, 229, 255, 14)  # Деликатная прозрачная бирюзовая заливка

# Торговые уровни
SIGNAL_LINE         = "#d4b106"  # Линия ожидания сигнала (желтый)
STOP_LOSS_LINE      = "#d32f2f"  # Линия Стоп-лосса (красный)
TAKE_PROFIT_LINE    = "#2e7d32"  # Линия Тейк-профита (зеленый)


# ============================================================
# 2. СТИЛИ ИНТЕРФЕЙСА (Строгий компактный QUIK: 0px, 11px шрифт)
# ============================================================
GLOBAL_STYLESHEET = """
/* Главное окно и базовые шрифты */
QMainWindow {
    background-color: #111111;
}
QWidget {
    color: #b5b5b5;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* Верхний тулбар */
QFrame#TopToolbar {
    background-color: #1a1a1a;
    border: 1px solid #282828;
    border-radius: 0px;
}

/* Правая панель управления */
QScrollArea#RightPanelScroll {
    background-color: #141414;
    border: 1px solid #242424;
    border-radius: 0px;
}
QWidget#RightPanelContainer {
    background-color: #141414;
}
QFrame#RightPanel {
    background-color: #141414;
    border: 1px solid #242424;
    border-radius: 0px;
}

/* Стилизация скроллбара (как на скриншотах 3 и 4) */
QScrollBar:vertical {
    background: #141414;
    width: 6px;
    margin: 0px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #383838;
    min-height: 25px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #555555;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* Панель плеера */
QFrame#ReplayerPanel {
    background-color: #161616;
    border: 1px solid #282828;
    border-radius: 0px;
}

/* Общий стиль кнопок — строго 0px */
QPushButton {
    border-radius: 0px;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* Кнопки верхнего тулбара */
QPushButton.TopToolBtn {
    background-color: #222222;
    color: #b8b8b8;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 2px 6px;
    height: 18px;
    font-size: 10.5px;
}
QPushButton.TopToolBtn:hover {
    background-color: #2e2e2e;
    border-color: #444444;
    color: #ffffff;
}
QPushButton.TopToolBtn:pressed {
    background-color: #173650;
    border-color: #23527c;
    color: #ffffff;
}

/* Селектор торгового дня (QComboBox) */
QComboBox#ComboDays {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: bold;
    min-width: 230px;
    height: 18px;
}
QComboBox#ComboDays:hover {
    border-color: #4f4f4f;
    background-color: #222222;
}
QComboBox#ComboDays::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #333333;
    background: #202020;
}
QComboBox#ComboDays::drop-down:hover {
    background: #2b2b2b;
}
QComboBox#ComboDays QAbstractItemView {
    background-color: #161616;
    color: #cccccc;
    border: 1px solid #333333;
    selection-background-color: #173650;
    selection-color: #ffffff;
    outline: none;
    padding: 2px;
}
QPushButton#BtnBrowseDay {
    background-color: #222222;
    color: #b8b8b8;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 1px;
    height: 18px;
    font-size: 11px;
}
QPushButton#BtnBrowseDay:hover {
    border-color: #4f4f4f;
    background-color: #2b2b2b;
    color: #ffffff;
}

/* Селектор стратегии Lua (QComboBox) */
QComboBox#ComboStrategy {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 1px 4px;
    font-size: 10px;
    font-weight: bold;
    height: 20px;
}
QComboBox#ComboStrategy:hover {
    border-color: #4f4f4f;
    background-color: #222222;
}
QComboBox#ComboStrategy::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid #333333;
    background: #202020;
}
QComboBox#ComboStrategy::drop-down:hover {
    background: #2b2b2b;
}
QComboBox#ComboStrategy QAbstractItemView {
    background-color: #161616;
    color: #cccccc;
    border: 1px solid #333333;
    selection-background-color: #173650;
    selection-color: #ffffff;
    outline: none;
    padding: 2px;
}
QPushButton#BtnBrowseStrat {
    background-color: #222222;
    color: #b8b8b8;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 1px;
    height: 20px;
    font-size: 11px;
}
QPushButton#BtnBrowseStrat:hover {
    border-color: #4f4f4f;
    background-color: #2b2b2b;
    color: #ffffff;
}

/* Выпадающий список таймфреймов */
QComboBox#ComboTf {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 1px 4px;
    font-size: 11px;
    font-weight: bold;
    min-width: 52px;
    height: 18px;
}
QComboBox#ComboTf:hover {
    border-color: #4f4f4f;
    background-color: #222222;
}
QComboBox#ComboTf::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 14px;
    border-left: 1px solid #333333;
    background: #202020;
}
QComboBox#ComboTf::drop-down:hover {
    background: #2b2b2b;
}
QComboBox#ComboTf QAbstractItemView {
    background-color: #161616;
    color: #cccccc;
    border: 1px solid #333333;
    selection-background-color: #173650;
    selection-color: #ffffff;
    outline: none;
    padding: 2px;
}

/* Кнопки переключения режимов (МОК, ТЕСТ, БОЙ) */
QPushButton.ModeBtn {
    background-color: #1c1c1c;
    color: #888888;
    border: 1px solid #2c2c2c;
    border-radius: 0px;
    padding: 3px;
    font-weight: bold;
    font-size: 10px;
}
QPushButton.ModeBtn:hover {
    background-color: #262626;
    color: #dddddd;
    border-color: #3d3d3d;
}
QPushButton.ModeBtn:checked {
    background-color: #102416;
    color: #52c41a;
    border: 1px solid #276f43;
}

/* Кнопки выбора таймфрейма (1M, 3M, 5M...) */
QPushButton.TfBtn {
    background-color: #1e1e1e;
    color: #999999;
    border: 1px solid #2d2d2d;
    border-radius: 0px;
    padding: 4px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton.TfBtn:hover {
    background-color: #282828;
    color: #ffffff;
    border-color: #3d3d3d;
}
QPushButton.TfBtn:checked {
    background-color: #173650;
    color: #ffffff;
    border: 1px solid #2a629a;
}

/* Кнопки плеера */
QPushButton.ReplayBtn {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 2px 5px;
    font-size: 11px;
    font-weight: bold;
    min-height: 20px;
}
QPushButton.ReplayBtn:hover {
    background-color: #2a2a2a;
    border-color: #444444;
    color: #ffffff;
}
QPushButton.ReplayBtn:checked {
    background-color: #173650;
    border-color: #2a629a;
    color: #ffffff;
}

/* Слайдер-скруббер времени */
QSlider::groove:horizontal {
    height: 4px;
    background: #222222;
    border: 1px solid #303030;
    border-radius: 0px;
}
QSlider::sub-page:horizontal {
    background: #6e5812;
}
QSlider::handle:horizontal {
    background: #c9b037;
    border: 1px solid #f1c40f;
    width: 10px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 0px;
}
QSlider::handle:horizontal:hover {
    background: #ffd700;
}

/* Кнопка 'Обновить' */
QPushButton#BtnRefresh {
    background-color: #182833;
    color: #cccccc;
    border: 1px solid #233d50;
    border-radius: 0px;
    padding: 5px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton#BtnRefresh:hover {
    background-color: #203545;
    color: #ffffff;
}

/* Кнопка 'Перезапуск' */
QPushButton#BtnRestart {
    background-color: #33181f;
    color: #cccccc;
    border: 1px solid #4a212c;
    border-radius: 0px;
    padding: 5px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton#BtnRestart:hover {
    background-color: #45202a;
    color: #ffffff;
}

/* Кнопка 'Показать все' */
QPushButton#BtnShowAll {
    background-color: #172823;
    color: #cccccc;
    border: 1px solid #234237;
    border-radius: 0px;
    padding: 5px;
    font-weight: bold;
    font-size: 11px;
}
QPushButton#BtnShowAll:hover {
    background-color: #1e362e;
    color: #ffffff;
}

/* Дерево слоев видимости (QTreeWidget) */
QTreeWidget#VisibilityTree {
    background-color: #121212;
    border: 1px solid #282828;
    border-radius: 0px;
    color: #cccccc;
    font-size: 10.5px;
    padding: 2px;
}
QTreeWidget#VisibilityTree::item {
    padding: 2px 1px;
    border: none;
}
QTreeWidget#VisibilityTree::item:hover {
    background-color: #1e1e1e;
}
QTreeWidget#VisibilityTree::item:selected {
    background-color: #162836;
    color: #ffffff;
}

/* Стрелки раскрывающихся веток дерева (серые в неактивном состоянии, голубые при наведении) */
QTreeWidget#VisibilityTree::branch:has-children:!has-siblings:closed,
QTreeWidget#VisibilityTree::branch:closed:has-children:has-siblings {
    border-image: none;
    image: url("__ICONS_DIR__/branch_closed.svg");
}
QTreeWidget#VisibilityTree::branch:has-children:!has-siblings:closed:hover,
QTreeWidget#VisibilityTree::branch:closed:has-children:has-siblings:hover,
QTreeWidget#VisibilityTree::branch:has-children:!has-siblings:closed:pressed,
QTreeWidget#VisibilityTree::branch:closed:has-children:has-siblings:pressed {
    border-image: none;
    image: url("__ICONS_DIR__/branch_closed_hover.svg");
}
QTreeWidget#VisibilityTree::branch:open:has-children:!has-siblings,
QTreeWidget#VisibilityTree::branch:open:has-children:has-siblings {
    border-image: none;
    image: url("__ICONS_DIR__/branch_open.svg");
}
QTreeWidget#VisibilityTree::branch:open:has-children:!has-siblings:hover,
QTreeWidget#VisibilityTree::branch:open:has-children:has-siblings:hover,
QTreeWidget#VisibilityTree::branch:open:has-children:!has-siblings:pressed,
QTreeWidget#VisibilityTree::branch:open:has-children:has-siblings:pressed {
    border-image: none;
    image: url("__ICONS_DIR__/branch_open_hover.svg");
}
""".replace("__ICONS_DIR__", ICONS_DIR)

