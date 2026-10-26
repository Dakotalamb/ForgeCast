"""Bounded TikTok LIVE activity normalization; no broadcast or account control."""
from collections import OrderedDict
import hashlib
import time
from .extra_chat import message


class TikTokEvents:
    def __init__(self, username, store, clock=time.time):
        self.username, self.store, self.clock = username, store, clock
        self.seen = OrderedDict()
        self.pending = {}  # At most one summary per kind and room (current LIVE only).
        self.room = ''

    def accept(self, kind, event):
        common = getattr(event, 'common', None)
        mid = str(getattr(common, 'msg_id', '') or '')
        room = str(getattr(common, 'room_id', '') or '')
        user = getattr(event, 'user', None)
        if not mid or mid == '0' or not room or room == '0' or not user:
            return  # No stable identity: do not invent events from incomplete data.
        uid = str(getattr(user, 'unique_id', '') or getattr(user, 'id', '') or '')[:100]
        name = str(getattr(user, 'nickname', '') or uid or 'Viewer')[:100]
        count, text = 1, ''
        identity = kind+':'+mid
        if kind == 'tiktok_gift':
            gift = getattr(event, 'gift', None)
            if gift is None: return
            streakable = getattr(gift, 'type', 0) == 1
            if streakable and getattr(event, 'repeat_end', 0) != 1: return
            count = max(1, min(1000000, int(getattr(event, 'repeat_count', 1) or 1)))
            group = getattr(event, 'group_id', 0)
            if streakable and group:
                identity = f'gift-streak:{uid}:{getattr(event,"gift_id",0)}:{group}'
            title = str(getattr(gift, 'name', '') or 'gift')[:120]
            text = f'Sent {count} × {title}'
        elif kind == 'follow': text = 'Followed on TikTok'
        elif kind == 'subscription': text = 'TikTok subscription notification'
        elif kind == 'like':
            count = max(0, min(1000000, int(getattr(event, 'count', 0) or 0)))
            if not count: return
        elif kind == 'share': pass  # One observed share notification, not a cumulative total.
        else: return
        digest = hashlib.sha256((room+':'+identity).encode()).hexdigest()
        row_id = 'tiktok:'+self.username+':activity:'+digest
        if row_id in self.seen or row_id in self.store.seen or hashlib.sha256(row_id.encode()).hexdigest() in self.store.persistent_seen:
            return
        self.seen[row_id] = True
        if len(self.seen) > 10000: self.seen.popitem(last=False)
        if self.room and room != self.room: self.flush(force=True)
        self.room = room
        now = self.clock()
        if kind in ('like', 'share'):
            self.flush()
            if kind not in self.pending:
                # First packet's stable ID keeps a summary distinct across restarts.
                self.pending[kind] = dict(id=row_id, room=room, count=0, time=now)
            self.pending[kind]['count'] = min(1000000000, self.pending[kind]['count']+count)
            return
        row = message('tiktok', self.username, name, text, 'activity:'+digest, user_id=uid)
        row.update(kind=kind, count=count, time=now)
        self.store.add(row)

    def flush(self, force=False):
        now = self.clock()
        for kind, pending in list(self.pending.items()):
            if not force and now-pending['time'] < 10: continue
            count = pending['count']
            text = f'{count} '+('likes' if kind == 'like' else 'share notifications')+' received on TikTok LIVE'
            row = message('tiktok', self.username, 'TikTok LIVE', text, pending['id'].split(':activity:',1)[1])
            row['id'] = pending['id']
            row.update(kind=kind, count=count, time=now)
            self.store.add(row)
            del self.pending[kind]
