import json
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from app.settings import Settings
from app.smarttext import censor_text,fast_process,mood_for,safe_llm_revision
from app.state import CaptionState
from app.overlay import OverlayServer


def test_censorship():
    assert censor_text('Ma che CAZZO fai?', ['cazzo'])=='Ma che C***O fai?'
    assert censor_text('È una cazzolata, cazzo!',['cazzo'])=='È una cazzolata, c***o!'
    assert censor_text('cazzo',['cazzo'],'soft')=='cavolo'
    assert censor_text('cazzo',['cazzo'],'remove')=='[censurato]'

def test_no_sensitive_text_in_fast_output():
    with TemporaryDirectory() as tmp:
        cfg=Settings(Path(tmp)/'test.json').snapshot()
        txt,mood=fast_process('raga cazzo attento dietro',cfg)
        assert 'cazzo' not in txt.lower() and 'c***o' in txt.lower()
        assert mood=='alert'


def test_censor_language_presets_and_shared_names():
    for language,term in [('it','porco Dio'),('en','fucking'),('es','gilipollas'),('fr','putain'),('de','scheiße')]:
        cfg={'language':language,'censor_mode':'remove','improve':False}
        text,_=fast_process(f'{term}, ALLAH e 上帝啊',cfg)
        assert text=='[censurato], [censurato] e [censurato]啊'
    assert fast_process('godfather e Madonna',{'language':'it','improve':False})[0]=='godfather e M*****a'


def test_censor_preset_exceptions_and_custom_entries():
    cfg={'language':'it','censor_mode':'remove','improve':False,
         'banned_words':['cazzo','gergo'], 'censor_exceptions':[' CAZZO ','DIO','gergo']}
    assert fast_process('cazzo e Dio, gergo',cfg)[0]=='cazzo e Dio, [censurato]'
    assert fast_process('porco, Dio',cfg)[0]=='[censurato]'
    cfg['censor_exceptions'].append('porco dio')
    assert fast_process('porco Dio',cfg)[0]=='porco Dio'


def test_whisper_download_only_for_missing_or_damaged_assets():
    from queue import Queue
    from unittest.mock import patch

    from app.engine import ASRWorker

    with TemporaryDirectory() as tmp:
        folder=Path(tmp)
        binary=folder/'model.bin'
        config=folder/'config.json'
        tokenizer=folder/'tokenizer.json'
        binary.write_bytes(b'mock model')
        config.write_text('{}',encoding='utf-8')
        tokenizer.write_text('{}',encoding='utf-8')
        events=[]
        worker=ASRWorker(Settings(folder/'prefs.json'),Queue(),None,lambda _:None,
                         on_state=lambda _,stage:events.append(stage))
        with patch('app.engine.BUNDLED_MODELS',folder/'bundled'), \
             patch('faster_whisper.utils.download_model',return_value=tmp) as lookup, \
             patch('huggingface_hub.snapshot_download') as download:
            assert worker._whisper_model_path('medium')==tmp
            assert lookup.call_count==1 and lookup.call_args.kwargs['local_files_only']
            download.assert_not_called()
            assert events==[]

            tokenizer.unlink()
            def restore_missing(*args,**kwargs):
                if not kwargs.get('local_files_only'):
                    tokenizer.write_text('{}',encoding='utf-8')
                return tmp
            lookup.reset_mock(side_effect=True)
            lookup.side_effect=restore_missing
            assert worker._whisper_model_path('medium')==tmp
            assert lookup.call_count==2 and events==['downloading','loading']
            download.assert_not_called()

            config.write_text('{broken',encoding='utf-8')
            def repair(**kwargs):
                assert kwargs['allow_patterns']==['config.json'] and kwargs['force_download']
                config.write_text('{}',encoding='utf-8')
                return tmp
            download.side_effect=repair
            assert worker._whisper_model_path('medium')==tmp
            assert events[-2:]==['repairing','loading']

        assert worker._binary_corrupt(RuntimeError('File model.bin is incomplete: failed to read'))
        assert not worker._binary_corrupt(RuntimeError('CUDA out of memory'))


def test_whisper_reports_cpu_baseline_and_cuda_fallback():
    from queue import Queue
    from unittest.mock import patch

    from app.engine import ASRWorker

    with TemporaryDirectory() as tmp:
        settings=Settings(Path(tmp)/'prefs.json')
        events=[]
        def ready(worker,stage):
            if stage=='ready':
                events.append((worker.selected_device,worker.active_device,worker.active_model))
                worker.stop()
        worker=ASRWorker(settings,Queue(),None,lambda _:None,on_state=ready)
        with patch.object(worker,'_whisper_model_path',return_value=tmp), \
             patch('faster_whisper.WhisperModel') as model:
            worker._run()
        assert events==[('auto','cpu','tiny')]
        assert model.call_args.kwargs['device']=='cpu'

        worker=ASRWorker(settings,Queue(),None,lambda _:None)
        with patch('app.engine._load_cuda_dll_paths'), \
             patch('faster_whisper.WhisperModel',side_effect=[RuntimeError('CUDA unavailable'),object()]) as model:
            worker._load_whisper_model('tiny','cuda:0',tmp)
        assert worker.active_device=='cpu'
        assert [call.kwargs['device'] for call in model.call_args_list]==['cuda','cpu']

