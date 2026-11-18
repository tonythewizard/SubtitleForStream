"""Check stable GitHub releases and stage verified Windows installers."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

import httpx

from .theme import asset_path


_REPO = re.compile(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+')
_VERSION = re.compile(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')
_DIGEST = re.compile(r'sha256:([a-fA-F0-9]{64})')
_MAX_BYTES = 2 * 1024**3


class NoPublicRelease(ValueError):
    """The repository or its latest stable release is not publicly available."""


def normalize_repository(value):
    repo = value.strip().removeprefix('https://github.com/').rstrip('/')
    if not _REPO.fullmatch(repo) or repo.split('/')[1] in ('.','..'):
        raise ValueError('Expected a public GitHub repository in owner/repo format.')
    return repo


def default_repository():
    for line in asset_path('UPDATE_REPOSITORY').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            return normalize_repository(line)
    return ''


def installed_version():
    return asset_path('VERSION').read_text(encoding='utf-8').strip()


def version_number(tag):
    match = _VERSION.fullmatch(tag) if isinstance(tag,str) else None
    if not match:
        raise ValueError(f'Unsupported release version: {tag}')
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class Release:
    repository: str
    tag: str
    version: str
    page: str
    asset_name: str = ''
    asset_url: str = ''
    sha256: str = ''
    size: int = 0


def find_update(repository,current,client):
    repository = normalize_repository(repository)
    response = client.get(
        f'https://api.github.com/repos/{repository}/releases/latest',
        headers={'Accept':'application/vnd.github+json','User-Agent':'SubtitleForStream'})
    if response.status_code==404:
        raise NoPublicRelease(repository)
    response.raise_for_status()
    release = response.json()
    if not isinstance(release,dict):
        raise ValueError('Invalid GitHub release response.')
    if release.get('draft') or release.get('prerelease'):
        return None
    tag = release.get('tag_name','')
    if version_number(tag) <= version_number(current):
        return None
    version = tag.removeprefix('v')
    page = f'https://github.com/{repository}/releases/tag/{tag}'
    name = f'SubtitleForStream-Setup-{version}-x64.exe'
    url = f'https://github.com/{repository}/releases/download/{tag}/{name}'
    assets = release.get('assets')
    for asset in assets if isinstance(assets,list) else ():
        if not isinstance(asset,dict) or asset.get('name')!=name:
            continue
        if str(asset.get('browser_download_url','')).casefold()!=url.casefold():
            continue
        digest = _DIGEST.fullmatch(str(asset.get('digest') or ''))
        size = asset.get('size')
        if digest and type(size) is int and 0<size<=_MAX_BYTES and asset.get('state')=='uploaded':
            return Release(repository,tag,version,page,name,url,digest[1].lower(),size)
    return Release(repository,tag,version,page)


def stage_installer(release,directory,client):
    if not release.asset_url or not release.sha256:
        raise ValueError('This release has no verified Windows installer.')
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    target = directory / release.asset_name
    if target.is_file() and target.stat().st_size==release.size:
        with target.open('rb') as file:
            if hashlib.file_digest(file,'sha256').hexdigest()==release.sha256:
                return target
    partial = None
    try:
        digest = hashlib.sha256()
        size = 0
        with NamedTemporaryFile(dir=directory,suffix='.part',delete=False) as output:
            partial = Path(output.name)
            with client.stream('GET',release.asset_url,follow_redirects=True) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size>release.size:
                        raise ValueError('Installer size exceeds the GitHub release asset size.')
                    digest.update(chunk)
                    output.write(chunk)
        if size!=release.size or digest.hexdigest()!=release.sha256:
            raise ValueError('Installer hash or size does not match the GitHub release.')
        os.replace(partial,target)
        return target
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
