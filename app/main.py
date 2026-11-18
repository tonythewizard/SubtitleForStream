"""SubtitleForStream single-window Windows desktop app."""
from __future__ import annotations
import sys
import html
import traceback
from queue import Queue
from pathlib import Path
from threading import Thread
import httpx
from PySide6.QtCore import QObject, Signal, QTimer, Qt, QUrl, QLibraryInfo, QTranslator, QProcess
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
   QPushButton,QCheckBox,QComboBox,QSpinBox,QSlider,QLineEdit,QTabWidget,QGroupBox,QPlainTextEdit,
   QFormLayout,QFontComboBox,QColorDialog,QInputDialog,QMessageBox,QScrollArea,QMenu,QSystemTrayIcon,QDialog,QProgressBar)

from .settings import Settings,ROOT
from .state import CaptionState
from .overlay import OverlayServer
from .audio import CaptureManager,LiveClipQueue,default_microphone_device,microphone_devices
from .engine import ASRWorker,LLMWorker,nvidia_gpus
from .vulkan import vulkan_gpus
from .theme import STYLESHEET, app_icon, asset_path
from .spectrum import Spectrum
from .i18n import UI_LANGUAGES, resolve_language, text
from .smarttext import LANGUAGES, preset_words
from .updates import NoPublicRelease, default_repository, find_update, installed_version, normalize_repository, stage_installer

RESTART_EXIT_CODE=73
UPDATE_EXIT_CODE=74


def relaunch_arguments(argv, frozen):
    return argv[1:] if frozen else [str(Path(argv[0]).resolve()),*argv[1:]]


