"""Receive-only Hub relay. No Meta credentials leave the Hub."""
import asyncio
import hashlib
import json
from aiohttp import ClientTimeout
import random
import re
import time
from datetime import datetime
from .chat import ApiError
from .core import username_color

PLATFORMS = ('facebook', 'instagram')
ACTIVE = {'waiting_for_live', 'receiving_comments', 'retrying'}
STATES = ACTIVE | {'disconnected', 'disabled', 'setup_required', 'authorization_needed', 'permission_denied'}
LABELS = {'waiting_for_live':'Waiting for a live broadcast (receive-only).',
          'receiving_comments':'Connected; receiving live comments (receive-only).',
          'retrying':'Hub is retrying live chat; no need to reconnect yet.',
          'disconnected':'Not connected. Connect this account in Hub Settings.',
          'disabled':'Chat is disabled on the Hub.', 'setup_required':'Hub chat setup is incomplete.',
          'authorization_needed':'Reconnect this account in Hub Settings.',
          'permission_denied':'Hub lacks permission to read this account’s live comments.'}

def cursor(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,18}', value):
        raise ValueError('Invalid relay cursor')
    return int(value)

def identity(value):
    return isinstance(value, str) and 0 < len(value) <= 200

async def relay_request(session, url, **kwargs):
    async with session.get(url, allow_redirects=False, timeout=ClientTimeout(total=15), **kwargs) as response:
        if response.status != 200:
            error = ApiError('Hub chat request failed.', response.status)
            try: error.retry_after = max(5, min(120, float(response.headers.get('Retry-After', '5'))))
            except ValueError: error.retry_after = 5
            raise error
        chunks, size = [], 0
        async for chunk in response.content.iter_chunked(65536):
            size += len(chunk)
            if size > 2000000: raise ValueError('Relay response too large')
            chunks.append(chunk)
        return json.loads(b''.join(chunks))

