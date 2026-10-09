import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from forgecast.server import State,secure
from forgecast.productivity import backup,validate_backup,productivity_action,feedback_payload,export_backup


class ProductivityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=State(self.temp.name,demo=True)
        self.s.obs=SimpleNamespace(connected=True,ws=object(),request=AsyncMock(return_value={'outputActive':False}))
    async def asyncTearDown(self):
        await self.s.audio_test.close();self.temp.cleanup()
    async def test_backup_excludes_credentials_urls_and_source_names(self):
        self.s.vault.set('stream:one','PRIVATE');self.s.config.update(hub_url='https://private',obs_port=4455,audio_guard={'sources':[{'name':'PRIVATE SOURCE'}]},doctor_sound=True,
            destinations=[{'id':'one','name':'Twitch','server':'rtmp://private','key':'PRIVATE'}])
        text=json.dumps(backup(self.s));self.assertNotIn('PRIVATE',text);self.assertNotIn('rtmp://private',text);self.assertNotIn('https://private',text)
        self.assertEqual(backup(self.s)['destinations'],[{'name':'Twitch'}]);self.assertTrue(backup(self.s)['preferences']['doctor_sound'])
    async def test_untrusted_backup_rejected_before_any_changes(self):
        valid=backup(self.s);before=copy.deepcopy(self.s.config)
        for change in ({'event_kinds':[{}]},{'doctor_sensitivity':'extreme'},{'doctor_sound':'yes'},{'token':'secret'},{'overlay_font':True}):
            data=copy.deepcopy(valid);data['preferences'].update(change)
            with self.assertRaises(ValueError):await productivity_action(self.s,'backup_restore',{'backup':data,'confirmed':True})
            self.assertEqual(self.s.config,before)
        with self.assertRaises(ValueError):validate_backup({**valid,'credentials':'secret'})
    async def test_restore_preserves_keys_adds_disabled_names_and_requires_disconnect(self):
        self.s.config['destinations']=[{'id':'one','name':'Twitch','enabled':True,'server':'rtmps://server'}];self.s.vault.set('stream:one','PRIVATE')
        data=backup(self.s);data['destinations'].append({'name':'YouTube'});data['preferences']['doctor_sensitivity']='relaxed'
        with self.assertRaises(ValueError):await productivity_action(self.s,'backup_restore',{'backup':data,'confirmed':True})
        self.s.obs.connected=False
        await productivity_action(self.s,'backup_restore',{'backup':data,'confirmed':True})
        self.assertEqual(self.s.vault.get('stream:one'),'PRIVATE');self.assertEqual(self.s.config['destinations'][0]['id'],'one')
        self.assertFalse(self.s.config['destinations'][1]['enabled']);self.assertEqual(self.s.config['destinations'][1]['server'],'')
        self.assertEqual(self.s.doctor.sensitivity,'relaxed');self.assertEqual(json.loads(self.s.config_path.read_text()),self.s.config)
    async def test_failed_disk_write_does_not_partially_restore(self):
        self.s.obs.connected=False;data=backup(self.s);data['preferences']['doctor_sound']=True;before=copy.deepcopy(self.s.config)
        with patch('forgecast.storage.atomic_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):await productivity_action(self.s,'backup_restore',{'backup':data,'confirmed':True})
        self.assertEqual(before,self.s.config)
    async def test_backup_endpoint_requires_companion_authentication(self):
        app=web.Application(middlewares=[secure]);app['state']=self.s;app.router.add_get('/api/backup',export_backup)
        async with TestClient(TestServer(app)) as client:
            headers={'Host':'127.0.0.1:8766'}
            from forgecast.server import PORT
            headers['Host']='127.0.0.1:'+str(PORT)
            self.assertEqual((await client.get('/api/backup',headers=headers)).status,401)
            headers['Authorization']='Bearer '+self.s.browser_key
            response=await client.get('/api/backup',headers=headers);self.assertEqual(response.status,200)
            self.assertEqual((await response.json())['schema_version'],1)
            headers['Authorization']='Bearer '+self.s.overlay_key
            self.assertEqual((await client.get('/api/backup',headers=headers)).status,401)
    async def test_feedback_preview_redacts_credentials_no_automatic_send(self):
        self.s.vault.set('hub_token','PRIVATE-TOKEN');text='PRIVATE-TOKEN '+self.s.browser_key+' fc_'+'a'*40+' rtmps://secret/key Bearer secret_token'
        with patch('forgecast.productivity.api',AsyncMock()) as send:
            result=await productivity_action(self.s,'feedback_preview',{'kind':'problem','title':'Help','details':text,'diagnostics':True})
            send.assert_not_awaited()
        encoded=json.dumps(result);self.assertNotIn('PRIVATE-TOKEN',encoded);self.assertNotIn(self.s.browser_key,encoded);self.assertNotIn('rtmps://secret',encoded);self.assertNotIn('secret_token',encoded)
        self.assertIn('diagnostics',result['payload'])
    async def test_feedback_sends_exact_preview_once_and_only_after_confirmation(self):
        self.s.config['hub_url']='https://hub.test';self.s.vault.set('hub_token','private')
        draft=await productivity_action(self.s,'feedback_preview',{'kind':'feature','title':'Idea','details':'Please add this.'})
        with patch('forgecast.productivity.api',AsyncMock(return_value={})) as send:
            with self.assertRaises(ValueError):await productivity_action(self.s,'feedback_send',{'preview_id':draft['preview_id']})
            send.assert_not_awaited()
            await productivity_action(self.s,'feedback_send',{'preview_id':draft['preview_id'],'confirmed':True})
            self.assertEqual(send.call_args.kwargs['json'],draft['payload']);self.assertNotIn('diagnostics',draft['payload'])
            with self.assertRaises(ValueError):await productivity_action(self.s,'feedback_send',{'preview_id':draft['preview_id'],'confirmed':True})
    async def test_audio_test_refuses_existing_recording_or_stream(self):
        self.s.obs.request.return_value={'outputActive':True}
        with self.assertRaises(ValueError):await self.s.audio_test.start()
        self.assertNotIn('StartRecord',[c.args[0] for c in self.s.obs.request.call_args_list])
    async def test_audio_test_stops_only_owned_recording_and_uses_obs_returned_file(self):
        sample=Path(self.temp.name)/'sample.mkv';sample.write_bytes(b'fixture')
        async def request(kind):return {'outputPath':str(sample)} if kind=='StopRecord' else {'outputActive':kind=='GetRecordStatus' and self.s.audio_test.owned}
        self.s.obs.request.side_effect=request
        await self.s.audio_test.start();self.assertEqual(self.s.audio_test.phase,'recording')
        await self.s.audio_test.stop();self.assertEqual(self.s.audio_test.phase,'ready');self.assertEqual(self.s.audio_test.path,sample)
        await productivity_action(self.s,'audio_test_review',{'review':{'microphone':True,'game_audio':False,'balance':True}})
        self.assertTrue(self.s.audio_test.review['microphone']);self.assertFalse(self.s.audio_test.review['game_audio'])
    async def test_recording_connection_change_does_not_stop_another_session(self):
        await self.s.audio_test.start();self.s.obs.ws=object();self.s.obs.request.reset_mock()
        with self.assertRaises(ValueError):await self.s.audio_test.stop()
        self.s.obs.request.assert_not_awaited();self.assertEqual(self.s.audio_test.phase,'interrupted')
    async def test_external_stop_revokes_ownership_before_restart(self):
        await self.s.audio_test.start()
        self.s.obs_event({'eventType':'RecordStateChanged','eventData':{'outputState':'OBS_WEBSOCKET_OUTPUT_STOPPED'}})
        self.s.obs.request.reset_mock()
        with self.assertRaises(ValueError):await self.s.audio_test.stop()
        self.s.obs.request.assert_not_awaited()
    async def test_start_timeout_requires_manual_check_without_claiming_ownership(self):
        async def request(kind):
            if kind=='StartRecord':raise asyncio.TimeoutError()
            return {'outputActive':False}
        self.s.obs.request.side_effect=request
        with self.assertRaisesRegex(ValueError,'manually'):await self.s.audio_test.start()
        self.assertFalse(self.s.audio_test.owned);self.assertEqual(self.s.audio_test.phase,'interrupted')
    async def test_cannot_open_arbitrary_file_from_client(self):
        with self.assertRaises(ValueError):await productivity_action(self.s,'audio_test_open',{'confirmed':True,'path':'evil.exe'})
        self.assertIsNone(self.s.audio_test.path)

    async def test_connection_change_during_status_read_does_not_stop_new_session(self):
        await self.s.audio_test.start()
        async def moved(kind):
            if kind=='GetRecordStatus':self.s.obs.ws=object();return {'outputActive':True}
            raise AssertionError('Must not stop after the connection changes')
        self.s.obs.request.side_effect=moved
        with self.assertRaises(ValueError):await self.s.audio_test.stop()
        self.assertFalse(self.s.audio_test.owned)
