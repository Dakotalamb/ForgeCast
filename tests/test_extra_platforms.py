import asyncio
import tempfile
import unittest
from aiohttp.test_utils import TestClient, TestServer
from forgecast.server import State, create_app, resolve_destination, queue_outputs
from forgecast.platforms import CATALOG
from forgecast.extra_chat import Rumble, TikTok, rumble_api_url, rumble_messages, connect_extra
from forgecast.core import ChatStore
from forgecast.productivity import redact
from forgecast.operations import chat_capabilities

PRIVATE='https://rumble.com/-livestream-api/get-data?key=PRIVATE&user_id=123'
def payload():
    return {'livestreams':[{'id':'live1','is_live':True,'stream_key':'DO-NOT-EXPOSE', 'chat':{'recent_messages':[
        {'username':'Viewer','text':'Hello','created_on':'2026-10-11T20:00:00Z','badges':['premium']},
        None, {'username':'Other','text':123,'created_on':'x'}]}},
        {'id':'live2','is_live':True,'chat':{'recent_messages':[{'username':'Viewer','text':'Hello','created_on':'2026-10-11T20:00:00Z'}]}},
        {'id':'old','is_live':False,'chat':{'recent_messages':[{'username':'Old','text':'No','created_on':'x'}]}}]}

class PlatformTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.s=State(self.temp.name,demo=True)
    async def asyncTearDown(self): self.temp.cleanup()
    async def test_manual_destinations_require_server_and_preserve_identity(self):
        for platform in ('rumble','tiktok','x','instagram','linkedin','dlive','vimeo'):
            with self.assertRaises(ValueError): await resolve_destination(self.s,{'platform':platform})
            d=await resolve_destination(self.s,{'platform':platform,'server':'rtmps://ingest.example/live'})
            self.assertEqual(d['platform'],platform);self.assertEqual(d['name'],CATALOG[platform]['name'])
            self.s.config['destinations']=[d];self.s.vault.set('stream:'+d['id'],'KEY');self.s.native_seen=__import__('time').time()
            queue_outputs(self.s,'start_all');self.assertEqual(self.s.commands.pop()['destinations'][0]['platform'],platform)
    async def test_facebook_uses_standard_server_with_custom_override(self):
        d=await resolve_destination(self.s,{'platform':'facebook'})
        self.assertEqual(d['server'],'rtmps://rtmp-api.facebook.com:443/rtmp/')
        d=await resolve_destination(self.s,{'platform':'facebook','server':'rtmps://custom.example/live'})
        self.assertEqual(d['server'],'rtmps://custom.example/live');self.assertEqual(d['platform'],'facebook')
    async def test_picture_formats_default_validate_and_reach_native_command(self):
        from forgecast.server import preflight
        self.s.native_features={'portrait_v1'}
        for picture in ('main','vertical_fill','vertical_fit'):
            d=await resolve_destination(self.s,{'platform':'youtube','picture':picture})
            self.assertEqual(d['picture'],picture)
            self.s.config['destinations']=[d];self.s.vault.set('stream:'+d['id'],'KEY')
            self.s.native_seen=__import__('time').time()
            for command in ('start','start_all'):
                queue_outputs(self.s,command,d['id'])
                row=self.s.commands.pop()
                self.assertEqual((row['destination'] if command=='start' else row['destinations'][0])['picture'],picture)
            self.assertEqual(any(r['label'].endswith(' picture') for r in preflight(self.s)),picture!='main')
        self.assertEqual((await resolve_destination(self.s,{'platform':'youtube'}))['picture'],'main')
        for bad in ('vertical','squash','',None,False):
            with self.assertRaises(ValueError):await resolve_destination(self.s,{'platform':'youtube','picture':bad})
    async def test_older_native_module_cannot_silently_send_landscape_for_vertical(self):
        self.s.native_seen=__import__('time').time()
        d=await resolve_destination(self.s,{'platform':'youtube','picture':'vertical_fill'})
        self.s.config['destinations']=[d];self.s.vault.set('stream:'+d['id'],'KEY')
        for command in ('start','start_all'):
            with self.assertRaisesRegex(ValueError,'matching FDGCast update'):queue_outputs(self.s,command,d['id'])
        self.assertEqual(len(self.s.commands),0)
        queue_outputs(self.s,'stop',d['id'])
        self.assertEqual(self.s.commands.pop()['action'],'stop')
    async def test_rumble_private_url_host_and_redirect_validation(self):
        self.assertEqual(rumble_api_url(PRIVATE),PRIVATE)
        for url in ('http://rumble.com/-livestream-api/get-data?key=x',
                    'https://rumble.com.evil.test/-livestream-api/get-data?key=x',
                    'https://u:p@rumble.com/-livestream-api/get-data?key=x',
                    'https://rumble.com:444/-livestream-api/get-data?key=x',
                    'https://rumble.com/account/livestream-api', 'https://127.0.0.1/-livestream-api/get-data'):
            with self.assertRaises(ValueError):rumble_api_url(url)
    async def test_rumble_matching_dedup_and_secret_exclusion(self):
        rows,live=rumble_messages(payload());self.assertTrue(live);self.assertEqual(len(rows),2)
        for row in rows:self.s.chat.add(row)
        for row in rumble_messages(payload())[0]:self.assertFalse(self.s.chat.add(row))
        self.assertEqual(len(rumble_messages(payload(),'live1')[0]),1)
        self.assertFalse(rumble_messages(payload(),'missing')[1])
        self.s.vault.set('rumble_api_url',PRIVATE)
        self.assertNotIn('PRIVATE',str(self.s.public()));self.assertNotIn('DO-NOT-EXPOSE',str(self.s.public()))
        self.assertNotIn('PRIVATE',str(redact(self.s,{'details':PRIVATE,'copied_key':'PRIVATE'})))
        self.assertFalse(chat_capabilities(self.s)['rumble']['ban'])
    async def test_chunked_rumble_response_is_read_completely_without_redirects(self):
        import json
        body=json.dumps(payload()).encode()
        class Content:
            async def iter_chunked(self,n):
                for i in range(0,len(body),7):yield body[i:i+7]
        class Response:
            status=200
            content=Content()
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        class Session:
            def get(self,url,**kwargs):
                self.kwargs=kwargs
                return Response()
        session=Session();adapter=Rumble(session,{},PRIVATE,ChatStore(),lambda *x:None)
        self.assertEqual(await adapter.fetch(),payload());self.assertFalse(session.kwargs['allow_redirects'])
    async def test_rumble_reader_can_cancel_while_sleeping(self):
        store=ChatStore(); statuses=[];adapter=Rumble(None,{},PRIVATE,store,lambda *x:statuses.append(x))
        async def fetch():return payload()
        adapter.fetch=fetch;task=asyncio.create_task(adapter.run());await asyncio.sleep(.01)
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(len(store.messages),2);self.assertIn('receive-only',statuses[-1][1])
    async def test_failed_rumble_transport_never_displays_private_url(self):
        statuses=[];adapter=Rumble(None,{},PRIVATE,ChatStore(),lambda *x:statuses.append(x))
        async def fail():raise RuntimeError(PRIVATE)
        adapter.fetch=fail;task=asyncio.create_task(adapter.run());await asyncio.sleep(.01)
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.assertNotIn('PRIVATE',str(statuses));self.assertIn('retrying',statuses[-1][1])
    async def test_tiktok_actual_proto_fields_and_disconnect(self):
        from TikTokLive.events import CommentEvent, ConnectEvent
        from TikTokLive.proto.custom_proto import ExtendedUser
        from TikTokLiveProto.v3.webcast.shared.message import CommonMessageData
        class Client:
            def __init__(self,**kwargs):self.callbacks={};self.closed=False
            def add_listener(self,key,callback):self.callbacks[key]=callback
            async def start(self):
                event=CommentEvent(common=CommonMessageData(msg_id=123,room_id=456),content='hello',user=ExtendedUser(nickname='Viewer',display_id='viewer'))
                await self.callbacks[ConnectEvent](None)
                await self.callbacks[CommentEvent](event);await self.callbacks[CommentEvent](event)
                return asyncio.create_task(asyncio.sleep(100))
            async def disconnect(self,**kwargs):self.closed=True
        made=[]
        def factory(**kwargs):client=Client(**kwargs);made.append(client);return client
        store=ChatStore();adapter=TikTok({'username':'creator'},store,lambda *x:None,factory)
        task=asyncio.create_task(adapter.run());await asyncio.sleep(.1);task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(len(store.messages),1);self.assertEqual(store.messages[0]['text'],'hello')
        self.assertEqual(store.messages[0]['user_id'],'viewer');self.assertTrue(made[0].closed)
    async def test_experimental_opt_in_checked_before_connection(self):
        with self.assertRaises(ValueError):await connect_extra(self.s,{'platform':'tiktok','username':'name'})
        self.assertNotIn('tiktok',self.s.config)
    async def test_invalid_config_does_not_cancel_existing_reader(self):
        class Existing:
            task=None
        old=Existing();old.task=asyncio.create_task(asyncio.sleep(100));self.s.adapters['rumble']=old
        with self.assertRaises(ValueError):await connect_extra(self.s,{'platform':'rumble','api_url':'https://evil.test/x'})
        self.assertIs(self.s.adapters['rumble'],old);self.assertFalse(old.task.cancelled());old.task.cancel();await asyncio.gather(old.task,return_exceptions=True)

class EndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_credential_never_returns_and_forget_removes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            s=State(directory,demo=True);client=TestClient(TestServer(create_app(s)));await client.start_server()
            headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+s.browser_key}
            s.vault.set('rumble_api_url',PRIVATE);s.config['rumble']={'video_id':''}
            try:
                for endpoint in ('/api/state','/api/report','/api/backup'):
                    response=await client.get(endpoint,headers=headers);self.assertNotIn('PRIVATE',await response.text())
                s.demo=False
                response=await client.post('/api/action',headers=headers,json={'op':'chat_disconnect','platform':'rumble','forget':True})
                self.assertEqual(response.status,200);self.assertFalse(s.vault.get('rumble_api_url'));self.assertNotIn('rumble',s.config)
                response=await client.get('/api/state',headers=headers);self.assertIn('facebook',[p['id'] for p in (await response.json())['destination_platforms']])
            finally:
                s.demo=True;await client.close()
