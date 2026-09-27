import asyncio
import base64
import hashlib
import uuid
import aiohttp


def auth_response(password, salt, challenge):
    secret = base64.b64encode(hashlib.sha256((password+salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret+challenge).encode()).digest()).decode()


class ObsClient:
    def __init__(self, session, event_callback):
        self.session, self.event_callback = session, event_callback
        self.ws, self.reader = None, None
        self.pending = {}
        self.connected = False

    async def connect(self, port, password):
        await self.close()
        self.ws = await self.session.ws_connect(f'http://127.0.0.1:{port}', heartbeat=20)
        try:
            hello = await asyncio.wait_for(self.ws.receive_json(), 5)
            if hello.get('op') != 0:
                raise RuntimeError('Not an OBS WebSocket v5 server.')
            identify = dict(rpcVersion=1, eventSubscriptions=2047)
            auth = hello['d'].get('authentication')
            if auth:
                identify['authentication'] = auth_response(password, auth['salt'], auth['challenge'])
            await self.ws.send_json(dict(op=1, d=identify))
            reply = await asyncio.wait_for(self.ws.receive_json(), 5)
            if reply.get('op') != 2:
                raise RuntimeError('OBS rejected authentication.')
        except Exception:
            await self.ws.close()
            raise
        self.connected = True
        self.reader = asyncio.create_task(self.read())

    async def read(self):
        try:
            async for frame in self.ws:
                if frame.type != aiohttp.WSMsgType.TEXT:
                    continue
                message = frame.json()
                d = message.get('d', {})
                if message.get('op') == 7:
                    future = self.pending.get(d.get('requestId'))
                    if future and not future.done():
                        if d['requestStatus']['result']:
                            future.set_result(d.get('responseData', {}))
                        else:
                            future.set_exception(RuntimeError('OBS request failed: '+str(d['requestStatus'].get('code'))))
                elif message.get('op') == 5:
                    self.event_callback(d)
        finally:
            self.connected = False
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(ConnectionError('OBS disconnected.'))

    async def request(self, kind, data=None):
        if not self.connected:
            raise ConnectionError('Connect OBS first.')
        rid = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[rid] = future
        try:
            await self.ws.send_json(dict(op=6, d=dict(requestType=kind, requestId=rid, requestData=data or {})))
            return await asyncio.wait_for(future, 8)
        finally:
            self.pending.pop(rid, None)

    async def close(self):
        if self.ws:
            await self.ws.close()
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        self.connected = False
