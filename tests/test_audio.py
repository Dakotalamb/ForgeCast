import base64
import tempfile
import unittest
from forgecast.audio import AudioGuard, validate_settings, toast_script

class AudioGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.guard=AudioGuard(self.temp.name,{'sources':[{'uuid':'mic','name':'Private Device','role':'microphone'}]},demo=True)
        self.row={'uuid':'mic','name':'Private Device','active':True,'muted':False,'mixers':2,'volume':1,
                  'monitor_only':False,'meter_age':0,'signal_age':0}
    def tearDown(self):self.temp.cleanup()
    def sample(self,now,**fields):
        snapshot={'sources':[{**self.row,**fields}],'stream_track':2,'track_verified':True}
        return self.guard.sample(snapshot,True,'Gameplay',now)
    def advance(self,end,**fields):
        notices=[]
        for second in range(end+1):notices.extend(self.sample(second,**fields))
        return notices
    def test_muted_warning_notification_and_five_minute_reminder(self):
        self.advance(29,muted=True)
        self.assertEqual(self.guard.current['issues'],[])
        self.sample(30,muted=True)
        self.assertEqual(self.guard.current['issues'][0]['code'],'muted')
        notices=[]
        for n in range(31,301):notices.extend(self.sample(n,muted=True))
        self.assertEqual(len(notices),2)
        self.assertFalse(any(n['sound'] for n in notices))
    def test_optional_sound_does_not_depend_on_toast_setting(self):
        self.guard.settings.update(sound=True,notifications=False)
        notices=self.advance(121,muted=True)
        self.assertEqual(len(notices),1)
        self.assertTrue(notices[0]['sound'])
        self.assertFalse(notices[0]['toast'])
        self.assertEqual(self.sample(122,muted=True),[])

    def test_sound_disabled_does_not_play_or_queue_when_notifications_off(self):
        self.guard.settings.update(sound=False,notifications=False)
        self.assertEqual(self.advance(301,muted=True),[])

    def test_exact_non_default_stream_track_mismatch_and_signal_evidence(self):
        notices=self.advance(10,mixers=1)
        issue=self.guard.current['issues'][0]
        self.assertEqual(issue['code'],'wrong_track')
        self.assertIn('Track 2',issue['evidence'])
        self.assertIn('working',issue['title'])
        self.assertEqual(len(notices),1)
    def test_unknown_track_does_not_claim_wrong_routing(self):
        snapshot={'sources':[{**self.row,'mixers':0}],'stream_track':0,'track_verified':False}
        for n in range(20):self.guard.sample(snapshot,True,'Gameplay',n)
        self.assertFalse(any(i['code']=='wrong_track' for i in self.guard.current['issues']))
    def test_scene_pause_and_stream_stop_do_not_claim_audio_recovered(self):
        self.advance(35,muted=True)
        snapshot={'sources':[self.row],'stream_track':2,'track_verified':True}
        self.guard.sample(snapshot,True,'BRB',36)
        self.assertEqual(self.guard.current['state'],'paused')
        self.assertFalse(any(e['kind']=='recovered' for e in self.guard.history))
        self.guard.sample(snapshot,False,'Gameplay',37)
        self.assertEqual(self.guard.current['state'],'offline')
    def test_scene_match_is_not_a_loose_substring(self):
        self.assertTrue(self.guard.is_quiet_scene('Starting Soon'))
        self.assertTrue(self.guard.is_quiet_scene('BRB - Coffee'))
        self.assertFalse(self.guard.is_quiet_scene('The Never Ending Story'))
    def test_snooze_and_acknowledgement_do_not_auto_unmute(self):
        self.advance(30,muted=True)
        self.guard.acknowledge(now=30,snooze=True)
        notices=[]
        for n in range(31,100):notices.extend(self.sample(n,muted=True))
        self.assertEqual(notices,[])
        self.assertTrue(self.guard.current['issues'][0]['snoozed'])
        self.assertTrue(self.row.get('muted',False)==False) # source data is never mutated
        self.guard.acknowledge(now=100)
        self.assertTrue(self.guard.acknowledged)
    def test_recovery_is_saved_and_new_incident_rearms(self):
        self.advance(60,muted=True)
        self.sample(61)
        self.assertTrue(any(e['kind']=='recovered' for e in self.guard.history))
        notices=[]
        for n in range(62,123):notices.extend(self.sample(n,muted=True))
        self.assertEqual(len(notices),1)
    def test_missing_and_monitor_only_are_distinct_from_silence(self):
        snapshot={'sources':[],'stream_track':2,'track_verified':True}
        for n in range(5):self.guard.sample(snapshot,True,'Gameplay',n)
        self.assertEqual(self.guard.current['issues'][0]['code'],'source_missing')
        self.guard.pause('test')
        self.advance(4,monitor_only=True)
        self.assertEqual(self.guard.current['issues'][0]['code'],'monitor_only')
    def test_silence_waits_and_does_not_claim_device_disconnected(self):
        self.advance(89,signal_age=None)
        self.assertEqual(self.guard.current['issues'],[])
        self.sample(90,signal_age=None)
        issue=self.guard.current['issues'][0]
        self.assertEqual(issue['code'],'silent')
        self.assertNotIn('disconnected',issue['title'])
    def test_stale_telemetry_resets_timers_instead_of_adding_missing_time(self):
        self.advance(29,muted=True)
        self.sample(100,muted=True)
        self.assertEqual(self.guard.current['issues'],[])
        self.guard.sample(None,True,'Gameplay',101)
        self.assertEqual(self.guard.current['state'],'unknown')
    def test_history_persists_but_report_summary_excludes_source_identity(self):
        saved=AudioGuard(self.temp.name,self.guard.settings,demo=False)
        snapshot={'sources':[{**self.row,'muted':True}],'stream_track':2,'track_verified':True}
        for n in range(32):saved.sample(snapshot,True,'Gameplay',n)
        reopened=AudioGuard(self.temp.name,self.guard.settings,demo=False)
        self.assertTrue(reopened.history)
        self.assertNotIn('Private Device',str(reopened.summary()))
        self.assertNotIn('mic',str(reopened.summary()))
    def test_notification_text_is_xml_escaped_and_not_executable_powershell(self):
        body="You're muted <tag> $(BAD) ' quote"
        script=toast_script('FDGCast',body)
        self.assertNotIn(body,script)
        encoded=script.split("FromBase64String('")[1].split("')")[0]
        xml=base64.b64decode(encoded).decode()
        self.assertIn('&lt;tag&gt;',xml)
        self.assertIn('silent="true"',xml)
    def test_snooze_expiry_emits_one_notice_instead_of_backlog(self):
        self.advance(30,muted=True)
        self.guard.acknowledge(now=30,snooze=True)
        notices=[]
        for n in range(31,633):notices.extend(self.sample(n,muted=True))
        self.assertEqual(len(notices),1)
    def test_meter_updates_missing_are_unknown_not_a_proven_device_disconnect(self):
        self.advance(30,meter_age=None,signal_age=None)
        issue=self.guard.current['issues'][0]
        self.assertEqual(issue['code'],'meter_unavailable')
        self.assertNotIn('disconnected',issue['title'])

    def test_settings_reject_duplicate_sources_and_invalid_delay(self):
        with self.assertRaises(ValueError):validate_settings({'silence_seconds':1})
        with self.assertRaises(ValueError):validate_settings({'sources':self.guard.settings['sources']*2})
