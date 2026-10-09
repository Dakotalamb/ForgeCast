import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from forgecast.chat import ApiError, api
from forgecast.core import ChatStore, twitch_message
from forgecast.server import State, sync_hub_accounts, ensure_kick_subscription, accept_kick_rows
from test_chat import Response, Session

class ReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = State(self.temp.name, demo=True)
        self.state.config['hub_url'] = 'https://hub.example.com'
        self.state.vault.set('hub_token', 'PRIVATE-HUB-TOKEN')
        async def idle(*args):
            await asyncio.Event().wait()
            yield {}
        self.stream_patch = patch('forgecast.youtube_stream.stream_responses', idle)
        self.stream_patch.start()
    async def asyncTearDown(self):
        for adapter in self.state.adapters.values():
            adapter.task.cancel()
            await asyncio.gather(adapter.task, return_exceptions=True)
        self.temp.cleanup()
        self.stream_patch.stop()
    async def test_youtube_finds_broadcast_after_pairing_before_live(self):
        account = {'platform':'youtube','user_id':'creator','username':'Deco','access_token':'TOKEN-ONE'}
        with patch('forgecast.server.api', AsyncMock(side_effect=[{'connections':[account]}, {'items':[]}])):
            await sync_hub_accounts(self.state)
        adapter = self.state.adapters['youtube']
        self.assertEqual(adapter.config['live_chat_id'], '')
        self.assertIn('Waiting', self.state.statuses['youtube'])
        with patch('forgecast.server.api', AsyncMock(side_effect=[
                {'connections':[{**account,'access_token':'TOKEN-TWO'}]},
                {'items':[{'snippet':{'liveChatId':'NEW-CHAT'}}]}])):
            await sync_hub_accounts(self.state)
        self.assertIs(self.state.adapters['youtube'], adapter)
        self.assertEqual(adapter.config['live_chat_id'], 'NEW-CHAT')
        self.assertEqual(adapter.token, 'TOKEN-TWO')
        self.assertEqual(self.state.vault.get('youtube_token'), 'TOKEN-TWO')
        self.assertNotIn('TOKEN-TWO', str(self.state.public()))
    async def test_account_failure_does_not_prevent_other_platform_setup(self):
        accounts = {'connections':[{'platform':'twitch','access_token':'INVALID','user_id':'missing-client'},
                                   {'platform':'youtube','access_token':'YT','user_id':'creator'}]}
        with patch('forgecast.server.api', AsyncMock(side_effect=[accounts, {'items':[]}])):
            await sync_hub_accounts(self.state)
        self.assertIn('identity', self.state.statuses['twitch'])
        self.assertIn('youtube', self.state.adapters)
    async def test_kick_reuses_subscription_without_claiming_delivery(self):
        request = AsyncMock(return_value={'data':[{'event':'chat.message.sent','broadcaster_user_id':123,
                                                  'method':'webhook','subscription_id':'sub-123'}]})
        with patch('forgecast.server.api', request):
            await ensure_kick_subscription(self.state, 'TOKEN', '123')
        self.assertEqual(request.await_count, 1)
        self.assertTrue(self.state.kick_verified)
        self.assertNotEqual(self.state.statuses['kick'], 'connected')
    async def test_kick_failed_subscription_is_not_ready(self):
        request = AsyncMock(side_effect=[{'data':[]}, {'data':[{'name':'chat.message.sent','error':'denied'}]}])
        with patch('forgecast.server.api', request):
            with self.assertRaises(ValueError): await ensure_kick_subscription(self.state, 'TOKEN', '123')
        self.assertFalse(self.state.kick_verified)
    async def test_kick_channel_filter_and_invalid_row_cursor(self):
        self.state.config['kick'] = {'channel_id':'123'}
        payload = {'broadcaster':{'user_id':123},'sender':{'user_id':2,'username':'Viewer'},'message_id':'hello','content':'hi'}
        accept_kick_rows(self.state, {'messages':[{'id':1,'payload':{**payload,'broadcaster':{'user_id':999}}},
            {'id':2,'payload':{'broadcaster':{'user_id':123}}}, {'id':3,'payload':payload}]})
        self.assertEqual(self.state.kick_after, 3)
        self.assertEqual(len(self.state.chat.messages), 1)
        self.assertEqual(self.state.statuses['kick'], 'connected')
    async def test_safe_api_reason_and_media_host_validation(self):
        response = Response(403, {'error':{'errors':[{'reason':'quotaExceeded','message':'SECRET-TOKEN'}]}})
        with self.assertRaises(ApiError) as caught: await api(Session(response), 'GET', 'https://example.com')
        self.assertEqual(caught.exception.reason, 'quotaExceeded')
        self.assertNotIn('SECRET-TOKEN', str(caught.exception))
        for url in ['https://localhost/x','https://files.kick.com.evil.test/x','https://TOKEN@files.kick.com/x',
                    'https://files.kick.com:bad/x','http://files.kick.com/x']:
            self.assertEqual(self.state.media_url(url), '')
    async def test_deleted_emote_message_clears_fragments(self):
        event = dict(broadcaster_user_id='1', message_id='1', chatter_user_id='2', chatter_user_name='Viewer',
                     message={'text':'Kappa','fragments':[{'text':'Kappa','emote':{'id':'25'}}]})
        message = twitch_message(event)
        self.assertIn('image', message['fragments'][0])
        store = ChatStore(); store.add(message); store.delete('twitch', message_id='1')
        self.assertEqual(message['fragments'], [{'text':'[Message removed]'}])

