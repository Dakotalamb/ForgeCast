import asyncio
import unittest
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
from forgecast.obs import ObsClient, auth_response


class ObsTests(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_request_event_and_failure(self):
        async def fake_obs(request):
            ws=web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({'op':0,'d':{'rpcVersion':1,'authentication':{'salt':'salt','challenge':'challenge'}}})
            identify=await ws.receive_json()
            self.assertEqual(identify['d']['authentication'],auth_response('password','salt','challenge'))
            await ws.send_json({'op':2,'d':{'negotiatedRpcVersion':1}})
            await ws.send_json({'op':5,'d':{'eventType':'CurrentProgramSceneChanged','eventData':{'sceneName':'Test'}}})
            async for msg in ws:
                d=msg.json()['d']
                await ws.send_json({'op':7,'d':{'requestId':d['requestId'],'requestStatus':{'result':d['requestType']=='GetStats','code':100},'responseData':{'activeFps':60}}})
            return ws
        app=web.Application()
        app.router.add_get('/',fake_obs)
        server=TestServer(app)
        await server.start_server()
        try:
            async with ClientSession() as session:
                events=[]
                client=ObsClient(session,events.append)
                await client.connect(server.port,'password')
                result=await client.request('GetStats')
                self.assertEqual(result['activeFps'],60)
                self.assertEqual(events[0]['eventData']['sceneName'],'Test')
                with self.assertRaises(RuntimeError):await client.request('Unknown')
                await client.close()
                self.assertFalse(client.connected)
                with self.assertRaises(ConnectionError):await client.request('GetStats')
        finally:
            await server.close()
