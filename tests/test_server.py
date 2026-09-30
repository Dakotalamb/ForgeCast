import tempfile
import unittest
import time
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
from forgecast.server import State, create_app


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=State(self.temp.name,demo=True)
        self.client=TestClient(TestServer(create_app(self.state)))
        await self.client.start_server()
        self.headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+self.state.browser_key}

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_state_auth(self):
        r=await self.client.get('/api/state',headers={'Host':'127.0.0.1:17654'})
        self.assertEqual(r.status,401)

    async def test_untrusted_host(self):
        r=await self.client.get('/api/state',headers={**self.headers,'Host':'evil.example'})
        self.assertEqual(r.status,403)

    async def test_untrusted_origin(self):
        r=await self.client.get('/api/state',headers={**self.headers,'Origin':'https://evil.example'})
        self.assertEqual(r.status,403)

    async def test_private_token_not_in_state(self):
        self.state.vault.set('obs_password','DO-NOT-LEAK')
        r=await self.client.get('/api/state',headers=self.headers)
        text=await r.text()
        self.assertNotIn('DO-NOT-LEAK',text)
        self.assertNotIn(self.state.browser_key,text)
        self.assertNotIn(self.state.native_key,text)

    async def test_demo_blocks_action(self):
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'obs_command','command':'StartStream','confirmed':True})
        self.assertEqual(r.status,400)

    async def test_native_separate_auth(self):
        r=await self.client.post('/native/poll',headers=self.headers,json={})
        self.assertEqual(r.status,401)

    async def test_native_docks_show_chat_origin_and_doctor(self):
        self.state.chat.add({'id':'twitch:box:one','platform':'twitch',
                             'origin':'Box_Beard','user':'Viewer','text':'hello','shared':True})
        self.state.current_issues=[{'title':'Network drops','evidence':'4 frames dropped',
                                    'suggestion':'Check upload headroom.'}]
        headers={**self.headers,'Authorization':'Bearer '+self.state.native_key}
        r=await self.client.post('/native/poll',headers=headers,json={'outputs':[]})
        self.assertEqual(r.status,200)
        payload=await r.json()
        selected=next(row for row in payload['messages'] if row['id']=='twitch:box:one')
        self.assertEqual(selected['origin'],'Box_Beard')
        self.assertTrue(selected['shared'])
        self.assertEqual(payload['issues'][0]['title'],'Network drops')
        self.assertNotIn(self.state.native_key,str(payload))
        self.assertNotIn(self.state.browser_key,str(payload))

    async def test_native_combined_events_exclude_chat_and_diagnostics(self):
        from forgecast.server import combined_events
        self.state.chat.add(dict(id='chat',platform='twitch',kind='chat',time=10,text='private chat'))
        self.state.chat.add(dict(id='raid',platform='twitch',origin='Box_Beard',user='Raider',
                                 kind='raid',time=20,text='raid incoming'))
        self.state.doctor.incidents.append(dict(time=30,title='Network drops',evidence='2 dropped frames'))
        result=combined_events(self.state)
        self.assertTrue(any('raid incoming' in e['text'] for e in result))
        self.assertFalse(any('2 dropped frames' in e['text'] for e in result))
        self.assertFalse(any('private chat' in e['text'] for e in result))

    async def test_native_chat_send_targets_selected_connected_platform(self):
        class Sender:
            def __init__(self): self.messages=[]
            async def send(self,text): self.messages.append(text)
        self.state.demo=False
        sender=Sender()
        self.state.adapters['youtube']=sender
        headers={**self.headers,'Authorization':'Bearer '+self.state.native_key}
        request={'action':'chat_send','platform':'youtube','text':'  hello stream  '}
        r=await self.client.post('/native/action',headers=headers,json=request)
        self.assertEqual(r.status,200)
        self.assertEqual(sender.messages,['hello stream'])
        self.assertFalse(any('hello stream' in e['text'] for e in self.state.events))
        r=await self.client.post('/native/action',headers=headers,
                                 json={**request,'platform':'kick'})
        self.assertEqual(r.status,400)
        self.assertEqual(sender.messages,['hello stream'])
        self.state.adapters.pop('youtube')

    async def test_kick_reply_uses_linked_channel_and_keeps_token_private(self):
        from unittest.mock import AsyncMock
        headers={**self.headers,'Authorization':'Bearer '+self.state.native_key}
        self.state.demo=False
        self.state.config['kick']={'channel_id':'12345'}
        self.state.vault.set('kick_token','FAKE-KICK-ACCESS-TOKEN')
        send=AsyncMock(return_value={'data':{'message_id':'abc'}})
        with patch('forgecast.server.api',send):
            r=await self.client.post('/native/action',headers=headers,
                                     json={'action':'chat_send','platform':'kick','text':'  hi kick '})
        self.assertEqual(r.status,200)
        self.assertEqual(send.await_args.args[1:3],('POST','https://api.kick.com/public/v1/chat'))
        self.assertEqual(send.await_args.kwargs['json'],
                         {'type':'user','broadcaster_user_id':12345,'content':'hi kick'})
        self.assertNotIn('FAKE-KICK-ACCESS-TOKEN',await r.text())

    async def test_kick_reply_requires_linked_account(self):
        self.state.demo=False
        r=await self.client.post('/native/action',headers={**self.headers,'Authorization':'Bearer '+self.state.native_key},
                                 json={'action':'chat_send','platform':'kick','text':'hi'})
        self.assertEqual(r.status,400)
        self.assertIn('Link Kick',await r.text())

    async def test_native_destination_action_needs_auth_and_live_mode(self):
        target={'action':'save','name':'YouTube','server':'rtmps://example.com/live','key':'TEST-KEY'}
        r=await self.client.post('/native/action',headers=self.headers,json=target)
        self.assertEqual(r.status,401)
        headers={**self.headers,'Authorization':'Bearer '+self.state.native_key}
        r=await self.client.post('/native/action',headers=headers,json=target)
        self.assertEqual(r.status,400)  # demo cannot alter stream destinations
        self.state.demo=False
        r=await self.client.post('/native/action',headers=headers,json=target)
        self.assertEqual(r.status,200)
        self.assertNotIn('TEST-KEY',self.state.config_path.read_text())
        self.assertEqual(self.state.config['destinations'][0]['name'],'YouTube')

    async def test_focus_action_requires_native_auth(self):
        self.state.demo=False
        r=await self.client.post('/native/action',headers=self.headers,json={'action':'focus'})
        self.assertEqual(r.status,401)

    async def test_report_excludes_chat(self):
        r=await self.client.get('/api/report',headers=self.headers)
        text=await r.text()
        self.assertNotIn('ViewerOne',text)
        self.assertNotIn('messages',text)
        self.assertTrue((await self.client.get('/',headers={'Host':'127.0.0.1:17654'})).headers.get('Content-Security-Policy'))

    async def test_native_command_expiry(self):
        self.state.commands.append({'id':'old','created':time.time()-20,'action':'start'})
        self.state.commands.append({'id':'new','created':time.time(),'action':'stop_all'})
        r=await self.client.post('/native/poll',headers={**self.headers,'Authorization':'Bearer '+self.state.native_key},json={'outputs':[]})
        self.assertEqual([c['id'] for c in (await r.json())['commands']],['new'])

    async def test_unknown_action(self):
        self.state.demo=False
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'execute_shell'})
        self.assertEqual(r.status,400)

    async def test_live_action_needs_confirmation(self):
        self.state.demo=False
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'obs_command','command':'StartStream'})
        self.assertEqual(r.status,400)

    async def test_save_destination_does_not_expose_key(self):
        self.state.demo=False
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'save_destination','id':'yt','name':'YouTube','server':'rtmps://example.com/app','key':'FAKE-KEY'})
        self.assertEqual(r.status,200)
        r=await self.client.get('/api/state',headers=self.headers)
        self.assertNotIn('FAKE-KEY',await r.text())
        self.assertNotIn('FAKE-KEY',self.state.config_path.read_text())

    async def test_hub_requires_https(self):
        self.state.demo=False
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'hub_save','url':'http://example.com','token':'fake'})
        self.assertEqual(r.status,400)