def test_llm_is_conservative():
    assert safe_llm_revision('Ciao a tutti come state','Ciao a tutti, come state?')
    assert not safe_llm_revision('100 punti','200 punti')
    assert not safe_llm_revision('Ciao ragazzi','Abbiamo vinto il campionato mondiale')

def test_overlay_loopback_http():
    with TemporaryDirectory() as tmp:
        conf=Settings(Path(tmp)/'test.json')
        state=CaptionState(conf)
        server=OverlayServer(state,0)
        port=server.httpd.server_address[1]
        server.start()
        try:
            source=conf.get('sources')[0]
            cid=state.publish(source,'Ciao mondo!','normal')
            body=urllib.request.urlopen(f'http://127.0.0.1:{port}/state',timeout=3).read()
            data=json.loads(body)
            assert data['captions'][0]['id']==cid
            assert data['captions'][0]['text']=='Ciao mondo!'
            html=urllib.request.urlopen(f'http://127.0.0.1:{port}/overlay',timeout=3).read()
            assert b'wrap' in html and b'caption' in html
            assert server.httpd.server_address[0]=='127.0.0.1'
        finally:server.stop()


def test_config_and_ttl():
    import time
    with TemporaryDirectory() as tmp:
        f=Path(tmp)/'settings.json'
        cfg=Settings(f)
        cfg.set('duration',0.03)
        cfg.set('font_size',72)
        assert Settings(f).get('font_size')==72
        state=CaptionState(cfg)
        state.publish(cfg.get('sources')[0],'Temporaneo')
        assert len(state.snapshot()['captions'])==1
        time.sleep(0.04)
        assert state.snapshot()['captions']==[]


def test_amara_credits_do_not_reach_overlay():
    from app.hallucinations import clean_asr_text
    credits=[
        'Sottotitoli creati dalla comunità Amara.org',
        'Sottotitoli a cura di amra.org.',
        'Sottotitoli di Amara.org. ',
        'Amara.org.',
        'Subtitles by Amara.org',
        'Sottotitoli a cura di QTSS',
    ]
    for phrase in credits:
        assert not clean_asr_text(phrase), phrase
    assert clean_asr_text('Ciao ragazzi. Sottotitoli creati dalla comunità Amara.org') == 'Ciao ragazzi.'
    assert clean_asr_text('Ciao, oggi visitiamo il sito Amara.org') == 'Ciao, oggi visitiamo il sito Amara.org'
    assert clean_asr_text('Non avevo capito. Andiamo!') == 'Non avevo capito. Andiamo!'
    assert clean_asr_text('Grazie per la visione!') == 'Grazie per la visione!'


def test_weak_silence_segment_rejected_but_speech_preserved():
    from types import SimpleNamespace
    from app.hallucinations import accept_segment
    assert not accept_segment(SimpleNamespace(avg_logprob=-1.3,no_speech_prob=0.96))
    assert accept_segment(SimpleNamespace(avg_logprob=-0.10,no_speech_prob=0.96))
    assert accept_segment(SimpleNamespace(avg_logprob=-1.3,no_speech_prob=0.04))


def test_decoding_sanitizes_segments_with_fake_whisper():
    from types import SimpleNamespace
    from app.engine import ASRWorker
    from queue import Queue
    class MockWhisper:
        def transcribe(self,*args,**kwargs):
            self.kwargs=kwargs
            return iter([
                SimpleNamespace(text=' Ciao ragazzi! ',no_speech_prob=0.05,avg_logprob=-0.2),
                SimpleNamespace(text=' Sottotitoli creati dalla comunità Amara.org',no_speech_prob=0.1,avg_logprob=-0.2),
                SimpleNamespace(text=' No, dietro! ',no_speech_prob=0.03,avg_logprob=-0.1),
            ]), None
    with TemporaryDirectory() as tmp:
        settings=Settings(Path(tmp)/'test.json')
        worker=ASRWorker(settings,Queue(),CaptionState(settings),lambda _:None)
        model=MockWhisper()
        text,_=worker._decode(model,[0,0,0],settings.snapshot())
        assert text=='Ciao ragazzi! No, dietro!'
        assert model.kwargs['language'] is None
        assert model.kwargs['task']=='transcribe'
        assert model.kwargs['vad_filter'] is True
        assert model.kwargs['beam_size']==1


def test_worker_discards_old_clips_before_inference():
    import time
    from unittest.mock import patch
    from queue import Queue
    from app.engine import ASRWorker
    class FakeModel:
        def __init__(self):self.calls=0
        def transcribe(self,*args,**kwargs):
            self.calls+=1
            return iter([]),None
    with TemporaryDirectory() as tmp:
        settings=Settings(Path(tmp)/'test.json')
        settings.set('max_caption_age',1.0)
        q=Queue()
        q.put((settings.get('sources')[0],[0]*100,time.monotonic()-10))
        events=[]
        worker=ASRWorker(settings,q,CaptionState(settings),events.append)
        fake=FakeModel()
        with patch.object(worker,'_create_model',return_value=fake):
            worker.start()
            time.sleep(0.2)
            worker.stop();worker.join(timeout=1)
        assert fake.calls==0
        assert any('scartato' in line for line in events)
