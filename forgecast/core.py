"""Pure, testable chat normalization and evidence-based diagnostics."""
from collections import OrderedDict, deque
import time
import hashlib
import re
import copy
from .diagnostics import policy


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
                is_creator=event['chatter_user_id'] == origin,
                reply_to=event.get('reply',{}).get('parent_user_name','') if event.get('reply') else '',
                highlighted=event.get('message_type')=='channel_points_highlighted',
                fragments=twitch_fragments(event['message']),
                color=username_color('twitch', event['chatter_user_id']),
                kind='chat', time=time.time())


def youtube_message(item, channel):
    snip, author = item['snippet'], item.get('authorDetails', {})
    return dict(id='youtube:'+item['id'], platform='youtube', origin=channel,
                origin_id=snip.get('liveChatId', ''), received_in=snip.get('liveChatId', ''),
                platform_message_id=item['id'], user_id=author.get('channelId', ''),
                user=author.get('displayName', 'YouTube'), text=snip.get('displayMessage', ''),
                avatar=author.get('profileImageUrl', '') if author.get('isChatOwner') else '',
                is_creator=bool(author.get('isChatOwner')),
                color=username_color('youtube', author.get('channelId') or author.get('displayName', '')),
                fragments=[{'text':snip.get('displayMessage', '')}],
                badges=[x for x in ['isChatOwner', 'isChatModerator', 'isChatSponsor'] if author.get(x)],
                shared=False, kind={'textMessageEvent':'chat','superChatEvent':'superchat','superStickerEvent':'supersticker','newSponsorEvent':'membership','membershipGiftingEvent':'gift','giftMembershipReceivedEvent':'membership'}.get(snip.get('type'), snip.get('type','event')),
                time=time.time())


def kick_message(item):
    broadcaster, sender = item['broadcaster'], item['sender']
    origin_id = str(broadcaster['user_id'])
    return dict(id='kick:'+origin_id+':'+str(item['message_id']), platform='kick',
                origin_id=origin_id, origin=broadcaster.get('channel_slug') or broadcaster.get('username') or origin_id,
                received_in=origin_id, platform_message_id=str(item['message_id']),
                user_id=str(sender.get('user_id', '')), user=sender.get('username', 'Kick'),
                text=item.get('content', ''), fragments=kick_fragments(item.get('content', '')),
                color=username_color('kick', str(sender.get('user_id') or sender.get('username', ''))),
                is_creator=str(sender.get('user_id')) == origin_id,
                avatar=sender.get('profile_picture', '') if str(sender.get('user_id')) == origin_id else '',
                badges=(sender.get('identity') or {}).get('badges', []), shared=False, kind='chat', time=time.time())


# A deterministic, readable palette; independent of platform/health colors.
def username_color(platform, identity):
    palette = ['#e6b3ff', '#8dd9f5', '#ffd28d', '#ffadca', '#b7d991', '#d3baff', '#91dfd3']
    index = int(hashlib.sha256((platform+':'+identity).encode()).hexdigest()[:8], 16)
    return palette[index % len(palette)]


def twitch_fragments(message):
    rows = []
    for fragment in message.get('fragments', [])[:200]:
        row = {'text':fragment.get('text', '')}
        emote = fragment.get('emote') or {}
        if re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(emote.get('id', ''))):
            row['image'] = 'https://static-cdn.jtvnw.net/emoticons/v2/'+emote['id']+'/default/dark/1.0'
        rows.append(row)
    return rows or [{'text':message.get('text', '')}]


def kick_fragments(text):
    rows, cursor = [], 0
    for match in re.finditer(r'\[emote:(\d{1,20}):([^\]]{1,100})\]', text):
        if match.start() > cursor: rows.append({'text':text[cursor:match.start()]})
        rows.append({'text':match.group(2), 'image':'https://files.kick.com/emotes/'+match.group(1)+'/fullsize'})
        cursor = match.end()
    if cursor < len(text): rows.append({'text':text[cursor:]})
    return rows or [{'text':text}]


class ChatStore:
    def __init__(self, limit=500):
        self.messages = deque(maxlen=limit)
        self.seen = OrderedDict()
        self.persistent_seen = set()
        self.on_add = None

    def add(self, message):
        if message['id'] in self.seen or hashlib.sha256(message['id'].encode()).hexdigest() in self.persistent_seen:
            return False
        self.seen[message['id']] = True
        if len(self.seen) > 10000:
            self.seen.popitem(last=False)
        self.messages.append(message)
        if self.on_add: self.on_add(message)
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
            m['fragments'] = [{'text':'[Message removed]'}]