class Signals(QObject):
    log=Signal(str)
    asr_state=Signal(object,str)
    update_result=Signal(object,bool,str)
    update_download=Signal(object,str)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=Settings()
        self.ui_language=resolve_language(self.settings.get('ui_language','auto'))
        self.t=lambda key,**values:text(self.ui_language,key,**values)
        self.qt_translation=QTranslator(self)
        translations=QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if self.qt_translation.load(f'qtbase_{self.ui_language}',translations):
            QApplication.installTranslator(self.qt_translation)
        if '--whisper-live' in sys.argv:
            self.settings.data.update(asr_model='medium', processing_mode='whisper', low_latency=True)
        self.state=CaptionState(self.settings)
        self.bus=Signals();self.bus.log.connect(self.add_log)
        self.bus.asr_state.connect(self.on_asr_state)
        self.bus.update_result.connect(self.on_update_result)
        self.bus.update_download.connect(self.on_update_download)
        self.clips=Queue(maxsize=6);self.captures=None;self.asr=None;self.llm=None
        self.running=False;self.server=None
        self.capture_ready=False
        self.startup_stage='idle'
        self.wait_message=''
        self.active_backend_text=''
        self.tray=None
        self.exiting=False
        self.restart_pending=False
        self.update_busy=False
        self.update_installer=None
        self.setWindowTitle('SubtitleForStream · OBS')
        self.setWindowIcon(app_icon())
        self.setMinimumSize(920,720);self.resize(1040,780)
        self.setStyleSheet(STYLESHEET)
        base=QWidget();base.setObjectName('Workspace')
        outer=QVBoxLayout(base);outer.setContentsMargins(20,18,20,18);outer.setSpacing(14)
        header=QWidget();header.setObjectName('Header')
        top=QHBoxLayout(header);top.setContentsMargins(17,13,17,13);top.setSpacing(13)
        mark=QLabel()
        mark.setAccessibleName('Icona SubtitleForStream')
        mark.setFixedSize(68,68)
        mark.setScaledContents(True)
        mark.setPixmap(QPixmap(str(asset_path('assets','SubtitleForStream-Mark.svg'))))
        top.addWidget(mark)
        heading=QVBoxLayout();heading.setSpacing(2)
        title=QLabel('SubtitleForStream');title.setObjectName('BrandTitle');heading.addWidget(title)
        subtitle=QLabel(self.t('subtitle'));subtitle.setObjectName('Subtitle')
        heading.addWidget(subtitle);top.addLayout(heading,1)
        self.live_badge=QLabel(self.t('idle'));self.live_badge.setObjectName('LiveBadge')
        top.addWidget(self.live_badge,0,Qt.AlignmentFlag.AlignVCenter)
        self.kill=QPushButton(self.t('clear'));self.kill.clicked.connect(self.state.clear);top.addWidget(self.kill)
        self.go=QPushButton(self.t('start'));self.go.setObjectName('Primary')
        self.go.clicked.connect(self.toggle);top.addWidget(self.go)
        outer.addWidget(header)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        self.make_sources();self.make_asr();self.make_smarttext();self.make_style();self.make_obs();self.make_preferences()
        self.status=QLabel(self.t('ready'))
        self.status.setObjectName('Status');self.status.setWordWrap(True);outer.addWidget(self.status)
        self.startup_progress=QProgressBar()
        self.startup_progress.setRange(0,0)
        self.startup_progress.setTextVisible(False)
        self.startup_progress.setFixedHeight(5)
        self.startup_progress.setAccessibleName(self.t('loading'))
        self.startup_progress.hide()
        outer.addWidget(self.startup_progress)
        self.setCentralWidget(base)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh_visible_preview);self.timer.start(150)
        self.spectrum_timer=QTimer(self)
        self.spectrum_timer.setInterval(33)
        self.spectrum_timer.timeout.connect(self.refresh_spectrum)
        try:
            self.server=OverlayServer(self.state,self.settings.get('obs_port',8765));self.server.start()
        except OSError as ex:
            self.add_log(self.t('port_error',error=ex))
        else:
            self.add_log(self.t('initialized'))
        self.setup_tray()
        self.refresh_controls()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray=QSystemTrayIcon(self.windowIcon(),self)
        self.tray_menu=QMenu(self)
        show=self.tray_menu.addAction(self.t('open_app'),self.restore_window)
        self.tray_menu.setDefaultAction(show)
        self.tray_toggle=self.tray_menu.addAction(self.t('start'),self.toggle)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.t('open_overlay'),lambda:QDesktopServices.openUrl(QUrl(self.url)))
        self.tray_menu.addAction(self.t('copy_overlay'),lambda:QApplication.clipboard().setText(self.url))
        self.tray_menu.addAction(self.t('clear'),self.state.clear)
        self.tray_menu.addAction(self.t('open_logs'),self.show_diagnostics)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.t('hide'),self.hide)
        close_to_tray=self.tray_menu.addAction(self.t('close_to_tray'))
        close_to_tray.setCheckable(True)
        close_to_tray.setChecked(self.settings.get('close_to_tray',False))
        close_to_tray.toggled.connect(lambda value:self.save('close_to_tray',value))
        self.tray_menu.addAction(self.t('exit'),self.exit_from_tray)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.activate_tray)
        self.tray.show()

    def activate_tray(self,reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_window()

    def restore_window(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def show_diagnostics(self):
        self.restore_window()
        self.tabs.setCurrentWidget(self.obs_page)

    def exit_from_tray(self):
        self.exiting=True
        self.close()
        QApplication.quit()

    def refresh_controls(self):
        action=self.t('stop' if self.running else 'start')
        waiting=self.startup_stage in ('loading','downloading','repairing','retry')
        state=self.t('downloading' if self.startup_stage in ('downloading','repairing') else
                     'loading' if waiting else 'active' if self.running else 'idle')
        self.go.setText(action)
        self.live_badge.setText(state)
        for widget in (self.go,self.live_badge):
            widget.setProperty('live',self.running)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        if self.tray is not None:
            self.tray_toggle.setText(action)
            tip=f'SubtitleForStream · {state}'
            if self.active_backend_text and not waiting:
                tip+=f'\n{self.active_backend_text}'
            self.tray.setToolTip(tip)
        if self.running:
            self.spectrum_timer.start()
        else:
            self.spectrum_timer.stop()
            self.spectrum.reset()
        self.startup_progress.setVisible(waiting)
        if waiting:
            self.backend_status.setText(self.t('backend_waiting'))
        elif self.active_backend_text:
            self.backend_status.setText(self.active_backend_text)
        else:
            self.backend_status.setText(self.t('backend_stopped'))

    def refresh_spectrum(self):
        if self.capture_ready and self.spectrum.isVisible() and not self.isMinimized():
            self.spectrum.set_activity(self.captures.input_level(),self.asr.decoding.is_set())

    def refresh_visible_preview(self):
        if not self.isVisible() or self.isMinimized():
            return
        if self.preview.isVisible():
            self.refresh_preview()
        if self.caption_monitor.isVisible():
            captions=self.state.snapshot()['captions']
            if captions:
                latest=captions[-1]
                self.monitor_source.setText(latest['label'])
                self.caption_monitor.setText(latest['text'])
            else:
                self.monitor_source.setText(self.t('monitor'))
                if self.wait_message:
                    self.caption_monitor.setText(self.wait_message)
                elif self.running and not self.captures.workers:
                    self.caption_monitor.setText(self.t('no_sources'))
                else:
                    self.caption_monitor.setText(self.t('monitor_active' if self.running else 'monitor_idle'))

    def save(self,key,value):self.settings.set(key,value)
    def add_log(self,text):
        if hasattr(self,'logs'):
            self.logs.appendPlainText(text)
            doc=self.logs.document()
            if doc.blockCount()>250:self.logs.clear();self.logs.appendPlainText('Log limitato a 250 righe.')
        if hasattr(self,'status') and not self.wait_message:self.status.setText(text[:180])
    def row(self,label,widget):
        box=QWidget();lay=QHBoxLayout(box);lay.setContentsMargins(0,2,0,2)
        name=QLabel(label);name.setMinimumWidth(195);lay.addWidget(name);lay.addWidget(widget,1)
        return box
    def section(self,title):
        w=QGroupBox(title);v=QVBoxLayout(w);v.setContentsMargins(15,20,15,14);v.setSpacing(11)
        return w,v
    def check(self,label,key):
        ch=QCheckBox(label);ch.setChecked(bool(self.settings.get(key)));ch.toggled.connect(lambda val:self.save(key,val));return ch

    def make_sources(self):
        page=QWidget();layout=QVBoxLayout(page)
        layout.setContentsMargins(17,17,17,16);layout.setSpacing(12)
        monitor=QWidget();monitor.setObjectName('Monitor')
        monitor_frame=QHBoxLayout(monitor)
        monitor_frame.setContentsMargins(23,17,15,17);monitor_frame.setSpacing(17)
        monitor_layout=QVBoxLayout();monitor_layout.setSpacing(8)
        self.monitor_source=QLabel(self.t('monitor'))
        self.monitor_source.setObjectName('MonitorSource')
        self.monitor_source.setTextFormat(Qt.TextFormat.PlainText)
        self.caption_monitor=QLabel(self.t('monitor_idle'))
        self.caption_monitor.setObjectName('MonitorText')
        self.caption_monitor.setTextFormat(Qt.TextFormat.PlainText)
        self.caption_monitor.setWordWrap(True)
        monitor_layout.addWidget(self.monitor_source)
        monitor_layout.addWidget(self.caption_monitor)
        monitor_frame.addLayout(monitor_layout,1)
        self.spectrum=Spectrum()
        monitor_frame.addWidget(self.spectrum,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(monitor)
        grp,v=self.section(self.t('audio_sources'))
        self.src_box=QVBoxLayout();v.addLayout(self.src_box)
        line=QHBoxLayout()
        add_mic=QPushButton('+ '+self.t('add_mic'))
        add_mic.clicked.connect(self.add_microphone_source);line.addWidget(add_mic)
        btn=QPushButton('+ '+self.t('add_app'));btn.clicked.connect(self.add_process_source);line.addWidget(btn)
        refresh=QPushButton('↻ '+self.t('refresh'));refresh.clicked.connect(self.rebuild_sources);line.addWidget(refresh)
        v.addLayout(line);layout.addWidget(grp)
        notice=QLabel(self.t('source_hint'))
        notice.setObjectName('Subtitle')
        notice.setWordWrap(True);layout.addWidget(notice)
        layout.addStretch(1);self.add_scroll_tab(page,self.t('sources'));self.rebuild_sources()

    def add_scroll_tab(self,page,label):
        page.setObjectName('TabPage')
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll,label)

    def rebuild_sources(self):
        while self.src_box.count():
            item=self.src_box.takeAt(0);w=item.widget()
            if w:w.deleteLater()
        devices=microphone_devices()
        for s in self.settings.get('sources',[]):
            row=QWidget();r=QHBoxLayout(row);r.setContentsMargins(0,4,0,4)
            ch=QCheckBox();ch.setFixedWidth(175);ch.setToolTip(s['name'])
            ch.setText(ch.fontMetrics().elidedText(s['name'],Qt.TextElideMode.ElideRight,151))
            ch.setChecked(s.get('enabled',False))
            ch.toggled.connect(lambda checked,sid=s['id']:self.update_source(sid,enabled=checked,restart=True))
            r.addWidget(ch)
            if s['kind']=='mic':
                select=QComboBox();select.addItem(self.t('default_mic'),None)
                select.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                select.setMinimumContentsLength(14)
                for num,name in devices:select.addItem(name,num)
                idx=select.findData(s.get('device'))
                if idx<0 and s.get('device') is not None:
                    select.addItem(self.t('missing_mic',device=s['device']),s['device'])
                    idx=select.count()-1
                select.setCurrentIndex(max(0,idx))
                select.currentIndexChanged.connect(lambda _,sid=s['id'],cb=select:self.change_microphone(sid,cb))
                r.addWidget(select,1)
            else:
                r.addWidget(QLabel(self.t('process',name=s.get('process',''))),1)
            rename=QPushButton(self.t('rename'))
            rename.clicked.connect(lambda _,sid=s['id']:self.rename_source(sid))
            r.addWidget(rename)
            color=QPushButton(self.t('color'));color.clicked.connect(lambda _,sid=s['id']:self.color_source(sid));r.addWidget(color)
            drop=QPushButton(self.t('remove'));drop.clicked.connect(lambda _,sid=s['id']:self.remove_source(sid));r.addWidget(drop)
            self.src_box.addWidget(row)

    def assigned_microphones(self,exclude=None,default=None):
        return {
            default if source.get('device') is None else source['device']
            for source in self.settings.get('sources',[])
            if source['kind']=='mic' and source['id']!=exclude
        }

    def change_microphone(self,sid,selector):
        device=selector.currentData()
        default=default_microphone_device()
        if (default if device is None else device) in self.assigned_microphones(sid,default):
            QMessageBox.information(self,self.t('assigned_mic'),self.t('different_mic'))
            self.rebuild_sources()
            return
        self.update_source(sid,device=device,restart=True)

    def add_microphone_source(self):
        import uuid
        assigned=self.assigned_microphones(default=default_microphone_device())
        available={label:index for index,label in microphone_devices() if index not in assigned}
        if not available:
            QMessageBox.information(self,self.t('no_mic'),self.t('no_mic_hint'))
            return
        label,accepted=QInputDialog.getItem(self,self.t('add_mic'),self.t('input_device'),
                                             list(available),0,False)
        if accepted:
            sources=self.settings.get('sources',[])
            sources.append({'id':uuid.uuid4().hex[:10],'name':label.rsplit(' [',1)[0],
                            'kind':'mic','device':available[label],'enabled':True,'color':'#C8A2FF'})
            self.save('sources',sources)
            self.rebuild_sources()
            self.restart_capture_if_ready()

    def update_source(self,sid,restart=False,**edits):
        sources=self.settings.get('sources');found=False
        for s in sources:
            if s['id']==sid:s.update(edits);found=True
        if found:self.save('sources',sources)
        if found and restart:self.restart_capture_if_ready()
    def rename_source(self,sid):
        source=next((s for s in self.settings.get('sources',[]) if s['id']==sid),None)
        if source is None:
            return
        name,accepted=QInputDialog.getText(self,self.t('rename_source'),self.t('caption_name'),text=source['name'])
        name=name.strip()
        if accepted and name and name!=source['name']:
            self.update_source(sid,name=name)
            self.rebuild_sources()
    def color_source(self,sid):
        sources=self.settings.get('sources');s=next((a for a in sources if a['id']==sid),None)
        if not s:return
        c=QColorDialog.getColor(QColor(s.get('color','#FFFFFF')),self)
        if c.isValid():self.update_source(sid,color=c.name())
    def remove_source(self,sid):
        self.save('sources',[s for s in self.settings.get('sources') if s['id']!=sid])
        self.rebuild_sources()
        self.restart_capture_if_ready()
    def add_process_source(self):
        import psutil
        names=sorted({p.info['name'] for p in psutil.process_iter(['name']) if p.info.get('name') and p.info['name'].lower().endswith('.exe')},key=str.lower)
        if not names:
            name,ok=QInputDialog.getText(self,self.t('add_app'),self.t('process_name'))
        else:name,ok=QInputDialog.getItem(self,self.t('add_app'),self.t('choose_process'),names,0,True)
        if ok and name.strip():
            name=name.strip()
            if any(s.get('process','').lower()==name.lower() for s in self.settings.get('sources')):
                QMessageBox.information(self,self.t('already_added'),self.t('already_added_hint'));return
            import uuid
            sources=self.settings.get('sources')
            sources.append({'id':uuid.uuid4().hex[:10],'name':name.replace('.exe','').upper(),
                'kind':'process','process':name,'enabled':True,'color':'#FFCA81'})
            self.save('sources',sources);self.rebuild_sources()
            self.restart_capture_if_ready()

    def make_asr(self):
        # One simple selector controls the complete inference pipeline.
        pipeline=QComboBox()
        pipeline.addItem(self.t('whisper_only'),'whisper')
        pipeline.addItem(self.t('both'),'both')
        pipeline.addItem(self.t('qwen'),'qwen')
        pipeline.setCurrentIndex(max(0,pipeline.findData(self.settings.get('processing_mode','whisper'))))
        pipeline.currentIndexChanged.connect(lambda _:self.save('processing_mode',pipeline.currentData()))
        page=QWidget();v=QVBoxLayout(page);grp,g=self.section(self.t('offline_engine'))
        g.addWidget(self.row(self.t('ai_mode'),pipeline))
        model=QComboBox();model.addItems(['tiny','base','small','medium'])
        model.setCurrentText(self.settings.get('asr_model','tiny'))
        model.currentTextChanged.connect(lambda x:self.save('asr_model',x))
        g.addWidget(self.row(self.t('model'),model))
        device=QComboBox()
        device.addItem(self.t('backend_auto'),'auto')
        device.addItem(self.t('cpu'),'cpu')
        self.device_names={'cpu':'CPU INT8'}
        for index,name,memory in nvidia_gpus():
            device.addItem(f'NVIDIA GPU {index}: {name} ({memory} MB) - CUDA FP16',f'cuda:{index}')
            self.device_names[f'cuda:{index}']=f'CUDA · {name}'
        for index,name in vulkan_gpus():
            device.addItem(f'Vulkan GPU {index}: {name}',f'vulkan:{index}')
            self.device_names[f'vulkan:{index}']=f'Vulkan · {name}'
        selected=self.settings.get('asr_device','auto')
        if device.findData(selected)<0 and selected.startswith(('cuda','vulkan:')):
            device.addItem(self.t('backend_not_listed',device=selected),selected)
        device.setCurrentIndex(max(0,device.findData(selected)))
        device.currentIndexChanged.connect(lambda _:self.save('asr_device',device.currentData()))
        g.addWidget(self.row(self.t('compute'),device))
        self.backend_status=QLabel(self.t('backend_stopped'))
        self.backend_status.setTextFormat(Qt.TextFormat.PlainText)
        self.backend_status.setObjectName('Status')
        self.backend_status.setWordWrap(True)
        g.addWidget(self.row(self.t('backend_effective'),self.backend_status))
        for label,key in [
            ('live','low_latency'),
            ('vad','vad_enabled'),
            ('hallucinations','hallucination_guard')
        ]:
            g.addWidget(self.check(self.t(label),key))
        lang=QComboBox()
        lang.addItem(self.t('original'),'auto')
        for code in LANGUAGES:lang.addItem(UI_LANGUAGES[code],code)
        lang.setCurrentIndex(max(0,lang.findData(self.settings.get('transcription_language','auto'))))
        lang.setToolTip(self.t('speech_hint'))
        lang.currentIndexChanged.connect(lambda _:self.save('transcription_language',lang.currentData()))
        g.addWidget(self.row(self.t('speech_language'),lang))
        threshold=QSpinBox();threshold.setRange(-65,-15);threshold.setValue(self.settings.get('silence_db',-34));threshold.setSuffix(' dB')
        threshold.valueChanged.connect(lambda x:self.save('silence_db',x));g.addWidget(self.row(self.t('threshold'),threshold))
        note=QLabel(self.t('engine_hint'));note.setWordWrap(True);g.addWidget(note)
        v.addWidget(grp);v.addStretch(1);self.add_scroll_tab(page,self.t('transcription'))

    def show_censor_preset(self):
        language=self.settings.get('transcription_language','auto')
        dialog=QDialog(self)
        dialog.setWindowTitle(self.t('preset_title',language=UI_LANGUAGES.get(language,self.t('all_languages'))))
        dialog.resize(500,520)
        layout=QVBoxLayout(dialog)
        listing=QPlainTextEdit('\n'.join(dict.fromkeys(preset_words(language))))
        listing.setReadOnly(True)
        layout.addWidget(listing)
        close=QPushButton(self.t('close'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def make_smarttext(self):
        page=QWidget();v=QVBoxLayout(page);grp,g=self.section(self.t('filters'))
        for label,key in [('censor','censor'),('punctuation','improve'),('effects','animate')]:
            g.addWidget(self.check(self.t(label),key))
        mode=QComboBox()
        for label,key in [('mask','mask'),('soft','soft'),('replace','remove'),('off','off')]:
            mode.addItem(self.t(label),key)
        ix=mode.findData(self.settings.get('censor_mode','mask'));mode.setCurrentIndex(max(0,ix))
        mode.currentIndexChanged.connect(lambda _:self.save('censor_mode',mode.currentData()));g.addWidget(self.row(self.t('censor_mode'),mode))
        preset=QWidget();preset_row=QHBoxLayout(preset);preset_row.setContentsMargins(0,0,0,0)
        preset_row.addStretch(1)
        show=QPushButton(self.t('show_list'));show.clicked.connect(self.show_censor_preset)
        preset_row.addWidget(show)
        g.addWidget(self.row(self.t('preset'),preset))
        for label,key,placeholder in (
            ('custom_words','banned_words','custom_hint'),
            ('exceptions','censor_exceptions','exceptions_placeholder'),
        ):
            edit=QLineEdit(', '.join(self.settings.get(key,[])))
            edit.setPlaceholderText(self.t(placeholder))
            edit.editingFinished.connect(lambda field=edit,setting=key:
                self.save(setting,[item.strip() for item in field.text().split(',') if item.strip()]))
            g.addWidget(self.row(self.t(label),edit))
        hint=QLabel(self.t('exceptions_hint'))
        hint.setWordWrap(True);g.addWidget(hint)
        note=QLabel(self.t('qwen_hint'));note.setWordWrap(True);g.addWidget(note)
        v.addWidget(grp)
        group,p=self.section(self.t('test_filters'))
        self.try_input=QLineEdit(self.t('sample'));p.addWidget(self.try_input)
        b=QPushButton(self.t('preview_filters'));b.clicked.connect(self.test_caption);p.addWidget(b)
        v.addWidget(group);v.addStretch(1);self.add_scroll_tab(page,'SmartText')

    def make_style(self):
        page=QWidget();v=QHBoxLayout(page);v.setContentsMargins(14,11,14,14);v.setSpacing(14)
        grp,g=self.section(self.t('style_editor'))
        g.setSpacing(6)
        preset=QComboBox();preset.addItems(['Gaming','Classic','Neon','Minimal']);preset.setCurrentText(self.settings.get('preset','Gaming'))
        preset.currentTextChanged.connect(lambda x:self.save('preset',x));g.addWidget(self.row(self.t('style'),preset))
        fonts=QFontComboBox();fonts.setCurrentFont(QFont(self.settings.get('font','Segoe UI')))
        fonts.currentFontChanged.connect(lambda ft:self.save('font',ft.family()));g.addWidget(self.row(self.t('font'),fonts))
        size=QSpinBox();size.setRange(18,120);size.setValue(self.settings.get('font_size',48));size.setSuffix(' px')
        size.valueChanged.connect(lambda x:self.save('font_size',x));g.addWidget(self.row(self.t('size'),size))
        opacity=QSpinBox();opacity.setRange(0,100);opacity.setValue(self.settings.get('bg_opacity',82));opacity.setSuffix(' %')
        opacity.valueChanged.connect(lambda x:self.save('bg_opacity',x));g.addWidget(self.row(self.t('opacity'),opacity))
        outline=QSpinBox();outline.setRange(0,6);outline.setValue(self.settings.get('outline',2));outline.setSuffix(' px')
        outline.valueChanged.connect(lambda x:self.save('outline',x));g.addWidget(self.row(self.t('outline'),outline))
        dur=QSpinBox();dur.setRange(1,20);dur.setValue(int(self.settings.get('duration',5)));dur.setSuffix(' sec')
        dur.valueChanged.connect(lambda x:self.save('duration',x));g.addWidget(self.row(self.t('duration'),dur))
        bottom=QSpinBox();bottom.setRange(0,700);bottom.setValue(self.settings.get('bottom',100));bottom.setSuffix(' px')
        bottom.valueChanged.connect(lambda x:self.save('bottom',x));g.addWidget(self.row(self.t('bottom'),bottom))
        lines=QSpinBox();lines.setRange(1,4);lines.setValue(self.settings.get('max_lines',2))
        lines.valueChanged.connect(lambda x:self.save('max_lines',x));g.addWidget(self.row(self.t('voices'),lines))
        buttons=QHBoxLayout()
        for key in ('text_color','background'):
            button=QPushButton(self.t(key));button.clicked.connect(lambda _,key=key:self.pick_color(key));buttons.addWidget(button)
        transparent=QPushButton(self.t('transparent'))
        transparent.clicked.connect(lambda:opacity.setValue(0))
        buttons.addWidget(transparent)
        g.addLayout(buttons);v.addWidget(grp,3,Qt.AlignmentFlag.AlignTop)
        preview_group,p=self.section(self.t('overlay_preview'))
        self.preview=QLabel(self.t('sample'));self.preview.setWordWrap(True)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumHeight(185)
        p.addWidget(self.preview);v.addWidget(preview_group,2,Qt.AlignmentFlag.AlignTop)
        self.add_scroll_tab(page,self.t('styles'))
    def pick_color(self,key):
        val=QColorDialog.getColor(QColor(self.settings.get(key,'#FFFFFF')),self)
        if val.isValid():self.save(key,val.name())
    def refresh_preview(self):
        s=self.state.snapshot();cfg=s['style'];captions=s['captions']
        text='   |   '.join(f'{html.escape(c["label"])}: {html.escape(c["text"])}' for c in captions)
        if not text:text=self.t('sample')
        self.preview.setText(text)
        color=QColor(cfg['background'])
        tc=cfg['text_color']
        opacity=0 if cfg['preset']=='Minimal' else max(0,min(100,cfg['bg_opacity']))
        bg=f'rgba({color.red()},{color.green()},{color.blue()},{round(opacity*255/100)})'
        self.preview.setStyleSheet(f'background:{bg};color:{tc};border-radius:10px;padding:15px;font-family:"{cfg["font"]}";font-size:{min(27,cfg["font_size"])}px;')
    def test_caption(self):
        from .smarttext import fast_process
        sources=[s for s in self.settings.get('sources',[]) if s['kind']=='mic']
        source=sources[0] if sources else {'id':'preview','name':'TEST','color':'#67E8F9'}
        cfg=self.settings.snapshot()
        text,mood=fast_process(self.try_input.text(),dict(cfg,language=cfg.get('transcription_language','auto')))
        if text:self.state.publish(source,text,mood)

    def make_obs(self):
        page=QWidget();page.setObjectName('TabPage')
        v=QVBoxLayout(page);grp,g=self.section(self.t('overlay_title'))
        self.url=f'http://127.0.0.1:{self.settings.get("obs_port",8765)}/overlay'
        address=QLineEdit(self.url);address.setReadOnly(True);g.addWidget(self.row(self.t('browser_source'),address))
        row=QHBoxLayout();cp=QPushButton(self.t('copy_overlay'));cp.clicked.connect(lambda:QApplication.clipboard().setText(self.url))
        web=QPushButton(self.t('open_overlay'));web.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(self.url)))
        row.addWidget(cp);row.addWidget(web);g.addLayout(row)
        instruction=QLabel(self.t('obs_hint'));instruction.setWordWrap(True);g.addWidget(instruction);v.addWidget(grp)
        group,p=self.section(self.t('websocket'))
        self.obs_pw=QLineEdit();self.obs_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.obs_pw.setPlaceholderText(self.t('obs_password'));p.addWidget(self.obs_pw)
        connect=QPushButton(self.t('obs_install'));connect.clicked.connect(self.install_obs)
        p.addWidget(connect)
        notice=QLabel(self.t('obs_websocket_hint'));notice.setWordWrap(True);p.addWidget(notice)
        v.addWidget(group)
        group2,p2=self.section(self.t('diagnostics'))
        self.logs=QPlainTextEdit();self.logs.setReadOnly(True);self.logs.setMaximumBlockCount(250);p2.addWidget(self.logs)
        self.obs_page=page
        v.addWidget(group2,1);self.tabs.addTab(page,self.t('obs_logs'))

    def make_preferences(self):
        page=QWidget()
        layout=QVBoxLayout(page)
        group,form=self.section(self.t('interface'))
        language=QComboBox()
        language.addItem(self.t('system_language'),'auto')
        for code,label in UI_LANGUAGES.items():
            language.addItem(label,code)
        language.setCurrentIndex(max(0,language.findData(self.settings.get('ui_language','auto'))))
        def save_language():
            self.apply_ui_language(language.currentData())
        language.currentIndexChanged.connect(save_language)
        form.addWidget(self.row(self.t('ui_language'),language))
        hint=QLabel(self.t('ui_language_hint'))
        hint.setWordWrap(True)
        form.addWidget(hint)
        form.addWidget(self.check(self.t('autostart'),'autostart_transcription'))
        layout.addWidget(group)
        group,form=self.section(self.t('updates'))
        self.update_repo_edit=QLineEdit(self.settings.get('update_repository') or default_repository())
        self.update_repo_edit.setPlaceholderText('owner/repository')
        self.update_repo_edit.editingFinished.connect(self.save_update_repository)
        form.addWidget(self.row(self.t('repository'),self.update_repo_edit))
        form.addWidget(self.check(self.t('update_on_start'),'check_updates_on_startup'))
        self.update_status=QLabel(self.t('update_version',version=installed_version()))
        self.update_status.setWordWrap(True)
        form.addWidget(self.update_status)
        self.update_check_button=QPushButton(self.t('check_update'))
        self.update_check_button.clicked.connect(lambda:self.check_for_updates(manual=True))
        form.addWidget(self.update_check_button,0,Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(group)
        layout.addStretch(1)
        self.add_scroll_tab(page,self.t('settings'))

    def apply_ui_language(self,language):
        if self.restart_pending or language==self.settings.get('ui_language','auto'):
            return
        self.save('ui_language',language)
        self.restart_pending=True
        self.status.setText(self.t('restarting'))
        QTimer.singleShot(0,self.restart_for_language)

    def restart_for_language(self):
        self.exit_for_handoff(RESTART_EXIT_CODE)

    def exit_for_handoff(self,code):
        self.exiting=True
        QApplication.setQuitOnLastWindowClosed(False)
        self.close()
        QApplication.exit(code)

    def save_update_repository(self):
        value=self.update_repo_edit.text().strip()
        try:
            repo=normalize_repository(value) if value else ''
        except ValueError:
            self.update_status.setText(self.t('update_repo_required'))
            return None
        self.update_repo_edit.setText(repo)
        if repo!=self.settings.get('update_repository',''):
            self.save('update_repository',repo)
        return repo

    def check_for_updates(self,manual=False):
        if self.update_busy or self.exiting:
            return
        repository=(self.save_update_repository() if manual else
                    self.settings.get('update_repository') or default_repository())
        if not repository:
            if manual:self.update_status.setText(self.t('update_repo_required'))
            return
        self.update_busy=True
        self.update_check_button.setEnabled(False)
        self.update_status.setText(self.t('update_checking'))

        def check():
            try:
                with httpx.Client(timeout=8) as client:
                    release=find_update(repository,installed_version(),client)
                self.bus.update_result.emit(release,manual,'')
            except NoPublicRelease:
                self.bus.update_result.emit(None,manual,'no_public_release')
            except (OSError,ValueError,httpx.HTTPError) as error:
                self.bus.update_result.emit(None,manual,str(error))

        Thread(target=check,daemon=True,name='github-update-check').start()

    def on_update_result(self,release,manual,error):
        self.update_busy=False
        self.update_check_button.setEnabled(True)
        if self.exiting:
            return
        if error:
            if error=='no_public_release':
                self.update_status.setText(self.t('no_public_release'))
            else:
                self.update_status.setText(self.t('update_check_failed'))
                if manual:self.logs.appendPlainText(error)
            return
        if release is None:
            self.update_status.setText(self.t('update_current'))
            return
        try:
            current=normalize_repository(self.update_repo_edit.text())
        except ValueError:
            return
        if current.casefold()!=release.repository.casefold():
            return
        dismissed=f'{release.repository.casefold()}:{release.tag}'
        if not manual and self.settings.get('update_dismissed')==dismissed:
            self.update_status.setText(self.t('update_skipped',version=release.version))
            return
        question='update_question' if release.asset_url else 'update_page_question'
        answer=QMessageBox.question(
            self,self.t('update_available'),self.t(question,version=release.version),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:
            self.save('update_dismissed',dismissed)
            self.update_status.setText(self.t('update_skipped',version=release.version))
            return
        if not release.asset_url:
            QDesktopServices.openUrl(QUrl(release.page))
            self.update_status.setText(self.t('update_available'))
            return
        self.update_busy=True
        self.update_check_button.setEnabled(False)
        self.update_status.setText(self.t('update_fetch',version=release.version))
        self.status.setText(self.t('update_fetch',version=release.version))

        def download():
            try:
                with httpx.Client(timeout=30) as client:
                    path=stage_installer(release,ROOT/'updates',client)
                self.bus.update_download.emit(path,'')
            except (OSError,ValueError,httpx.HTTPError) as error:
                self.bus.update_download.emit(None,str(error))

        Thread(target=download,daemon=True,name='github-update-download').start()

    def on_update_download(self,path,error):
        self.update_busy=False
        self.update_check_button.setEnabled(True)
        if self.exiting:
            return
        if error:
            self.logs.appendPlainText(error)
            self.update_status.setText(self.t('update_failed'))
            QMessageBox.warning(self,self.t('updates'),self.t('update_failed'))
            return
        self.update_installer=path
        self.exit_for_handoff(UPDATE_EXIT_CODE)
    def install_obs(self):
        try:
            import obsws_python as obs
            with obs.ReqClient(host='127.0.0.1',port=int(self.settings.get('obs_ws_port',4455)),
                               password=self.obs_pw.text(),timeout=3) as client:
                scene=client.get_current_program_scene().current_program_scene_name
                inputs=client.get_input_list().inputs
                existing={item['inputName'] for item in inputs if item.get('inputKind')=='browser_source'}
                source='SubtitleForStream'
                if source not in existing:
                    legacy=next((name for name in ('SubtitleForTwitch','StreamCaptions AI') if name in existing),None)
                    if legacy:
                        client.set_input_name(legacy,source)
                data={'url':self.url,'width':1920,'height':1080,'fps':30,'shutdown':False}
                try:
                    client.send('CreateInput',{'sceneName':scene,'inputName':source,
                         'inputKind':'browser_source','inputSettings':data,'sceneItemEnabled':True})
                    QMessageBox.information(self,self.t('obs_connected'),self.t('obs_created',scene=scene))
                except Exception as exc:
                    if 'already exists' in str(exc).lower() or 'resource already exists' in str(exc).lower():
                        client.send('SetInputSettings',{'inputName':source,'inputSettings':data,'overlay':True})
                        QMessageBox.information(self,self.t('obs_connected'),self.t('obs_updated'))
                    else:raise
        except Exception as ex:
            QMessageBox.warning(self,self.t('obs_failed'),str(ex))

    def toggle(self):
        if self.running:
            self.running=False
            self.capture_ready=False
            self.startup_stage='idle'
            self.wait_message=''
            self.active_backend_text=''
            self.captures.stop();self.asr.stop();self.llm.stop()
            self.refresh_controls();self.add_log(self.t('stopped'));return
        self.start_transcription()

    def restart_capture_if_ready(self):
        if self.running and self.capture_ready:
            self.captures.start()

    def on_asr_state(self,worker,stage):
        if not self.running or worker is not self.asr:
            return
        self.startup_stage=stage
        if stage=='ready':
            self.wait_message=''
            backend=worker.active_device
            if backend:
                name=self.device_names.get(backend,backend.upper())
                key='backend_fallback' if backend=='cpu' and worker.selected_device not in ('cpu','auto') else 'backend_loaded'
                self.active_backend_text=self.t(key,device=name,model=worker.active_model)
            if not self.capture_ready:
                self.capture_ready=True
                self.captures.start()
            self.add_log(self.t('started' if self.captures.workers else 'no_sources'))
        else:
            self.active_backend_text=''
            key={'retry':'model_retry','downloading':'download_model','repairing':'repair_model','loading':'loading_model'}[stage]
            self.wait_message=self.t(key)
            self.status.setText(self.wait_message)
        self.refresh_controls()

    def start_transcription(self):
        if self.running:
            return
        self.clips=LiveClipQueue(maxsize=4) if self.settings.get('low_latency',True) else Queue(maxsize=6)
        self.llm=LLMWorker(self.settings,self.state,self.bus.log.emit,self.clips)
        self.asr=ASRWorker(self.settings,self.clips,self.state,self.bus.log.emit,self.llm,self.bus.asr_state.emit)
        self.captures=CaptureManager(self.settings,self.clips,self.bus.log.emit)
        self.running=True
        self.on_asr_state(self.asr,'loading')
        self.llm.start();self.asr.start()
    def closeEvent(self,event):
        if self.tray is not None and not self.exiting and self.settings.get('close_to_tray',False):
            self.hide()
            event.ignore()
            return
        if self.tray is not None:
            self.tray.hide()
        self.running=False
        QApplication.removeTranslator(self.qt_translation)
        try:
            if self.captures:self.captures.stop()
            if self.asr:self.asr.stop()
            if self.llm:self.llm.stop()
            if self.server:self.server.stop()
        except Exception:pass
        event.accept()

def main():
    if sys.platform=='win32':
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('SubtitleForStream.Desktop')
    app=QApplication(sys.argv);app.setApplicationName('SubtitleForStream')
    app.setWindowIcon(app_icon())
    window=Window()
    window.show()
    if window.settings.get('autostart_transcription',True):
        QTimer.singleShot(0,window.start_transcription)
    if window.settings.get('check_updates_on_startup',True):
        QTimer.singleShot(1500,window.check_for_updates)
    code=app.exec()
    if code==RESTART_EXIT_CODE:
        started,_=QProcess.startDetached(
            sys.executable,relaunch_arguments(sys.argv,getattr(sys,'frozen',False)),str(Path.cwd()))
        if not started:
            language=resolve_language(window.settings.get('ui_language','auto'))
            QMessageBox.critical(None,'SubtitleForStream',text(language,'restart_failed'))
            sys.exit(1)
        code=0
    if code==UPDATE_EXIT_CODE:
        path=window.update_installer
        started,_=QProcess.startDetached(str(path),[],str(path.parent))
        if not started:
            QMessageBox.critical(None,'SubtitleForStream',window.t('update_launch_failed',path=path))
            sys.exit(1)
        code=0
    sys.exit(code)

if __name__=='__main__':main()
