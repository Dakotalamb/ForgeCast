import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from forgecast.server import State
from forgecast.updates import version_key, release_link


class Content:
    def __init__(self, body): self.body=body
    async def read(self, size):
        chunk,self.body=self.body[:size],self.body[size:]
        return chunk


class Reply:
    def __init__(self, body, status=200):self.content=Content(body);self.status=status
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass


class Session:
    def __init__(self, body):self.body=body;self.calls=[]
    def get(self, *args, **kwargs):self.calls.append((args,kwargs));return Reply(self.body)


class UpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.s=State(self.temp.name,demo=True)
        self.s.config['hub_url']='https://hub.example'
    async def asyncTearDown(self):self.temp.cleanup()
    async def test_version_numeric_and_prerelease_order(self):
        self.assertGreater(version_key('0.10.0-preview'),version_key('0.9.9'))
        self.assertGreater(version_key('0.6.0'),version_key('0.6.0-preview'))
        with self.assertRaises(ValueError):version_key('latest')
    async def test_links_require_trusted_https(self):
        for url in ['http://hub.example/setup.exe','https://evil.example/setup.exe','javascript:alert(1)','https://user:pass@hub.example/setup.exe']:
            with self.assertRaises(ValueError):release_link(url,'https://hub.example')
        self.assertEqual(release_link('/downloads/setup.exe','https://hub.example'),'https://hub.example/downloads/setup.exe')
    async def test_check_is_public_and_dismissal_survives_restart(self):
        self.s.session=Session(b'{"schema_version":1,"version":"0.7.0-preview","platform":"windows-x64","notes":"New release","download_url":"/downloads/setup.exe"}')
        self.s.vault.set('hub_token','PRIVATE')
        result=await self.s.updates.check()
        self.assertTrue(result['show_notice'])
        self.assertNotIn('PRIVATE',str(self.s.session.calls))
        self.assertFalse(self.s.session.calls[0][1]['allow_redirects'])
        self.s.updates.later()
        self.assertFalse(self.s.updates.public()['show_notice'])
        restored=State(self.temp.name,demo=True)
        self.assertEqual(restored.config['update_later_version'],'0.7.0-preview')
    async def test_malformed_and_oversized_feed_is_nonfatal(self):
        for body in [b'not json',b'{}',b'x'*65537]:
            self.s.session=Session(body)
            result=await self.s.updates.check()
            self.assertFalse(result['available'])
            self.assertIn('unavailable',result['status'])
    async def test_switching_hub_hides_old_release(self):
        self.s.session=Session(b'{"schema_version":1,"version":"0.7.0-preview","platform":"windows-x64","download_url":"/downloads/setup.exe"}')
        await self.s.updates.check()
        self.s.config['hub_url']='https://different.example'
        self.assertFalse(self.s.updates.public()['available'])
