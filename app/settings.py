from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from threading import RLock

DATA_PARENT = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share')
NEW_ROOT = DATA_PARENT / 'SubtitleForStream'
LEGACY_ROOT = DATA_PARENT / 'StreamCaptionsAI'
# Existing installations keep their cached models and settings in place.
ROOT = LEGACY_ROOT if not NEW_ROOT.exists() and LEGACY_ROOT.is_dir() else NEW_ROOT
CONFIG_FILE = ROOT / 'config.json'
BUNDLED_MODELS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'bundled_models'

DEFAULTS = {
    'sources': [
        {'id':'mic','name':'TU · Microfono','kind':'mic','device':None,'enabled':True,'color':'#67E8F9'},
        {'id':'discord','name':'DISCORD · Amici','kind':'process','process':'Discord.exe','enabled':True,'color':'#D8B4FE'},
    ],
    'asr_model': 'tiny', 'transcription_language':'auto', 'silence_db': -34,
    'asr_device':'auto', 'processing_mode':'whisper', 'low_latency':True, 'vad_enabled':True, 'hallucination_guard':True,
    'close_to_tray':False, 'ui_language':'auto', 'autostart_transcription':True,
    'check_updates_on_startup':True, 'update_repository':'', 'update_dismissed':'',
    'max_caption_age':4.0,
    'censor':True, 'censor_mode':'mask', 'banned_words':[], 'censor_exceptions':[],
    'improve':True, 'animate':True, 'llm_enabled':False,
    'preset':'Gaming', 'font':'Segoe UI', 'font_size':48,
    'text_color':'#FFFFFF', 'background':'#111827', 'bg_opacity':82,
    'outline':2, 'duration':5.0, 'max_lines':2, 'bottom':100,
    'obs_port':8765, 'obs_ws_port':4455, 'obs_password':'',
}

class Settings:
    def __init__(self, file:Path=CONFIG_FILE):
        self.file = Path(file)
        self.lock = RLock()
        self.data = copy.deepcopy(DEFAULTS)
        if self.file.exists():
            try:
                with self.file.open(encoding='utf-8') as f:
                    incoming=json.load(f)
                if isinstance(incoming,dict):
                    self.data.update(incoming)
                    old='tonythewizard/subtitlefortwitch'
                    repo=str(self.data.get('update_repository','')).strip().lower()
                    if repo.removeprefix('https://github.com/').rstrip('/')==old:
                        self.data['update_repository']=''
                    if str(self.data.get('update_dismissed','')).lower().startswith(old+':'):
                        self.data['update_dismissed']=''
            except (OSError,ValueError): pass

    def get(self,key,default=None):
        with self.lock:return copy.deepcopy(self.data.get(key,default))
    def set(self,key,value):
        with self.lock:
            self.data[key]=copy.deepcopy(value)
            self.save()
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.data)
    def save(self):
        with self.lock:
            self.file.parent.mkdir(parents=True,exist_ok=True)
            temp=self.file.with_suffix('.tmp')
            temp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(temp,self.file)
