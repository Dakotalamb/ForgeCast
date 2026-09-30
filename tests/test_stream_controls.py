import tempfile
import time
import unittest
from forgecast.server import State, queue_outputs, set_destination_enabled

class StreamControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=State(self.temp.name,demo=True)
        self.state.native_seen=time.time()
        self.state.config['destinations']=[
            {'id':'yt','name':'YouTube','server':'rtmps://example.com/live'},
            {'id':'kick','name':'Kick','server':'rtmps://example.com/live','enabled':False}]
        self.state.vault.set('stream:yt','PRIVATE-STREAM-KEY')
        self.state.vault.set('stream:kick','OTHER-PRIVATE-KEY')
    def tearDown(self): self.temp.cleanup()
    def test_start_all_selects_enabled_destinations_and_keeps_keys_private(self):
        queue_outputs(self.state,'start_all')
        command=self.state.commands[0]
        self.assertEqual(command['action'],'start_all')
        self.assertEqual([d['id'] for d in command['destinations']],['yt'])
        self.assertEqual(command['destinations'][0]['key'],'PRIVATE-STREAM-KEY')
        self.assertNotIn('PRIVATE-STREAM-KEY',str(self.state.public()))
    def test_enable_choice_persists_without_stopping_outputs(self):
        self.state.native_outputs=[{'id':'yt','active':True}]
        set_destination_enabled(self.state,{'id':'yt','enabled':False})
        self.assertFalse(self.state.config['destinations'][0]['enabled'])
        self.assertEqual(len(self.state.commands),0)
        self.assertTrue(self.state.native_outputs[0]['active'])
        self.assertFalse(State(self.temp.name,demo=True).config['destinations'][0]['enabled'])
    def test_start_all_refuses_missing_key_without_partial_queue(self):
        self.state.config['destinations'][1]['enabled']=True
        self.state.vault.delete('stream:kick')
        with self.assertRaises(ValueError):queue_outputs(self.state,'start_all')
        self.assertEqual(len(self.state.commands),0)
    def test_start_all_with_no_enabled_destinations(self):
        self.state.config['destinations'][0]['enabled']=False
        with self.assertRaises(ValueError):queue_outputs(self.state,'start_all')
    def test_stop_all_has_no_keys_and_works_with_no_destinations(self):
        self.state.config['destinations']=[]
        queue_outputs(self.state,'stop_all')
        self.assertNotIn('destinations',self.state.commands[0])
    def test_disconnected_native_and_non_boolean_checkbox_are_rejected(self):
        self.state.native_seen=0
        with self.assertRaises(ValueError):queue_outputs(self.state,'start_all')
        with self.assertRaises(ValueError):set_destination_enabled(self.state,{'id':'yt','enabled':'false'})
