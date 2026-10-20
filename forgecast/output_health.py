"""Bounded, runtime-only transport evidence. Sending is not viewer playback."""
import math
import time

STATES = {'offline', 'starting', 'sending', 'stalled', 'reconnecting', 'stopping', 'error'}


class OutputMonitor:
    def __init__(self):
        self.previous = {}

    def sample(self, rows, now=None):
        now = time.monotonic() if now is None else now
        clean = []
        keep = set()
        for raw in rows[:9]:
            if not isinstance(raw, dict) or not isinstance(raw.get('id'), str): continue
            uid = raw['id'][:80]
            if uid in keep: continue
            keep.add(uid)
            row = {k: v for k, v in raw.items() if k in {'id','name','active','busy','reconnecting','intentional_stop','error','detail','picture','vertical_supported','bytes','frames','dropped','width','height','fps_num','fps_den'}}
            row['id'] = uid
            for k in ('bytes','frames','dropped','width','height','fps_num','fps_den'):
                v = row.get(k, 0)
                row[k] = int(v) if isinstance(v, (int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0 <= v <= 2**63-1 else 0
            before = self.previous.get(uid)
            # A gap, reconnect, counter reset or a new activation starts a new baseline.
            reset = (not before or now-before['at'] > 5 or now <= before['at'] or
                     not before['row'].get('active') or before['row'].get('reconnecting') or
                     row['bytes'] < before['row']['bytes'] or row['frames'] < before['row']['frames'])
            since = now if reset else before['since']
            progress = None if reset else before['progress']
            rate = None
            if row.get('active') and not row.get('reconnecting') and not reset:
                sent = row['bytes']-before['row']['bytes']
                rate = round(sent*8/(now-before['at'])/1000)
                if sent > 0: progress = now
            if row.get('error') and not row.get('active'): status = 'error'
            elif row.get('reconnecting'): status = 'reconnecting'
            elif not row.get('active'): status = 'stopping' if row.get('busy') else 'offline'
            elif progress is not None and now-progress < 5: status = 'sending'
            elif now-(progress if progress is not None else since) >= 5: status = 'stalled'
            else: status = 'starting'
            row.update(transmission_state=status, bitrate_kbps=rate,
                       delivery_note='Sending bytes does not verify platform publication or viewer playback.')
            self.previous[uid] = dict(row=row.copy(),at=now,since=since,progress=progress)
            clean.append(row)
        self.previous = {k: v for k,v in self.previous.items() if k in keep}
        return clean
