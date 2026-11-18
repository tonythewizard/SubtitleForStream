import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from app.updates import NoPublicRelease, find_update, stage_installer


def test_update_requires_new_stable_version_and_verified_asset():
    payload=b'test installer fixture'
    repo='owner/SubtitleForStream'
    tag='v0.2.1'
    name='SubtitleForStream-Setup-0.2.1-x64.exe'
    url=f'https://github.com/{repo}/releases/download/{tag}/{name}'
    manifest={'tag_name':tag,'prerelease':False,'draft':False,'assets':[
        {'name':name,'browser_download_url':url,'state':'uploaded',
         'digest':'sha256:'+hashlib.sha256(payload).hexdigest(),'size':len(payload)}
    ]}

    def route(request):
        if request.url.host=='api.github.com':
            return httpx.Response(200,json=manifest)
        assert str(request.url)==url
        return httpx.Response(200,content=payload)

    with httpx.Client(transport=httpx.MockTransport(route)) as client, TemporaryDirectory() as temp:
        assert find_update(repo,'0.2.1',client) is None
        assert find_update(repo,'0.3.0',client) is None
        release=find_update(repo,'0.2.0',client)
        assert release.asset_url==url
        assert stage_installer(release,temp,client).read_bytes()==payload

        manifest['assets'][0]['digest']='sha256:'+'0'*64
        corrupt=find_update(repo,'0.2.0',client)
        try:
            stage_installer(corrupt,temp,client)
        except ValueError:
            pass
        else:
            assert False, 'Installer with the wrong hash was accepted'
        assert (Path(temp)/name).read_bytes()==payload
        assert not list(Path(temp).glob('*.part'))

        manifest['assets'][0]['digest']=None
        assert not find_update(repo,'0.2.0',client).asset_url
        manifest['prerelease']=True
        assert find_update(repo,'0.2.0',client) is None


def test_no_public_release_is_not_reported_as_up_to_date():
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(404))) as client:
        try:
            find_update('owner/SubtitleForStream','0.2.0',client)
        except NoPublicRelease:
            return
    assert False, 'A 404 should report no public release'