class MetaChat:
    def __init__(self, state):
        self.s = state
        self.readers = {}
        self.scope = None
        self.unauthorized = False
        self.tasks = {}
        self.rediscover = False

    def pairing(self):
        token = self.s.vault.get('hub_token') or ''
        return (self.s.config.get('hub_url', ''), hashlib.sha256(token.encode()).hexdigest())

    def clear(self, platform):
        s = self.s
        removed = {m['id'] for m in s.chat.messages if m['platform'] == platform}
        s.chat.messages = type(s.chat.messages)((m for m in s.chat.messages if m['platform'] != platform), maxlen=s.chat.messages.maxlen)
        for mid in list(s.chat.seen):
            if mid.startswith(platform+':'): s.chat.seen.pop(mid, None)
        s.highlight_ids = type(s.highlight_ids)((mid for mid in s.highlight_ids if mid not in removed), maxlen=s.highlight_ids.maxlen)

    def reset(self):
        for p in PLATFORMS:
            self.clear(p)
            self.s.status(p, 'Not checked. Sync linked accounts to check this Hub pairing (receive-only).')
        self.readers.clear()
        self.scope = self.pairing()
        self.unauthorized = False

    def describe(self, p, descriptor):
        if not isinstance(descriptor, dict) or descriptor.get('platform') != p:
            raise ValueError('Invalid relay connection')
        state = descriptor.get('state')
        if state not in STATES: raise ValueError('Unknown relay state')
        old = self.readers.get(p)
        scope = (descriptor.get('account_id'), descriptor.get('generation'))
        if not old or old['scope'] != scope:
            self.clear(p)
            old = {'scope':scope, 'after':'0', 'due':0, 'failures':0}
            self.readers[p] = old
        if state in ACTIVE and not all(identity(x) for x in scope):
            raise ValueError('Missing relay identity')
        # Discovery explicitly gates configured/enabled connections. Feed descriptors
        # omit these booleans; discovery has already authorized that reader.
        if descriptor.get('enabled') is False: state = 'disabled'
        elif descriptor.get('configured') is False: state = 'setup_required'
        old['state'] = state
        old['username'] = str(descriptor.get('username') or p.title())[:100]
        if state not in ACTIVE:
            self.clear(p)
            old['after'] = '0'
        self.s.status(p, LABELS[state])
        return old

    def discover(self, rows):
        if self.scope != self.pairing(): self.reset()
        if self.unauthorized: return
        if not isinstance(rows, list): rows = []
        for p in PLATFORMS:
            if p in self.s.paused_platforms: continue
            matches = [r for r in rows if isinstance(r, dict) and r.get('platform') == p]
            row = matches[0] if len(matches) == 1 else {'platform':p, 'state':'setup_required'}
            if row.get('state') in ACTIVE and (row.get('enabled') is not True or row.get('configured') is not True):
                row = {'platform':p, 'state':'setup_required'}
            try: self.describe(p, row)
            except ValueError:
                self.describe(p, {'platform':p, 'state':'setup_required'})

    def ingest(self, p, result, expected):
        if not isinstance(result, dict) or result.get('schema_version') != 1 or result.get('platform') != p:
            raise ValueError('Invalid relay schema')
        descriptor = result.get('connection')
        if not isinstance(descriptor, dict): raise ValueError('Invalid relay connection')
        if descriptor.get('state') in ACTIVE and (descriptor.get('account_id'), descriptor.get('generation')) != expected:
            self.clear(p)
            self.readers.pop(p, None)
            self.rediscover = True
            return False
        reader = self.describe(p, descriptor)
        if reader['scope'] != expected or reader['state'] not in ACTIVE: return False
        rows = result.get('messages')
        if not isinstance(rows, list) or len(rows) > 100: raise ValueError('Invalid relay messages')
        after = cursor(reader['after'])
        next_value = cursor(result.get('next_cursor'))
        normalized = []
        for row in rows:
            if not isinstance(row, dict): raise ValueError('Invalid relay message')
            value = cursor(row.get('cursor'))
            if value <= after: raise ValueError('Unordered relay page')
            if (row.get('platform') != p or row.get('account_id') != expected[0] or
                row.get('broadcaster_id') != expected[0] or row.get('generation') != expected[1]):
                raise ValueError('Relay account mismatch')
            mid, broadcast, text = row.get('message_id'), row.get('broadcast_id'), row.get('text')
            author = row.get('author')
            if not identity(mid) or not identity(broadcast) or not isinstance(text, str) or len(text) > 10000 or not isinstance(author, dict):
                raise ValueError('Invalid relay content')
            name, uid = author.get('name') or 'Viewer', author.get('id') or ''
            if not isinstance(name, str) or not isinstance(uid, str): raise ValueError('Invalid relay author')
            stamp = row.get('timestamp')
            if not isinstance(stamp, str) or len(stamp) > 50: raise ValueError('Invalid relay timestamp')
            stamp = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if stamp.tzinfo is None: raise ValueError('Relay timestamp needs timezone')
            key = hashlib.sha256((':'.join([p, *expected, mid])).encode()).hexdigest()
            normalized.append(dict(id=p+':'+key, platform=p, origin_id=expected[0], origin=reader['username'],
                received_in=expected[0], platform_message_id=mid, broadcast_id=broadcast,
                account_id=expected[0], generation=expected[1], user_id=uid[:200], user=name[:100],
                text=text, fragments=[{'text':text}], badges=[], shared=False, kind='chat',
                color=username_color(p, uid or name), time=stamp.timestamp()))
            after = value
        if next_value != after: raise ValueError('Invalid next cursor')
        # Validate the entire page before inserting anything or advancing the cursor.
        for message in normalized: self.s.chat.add(message)
        reader['after'] = str(next_value)
        delay = result.get('retry_after_ms', 5000)
        if type(delay) is not int: delay = 5000
        reader['due'] = time.monotonic() + max(1, min(120, delay/1000))
        reader['failures'] = 0
        if len(rows) == 100 and next_value > 0: reader['due'] = time.monotonic()
        return True

    async def poll(self, p):
        s, reader = self.s, self.readers[p]
        scope, expected = self.scope, reader['scope']
        try:
            result = await relay_request(s.session, scope[0]+'/api/forgecast/v1/chat',
                headers={'Authorization':'Bearer '+s.vault.get('hub_token')},
                params={'platform':p, 'after':reader['after']})
            async with s.lock:
                if not self.unauthorized and self.scope == scope and self.pairing() == scope and self.readers.get(p) is reader and p not in s.paused_platforms:
                    self.ingest(p, result, expected)
        except asyncio.CancelledError: raise
        except Exception as exc:
            if self.scope != scope or self.pairing() != scope or self.readers.get(p) is not reader: return
            if isinstance(exc, ApiError) and exc.status == 401:
                self.unauthorized = True
                for platform in PLATFORMS:
                    self.clear(platform)
                    s.status(platform, 'Hub pairing expired or revoked. Repair pairing, then Sync linked accounts.')
                return
            reader['failures'] = min(reader['failures']+1, 6)
            reader['due'] = time.monotonic()+min(120, max(getattr(exc, 'retry_after', 5), 5*2**reader['failures'])*random.uniform(1, 1.2))
            s.status(p, 'Live chat relay unavailable; retrying automatically.')

    async def run(self):
        try:
            while True:
                if self.scope != self.pairing(): self.reset()
                for p, reader in list(self.readers.items()):
                    if (not self.unauthorized and reader['state'] in ACTIVE and p not in self.s.paused_platforms
                        and time.monotonic() >= reader['due'] and (p not in self.tasks or self.tasks[p].done())):
                        self.tasks[p] = asyncio.create_task(self.poll(p))
                await asyncio.sleep(.25)
        finally:
            for task in self.tasks.values(): task.cancel()
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
