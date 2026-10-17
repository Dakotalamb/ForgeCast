import asyncio
import copy
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from aiohttp import web, ClientSession
from aiohttp.test_utils import TestServer
from forgecast.server import State
from forgecast.meta_chat import MetaChat, relay_request
from forgecast.chat import ApiError
from forgecast.operations import chat_capabilities
from forgecast.overlay_studio import validate_design


def descriptor(p='facebook', account='page', generation='one', state='receiving_comments'):
    return dict(platform=p, account_id=account, generation=generation, state=state,
                username='My Page', enabled=True, configured=True)

def page(p='facebook', after='1', account='page', generation='one', state='receiving_comments'):
    return dict(schema_version=1, platform=p, connection=descriptor(p,account,generation,state),
        messages=[dict(cursor=after,platform=p,message_id='comment-'+after,account_id=account,
            broadcaster_id=account,generation=generation,broadcast_id='live',
            author={'id':None,'name':'Viewer'},text='<script>hello</script>',
            timestamp='2026-10-17T18:00:00.000Z')],next_cursor=after,retry_after_ms=5000)

class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=State(self.tmp.name,demo=True)
        self.s.config['hub_url']='https://hub.forgeddestinygaming.com';self.s.vault.set('hub_token','OWNER-ONE')
        self.m=self.s.meta_chat;self.m.discover([descriptor(),descriptor('instagram')])
    async def asyncTearDown(self): self.tmp.cleanup()
    def ingest(self,data=None,p='facebook'):
        return self.m.ingest(p,data or page(p),('page','one'))
    async def test_normalization_dedup_and_independent_cursors(self):
        self.ingest();self.assertEqual(self.m.readers['facebook']['after'],'1')
        self.assertEqual(self.m.readers['instagram']['after'],'0')
        row=self.s.chat.messages[0];self.assertEqual(row['text'],'<script>hello</script>')
        self.assertEqual(row['fragments'],[{'text':row['text']}]);self.assertEqual(row['user'],'Viewer')
        self.m.readers['facebook']['after']='0';self.ingest();self.assertEqual(len(self.s.chat.messages),1)
        self.ingest(page('instagram'), 'instagram');self.assertEqual(len(self.s.chat.messages),2)
        for p in ('facebook','instagram'): self.assertFalse(any(chat_capabilities(self.s)[p].values()))
    async def test_invalid_page_is_atomic_and_does_not_advance(self):
        for field,value in [('account_id','someone-else'),('generation','other'),('platform','instagram')]:
            bad=page();bad['messages'].append(copy.deepcopy(bad['messages'][0]));bad['messages'][1]['cursor']='2';bad['messages'][1][field]=value;bad['next_cursor']='2'
            with self.assertRaises(ValueError):self.ingest(bad)
            self.assertEqual(self.m.readers['facebook']['after'],'0');self.assertEqual(len(self.s.chat.messages),0)
        bad=page();bad['next_cursor']='999'
        with self.assertRaises(ValueError):self.ingest(bad)
    async def test_large_decimal_cursors_are_not_float(self):
        self.ingest(page(after='9007199254740993'));self.assertEqual(self.m.readers['facebook']['after'],'9007199254740993')
    async def test_generation_change_clears_messages_and_highlights(self):
        self.ingest();self.s.highlight_ids.append(self.s.chat.messages[0]['id'])
        self.assertFalse(self.ingest(page(generation='two')))
        self.assertEqual(len(self.s.chat.messages),0);self.assertEqual(len(self.s.highlight_ids),0)
        self.assertTrue(self.m.rediscover);self.assertNotIn('facebook',self.m.readers)
        self.m.discover([descriptor(generation='two')]);self.assertEqual(self.m.readers['facebook']['after'],'0')
    async def test_terminal_state_clears_only_that_platform(self):
        self.ingest();self.ingest(page('instagram'),'instagram')
        for state in ('disabled','authorization_needed','permission_denied','setup_required','disconnected'):
            self.m.describe('facebook',descriptor(state=state))
            self.assertEqual([m['platform'] for m in self.s.chat.messages],['instagram'])
    async def test_discovery_requires_enabled_and_configured(self):
        self.ingest();d=descriptor();d.pop('enabled');self.m.discover([d])
        self.assertEqual(self.m.readers['facebook']['state'],'setup_required');self.assertEqual(len(self.s.chat.messages),0)
    async def test_stale_inflight_reply_after_pairing_switch_is_ignored(self):
        ready,release=asyncio.Event(),asyncio.Event()
        async def request(*a,**kw):ready.set();await release.wait();return page()
        with patch('forgecast.meta_chat.relay_request',request):
            task=asyncio.create_task(self.m.poll('facebook'));await ready.wait()
            self.s.vault.set('hub_token','OWNER-TWO');self.m.reset();self.m.discover([descriptor()]);release.set();await task
        self.assertEqual(len(self.s.chat.messages),0)
    async def test_401_clears_both_and_stops_until_repair(self):
        self.ingest();self.ingest(page('instagram'),'instagram')
        with patch('forgecast.meta_chat.relay_request',AsyncMock(side_effect=ApiError('secret',401))):await self.m.poll('facebook')
        self.assertTrue(self.m.unauthorized);self.assertEqual(len(self.s.chat.messages),0)
        self.m.discover([descriptor()]);self.assertTrue(self.m.unauthorized)
        self.assertNotIn('secret',str(self.s.statuses))
    async def test_retry_does_not_clear_other_reader_or_cursor(self):
        self.ingest();self.ingest(page('instagram'),'instagram')
        with patch('forgecast.meta_chat.relay_request',AsyncMock(side_effect=ConnectionError('SECRET-URL'))):await self.m.poll('facebook')
        self.assertEqual(len(self.s.chat.messages),2);self.assertEqual(self.m.readers['facebook']['after'],'1')
        self.assertNotIn('SECRET-URL',str(self.s.statuses));self.assertGreater(self.m.readers['facebook']['due'],0)
    async def test_full_pages_drain_and_delay_is_bounded(self):
        d=page();d['messages']=[{**d['messages'][0],'cursor':str(i),'message_id':str(i)} for i in range(1,101)];d['next_cursor']='100'
        self.ingest(d);self.assertEqual(len(self.s.chat.messages),100)
    async def test_overlay_accepts_meta_but_does_not_unlock_access(self):
        d=validate_design({'name':'Meta','layers':[{'id':'a','type':'chat','platforms':['facebook','instagram']}]})
        self.assertEqual(d['layers'][0]['platforms'],['facebook','instagram'])
        self.ingest();from forgecast.entitlements import overlay_access
        self.assertFalse(overlay_access(self.s))

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_headers_cursor_redirect_refusal_and_response_bound(self):
        async def handler(req):
            self.assertEqual(req.headers.get('Authorization'),'Bearer SECRET')
            self.assertNotIn('SECRET',str(req.rel_url));self.assertEqual(req.query.get('after'),'9007199254740993')
            if req.path=='/redirect':raise web.HTTPFound('/target')
            if req.path=='/big':return web.Response(body=b'x'*2000001)
            return web.json_response({'ok':True})
        app=web.Application();app.router.add_get('/{path}',handler)
        async with TestServer(app) as server,ClientSession() as session:
            kwargs=dict(headers={'Authorization':'Bearer SECRET'},params={'after':'9007199254740993'})
            self.assertEqual(await relay_request(session,str(server.make_url('/ok')),**kwargs),{'ok':True})
            with self.assertRaises(ApiError):await relay_request(session,str(server.make_url('/redirect')),**kwargs)
            with self.assertRaises(ValueError):await relay_request(session,str(server.make_url('/big')),**kwargs)
