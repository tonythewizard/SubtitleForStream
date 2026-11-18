"""Live visual feedback for audio capture and Whisper inference."""
import math
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from .theme import asset_path


class Spectrum(QWidget):
    POINTS = ((2,0),(45,0),(56,-8),(66,8),(77,-21),(89,26),(101,-42),
              (113,44),(124,-28),(136,22),(149,-11),(158,5),(167,0),(231,0))

    def __init__(self):
        super().__init__()
        self.setFixedSize(193,96)
        self.setAccessibleName('Attività audio e trascrizione')
        self.background=QSvgRenderer(str(asset_path('assets','SubtitleForStream-Spectrum.svg')))
        self.level=0.0
        self.processing=False
        self.phase=0.0

    def set_activity(self,level,processing):
        self.level=max(level,self.level*.72)
        if self.level<.01:
            self.level=0.0
        self.processing=processing
        self.phase=time.monotonic()*9 if self.level or processing else 0.0
        self.update()

    def reset(self):
        self.level=0.0
        self.phase=0.0
        self.processing=False
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.background.render(painter)
        painter.scale(self.width()/232,self.height()/115)
        wave=QPainterPath()
        for index,(x,y) in enumerate(self.POINTS):
            if self.phase:
                pulse=.12*(1+math.sin(self.phase)) if self.processing else 0.0
                gain=min(1.16,.44+pulse+self.level*(.62+.14*math.sin(self.phase-index*.74)))
            else:
                gain=.68
            (wave.moveTo if index==0 else wave.lineTo)(x,58+y*gain)
        glow=QPen(QColor(191,121,255,38+int(self.level*60)),8)
        glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow)
        painter.drawPath(wave)
        gradient=QLinearGradient(0,0,232,0)
        gradient.setColorAt(0,QColor(178,119,255,24))
        gradient.setColorAt(.48,QColor('#dca4ff'))
        gradient.setColorAt(.68,QColor('#fff0ff'))
        gradient.setColorAt(1,QColor(176,113,255,24))
        pen=QPen(QBrush(gradient),2.2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(wave)
