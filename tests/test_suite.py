import asyncio
import hashlib
import json
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer
from forgecast.chat import Twitch, api, ApiError
from forgecast.core import ChatStore, twitch_message
from forgecast.server import State, create_app, sync_hub_accounts, combined_events, preflight
from forgecast.operations import suite_action, moderate, overlay_feed
from forgecast.suite import normalize_events, session_summaries
from forgecast.audio import AudioGuard
from test_chat import Response, Session


def message(platform='twitch', uid='message', origin='channel', **extra):
    return dict(id=uid,platform=platform,origin='Creator',origin_id=origin,received_in=origin,
        platform_message_id='platform-'+uid,user='Viewer',user_id='viewer',text='Hello',kind='chat',time=time.time(),**extra)


class SuiteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.state=State(self.temp.name,demo=True)
    async def asyncTearDown(self):
        for adapter in self.state.adapters.values():
            if adapter.task:
                adapter.task.cancel();await asyncio.gather(adapter.task,return_exceptions=True)
        self.temp.cleanup()

    async def test_204_delete_does_not_try_to_decode_json(self):
        class Empty(Response):
            async def json(self): raise AssertionError('No JSON on 204')
        self.assertEqual(await api(Session(Empty(204)),'DELETE','https://example.com'),{})

    async def test_hub_expired_youtube_does_not_break_other_accounts(self):
        self.state.config['hub_url']='https://example.com';self.state.vault.set('hub_token','private')
        with patch('forgecast.server.api',AsyncMock(return_value={'connections':[{'platform':'youtube','error':'YouTube authorization expired. Reconnect in Hub Settings.'}]})):
            await sync_hub_accounts(self.state)
        self.assertIn('expired',self.state.statuses['youtube']);self.assertEqual(self.state.statuses['twitch'],'not connected')

    async def test_youtube_manual_selection_and_auto_reset(self):
        self.state.youtube_broadcasts=[{'id':'one','title':'One','live_chat_id':'chat-one'},{'id':'two','title':'Two','live_chat_id':'chat-two'}]
        from forgecast.chat import YouTube
        self.state.adapters['youtube']=YouTube(None,{'live_chat_id':'chat-one'},'private',self.state.chat,self.state.status)
        await suite_action(self.state,'youtube_select',{'id':'two'})
        self.assertEqual(self.state.adapters['youtube'].config['live_chat_id'],'chat-two')
        with self.assertRaises(ValueError): await suite_action(self.state,'youtube_select',{'id':'gone'})
        await suite_action(self.state,'youtube_select',{'id':''});self.assertEqual(self.state.adapters['youtube'].config['live_chat_id'],'')

    async def test_output_presets_save_ids_only_and_never_start(self):
        self.state.config['destinations']=[{'id':'one','enabled':True},{'id':'two','enabled':False}]
        self.state.vault.set('stream:one','PRIVATE-KEY')
        await suite_action(self.state,'preset_save',{'name':'Regular'})
        self.state.config['destinations'][0]['enabled']=False
        await suite_action(self.state,'preset_apply',{'name':'Regular'})
        self.assertTrue(self.state.config['destinations'][0]['enabled']);self.assertFalse(self.state.config['destinations'][1]['enabled'])
        self.assertEqual(self.state.config['output_presets'],{'Regular':['one']});self.assertFalse(self.state.commands)

    async def test_optional_events_off_by_default_and_tests_labelled(self):
        self.state.chat.add(message(platform='youtube',uid='paid',kind_override=True))
        self.state.chat.messages[-1]['kind']='superchat'
        self.assertFalse(combined_events(self.state))
        await suite_action(self.state,'event_settings',{'kinds':['superchat','follow'],'merge':True})
        self.assertEqual(combined_events(self.state)[0]['kind'],'superchat')
        await suite_action(self.state,'event_test',{'kind':'follow'})
        self.assertTrue(combined_events(self.state)[0]['simulated'])
        await suite_action(self.state,'event_ack',{'id':combined_events(self.state)[0]['id']})
        self.assertTrue(combined_events(self.state)[0]['acknowledged'])

    async def test_shared_chat_moderation_requires_original_channel(self):
        adapter=Twitch(None,{'client_id':'client','user_id':'owner','channel_id':'own'},'private',self.state.chat,self.state.status)
        adapter.scopes={'moderator:manage:chat_messages','moderator:manage:banned_users'};self.state.adapters['twitch']=adapter
        self.state.chat.add(message(origin='collaborator'))
        with patch('forgecast.operations.api',AsyncMock()) as call:
            with self.assertRaises(ValueError):await moderate(self.state,{'id':'message','operation':'ban','confirmed':True})
        call.assert_not_awaited();self.assertFalse(self.state.chat.messages[-1].get('deleted'))

    async def test_moderation_checks_confirmation_and_permissions(self):
        self.state.chat.add(message())
        with self.assertRaises(ValueError): await moderate(self.state,{'id':'message','operation':'ban'})
        with self.assertRaises(ValueError): await moderate(self.state,{'id':'message','operation':'ban','confirmed':True})

    async def test_twitch_delete_preserves_other_platform_same_name(self):
        adapter=Twitch(None,{'client_id':'client','user_id':'owner','channel_id':'channel'},'private',self.state.chat,self.state.status)
        adapter.scopes={'moderator:manage:chat_messages'};self.state.adapters['twitch']=adapter
        self.state.chat.add(message());self.state.chat.add(message(platform='youtube',uid='other'))
        with patch('forgecast.operations.api',AsyncMock(return_value={})) as call:
            await moderate(self.state,{'id':'message','operation':'delete','confirmed':True})
        self.assertEqual(call.call_args.args[1],'DELETE');self.assertTrue(self.state.chat.messages[0]['deleted']);self.assertFalse(self.state.chat.messages[1].get('deleted'))

    async def test_multi_send_partial_failure_is_per_platform(self):
        async def send(state,platform,text):
            if platform=='youtube':raise ApiError('Permission missing')
        with patch('forgecast.server.send_chat',send):result=await suite_action(self.state,'chat_send_many',{'platforms':['twitch','youtube'],'text':'Hello'})
        self.assertFalse(result['ok']);self.assertTrue(result['deliveries'][0]['sent']);self.assertFalse(result['deliveries'][1]['sent'])

    async def test_overlay_validation_does_not_partially_enable(self):
        with self.assertRaises(ValueError): await suite_action(self.state,'overlay_settings',{'enabled':True,'mode':'all','seconds':999})
        self.assertFalse(self.state.config.get('overlay_enabled',False))

    async def test_preflight_selected_event_does_not_start_or_modify_titles(self):
        self.state.hub_events=[{'id':'one','title':'Collab','starts_at':'2026-10-08T19:00:00Z'}]
        await suite_action(self.state,'hub_select',{'id':'one'})
        self.assertIn('Collab',next(c['result'] for c in preflight(self.state) if c['label']=='Hub event'))
        self.assertFalse(self.state.commands)

    async def test_recording_preflight_uses_fresh_native_status(self):
        await suite_action(self.state,'preflight_settings',{'recording_expected':True})
        self.state.native_seen=time.time();self.state.audio_snapshot={'recording_active':False}
        self.assertIn('not active',next(r['result'] for r in preflight(self.state) if r['label']=='Recording'))
        self.state.native_seen=0
        self.assertIn('unavailable',next(r['result'] for r in preflight(self.state) if r['label']=='Recording'))

    async def test_event_history_moderation_after_chat_eviction(self):
        event=message(uid='paid');event['kind']='superchat';self.state.chat.add(event)
        for n in range(500):self.state.chat.add(message(uid=str(n)))
        self.state.chat.delete('twitch',message_id='platform-paid')
        self.assertTrue(self.state.audience_history[0]['deleted'])

    async def test_dedup_survives_restart_without_storing_chat(self):
        self.state.demo=False;self.state.chat.add(message());self.state.checkpoint()
        saved=json.loads(self.state.checkpoint_path.read_text());self.assertNotIn('Hello',str(saved));self.assertNotIn('Viewer',str(saved))
        restored=State(self.temp.name,demo=True);self.assertFalse(restored.chat.add(message()));self.assertTrue(restored.chat.add(message(uid='new')))

    async def test_checkpoint_failure_keeps_monitoring_available(self):
        self.state.demo=False
        with patch('forgecast.server.atomic_json',side_effect=OSError('disk full')): self.state.checkpoint()
        self.assertIn('monitoring continues',self.state.events[-1]['text'])

    async def test_session_counts_survive_feed_eviction_and_dedup(self):
        self.state.history.session={'id':'session','started_at':time.time()-30}
        self.state.history.record('session_started')
        for n in range(600):self.state.chat.add(message(uid=str(n)))
        self.state.chat.add(message(uid='599'))
        self.assertEqual(session_summaries(self.state)[0]['chat_messages']['twitch'],600)
        self.assertEqual(len(self.state.chat.messages),500)


class OverlayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.state=State(self.temp.name,demo=True)
        self.client=TestClient(TestServer(create_app(self.state)));await self.client.start_server();self.state.chat.messages.clear()
        self.headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+self.state.browser_key}
    async def asyncTearDown(self):await self.client.close();self.temp.cleanup()
    async def test_overlay_cannot_read_private_state_or_control_obs(self):
        headers={**self.headers,'Authorization':'Bearer '+self.state.overlay_key}
        for path in ('/api/state','/api/pairing','/api/overlay-link'):
            self.assertEqual((await self.client.get(path,headers=headers)).status,401)
        self.assertEqual((await self.client.post('/native/action',headers=headers,json={'action':'start_all'})).status,401)
        self.assertNotIn(self.state.overlay_key,str(self.state.public()));self.assertNotIn(self.state.overlay_key,str(self.state.report()))
    async def test_selected_overlay_queue_advances_and_skips_deleted_messages(self):
        self.state.chat.add(message(uid='one'));self.state.chat.add(message(uid='two'));self.state.chat.add(message(uid='three'))
        await suite_action(self.state,'overlay_settings',{'enabled':True,'mode':'selected','seconds':10})
        for uid in ('one','two','three'):await suite_action(self.state,'highlight',{'id':uid})
        headers={**self.headers,'Authorization':'Bearer '+self.state.overlay_key}
        result=await self.client.get('/overlay/feed',headers=headers)
        self.assertEqual((await result.json())['messages'][0]['id'],'one')
        self.state.chat.delete('twitch',message_id='platform-two')
        self.state.highlight_started=time.time()-11
        result=await self.client.get('/overlay/feed',headers=headers)
        self.assertEqual((await result.json())['messages'][0]['id'],'three')
        await suite_action(self.state,'overlay_settings',{'enabled':False,'mode':'selected','seconds':10})
        self.assertFalse(self.state.highlight_ids);self.assertIsNone(self.state.highlight_current)

    async def test_overlay_disabled_rotation_and_moderation(self):
        headers={**self.headers,'Authorization':'Bearer '+self.state.overlay_key}
        self.state.chat.add(message());self.state.vault.set('hub_token','SECRET-PAIR')
        r=await self.client.get('/overlay/feed',headers=headers);self.assertEqual((await r.json())['messages'],[])
        await suite_action(self.state,'overlay_settings',{'enabled':True,'mode':'all','seconds':30})
        r=await self.client.get('/overlay/feed',headers=headers);body=await r.json();self.assertEqual(body['messages'][-1]['text'],'Hello');self.assertNotIn('SECRET-PAIR',str(body))
        self.state.chat.delete('twitch',message_id='platform-message')
        r=await self.client.get('/overlay/feed',headers=headers);self.assertEqual((await r.json())['messages'],[])
        await suite_action(self.state,'overlay_rotate',{});self.assertEqual((await self.client.get('/overlay/feed',headers=headers)).status,401)


class CoordinationTests(unittest.TestCase):
    def test_event_times_and_accepted_participants_without_live_claims(self):
        rows=normalize_events([{'id':1,'title':'Party','starts_at':'2026-10-08T19:00:00Z','url':'/events/1',
            'participants':[{'name':'Box','status':'accepted'},{'name':'Pending','status':'pending'}]},
            {'id':2,'starts_at':'ambiguous','url':'https://evil.example','participants':'invalid'}],'https://hub.example')
        self.assertEqual(rows[0]['participants'],['Box']);self.assertEqual(rows[0]['url'],'https://hub.example/events/1');self.assertIsNone(rows[1]['starts_at_unix']);self.assertEqual(rows[1]['url'],'')
    def test_optional_vod_and_clipping_checks_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            guard=AudioGuard(directory,{'sources':[{'uuid':'mic','name':'Mic','role':'microphone'}],'clipping':True,'vod_track':2},demo=True)
            issues=guard.evaluate({'sources':[{'uuid':'mic','active':True,'muted':False,'mixers':1,'meter_age':0,'signal_age':0,'hot_duration':4}],'stream_track':1,'track_verified':True},0)
            self.assertEqual({i['code'] for i in issues},{'near_clipping','vod_routing'})
