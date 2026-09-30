import tempfile
import unittest
from forgecast.history import StreamHistory
from forgecast.server import State, preflight


def output(uid='yt',active=True,reconnecting=False,dropped=0,**extras):
    return dict(id=uid,name={'yt':'YouTube','kick':'Kick'}.get(uid,uid),active=active,reconnecting=reconnecting,dropped=dropped,bytes=10000,**extras)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.history=StreamHistory(self.temp.name,demo=True)
    def tearDown(self): self.temp.cleanup()
    def kinds(self):return [e['kind'] for e in self.history.events]
    def test_single_platform_problem_preserves_other_health(self):
        h=self.history;h.sample(True,[output(),output('kick')],now=0)
        self.assertEqual(h.sample(True,[output(reconnecting=True),output('kick')],now=1),[])
        notice=h.sample(True,[output(reconnecting=True),output('kick')],now=4)
        self.assertEqual(len(notice),1)
        self.assertIn('Kick remain active',h.issues[0]['evidence'])
        self.assertEqual(len(h.sample(True,[output(reconnecting=True),output('kick')],now=5)),0)
    def test_multi_output_problem_does_not_claim_root_cause(self):
        h=self.history;h.sample(True,[output(),output('kick')],now=0)
        h.sample(True,[output(dropped=4),output('kick',dropped=3)],now=1)
        shared=next(i for i in h.issues if i['code']=='shared')
        self.assertEqual(shared['confidence'],'medium')
        self.assertIn('not proven',shared['suggestion'])
    def test_recovery_requires_stable_live_output_and_records_duration(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.sample(True,[output(reconnecting=True)],now=1)
        h.sample(True,[output(reconnecting=True)],now=4)
        h.sample(True,[output(active=False)],now=5)
        self.assertNotIn('recovered',self.kinds())
        h.sample(True,[output()],now=6)
        h.sample(True,[output()],now=9)
        notice=h.sample(True,[output()],now=11)
        self.assertEqual(len(notice),1)
        recovered=next(e for e in h.events if e['kind']=='recovered')
        self.assertEqual(recovered['duration'],5)
    def test_intentional_stop_never_alerts(self):
        h=self.history;h.sample(True,[output()],now=0);h.command('stop',['yt'])
        h.sample(True,[output()],now=1)
        h.sample(True,[output(active=False)],now=2)
        self.assertNotIn('incident',self.kinds())
    def test_native_emergency_stop_flag_never_alerts(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.sample(True,[output(active=False,intentional_stop=True)],now=1)
        self.assertNotIn('incident',self.kinds())
    def test_unexpected_stop_remains_warning_until_restart(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.sample(True,[output(active=False)],now=1)
        self.assertEqual(len(h.sample(True,[output(active=False)],now=4)),1)
        self.assertNotIn('recovered',self.kinds())
    def test_missing_telemetry_never_claims_recovery(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.sample(True,[output(reconnecting=True)],now=1)
        self.assertEqual(len(h.sample(None,[],now=2)),1)
        self.assertEqual(h.sample(None,[],now=3),[])
        h.sample(True,[output()],now=4)
        self.assertNotIn('recovered',self.kinds())
        self.assertIn('telemetry_restored',self.kinds())
    def test_sampling_gap_resets_disruption_timer(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.sample(True,[output(reconnecting=True)],now=1)
        self.assertEqual(h.sample(True,[output(reconnecting=True)],now=20),[])
        self.assertIn('telemetry_gap',self.kinds())
    def test_normal_session_end_is_not_platform_failure(self):
        h=self.history;h.sample(True,[output()],now=0)
        self.assertEqual(h.sample(False,[],now=10),[])
        self.assertIsNone(h.session)
        self.assertEqual(h.events[-1]['duration'],10)
    def test_persistence_and_restart_marks_unknown_end(self):
        h=StreamHistory(self.temp.name);h.sample(True,[output()],now=0)
        recovered=StreamHistory(self.temp.name)
        self.assertEqual(recovered.events[-1]['kind'],'session_interrupted')
        self.assertIsNone(recovered.session)
    def test_reports_omit_arbitrary_details_and_audio_source_names(self):
        h=self.history;h.record('audio_warning',title='PRIVATE-MIC',source_uuid='PRIVATE-UUID',token='SECRET',server='PRIVATE-URL',code='muted')
        report=str(h.report())
        for private in ('PRIVATE-MIC','PRIVATE-UUID','SECRET','PRIVATE-URL'):self.assertNotIn(private,report)
    def test_bitrate_is_byte_delta_and_counter_reset_not_negative(self):
        h=self.history;h.sample(True,[output()],now=0)
        row=output();row['bytes']=12000;h.sample(True,[row],now=2)
        self.assertEqual(h.health[0]['bitrate_kbps'],8)
        row['bytes']=1;h.sample(True,[row],now=3)
        self.assertEqual(h.health[0]['bitrate_kbps'],0)
    def test_failed_start_recorded_without_raw_error(self):
        h=self.history;h.sample(True,[output(active=False,error='RAW-KEY')],now=0)
        self.assertEqual(h.issues[0]['code'],'failed')
        self.assertNotIn('RAW-KEY',str(h.events))
    def test_frame_incidents_and_verified_counter_recovery(self):
        h=self.history;h.sample(True,[output()],now=0)
        issue={'code':'encode','title':'Encoding lag','evidence':'4 missed frames.'}
        self.assertEqual(len(h.frames([issue],True,now=0)),1)
        self.assertEqual(h.frames([issue],True,now=1),[])
        h.frames([],True,now=2);h.frames([],True,now=7)
        self.assertIn('frame_recovered',self.kinds())
    def test_storage_failure_does_not_stop_monitor(self):
        h=StreamHistory(self.temp.name)
        from pathlib import Path
        h.path=Path(self.temp.name)/'missing'/'history.jsonl'
        h.sample(True,[output()],now=0)
        self.assertIsNotNone(h.storage_error)
        self.assertIsNotNone(h.session)
    def test_preflight_warns_without_blocking_and_uses_selected_destinations(self):
        s=State(self.temp.name,demo=True)
        s.config['destinations']=[{'id':'yt','name':'YouTube'},{'id':'kick','name':'Kick','enabled':False}]
        rows=preflight(s)
        self.assertTrue(any(r['label']=='YouTube' and 'Missing stream key' in r['result'] for r in rows))
        self.assertFalse(any(r['label']=='Kick' for r in rows))
        self.assertTrue(any('not verified offline' in r['result'] for r in rows))

    def test_frame_telemetry_gap_does_not_invent_recovery(self):
        h=self.history;h.sample(True,[output()],now=0)
        h.frames([{'code':'render','title':'Rendering lag','evidence':'One missed frame.'}],True,now=0)
        h.frames_unavailable();h.frames([],True,now=10)
        self.assertNotIn('frame_recovered',self.kinds())
        self.assertIn('frame_telemetry_lost',self.kinds())

    def test_multi_platform_notifications_are_grouped(self):
        h=self.history;h.sample(True,[output(),output('kick')],now=0)
        h.sample(True,[output(reconnecting=True),output('kick',reconnecting=True)],now=1)
        notices=h.sample(True,[output(reconnecting=True),output('kick',reconnecting=True)],now=4)
        self.assertEqual(len(notices),1)
        self.assertIn('Multiple destinations',notices[0]['body'])
