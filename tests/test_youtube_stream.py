import asyncio
from datetime import datetime, timezone
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import grpc
from forgecast.chat import YouTube, ApiError
from forgecast.core import ChatStore
from forgecast.youtube_stream import proto, response_dict, stream_responses, stream_error, quota_retry_seconds, METHOD
from forgecast.server import (State, sync_hub_accounts, kick_delivery_status,
                             kick_waiting_status, accept_kick_rows, ensure_kick_subscription)


async def until(check):
    async def wait():
        while not check(): await asyncio.sleep(.01)
    await asyncio.wait_for(wait(), 4)


class FakeError(grpc.RpcError):
    def __init__(self, code, details=''): self._code,self._details=code,details
    def code(self): return self._code
    def details(self): return self._details


class YouTubeStreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store=ChatStore();self.statuses=[]
        self.adapter=YouTube(None, {'live_chat_id':'chat-one','channel_name':'Deco'}, 'PRIVATE',
                             self.store, lambda *x:self.statuses.append(x))
        self.tasks=[]
    async def asyncTearDown(self):
        for task in self.tasks: task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
    def start(self):
        task=asyncio.create_task(self.adapter.run());self.tasks.append(task);return task
    def test_conversion_preserves_author_event_and_resume_fields(self):
        response=proto.LiveChatMessageListResponse(next_page_token='cursor')
        row=response.items.add(id='hello')
        row.snippet.type=15;row.snippet.live_chat_id='chat';row.snippet.display_message='Thank you!'
        row.snippet.super_chat_details.amount_micros=2000000
        row.author_details.channel_id='viewer';row.author_details.display_name='Viewer';row.author_details.is_chat_moderator=True
        data=response_dict(response)
        self.assertEqual(data['nextPageToken'],'cursor')
        self.assertEqual(data['items'][0]['snippet']['type'],'superChatEvent')
        self.adapter.receive(data['items'][0])
        self.assertEqual(self.store.messages[0]['kind'],'superchat')
        self.assertIn('isChatModerator',self.store.messages[0]['badges'])
    def test_quota_reset_tracks_pacific_dst(self):
        # October midnight Pacific is 07:00 UTC; January is 08:00 UTC.
        for now, seconds in [(datetime(2026,10,9,6,0,tzinfo=timezone.utc),3660),
                             (datetime(2026,1,9,7,0,tzinfo=timezone.utc),3660)]:
            self.assertEqual(quota_retry_seconds(now),seconds)
    def test_error_classification_never_returns_rpc_details(self):
        for code,reason in [(grpc.StatusCode.UNAUTHENTICATED,'authorization'),
                            (grpc.StatusCode.PERMISSION_DENIED,'permission'),
                            (grpc.StatusCode.FAILED_PRECONDITION,'ended_or_disabled'),
                            (grpc.StatusCode.UNAVAILABLE,'network')]:
            self.assertEqual(stream_error(FakeError(code,'Bearer SECRET https://private.example')),reason)
        self.assertEqual(stream_error(FakeError(grpc.StatusCode.RESOURCE_EXHAUSTED,'daily quota exhausted')),'quota')
        self.assertEqual(stream_error(FakeError(grpc.StatusCode.RESOURCE_EXHAUSTED,'rate limit')),'limit')
    async def test_real_grpc_serialization_and_oauth_metadata(self):
        captured=[]
        async def handler(request,context):
            captured.append((request,dict(context.invocation_metadata())))
            yield proto.LiveChatMessageListResponse(next_page_token='resumed')
        server=grpc.aio.server()
        service=grpc.method_handlers_generic_handler('youtube.api.v3.V3DataLiveChatMessageService',
            {'StreamList':grpc.unary_stream_rpc_method_handler(handler,
                request_deserializer=proto.LiveChatMessageListRequest.FromString,
                response_serializer=proto.LiveChatMessageListResponse.SerializeToString)})
        server.add_generic_rpc_handlers((service,))
        port=server.add_insecure_port('127.0.0.1:0');await server.start()
        def local_channel(*args,**kwargs):
            self.assertEqual(args[0],'youtube.googleapis.com:443')
            return grpc.aio.insecure_channel(f'127.0.0.1:{port}')
        try:
            with patch('forgecast.youtube_stream.grpc.aio.secure_channel',local_channel):
                rows=[r async for r in stream_responses('chat','PRIVATE','saved-cursor')]
            self.assertEqual(rows,[{'nextPageToken':'resumed'}])
            request,headers=captured[0]
            self.assertEqual(request.live_chat_id,'chat');self.assertEqual(request.page_token,'saved-cursor')
            self.assertEqual(list(request.part),['id','snippet','authorDetails'])
            self.assertEqual(headers['authorization'],'Bearer PRIVATE')
            self.assertEqual(METHOD,'/youtube.api.v3.V3DataLiveChatMessageService/StreamList')
        finally: await server.stop(None)
    async def test_idle_stream_keeps_one_connection_and_cancels_cleanly(self):
        calls=[];closed=[]
        async def source(*args):
            calls.append(args)
            try:
                yield {'nextPageToken':'cursor','items':[]}
                await asyncio.Event().wait()
            finally: closed.append(True)
        with patch('forgecast.youtube_stream.stream_responses',source):
            task=self.start();await until(lambda:self.statuses and self.statuses[-1][1]=='connected')
            await asyncio.sleep(.05)
            self.assertEqual(len(calls),1)
            task.cancel();await asyncio.gather(task,return_exceptions=True)
            self.assertEqual(closed,[True])
    async def test_refresh_resumes_cursor_broadcast_change_resets_it(self):
        calls=[];closed=[]
        async def source(*args):
            calls.append(args)
            try:
                yield {'nextPageToken':'resume-one','items':[]}
                await asyncio.Event().wait()
            finally: closed.append(args[0])
        with patch('forgecast.youtube_stream.stream_responses',source):
            self.start();await until(lambda:self.statuses and self.statuses[-1][1]=='connected')
            self.adapter.token='FRESH';await until(lambda:len(calls)==2)
            self.assertEqual(calls[1],('chat-one','FRESH','resume-one'))
            await until(lambda:self.statuses[-1][1]=='connected')
            self.adapter.config['live_chat_id']='chat-two';await until(lambda:len(calls)==3)
            self.assertEqual(calls[2],('chat-two','FRESH',None))
            self.assertEqual(closed,['chat-one','chat-one'])
    async def test_quota_error_pauses_until_reset_without_polling(self):
        calls=[]
        async def source(*args):
            calls.append(args)
            raise FakeError(grpc.StatusCode.RESOURCE_EXHAUSTED,'daily quota: PRIVATE')
            yield {}
        with patch('forgecast.youtube_stream.stream_responses',source):
            self.start();await until(lambda:self.adapter.quota_paused)
            self.assertGreater(self.adapter.retry_at,time.monotonic()+60)
            await asyncio.sleep(.05);self.assertEqual(len(calls),1)
            self.assertIn('daily reset',self.statuses[-1][1]);self.assertNotIn('PRIVATE',self.statuses[-1][1])
    async def test_end_event_waits_for_next_broadcast(self):
        async def source(*args):
            yield {'items':[{'id':'end','snippet':{'type':'chatEndedEvent'}}]}
        with patch('forgecast.youtube_stream.stream_responses',source):
            self.start();await until(lambda:not self.adapter.config['live_chat_id'])
            self.assertFalse(self.store.messages)
            self.assertIn('Broadcast ended',self.statuses[-1][1])
    def test_tombstone_removes_prior_message(self):
        self.adapter.receive({'id':'one','snippet':{'type':'textMessageEvent','displayMessage':'hello'}})
        self.adapter.receive({'id':'one','snippet':{'type':'tombstone'}})
        self.assertTrue(self.store.messages[0]['deleted'])


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=State(self.temp.name,demo=True)
        self.s.config.update(hub_url='https://hub.example',kick={'channel_id':'123'})
        self.s.vault.set('hub_token','PRIVATE')
    async def asyncTearDown(self):
        self.temp.cleanup()
    async def test_optional_diagnostics_missing_does_not_break_old_hubs(self):
        with patch('forgecast.server.api',AsyncMock(side_effect=ApiError('not found',404))):
            await kick_delivery_status(self.s,'https://hub.example','PRIVATE')
        self.assertEqual(self.s.kick_delivery,'unknown')
        self.assertIn('verification logs',kick_waiting_status(self.s))
    async def test_diagnostics_receipt_is_not_companion_delivery(self):
        with patch('forgecast.server.api',AsyncMock(return_value={'delivery_verified':True})):
            await kick_delivery_status(self.s,'https://hub.example','PRIVATE')
        self.assertIn('Hub has received',kick_waiting_status(self.s))
        self.assertNotEqual(kick_waiting_status(self.s),'connected')
        self.s.kick_received=1;self.assertEqual(kick_waiting_status(self.s),'connected')
    async def test_invalid_relay_warning_not_overwritten_by_subscription_ready(self):
        self.s.kick_verified=True
        accept_kick_rows(self.s,{'messages':[{'id':1,'payload':{}}]})
        self.assertIn('invalid chat',kick_waiting_status(self.s))
    async def test_wrong_method_does_not_count_as_webhook_subscription(self):
        request=AsyncMock(side_effect=[{'data':[{'event':'chat.message.sent','broadcaster_user_id':123,
                    'method':'websocket','subscription_id':'wrong'}]},
                    {'data':[{'name':'chat.message.sent','subscription_id':'new'}]}])
        with patch('forgecast.server.api',request): await ensure_kick_subscription(self.s,'PRIVATE','123')
        self.assertEqual(request.await_count,2)
    async def test_daily_quota_hold_skips_broadcast_enumeration_even_on_sync(self):
        adapter=YouTube(None,{'live_chat_id':'','account_id':'creator'},'PRIVATE',self.s.chat,self.s.status)
        adapter.quota_paused=True;adapter.retry_at=time.monotonic()+100
        adapter.task=asyncio.create_task(asyncio.Event().wait());self.s.adapters['youtube']=adapter
        request=AsyncMock(return_value={'connections':[{'platform':'youtube','user_id':'creator','access_token':'FRESH'}]})
        try:
            with patch('forgecast.server.api',request): await sync_hub_accounts(self.s,retry_events=True)
            self.assertEqual(request.await_count,1);self.assertEqual(adapter.token,'FRESH')
            self.assertTrue(adapter.quota_paused)
        finally: adapter.task.cancel();await asyncio.gather(adapter.task,return_exceptions=True)
