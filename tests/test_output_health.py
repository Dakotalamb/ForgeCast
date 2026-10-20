import unittest
from forgecast.output_health import OutputMonitor


def row(**kw):
    return dict(dict(id='main',active=True,bytes=0,frames=0,width=1920,height=1080),**kw)


class OutputHealthTests(unittest.TestCase):
    def test_active_without_bytes_is_not_sending_and_becomes_stalled(self):
        m=OutputMonitor()
        self.assertEqual(m.sample([row()],0)[0]['transmission_state'],'starting')
        self.assertEqual(m.sample([row(frames=90)],3)[0]['transmission_state'],'starting')
        self.assertEqual(m.sample([row(frames=150)],5)[0]['transmission_state'],'stalled')
        value=m.sample([row(bytes=125000,frames=180)],6)[0]
        self.assertEqual(value['transmission_state'],'sending');self.assertEqual(value['bitrate_kbps'],1000)
        self.assertEqual(value['width'],1920);self.assertIn('not verify',value['delivery_note'])
        self.assertEqual(m.sample([row(bytes=125000,frames=300)],10)[0]['transmission_state'],'sending')
        self.assertEqual(m.sample([row(bytes=125000,frames=330)],11)[0]['transmission_state'],'stalled')
    def test_reconnect_reset_and_gap_do_not_claim_sending(self):
        m=OutputMonitor();m.sample([row()],0);m.sample([row(bytes=1000)],1)
        self.assertEqual(m.sample([row(bytes=1000,reconnecting=True)],2)[0]['transmission_state'],'reconnecting')
        self.assertEqual(m.sample([row(bytes=1500)],3)[0]['transmission_state'],'starting')
        self.assertEqual(m.sample([row(bytes=1600)],4)[0]['transmission_state'],'sending')
        self.assertEqual(m.sample([row(bytes=0)],5)[0]['transmission_state'],'starting')
        self.assertEqual(m.sample([row(bytes=5000)],20)[0]['transmission_state'],'starting')
        self.assertEqual(m.sample([row(active=False)],21)[0]['transmission_state'],'offline')
    def test_outputs_are_independent_and_credentials_are_not_forwarded(self):
        m=OutputMonitor();m.sample([row(),row(id='second')],0)
        value=m.sample([row(bytes=999,key='SECRET',server='PRIVATE'),row(id='second')],1)
        self.assertEqual([r['transmission_state'] for r in value],['sending','starting'])
        self.assertNotIn('SECRET',str(value));self.assertNotIn('server',value[0])
        for n in range(2,7):value=m.sample([row(bytes=999+n),row(id='second')],n)
        self.assertEqual([r['transmission_state'] for r in value],['sending','stalled'])
        m.sample([],7);self.assertEqual(m.previous,{})
    def test_bad_counters_are_bounded_and_no_data_is_not_fabricated(self):
        m=OutputMonitor();v=m.sample([row(bytes=float('inf'),width=-1),row(),None],0)
        self.assertEqual(len(v),1);self.assertEqual(v[0]['bytes'],0);self.assertEqual(v[0]['width'],0)
