"""Fast, deterministic censorship and conservative text improvement."""
from __future__ import annotations
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path


LANGUAGES = {'it':'Italiano','en':'Inglese','es':'Spagnolo','fr':'Francese','de':'Tedesco'}
PRESETS_DIR = Path(__file__).resolve().parent / 'censor_presets'


def _clean_term(word):
    return unicodedata.normalize('NFC',' '.join(word.split()))


@lru_cache(maxsize=6)
def _read_terms(filename):
    return tuple(_clean_term(line) for line in (PRESETS_DIR / filename).read_text(encoding='utf-8').splitlines()
                 if line.strip() and not line.lstrip().startswith('#'))


def preset_words(language):
    common = _read_terms('divine_names.txt')
    if language == 'auto':
        # A typed preview has no audio from which to detect a language.
        return tuple(term for code in LANGUAGES for term in _read_terms(f'{code}.txt')) + common
    return _read_terms(f'{language}.txt') + common if language in LANGUAGES else common


def _effective_words(cfg):
    preset = preset_words(cfg.get('language',cfg.get('transcription_language','it')))
    preset_keys = {word.casefold() for word in preset}
    exceptions = {_clean_term(word).casefold() for word in cfg.get('censor_exceptions',[])
                  if isinstance(word,str)} & preset_keys
    return [word for word in (*preset,*cfg.get('banned_words',[]))
            if isinstance(word,str) and _clean_term(word).casefold() not in exceptions]


@lru_cache(maxsize=32)
def _censor_pattern(words):
    # CJK and Thai text may contain no spaces between adjacent words.
    unspaced = re.compile(r'[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff]')
    patterns = []
    for word in words:
        expression = r'[\s,._-]+'.join(re.escape(part) for part in word.split())
        left = '' if unspaced.match(word[0]) else r'(?<!\w)'
        right = '' if unspaced.match(word[-1]) else r'(?!\w)'
        patterns.append(left+expression+right)
    return re.compile('|'.join(patterns),re.IGNORECASE)

MOODS = {
  'alert':['attento','attenzione','dietro','scappa','aiuto','pericolo','nemico'],
  'excited':['incredibile','grandissimo','wow','fantastico','vittoria','goal','pazzesco'],
  'sad':['peccato','triste','mi dispiace','sconfitto','perso'],
  'question':['perché','come mai','cosa','dove','quando'],
}

def censor_text(text:str, words:list[str], mode='mask')->str:
    if not text or mode=='off':return text
    terms={_clean_term(word) for word in words if isinstance(word,str) and word.strip()}
    if not terms:return text
    pattern=_censor_pattern(tuple(sorted(terms,key=lambda word:(-len(word),word))))
    def sub(match):
        word=match.group()
        if mode=='remove':return '[censurato]'
        masked=word[0]+'*'*max(1,len(word)-2)+word[-1] if len(word)>1 else '*'
        if mode=='soft':
            return {'cazzo':'cavolo','merda':'accidenti','stronzo':'antipatico','stronza':'antipatica','vaffanculo':'lascia perdere'}.get(word.lower(),masked)
        return masked
    return pattern.sub(sub,unicodedata.normalize('NFC',text))

def mood_for(text:str)->str:
    s=text.lower()
    if any(x in s for x in MOODS['alert']):return 'alert'
    if any(x in s for x in MOODS['excited']):return 'excited'
    if any(x in s for x in MOODS['sad']):return 'sad'
    if '?' in text or any(x in s for x in MOODS['question']):return 'question'
    return 'normal'

def fast_process(raw:str, cfg:dict)->tuple[str,str]:
    txt=' '.join(raw.strip().split())
    if not txt:return '', 'normal'
    if cfg.get('improve',True):
        txt=txt[0].upper()+txt[1:]
        txt=re.sub(r'\s+([,.!?;:])',r'\1',txt)
        if not re.search(r'[.?!…]$',txt):txt+='.'
    mood=mood_for(txt) if cfg.get('animate',True) else 'normal'
    if cfg.get('censor',True):
        mode=cfg.get('censor_mode','mask')
        if mode!='off':txt=censor_text(txt,_effective_words(cfg),mode)
    return txt,mood

def safe_llm_revision(original:str, proposed:str)->bool:
    """Reject major rewrites; preserve most information from the ASR."""
    if not isinstance(proposed,str) or not proposed.strip():return False
    if len(proposed)>max(200,len(original)*1.4):return False
    orig_digits=re.findall(r'\d+',original)
    if orig_digits!=re.findall(r'\d+',proposed):return False
    def normalize(s):
        return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if c.isalnum() or c.isspace())
    return SequenceMatcher(None,normalize(original),normalize(proposed)).ratio()>=0.72
