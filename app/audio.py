"""Microphone and Windows per-process (Discord/game) audio capture.

A separate worker per source avoids mixing people's words. Windows per-process capture
uses ProcTap's WASAPI PROCESS_LOOPBACK support. No virtual audio driver needed.
"""
from __future__ import annotations
from threading import Thread, Event
from queue import Queue, Empty, Full
from collections import deque
import time
import numpy as np
from scipy.signal import resample_poly

RATE=16000
CAPTURE_RATE=48000


class LiveClipQueue(Queue):
    def put_clip(self, clip):
        source = clip[0]
        with self.not_full:
            # Drop superseded previews for this source, preserving finalized audio.
            for index in range(len(self.queue)-1, -1, -1):
                pending = self.queue[index][0]
                if pending['id']==source['id'] and pending.get('_partial'):
                    del self.queue[index]
                    self.unfinished_tasks -= 1
            if len(self.queue)>=self.maxsize:
                preview = next((i for i,item in enumerate(self.queue) if item[0].get('_partial')), None)
                if preview is None and source.get('_partial'):
                    return
                del self.queue[0 if preview is None else preview]
                self.unfinished_tasks -= 1
            if source.get('_partial'):
                self.queue.append(clip)
            else:
                index = next((i for i,item in enumerate(self.queue) if item[0].get('_partial')), len(self.queue))
                self.queue.insert(index,clip)
            self.unfinished_tasks += 1
            self.not_empty.notify()


def get_process_pid(executable:str)->int|None:
    import psutil
    choices=[]
    name=executable.lower()
    for p in psutil.process_iter(['pid','name','ppid']):
        try:
            if (p.info.get('name') or '').lower()==name:
                choices.append(p)
        except (psutil.Error,OSError):continue
    if not choices:return None
    candidate_pids={p.pid for p in choices}
    # Electron apps (like Discord) spawn renderer processes. Prefer the root.
    roots=[p for p in choices if p.info.get('ppid') not in candidate_pids]
    return (roots[0] if roots else choices[0]).pid


def microphone_devices()->list[tuple[int,str]]:
    try:
        import sounddevice as sd
        return [(i,f'{v["name"]} [{i}]') for i,v in enumerate(sd.query_devices()) if v['max_input_channels']>0]
    except Exception:return []


def default_microphone_device():
    try:
        import sounddevice as sd
        index=int(sd.default.device[0])
        return index if index>=0 else None
    except (ImportError, OSError, ValueError, TypeError, IndexError):
        return None

