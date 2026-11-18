"""Visual system shared by the window and its tray menu."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

def asset_path(*parts):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return root.joinpath(*parts)


def icon_images(sizes):
    renderer = QSvgRenderer(str(asset_path('assets','SubtitleForStream-Mark.svg')))
    if not renderer.isValid():
        raise RuntimeError('Risorsa icona SubtitleForStream mancante o non valida.')
    for size in sizes:
        image = QImage(size,size,QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        yield image


def app_icon():
    icon = QIcon()
    for image in icon_images((16,20,24,32,40,48,64,128,256)):
        icon.addPixmap(QPixmap.fromImage(image))
    return icon


STYLESHEET = """
QWidget { color: #f4edff; font: 10pt "Segoe UI"; }
QMainWindow, QDialog { background: #100b1d; }
QWidget#Workspace {
    background: qradialgradient(cx:.83,cy:.08,radius:1.05,fx:.83,fy:.08,
                                stop:0 #341451, stop:.48 #1b1032, stop:1 #0d0918);
}
QWidget#TabPage { background: #161025; }
QWidget#Header {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(148,72,221,80),
                                 stop:.44 rgba(116,48,191,36),stop:1 rgba(56,30,96,105));
    border: 1px solid rgba(205,154,255,86); border-top-color: #9868bd; border-radius: 19px;
}
QLabel#BrandTitle { color: #ffffff; font-size: 25pt; font-weight: 700; }
QLabel#Subtitle, QLabel#Status { color: #cdbce2; }
QLabel#Status { background: rgba(116,64,185,31); border: 1px solid #432b61; border-radius: 9px; padding: 8px 12px; }
QLabel#LiveBadge { background: rgba(184,139,253,42); color: #ead9ff; border: 1px solid #644985;
                  border-radius: 12px; padding: 5px 10px; font-weight: 700; }
QLabel#LiveBadge[live="true"] { background: #432466; color: #f5dcff; border: 1px solid #ac6beb; }
QWidget#Monitor {
    background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #1b1331,stop:.55 #2e164c,stop:1 #5c287a);
    border: 1px solid #70468f; border-top-color: #a16fbb; border-radius: 15px;
}
QLabel#MonitorSource { color: #eac9ff; font-size: 10pt; font-weight: 700; }
QLabel#MonitorText { color: #fff7ff; font-size: 20pt; font-weight: 600; }
QTabWidget::pane { background: #161025; border: 1px solid #52336d; border-radius: 13px; }
QTabBar::tab { background: rgba(72,40,112,78); color: #dcc8f1; border: 1px solid transparent;
               border-top-left-radius: 9px; border-top-right-radius: 9px; padding: 10px 18px; margin-right: 4px; }
QTabBar::tab:hover { background: #3b2358; }
QTabBar::tab:selected { color: white; background: #442462; border-color: #8152a3; }
QGroupBox { background: rgba(104,62,149,33); border: 1px solid #4b3465; border-radius: 12px; margin-top: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 7px; color: #e1c7ff; font-weight: 700; }
QPushButton { background: rgba(144,83,208,42); color: #f4eaff; border: 1px solid #63447e;
              border-radius: 8px; padding: 8px 12px; font-weight: 600; }
QPushButton:hover { background: #3a2556; border-color: #8c58bd; }
QPushButton:pressed { background: #241734; }
QPushButton:disabled { background: #21192b; color: #8f7f9f; border-color: #382c45; }
QPushButton#Primary {
    background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #6529b3,stop:1 #a445e0);
    color: white; border-color: #c38afb; padding: 11px 15px;
}
QPushButton#Primary:hover { background: #8a43d5; }
QPushButton#Primary[live="true"] { background: #473063; border-color: #aa7cda; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QFontComboBox {
    border: 1px solid #503763; border-radius: 7px; background: #130e1c; padding: 6px 8px;
    selection-background-color: #7338b5; selection-color: white;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QPushButton:focus {
    border: 1px solid #b984ff;
}
QComboBox QAbstractItemView { background: #21162e; border: 1px solid #67458a;
                             selection-background-color: #5c3387; selection-color: white; }
QCheckBox { spacing: 8px; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #171020; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #6a478c; border-radius: 5px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #2a1b3f; border: 0; border-radius: 2px; }
QProgressBar::chunk { background: #bb76ff; border-radius: 2px; }
QMenu { background: #21162e; border: 1px solid #67458a; padding: 5px; }
QMenu::item { padding: 7px 24px; }
QMenu::item:selected { background: #4b2a71; border-radius: 5px; color: white; }
QMenu::item:disabled { color: #ad9cbe; }
QMenu::separator { height: 1px; margin: 4px 8px; background: #483159; }
"""
