from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
import time
import uuid

class CaptionState:
    def __init__(self,settings):
        self.settings=settings
        self.lock=RLock()
        self.entries={}
    def publish(self,source,text,mood='normal'):
        cid=uuid.uuid4().hex
        with self.lock:
            self.entries[source['id']]={'id':cid,'source':source['id'],'label':source['name'],
                'color':source.get('color','#FFFFFF'),'text':text,'mood':mood,'updated':time.monotonic(),
                'expires':time.monotonic()+float(self.settings.get('duration',5.0))}
        return cid
    def revise(self,source_id,cid,text,mood):
        with self.lock:
            e=self.entries.get(source_id)
            if e and e['id']==cid and e['expires']>time.monotonic():
                e['text']=text;e['mood']=mood
                return True
        return False
    def clear(self):
        with self.lock:self.entries.clear()
    def snapshot(self):
        now=time.monotonic()
        with self.lock:
            expired=[k for k,v in self.entries.items() if v['expires']<=now]
            for k in expired:del self.entries[k]
            captions=sorted((v.copy() for v in self.entries.values()),key=lambda v:v['updated'])
        names={source['id']:source['name'] for source in self.settings.get('sources',[])}
        for caption in captions:
            caption['label']=names.get(caption['source'],caption['label'])
        return {'captions':captions,'style':{k:self.settings.get(k) for k in
            ['preset','font','font_size','text_color','background','bg_opacity','outline','bottom','max_lines','animate']}}