class SourceCapture(Thread):
    def __init__(self,source,output_queue:Queue,stop:Event,error_callback,threshold_db=-34,low_latency=True):
        super().__init__(daemon=True,name='capture-'+source['id'])
        self.source=source.copy();self.output_queue=output_queue;self.stop_event=stop
        self.error_callback=error_callback;self.threshold_db=threshold_db;self.low_latency=low_latency
        self.audio_q=Queue(maxsize=150)
        self.level_sample=(0.0,0.0)

    def _emit(self,pcm:bytes):
        if not self.stop_event.is_set():
            try:self.audio_q.put_nowait(pcm)
            except Full:
                try:self.audio_q.get_nowait();self.audio_q.put_nowait(pcm)
                except (Empty,Full):pass

    def run(self):
        try:
            if self.source['kind']=='mic':self._capture_mic()
            else:self._capture_process()
        except Exception as ex:
            if not self.stop_event.is_set(): self.error_callback(f'{self.source["name"]}: {ex}')

    def _capture_mic(self):
        import sounddevice as sd
        def callback(indata,frames,time_info,status):
            if not self.stop_event.is_set():self._emit(indata.copy().tobytes())
        device=self.source.get('device',None)
        if device=='':device=None
        rates=[CAPTURE_RATE,44100]
        try:
            default_rate=int(sd.query_devices(device, 'input')['default_samplerate'])
            if default_rate not in rates:rates.append(default_rate)
        except Exception:pass
        last_error=None
        for rate in rates:
            try:
                sd.check_input_settings(device=device,channels=1,samplerate=rate,dtype='float32')
                break
            except Exception as ex:last_error=ex
        else:raise RuntimeError(f'Nessun formato microfono compatibile: {last_error}')
        with sd.InputStream(device=device,channels=1,samplerate=rate,dtype='float32',
                            blocksize=int(rate*(.02 if self.low_latency else .05)),callback=callback):
            self._buffer_loop(channels=1,capture_rate=rate)

    def _capture_process(self):
        # proc-tap 1.1 exposes ProcessAudioCapture (the old ProcTap API was
        # removed). It already returns 48 kHz stereo float32 PCM.
        from proctap import ProcessAudioCapture
        # Wait for Discord or the requested app to open; reconnect when restarted.
        while not self.stop_event.is_set():
            pid=get_process_pid(self.source.get('process','Discord.exe'))
            if not pid:
                self.stop_event.wait(1.5);continue
            tap=None
            try:
                def on_data(pcm:bytes,frames:int):self._emit(pcm)
                tap=ProcessAudioCapture(pid,on_data=on_data,resample_quality='fast')
                tap.start()
                self._buffer_loop(channels=2,process_pid=pid)
            except Exception as ex:
                if not self.stop_event.is_set():self.error_callback(f'{self.source["name"]}: {ex}')
            finally:
                if tap:
                    try:tap.close()
                    except Exception:pass
            self.stop_event.wait(2)

    def _buffer_loop(self,channels:int,process_pid:int|None=None,capture_rate:int=CAPTURE_RATE):
        # Lower end-of-speech delay; preserve a short pre-roll so the first phoneme is not lost.
        active=[];total=0;silence=0;last_check=time.monotonic()
        preroll=deque();preroll_samples=0
        end_silence_ms=300 if self.low_latency else 520
        max_seconds=3.2 if self.low_latency else 3.8
        min_clip_ms=200 if self.low_latency else 400
        update_samples=int(RATE*.5)
        last_update=0
        window_id=time.monotonic()
        overlap=False
        preroll_size=int(RATE*.14)
        while not self.stop_event.is_set():
            if process_pid and time.monotonic()-last_check>3:
                last_check=time.monotonic()
                if get_process_pid(self.source.get('process','Discord.exe'))!=process_pid:break
            try:pcm=self.audio_q.get(timeout=.2)
            except Empty:continue
            data=np.frombuffer(pcm,dtype=np.float32)
            if not len(data) or len(data)%channels:continue
            if channels>1:data=data.reshape(-1,channels).mean(axis=1)
            audio=resample_poly(data,RATE,capture_rate).astype(np.float32,copy=False)
            if not len(audio):continue
            rms=float(np.sqrt(np.mean(audio*audio)))
            db=20*np.log10(max(rms,1e-7))
            voiced=db>=self.threshold_db
            level=max(0.0,min(1.0,(db-self.threshold_db+6)/30))
            self.level_sample=(time.monotonic(),level)
            if not active:
                if not voiced:
                    preroll.append(audio.copy());preroll_samples+=len(audio)
                    while preroll and preroll_samples-len(preroll[0])>=preroll_size:
                        preroll_samples-=len(preroll.popleft())
                    continue
                if preroll:
                    active=list(preroll);total=sum(len(x) for x in active)
                    preroll.clear();preroll_samples=0
            active.append(audio.copy());total+=len(audio)
            silence=0 if voiced else silence+len(audio)
            final = silence>=RATE*end_silence_ms/1000 or total>=RATE*max_seconds
            partial = self.low_latency and voiced and total-last_update>=update_samples
            if total>=RATE*min_clip_ms/1000 and (final or partial):
                clip=np.concatenate(active)
                if final and silence>=RATE*(.1 if self.low_latency else .2):
                    tail_seconds = .06 if self.low_latency else .1
                    clip=clip[:max(1,len(clip)-silence+int(RATE*tail_seconds))]
                if len(clip)>=RATE*min_clip_ms/1000:
                    # Capture timestamp lets ASR drop stale subtitles instead of lagging.
                    source=dict(self.source,_window=window_id,_partial=not final,_overlap=overlap)
                    item=(source,clip,time.monotonic())
                    try:
                        if isinstance(self.output_queue,LiveClipQueue):
                            self.output_queue.put_clip(item)
                        else:
                            self.output_queue.put_nowait(item)
                    except Full:
                        # Prefer recent utterances to minutes-old queue entries.
                        try:
                            self.output_queue.get_nowait()
                            self.output_queue.put_nowait(item)
                            self.error_callback('Coda ASR piena: audio più vecchio scartato.')
                        except (Empty,Full):pass
                last_update=total
                if final:
                    active=[];total=0;silence=0;last_update=0
                    window_id=time.monotonic()
                    overlap=self.low_latency and voiced and len(clip)>=RATE*max_seconds
                    if overlap:
                        context=clip[-int(RATE*.35):].copy()
                        active=[context]
                        total=last_update=len(context)

class CaptureManager:
    def __init__(self,settings,clip_queue,error_callback):
        self.settings=settings;self.clip_queue=clip_queue;self.error_callback=error_callback
        self.workers=[];self.stop_event=None

    def input_level(self):
        cutoff=time.monotonic()-.25
        samples=[worker.level_sample for worker in self.workers]
        return max((level for timestamp,level in samples if timestamp>=cutoff),default=0.0)

    def start(self):
        self.stop()
        self.stop_event=Event()
        for src in self.settings.get('sources',[]):
            if src.get('enabled'):
                w=SourceCapture(src,self.clip_queue,self.stop_event,self.error_callback,self.settings.get('silence_db',-34),self.settings.get('low_latency',True))
                self.workers.append(w);w.start()
    def stop(self):
        if self.stop_event:self.stop_event.set()
        # Do not block the GUI for long; workers are daemon threads.
        for w in self.workers:w.join(timeout=.6)
        self.workers=[];self.stop_event=None
