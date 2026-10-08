import copy
import json
import tempfile
import unittest
from pathlib import Path
from forgecast.core import ChatStore, Doctor, twitch_message, youtube_message, kick_message, validate_destination
from forgecast.storage import Vault, atomic_json
from forgecast.obs import auth_response


def event(**overrides):
    data = dict(broadcaster_user_id='1', broadcaster_user_name='Deco', message_id='copy-1',
                chatter_user_id='viewer-1', chatter_user_name='Alice', message={'text':'Hello'})
    data.update(overrides)
    return data


class ChatTests(unittest.TestCase):
    def test_normal_origin(self):
        m=twitch_message(event())
        self.assertEqual(m['origin'], 'Deco')
        self.assertFalse(m['shared'])

    def test_shared_origin_is_not_receiving_channel(self):
        m=twitch_message(event(source_broadcaster_user_id='2', source_broadcaster_user_name='Box_Beard', source_message_id='original'))
        self.assertEqual(m['origin'], 'Box_Beard')
        self.assertEqual(m['origin_id'], '2')
        self.assertEqual(m['received_in'], '1')

    def test_shared_duplicate(self):
        store=ChatStore()
        m=twitch_message(event(source_broadcaster_user_id='2', source_broadcaster_user_name='Box', source_message_id='original'))
        self.assertTrue(store.add(m))
        m2=twitch_message(event(broadcaster_user_id='3', message_id='copy-2', source_broadcaster_user_id='2', source_message_id='original'))
        self.assertFalse(store.add(m2))
        self.assertEqual(len(store.messages), 1)

    def test_origin_and_relay_dedup(self):
        store=ChatStore()
        store.add(twitch_message(event(broadcaster_user_id='2', message_id='original')))
        self.assertFalse(store.add(twitch_message(event(source_broadcaster_user_id='2', source_message_id='original'))))

    def test_same_text_distinct_messages_kept(self):
        store=ChatStore()
        store.add(twitch_message(event()))
        self.assertTrue(store.add(twitch_message(event(message_id='another'))))

    def test_delete_shared_original(self):
        store=ChatStore()
        store.add(twitch_message(event(source_broadcaster_user_id='2', source_message_id='original')))
        store.delete('twitch', message_id='original', channel='2')
        self.assertTrue(store.messages[0]['deleted'])

    def test_delete_does_not_cross_channels(self):
        store=ChatStore()
        store.add(twitch_message(event()))
        store.delete('twitch', channel='other')
        self.assertNotIn('deleted', store.messages[0])

    def test_bounded_history(self):
        store=ChatStore(limit=2)
        for n in range(5): store.add(twitch_message(event(message_id=str(n))))
        self.assertEqual(len(store.messages), 2)

    def test_youtube_normalization(self):
        m=youtube_message({'id':'a','snippet':{'liveChatId':'b','type':'superChatEvent','displayMessage':'Thank you!'},'authorDetails':{'displayName':'Bob','isChatSponsor':True}}, 'Deco YT')
        self.assertEqual(m['origin'], 'Deco YT')
        self.assertEqual(m['kind'], 'superchat')
        self.assertIn('isChatSponsor', m['badges'])

    def test_kick_origin_and_dedup(self):
        message={'message_id':'k-1','broadcaster':{'user_id':123,'channel_slug':'deco'},
                 'sender':{'user_id':456,'username':'Viewer'},'content':'Hi'}
        item=kick_message(message)
        self.assertEqual((item['origin'],item['received_in']),('deco','123'))
        store=ChatStore()
        self.assertTrue(store.add(item))
        self.assertFalse(store.add(kick_message(message)))


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.d=Doctor()
        self.sample=dict(renderSkippedFrames=0, renderTotalFrames=100, outputSkippedFrames=0, outputTotalFrames=100,
                         outputs=[dict(id='a',name='Twitch',active=True,dropped=0),dict(id='b',name='YouTube',active=True,dropped=0)])
        self.d.sample(copy.deepcopy(self.sample), 0)

    def test_healthy(self):
        self.assertEqual(self.d.sample(self.sample,2), [])

    def sustained(self):
        result=[]
        for index in range(1,7):
            current=copy.deepcopy(self.sample)
            current['renderTotalFrames']=100+(self.sample['renderTotalFrames']-100)*index
            current['outputTotalFrames']=100+(self.sample['outputTotalFrames']-100)*index
            current['renderSkippedFrames']=self.sample['renderSkippedFrames']*index
            current['outputSkippedFrames']=self.sample['outputSkippedFrames']*index
            for out in current['outputs']: out['dropped'] *= index
            result=self.d.sample(current,index*2)
        return result

    def test_render(self):
        self.sample.update(renderSkippedFrames=3,renderTotalFrames=220)
        issue=self.sustained()[0]
        self.assertEqual(issue['code'],'render')
        self.assertIn('3 of 120',issue['evidence'])

    def test_encoding(self):
        self.sample.update(outputSkippedFrames=6,outputTotalFrames=220)
        self.assertEqual(self.sustained()[0]['code'],'encode')

    def test_single_route_not_definitive(self):
        self.sample['outputs'][0]['dropped']=10
        issues=self.sustained()
        self.assertEqual(issues[-1]['title'],'Some outputs affected')
        self.assertEqual(issues[-1]['confidence'],'medium')

    def test_all_outputs(self):
        for out in self.sample['outputs']:out['dropped']=10
        self.assertEqual(self.sustained()[-1]['title'],'All active outputs affected')

    def test_transient_spike_is_ignored(self):
        self.assertEqual(self.d.sample(dict(self.sample,renderSkippedFrames=40,renderTotalFrames=220),2),[])
        self.assertEqual(self.d.sample(dict(self.sample,renderSkippedFrames=40,renderTotalFrames=340),4),[])
        self.assertEqual(list(self.d.incidents),[])

    def test_small_frame_fluctuation_is_ignored(self):
        for n in range(1,40):
            self.assertEqual(self.d.sample(dict(self.sample,renderSkippedFrames=n,renderTotalFrames=100+120*n),n*2),[])

    def test_counter_reset(self):
        self.sample.update(renderTotalFrames=1,renderSkippedFrames=0)
        self.assertEqual(self.d.sample(self.sample,2),[])

    def test_disconnected_output_not_network_issue(self):
        self.sample['outputs'][0].update(active=False,dropped=9)
        self.assertEqual(self.d.sample(self.sample,2),[])

    def test_continuing_issue_does_not_repeat(self):
        for n in range(1,40):
            self.d.sample(dict(self.sample,renderSkippedFrames=3*n,renderTotalFrames=100+120*n),n*2)
        self.assertEqual(len(self.d.incidents),1)

    def test_severity_escalates_only_after_persistence(self):
        for n in range(1,7):
            self.d.sample(dict(self.sample,renderSkippedFrames=3*n,renderTotalFrames=100+120*n),n*2)
        self.assertEqual(self.d.incidents[-1]['severity'],'warning')
        for n in range(1,4):
            result=self.d.sample(dict(self.sample,renderSkippedFrames=18+12*n,renderTotalFrames=820+120*n),12+n*2)
        self.assertEqual(result[0]['severity'],'critical')
        self.assertEqual(len(self.d.incidents),2)

    def test_reset_baseline(self):
        self.d.reset()
        self.sample.update(renderSkippedFrames=100,renderTotalFrames=1000)
        self.assertEqual(self.d.sample(self.sample,2),[])


