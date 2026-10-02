import unittest
from forgecast.chat import Twitch, YouTube, ApiError, api
from forgecast.core import ChatStore


class Response:
    def __init__(self,status=200,data=None):self.status=status;self.data=data
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def json(self):return self.data


class Session:
    def __init__(self,response):self.response=response;self.calls=[]
    def request(self,*args,**kwargs):self.calls.append((args,kwargs));return self.response


class ChatApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_does_not_leak_body_or_token(self):
        session=Session(Response(401,{'access_token':'SECRET'}))
        with self.assertRaises(ApiError) as caught:
            await api(session,'GET','https://example.com',headers={'Authorization':'Bearer SECRET'})
        self.assertNotIn('SECRET',str(caught.exception))
        self.assertFalse(session.calls[0][1]['allow_redirects'])

    async def test_twitch_token_owner_validation(self):
        session=Session(Response(data={'client_id':'wrong','user_id':'u','scopes':['user:read:chat']}))
        adapter=Twitch(session,{'client_id':'right','user_id':'u','channel_id':'c'},'TOKEN',ChatStore(),lambda *x:None)
        with self.assertRaises(ApiError):await adapter.validate()

    async def test_twitch_missing_scope(self):
        session=Session(Response(data={'client_id':'a','user_id':'u','scopes':[]}))
        adapter=Twitch(session,{'client_id':'a','user_id':'u','channel_id':'c'},'TOKEN',ChatStore(),lambda *x:None)
        with self.assertRaises(ApiError):await adapter.validate()

    async def test_twitch_send_delivery_failure(self):
        session=Session(Response(data={'data':[{'is_sent':False}]}))
        adapter=Twitch(session,{'client_id':'a','user_id':'u','channel_id':'c'},'TOKEN',ChatStore(),lambda *x:None)
        with self.assertRaises(ApiError):await adapter.send('hello')
        self.assertEqual(session.calls[0][1]['json']['broadcaster_id'],'c')

    async def test_youtube_destination(self):
        session=Session(Response(data={}))
        adapter=YouTube(session,{'live_chat_id':'configured-chat'},'TOKEN',ChatStore(),lambda *x:None)
        await adapter.send('hello')
        self.assertEqual(session.calls[0][1]['json']['snippet']['liveChatId'],'configured-chat')

    async def test_redemptions_require_broadcaster_permission(self):
        status=[]
        session=Session(Response(data={}))
        adapter=Twitch(session,{'client_id':'a','user_id':'u','channel_id':'u'},'TOKEN',ChatStore(),lambda *x:status.append(x))
        await adapter.subscribe_redemptions('session')
        self.assertEqual(session.calls,[])
        self.assertIn('channel:read:redemptions',status[-1][1])
        adapter.scopes={'channel:read:redemptions'}
        await adapter.subscribe_redemptions('session')
        body=session.calls[-1][1]['json']
        self.assertEqual(body['condition'],{'broadcaster_user_id':'u'})
        self.assertEqual(body['type'],'channel.channel_points_custom_reward_redemption.add')

    async def test_redemption_denied_does_not_break_chat(self):
        status=[]
        adapter=Twitch(Session(Response(403,{})),{'client_id':'a','user_id':'u','channel_id':'u'},'TOKEN',ChatStore(),lambda *x:status.append(x))
        adapter.scopes={'channel:read:redemptions'}
        await adapter.subscribe_redemptions('session')
        self.assertIn('denied',status[-1][1])

    async def test_redemption_is_event_and_duplicates_merge(self):
        store=ChatStore()
        adapter=Twitch(None,{},'TOKEN',store,lambda *x:None)
        event={'id':'redeem1','broadcaster_user_id':'u','broadcaster_user_name':'Deco','user_name':'Viewer','reward':{'title':'Hydrate'}}
        for _ in range(2):adapter.handle('channel.channel_points_custom_reward_redemption.add',event)
        self.assertEqual(len(store.messages),1)
        self.assertEqual(store.messages[0]['kind'],'redeem')
        self.assertEqual(store.messages[0]['text'],'Redeemed Hydrate')
