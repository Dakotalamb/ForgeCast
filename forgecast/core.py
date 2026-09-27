"""Pure, testable chat normalization and evidence-based diagnostics."""
from collections import OrderedDict, deque
import time


def twitch_message(event):
    origin = event.get('source_broadcaster_user_id') or event['broadcaster_user_id']
    mid = event.get('source_message_id') or event['message_id']
    return dict(id=f'twitch:{origin}:{mid}', platform='twitch',
                origin_id=origin,
                origin=event.get('source_broadcaster_user_name') or event.get('broadcaster_user_name', origin),
                received_in=event['broadcaster_user_id'], platform_message_id=event['message_id'],
                user_id=event['chatter_user_id'], user=event['chatter_user_name'],
                text=event['message']['text'], badges=event.get('source_badges') or event.get('badges', []),
                shared=bool(event.get('source_broadcaster_user_id')),
                kind='chat', time=time.time())


def youtube_message(item, channel):
    snip, author = item['snippet'], item.get('authorDetails', {})
    return dict(id='youtube:'+item['id'], platform='youtube', origin=channel,
                origin_id=snip.get('liveChatId', ''), received_in=snip.get('liveChatId', ''),
                platform_message_id=item['id'], user_id=author.get('channelId', ''),
                user=author.get('displayName', 'YouTube'), text=snip.get('displayMessage', ''),
                badges=[x for x in ['isChatOwner', 'isChatModerator', 'isChatSponsor'] if author.get(x)],
                shared=False, kind='chat' if snip.get('type') == 'textMessageEvent' else snip.get('type', 'event'),
                time=time.time())


def kick_message(item):
    broadcaster, sender = item['broadcaster'], item['sender']
    origin_id = str(broadcaster['user_id'])
    return dict(id='kick:'+origin_id+':'+str(item['message_id']), platform='kick',
                origin_id=origin_id, origin=broadcaster.get('channel_slug') or broadcaster.get('username') or origin_id,
                received_in=origin_id, platform_message_id=str(item['message_id']),
                user_id=str(sender.get('user_id', '')), user=sender.get('username', 'Kick'),
                text=item.get('content', ''), badges=[], shared=False, kind='chat', time=time.time())


class ChatStore:
    def __init__(self, limit=500):
        self.messages = deque(maxlen=limit)
        self.seen = OrderedDict()

    def add(self, message):
        if message['id'] in self.seen:
            return False
        self.seen[message['id']] = True
        if len(self.seen) > 10000:
            self.seen.popitem(last=False)
        self.messages.append(message)
        return True

    def delete(self, platform, message_id=None, user_id=None, channel=None):
        for m in self.messages:
            if m['platform'] != platform:
                continue
            if channel and channel not in (m['origin_id'], m['received_in']):
                continue
            if message_id and message_id not in (m['platform_message_id'], m['id'].rsplit(':', 1)[-1]):
                continue
            if user_id and m['user_id'] != user_id:
                continue
            m['text'], m['deleted'] = '[Message removed]', True


class Doctor:
    """Counter deltas, not lifetime percentages. No unsupported root-cause claims."""
    def __init__(self):
        self.previous = None
        self.incidents = deque(maxlen=300)
        self.samples = deque(maxlen=120)
        self.last_notice = {}

    def reset(self):
        self.previous = None

    def sample(self, current, now=None):
        now = time.time() if now is None else now
        self.samples.append(dict(time=now, **current))
        prev, self.previous = self.previous, current
        if not prev:
            return []
        result = []

        def issue(code, title, evidence, suggestion, confidence='high'):
            record = dict(time=now, code=code, title=title, evidence=evidence,
                          suggestion=suggestion, confidence=confidence)
            result.append(record)
            if now - self.last_notice.get(code, -1e9) >= 30:
                self.incidents.append(record)
                self.last_notice[code] = now

        for missed, total, name, code, tip in [
            ('renderSkippedFrames', 'renderTotalFrames', 'Rendering lag', 'render',
             'Try limiting game FPS or simplifying the active scene; GPU/source attribution is not available here.'),
            ('outputSkippedFrames', 'outputTotalFrames', 'Encoding lag', 'encode',
             'Review encoder load, preset and resolution. Shared encoders can reduce duplicate work.')]:
            d, n = current.get(missed, 0)-prev.get(missed, 0), current.get(total, 0)-prev.get(total, 0)
            if d > 0 and n > 0:
                issue(code, name, f'{d} of {n} frames missed in the latest sample ({100*d/n:.1f}%).', tip)
        old = {o['id']: o for o in prev.get('outputs', [])}
        affected, active = [], []
        for out in current.get('outputs', []):
            if out.get('active'):
                active.append(out['name'])
            before = old.get(out['id'])
            if before and out.get('active') and before.get('active'):
                drops = out.get('dropped', 0)-before.get('dropped', 0)
                if drops > 0:
                    affected.append(out['name'])
                    issue('network:'+out['id'], 'Network drops · '+out['name'],
                          f'{drops} frames dropped on this output in the latest sample.',
                          'Check upload headroom, network stability and this ingest route. OBS alone cannot identify the faulty hop.')
        if affected:
            pattern = 'All active outputs affected' if set(active) == set(affected) else 'Some outputs affected'
            issue('pattern', pattern, ', '.join(affected),
                  'A common local bottleneck is possible.' if set(active) == set(affected)
                  else 'Investigate destination settings and route; a local bottleneck is still possible.', 'medium')
        return result


def validate_destination(data):
    from urllib.parse import urlparse
    import re
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', data.get('id', '')):
        raise ValueError('Destination ID must contain 1–40 letters, numbers, underscores or hyphens.')
    url = urlparse(data.get('server', ''))
    if url.scheme not in ('rtmp', 'rtmps') or not url.hostname or url.username or url.password:
        raise ValueError('Enter an RTMP(S) server URL without credentials; put the key in the separate field.')
    if url.query or url.fragment:
        raise ValueError('Server URLs with query strings/fragments are unsupported; use the stream key field.')
    if not data.get('name', '').strip() or len(data['name']) > 80:
        raise ValueError('Enter a destination name (maximum 80 characters).')
    return {k: data[k] for k in ('id', 'name', 'server')}
