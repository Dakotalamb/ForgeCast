"""Local readiness, coordination and session views; never platform credentials."""
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse
import time

EVENT_KINDS = {'follow', 'redeem', 'raid', 'subscription', 'gift', 'bits', 'membership', 'superchat', 'supersticker'}
DEFAULT_EVENTS = ['follow', 'redeem', 'raid']


def connection_help(platform, message, hub_url=''):
    lower = message.lower()
    if platform == 'twitch_events' and 'permission' in lower:
        title, steps = 'Twitch needs event permissions', ['Reconnect Twitch in Hub Settings, then Sync linked accounts.', 'If follows are still unavailable, the Hub OAuth app must request moderator:read:followers.', 'Redeems require channel:read:redemptions and an eligible channel with channel points. Raids are independent.']
    elif platform == 'kick' and ('ready' in lower or 'webhook' in lower):
        title, steps = 'Kick is subscribed; delivery is not verified', ['Send a new message in your connected Kick channel.', 'If it stays empty, check the Hub webhook receipt and relay diagnostics. Sync cannot repair a server rejecting signed webhooks.', 'The developer webhook endpoint is /api/forgecast/v1/webhooks/kick on your Hub.']
    elif 'expired' in lower or 'authorization' in lower or 'reconnect' in lower:
        title, steps = 'Sign in again', ['Open Hub Settings and reconnect '+platform.replace('_', ' ').title()+'.', 'Return here and select Sync linked accounts.', 'If authorization expires again, the Hub needs to save and refresh the platform refresh token.']
    elif platform == 'youtube' and ('waiting' in lower or 'broadcast' in lower):
        title, steps = 'YouTube is waiting for live chat', ['Start a broadcast with chat enabled on the authorized YouTube channel.', 'Refresh broadcasts and select the correct live broadcast below.', 'Chat writing requires an authorized write scope; Google branding verification is separate.']
    elif message == 'connected':
        title, steps = 'Connected', ['A connected API does not verify your stream picture or sound. Check the platform dashboard.']
    else:
        title, steps = 'Check this connection', ['Pair Companion with your Hub, connect the platform in Hub Settings, then Sync linked accounts.', 'Read the status above before reconnecting. Quota and disabled chat need a different fix from expired authorization.']
    return dict(title=title, steps=steps, settings_url=hub_url.rstrip('/')+'/settings' if hub_url else '')


def normalize_events(rows, hub_url):
    result = []
    if not isinstance(rows, list): return result
    for row in rows[:50]:
        if not isinstance(row, dict): continue
        uid = str(row.get('id', ''))[:100]
        if not uid: continue
        raw = row.get('starts_at') or row.get('start_at') or row.get('start_time') or ''
        try:
            stamp = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            starts = stamp.timestamp() if stamp.tzinfo else None
        except (ValueError, TypeError, OverflowError): starts = None
        people = row.get('participants') or row.get('collaborators') or []
        accepted = []
        if isinstance(people, list):
            for person in people[:30]:
                if isinstance(person, dict) and person.get('status') in ('accepted', 'confirmed', 'going'):
                    accepted.append(str(person.get('display_name') or person.get('name') or person.get('username') or 'Collaborator')[:100])
        url = str(row.get('url') or '')
        base = urlparse(hub_url)
        parsed = urlparse(url)
        if url.startswith('/') and not url.startswith('//'): url = hub_url.rstrip('/')+url
        elif parsed.scheme != 'https' or parsed.hostname != base.hostname or parsed.username or parsed.password: url = ''
        result.append(dict(id=uid, title=str(row.get('title') or 'Untitled event')[:200], starts_at=str(raw)[:80], starts_at_unix=starts,
            game=str(row.get('game_name') or row.get('game') or '')[:200], status=str(row.get('status') or 'upcoming')[:50],
            instructions=str(row.get('instructions') or row.get('description') or '')[:2000], participants=accepted, url=url))
    return sorted(result, key=lambda r:r['starts_at_unix'] or float('inf'))


def session_summaries(state):
    groups = {}
    for row in state.history.events:
        uid = row.get('session_id')
        if not uid: continue
        group = groups.setdefault(uid, dict(id=uid, started_at=None, duration_seconds=None, ended=False, interrupted=False,
            destinations=[], performance_incidents=0, output_failures=0, audio_warnings=0, chat_messages={}, audience_events={}))
        if row['kind'] == 'session_started': group['started_at'] = row['time']
        elif row['kind'] == 'session_ended':
            group['ended'] = True
            group['duration_seconds'] = row.get('duration')
        elif row['kind'] == 'session_interrupted': group['interrupted'] = True
        elif row['kind'] in ('incident','frame_incident'): group['performance_incidents'] += 1
        elif row['kind'] == 'output_failure': group['output_failures'] += 1
        elif row['kind'] == 'audience_counts':
            group['chat_messages'] = row.get('chat_messages', {})
            group['audience_events'] = row.get('audience_events', {})
            group['audio_warnings'] = row.get('audio_warnings', 0)
        for uid in row.get('destinations', []):
            if uid not in group['destinations']: group['destinations'].append(uid)
    if state.history.session:
        group = groups.get(state.history.session['id'])
        if group:
            group['duration_seconds'] = max(0, round(time.time()-state.history.session['started_at']))
            group.update(state.session_counts.get(state.history.session['id'], {'chat_messages':{},'audience_events':{}}))
            group['audio_warnings']=sum(1 for r in state.audio.history if r.get('time',0)>=state.history.session['started_at'] and r['kind']=='warning')
    return list(groups.values())[-20:][::-1]


def audience_counts(state):
    start = (state.history.session or {}).get('started_at', state.session_count_start)
    rows = [m for m in state.chat.messages if m.get('time', 0) >= start and not m.get('simulated')]
    # Counts are sampled from bounded locally received data, not totals or unique viewers.
    return dict(chat_messages=dict(Counter(m['platform'] for m in rows if m.get('kind', 'chat') == 'chat')),
        audience_events=dict(Counter(m['kind'] for m in rows if m.get('kind') in EVENT_KINDS)),
        audio_warnings=sum(1 for m in state.audio.history if m.get('time', 0) >= start and m.get('kind') == 'incident'))
