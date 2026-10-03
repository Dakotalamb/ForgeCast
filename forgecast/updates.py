"""Public release notices. Never runs an installer or restarts OBS."""
import asyncio
import json
import re
import time
from urllib.parse import urljoin, urlparse
from . import __version__


def version_key(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-(preview|beta|rc)(?:\.(\d+))?)?', str(value))
    if not match:
        raise ValueError('Unsupported release version.')
    major, minor, patch, stage, build = match.groups()
    return (int(major), int(minor), int(patch), {'preview':0,'beta':1,'rc':2,None:3}[stage], int(build or 0))


def release_link(value, hub_url):
    if not isinstance(value, str) or len(value)>2048:
        raise ValueError('Invalid release link.')
    url = urljoin(hub_url.rstrip('/')+'/', value)
    parsed, hub = urlparse(url), urlparse(hub_url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Release links must use HTTPS.')
    if parsed.hostname != hub.hostname and not (parsed.hostname == 'github.com' and parsed.path.startswith('/Dakotalamb/ForgeCast/releases/')):
        raise ValueError('Release link is outside the Hub or official releases.')
    return url


class Updates:
    def __init__(self, state):
        self.state = state
        self.check_lock = asyncio.Lock()
        self.latest = None
        self.status = 'Pair your Hub to check for updates.'
        self.checked_at = None
        self.source = None
        self.last_check_ok = False

    def public(self):
        hub = self.state.config.get('hub_url', '')
        latest = self.latest if self.source == hub else None
        available = bool(latest and version_key(latest['version']) > version_key(__version__))
        dismissed = (latest or {}).get('version') == self.state.config.get('update_later_version')
        return dict(installed=__version__, latest=latest, available=available,
                    show_notice=available and not dismissed, status=self.status,
                    checked_at=self.checked_at, streaming=bool(self.state.stats.get('stream_active')))

    async def check(self):
        async with self.check_lock:
            hub = self.state.config.get('hub_url', '')
            if urlparse(hub).scheme != 'https':
                self.status = 'Pair an HTTPS Hub to check for updates.'
                return self.public()
            if self.source != hub:
                self.latest = None
            self.source = hub
            self.last_check_ok = False
            try:
                # Public metadata only: no pairing code or platform credentials.
                async with self.state.session.get(hub.rstrip('/')+'/fdgcast/releases/latest.json', allow_redirects=False) as response:
                    if response.status != 200:
                        raise ValueError('Release information is not available on your Hub yet.')
                    chunks, size = [], 0
                    while True:
                        chunk = await response.content.read(min(8192,65537-size))
                        if not chunk: break
                        chunks.append(chunk); size += len(chunk)
                        if size>65536: break
                    raw = b''.join(chunks)
                    if len(raw)>65536: raise ValueError('Release information is too large.')
                    data = json.loads(raw)
                if not isinstance(data, dict) or data.get('schema_version') != 1:
                    raise ValueError('Release information has an unsupported format.')
                version_key(data.get('version'))
                if data.get('platform') != 'windows-x64': raise ValueError('Release is not for Windows 64-bit.')
                notes = data.get('notes', '')
                if not isinstance(notes, str) or len(notes)>16000: raise ValueError('Invalid release notes.')
                self.latest = dict(version=data['version'], notes=notes,
                    download_url=release_link(data.get('download_url'), hub),
                    changes_url=release_link(data.get('changes_url'), hub) if data.get('changes_url') else '')
                self.last_check_ok = True
                self.checked_at = time.time()
                self.status = 'Update available.' if self.public()['available'] else 'You have the latest release.'
            except (asyncio.TimeoutError, OSError):
                self.status = 'Could not reach the Hub. Updates will check again automatically.'
            except (ValueError, TypeError, KeyError):
                self.status = 'Release information is unavailable. Check again later.'
            except Exception:
                self.status = 'Update check failed. Streaming can continue.'
            return self.public()

    def later(self):
        public = self.public()
        if public['available']:
            self.state.config['update_later_version'] = public['latest']['version']
            self.state.save()

    async def run(self):
        next_check, last_hub = 0, None
        while True:
            hub = self.state.config.get('hub_url', '')
            if hub and (hub != last_hub or time.monotonic() >= next_check):
                await self.check()
                next_check = time.monotonic() + (86400 if self.last_check_ok else 3600)
                last_hub = hub
            await asyncio.sleep(30)