class Doctor:
    """Counter deltas, not lifetime percentages. No unsupported root-cause claims."""
    def __init__(self, sensitivity="balanced"):
        self.sensitivity = sensitivity
        policy(sensitivity)
        self.conditions = {}
        self.previous = None
        self.incidents = deque(maxlen=300)
        self.samples = deque(maxlen=120)
        self.last_notice = {}

    def configure(self, sensitivity):
        policy(sensitivity)
        self.sensitivity = sensitivity
        self.reset()

    def reset(self):
        self.previous = None
        self.conditions.clear()

    def sample(self, current, now=None):
        now = time.time() if now is None else now
        self.samples.append(dict(time=now, **current))
        prev, self.previous = self.previous, copy.deepcopy(current)
        if not prev:
            return []
        result = []
        settings = policy(self.sensitivity)
        observed = set()

        def issue(code, title, evidence, suggestion, confidence='high'):
            observed.add(code)
            severity = 'critical' if confidence == 'critical' else 'warning'
            record = dict(time=now, code=code, title=title, evidence=evidence,
                          suggestion=suggestion, confidence='high' if confidence == 'critical' else confidence, severity=severity)
            condition = self.conditions.setdefault(code, {'since':now, 'severity_since':now, 'observed_severity':severity, 'notice':None})
            condition.pop('clear_since', None)
            if condition['observed_severity'] != severity:
                condition['severity_since'], condition['observed_severity'] = now, severity
            wait = 3 if severity == 'critical' else settings['wait']
            if now-condition['since'] >= wait and (severity != 'critical' or now-condition['severity_since'] >= 3):
                previous_notice = condition['notice']
                if previous_notice and previous_notice['severity'] == 'critical' and now-condition['severity_since'] < settings['clear']:
                    record = dict(previous_notice, time=now)
                condition['notice'] = record
                result.append(record)
                if not previous_notice or (previous_notice['severity'] != record['severity'] and record['severity'] == 'critical'):
                    self.incidents.append(record)

        for missed, total, name, code, tip in [
            ('renderSkippedFrames', 'renderTotalFrames', 'Rendering lag', 'render',
             'Try limiting game FPS or simplifying the active scene; GPU/source attribution is not available here.'),
            ('outputSkippedFrames', 'outputTotalFrames', 'Encoding lag', 'encode',
             'Review encoder load, preset and resolution. Shared encoders can reduce duplicate work.')]:
            d, n = current.get(missed, 0)-prev.get(missed, 0), current.get(total, 0)-prev.get(total, 0)
            if d >= 3 and n > 0 and d/n >= settings['ratio']:
                issue(code, name, f'{d} of {n} frames missed in the latest sample ({100*d/n:.1f}%).', tip, 'critical' if d/n >= 0.05 else 'high')
        old = {o['id']: o for o in prev.get('outputs', [])}
        affected, active = [], []
        for out in current.get('outputs', []):
            if out.get('active'):
                active.append(out['name'])
            before = old.get(out['id'])
            if before and out.get('active') and before.get('active'):
                drops = out.get('dropped', 0)-before.get('dropped', 0)
                if drops >= 3:
                    affected.append(out['name'])
                    issue('network:'+out['id'], 'Network drops · '+out['name'],
                          f'{drops} frames dropped on this output in the latest sample.',
                          'Check upload headroom, network stability and this ingest route. OBS alone cannot identify the faulty hop.')
        if affected:
            pattern = 'All active outputs affected' if set(active) == set(affected) else 'Some outputs affected'
            issue('pattern', pattern, ', '.join(affected),
                  'A common local bottleneck is possible.' if set(active) == set(affected)
                  else 'Investigate destination settings and route; a local bottleneck is still possible.', 'medium')
        for code in list(self.conditions):
            if code in observed: continue
            condition = self.conditions[code]
            condition.setdefault('clear_since', now)
            if now-condition['clear_since'] >= settings['clear'] or not condition['notice']:
                self.conditions.pop(code)
            elif condition['notice']:
                result.append(dict(condition['notice'], time=now))
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