class SafetyTests(unittest.TestCase):
    def test_destination(self):
        self.assertEqual(validate_destination({'id':'kick','name':'Kick','server':'rtmps://example.com/app','key':'secret'})['id'],'kick')

    def test_reject_non_rtmp(self):
        with self.assertRaises(ValueError):validate_destination({'id':'a','name':'x','server':'file:///etc/passwd'})

    def test_reject_embedded_credentials(self):
        with self.assertRaises(ValueError):validate_destination({'id':'a','name':'x','server':'rtmps://a:b@example.com/app'})

    def test_reject_query_secret(self):
        with self.assertRaises(ValueError):validate_destination({'id':'a','name':'x','server':'rtmps://example.com/app?key=secret'})

    def test_reject_id_path(self):
        with self.assertRaises(ValueError):validate_destination({'id':'../a','name':'x','server':'rtmp://example.com/app'})

    def test_memory_vault_never_writes(self):
        with tempfile.TemporaryDirectory() as d:
            vault=Vault(d,memory=True)
            vault.set('token','secret')
            self.assertEqual(vault.get('token'),'secret')
            self.assertFalse(vault.path.exists())
            vault.delete('token')
            self.assertEqual(vault.get('token'),'')

    def test_atomic_config(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json'
            atomic_json(p,{'x':1})
            self.assertEqual(json.loads(p.read_text()),{'x':1})

    def test_obs_auth_known_vector(self):
        # Protocol salt/challenge; expected hash independently checked with Node crypto.
        self.assertEqual(auth_response('supersecretpassword','lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=',
                                      '+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY='),
                         '1Ct943GAT+6YQUUX47Ia/ncufilbe6+oD6lY+5kaCu4=')

