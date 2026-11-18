"""Desktop localization, independent of speech recognition settings."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QLocale


UI_LANGUAGES = {'it':'Italiano','en':'English','es':'Español','fr':'Français','de':'Deutsch'}


def resolve_language(selected='auto', system_languages=None):
    if selected in UI_LANGUAGES:
        return selected
    if system_languages is None:
        system_languages = QLocale.system().uiLanguages()
    for tag in system_languages:
        code = tag.replace('_','-').split('-',1)[0].lower()
        if code in UI_LANGUAGES:
            return code
    return 'en'


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).resolve().parent / 'ui_strings.txt'
    entries = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        key,*values = line.split('|')
        if len(values)!=len(UI_LANGUAGES) or key in entries:
            raise ValueError(f'Invalid UI translation: {key}')
        entries[key] = dict(zip(UI_LANGUAGES,values))
    return entries


def text(locale,key,**values):
    phrases = catalog()[key]
    return phrases.get(locale,phrases['en']).format(**values)
