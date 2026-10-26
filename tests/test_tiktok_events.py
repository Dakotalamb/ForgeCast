import asyncio
import tempfile
import unittest
from TikTokLive.events import FollowEvent, GiftEvent, LikeEvent, ShareEvent, SubNotifyEvent, ConnectEvent
from TikTokLive.proto.custom_proto import ExtendedUser
from TikTokLiveProto.v3.webcast.model import Gift
from TikTokLiveProto.v3.webcast.shared.message import CommonMessageData
from forgecast.core import ChatStore
from forgecast.extra_chat import TikTok
from forgecast.tiktok_events import TikTokEvents
from forgecast.server import State, combined_events
from forgecast.operations import suite_action


def event(cls, mid=1, room=20, **kw):
    return cls(common=CommonMessageData(msg_id=mid, room_id=room),
               user=ExtendedUser(nickname='Viewer', display_id='viewer'), **kw)


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.store = ChatStore()
        self.now = 100
        self.reader = TikTokEvents('creator', self.store, lambda: self.now)

    def test_follow_and_subscription_use_real_proto_and_dedup(self):
        for kind, cls in [('follow', FollowEvent), ('subscription', SubNotifyEvent)]:
            self.reader.accept(kind, event(cls))
            self.reader.accept(kind, event(cls))
        self.assertEqual([r['kind'] for r in self.store.messages], ['follow', 'subscription'])
        self.assertEqual(self.store.messages[0]['user_id'], 'viewer')
        self.reader.accept('follow', event(FollowEvent, room=21))
        self.assertEqual(len(self.store.messages), 3)

    def test_gift_streak_counted_once_and_separate_from_gift_subs(self):
        rose = Gift(name='Rose', type=1)
        for mid, count, end in [(1, 1, 0), (2, 5, 0), (3, 5, 1), (4, 5, 1)]:
            self.reader.accept('tiktok_gift', event(GiftEvent, mid, gift=rose, gift_id=7,
                                                  group_id=8, repeat_count=count, repeat_end=end))
        rows = list(self.store.messages)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['kind'], rows[0]['count'], rows[0]['text']), ('tiktok_gift', 5, 'Sent 5 × Rose'))
        self.reader.accept('tiktok_gift', event(GiftEvent, 5, gift=Gift(name='Star', type=2), repeat_count=2))
        self.assertEqual(len(self.store.messages), 2)

    def test_likes_and_shares_are_bounded_summaries_not_cumulative_totals(self):
        self.reader.accept('like', event(LikeEvent, 1, count=3, total=999))
        self.reader.accept('like', event(LikeEvent, 1, count=3, total=999))
        self.reader.accept('like', event(LikeEvent, 2, count=4, total=1003))
        self.reader.accept('share', event(ShareEvent, 3, share_count=100))
        self.assertFalse(self.store.messages)
        self.now = 111
        self.reader.flush()
        self.assertEqual([(r['kind'], r['count']) for r in self.store.messages], [('like', 7), ('share', 1)])
        self.reader.accept('like', event(LikeEvent, 1, count=3))
        self.reader.flush(force=True)
        self.assertEqual(len(self.store.messages), 2)
        self.assertFalse(self.reader.pending)

    def test_incomplete_events_are_not_invented_and_history_dedup_survives_reader_recreation(self):
        for obj in [event(FollowEvent, 0), event(FollowEvent, room=0), FollowEvent()]:
            self.reader.accept('follow', obj)
        self.assertFalse(self.store.messages)
        self.reader.accept('follow', event(FollowEvent))
        self.store.persistent_seen = {__import__('hashlib').sha256(self.store.messages[0]['id'].encode()).hexdigest()}
        self.store.messages.clear();self.store.seen.clear()
        TikTokEvents('creator', self.store).accept('follow', event(FollowEvent))
        self.assertFalse(self.store.messages)


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_events_reach_filtered_feed_and_history_without_any_obs_or_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            s = State(directory, demo=True)
            activity = TikTokEvents('creator', s.chat)
            activity.accept('follow', event(FollowEvent))
            activity.accept('tiktok_gift', event(GiftEvent, 2, gift=Gift(name='Rose', type=2)))
            activity.accept('subscription', event(SubNotifyEvent, 3))
            self.assertEqual({r['kind'] for r in combined_events(s)}, {'follow', 'tiktok_gift'})
            await suite_action(s, 'event_settings', {'kinds': ['subscription'], 'merge': False})
            self.assertEqual([r['kind'] for r in combined_events(s)], ['subscription'])
            self.assertEqual(combined_events(s)[0]['platform'], 'tiktok')
            self.assertEqual(combined_events(s)[0]['source'], 'TIKTOK · creator')
            self.assertFalse(s.commands)
            self.assertEqual(len(s.audience_history), 3)
            s.demo = False;s.checkpoint()
            restored = State(directory, demo=True)
            self.assertEqual(len(restored.audience_history), 3)
            self.assertNotIn('tiktok', s.adapters)

    async def test_one_receive_only_client_handles_all_events_and_flushes_on_cancel(self):
        ready = asyncio.Event()
        clients = []
        class Client:
            def __init__(self, **kwargs):
                self.callbacks = {};self.closed = False;clients.append(self)
                self.kwargs = kwargs
            def add_listener(self, cls, cb): self.callbacks[cls] = cb
            async def start(self):
                await self.callbacks[ConnectEvent](None)
                for cls in (FollowEvent, SubNotifyEvent, ShareEvent):
                    await self.callbacks[cls](event(cls))
                await self.callbacks[LikeEvent](event(LikeEvent, count=3))
                await self.callbacks[GiftEvent](event(GiftEvent, gift=Gift(name='Star', type=2)))
                ready.set()
                return asyncio.create_task(asyncio.sleep(100))
            async def disconnect(self, **kwargs): self.closed = True
        store = ChatStore()
        adapter = TikTok({'username': 'creator'}, store, lambda *args: None, Client)
        task = asyncio.create_task(adapter.run())
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel();await asyncio.gather(task, return_exceptions=True)
        self.assertEqual({r['kind'] for r in store.messages}, {'follow', 'subscription', 'share', 'like', 'tiktok_gift'})
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].kwargs, {'unique_id': '@creator'})
        self.assertTrue(clients[0].closed)
