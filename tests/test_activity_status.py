import unittest
from forgecast.activity_status import activity_connection


class ActivityConnectionTests(unittest.TestCase):
    def test_no_connection_never_uses_old_events_as_evidence(self):
        result = activity_connection({'twitch': 'not connected', 'youtube':'not connected'})
        self.assertEqual(result['level'], 'attention')
        self.assertIn('not connected', result['message'])

    def test_disconnected_transport_overrides_previously_ready_subscriptions(self):
        result = activity_connection({'twitch':'Disconnected; retrying.', 'twitch_events':'Follows: ready · Raids: ready'})
        self.assertEqual(result['level'], 'attention')
        self.assertIn('Disconnected', result['platforms'][0]['message'])

    def test_partial_permission_failure_is_not_green_chat_connection(self):
        result = activity_connection({'twitch':'connected', 'twitch_events':'Follows: permission needed; reconnect Twitch in Hub settings · Raids: ready'})
        self.assertEqual(result['level'], 'attention')
        self.assertIn('Follows: permission needed', result['platforms'][0]['message'])

    def test_ready_transport_does_not_claim_delivery_or_recover_history(self):
        result = activity_connection({'twitch':'connected', 'twitch_events':'Follows: ready · Raids: ready'})
        self.assertEqual(result['level'], 'ready')
        self.assertIn('not automatically recovered', result['detail'])
        self.assertEqual(activity_connection({'twitch':'connected'})['level'], 'attention')

    def test_one_platform_offline_and_paused_readers_stay_visible(self):
        result=activity_connection({'twitch':'connected','twitch_events':'Follows: ready', 'tiktok':'Offline or TikTok connection unavailable; retrying.'})
        self.assertEqual(result['level'],'attention')
        self.assertIn('TikTok',result['message'])
        result=activity_connection({'tiktok':'Connected; reading LIVE chat and events (experimental, receive-only).'}, {'tiktok'})
        self.assertEqual(result['level'],'attention')
        self.assertIn('Paused',result['platforms'][0]['message'])

    def test_saved_disconnected_account_not_hidden_by_another_connected_platform(self):
        result=activity_connection({'twitch':'not connected','youtube':'connected'}, configured={'twitch':{}})
        self.assertEqual(result['level'],'attention')
        self.assertIn('Twitch',result['message'])
        self.assertEqual(len(result['platforms']),2)
