"""Activity transport readiness, independent of saved events and OBS outputs.

SPDX-License-Identifier: GPL-2.0-or-later
"""


def activity_connection(statuses, paused=(), configured=()):
    rows = []
    for platform, label in [('twitch', 'Twitch'), ('youtube', 'YouTube'), ('tiktok', 'TikTok')]:
        message = str(statuses.get(platform, ''))
        if (not message or message.lower().startswith('not connected')) and platform not in configured and platform not in paused:
            continue
        message = message or 'Not connected.'
        lower = message.lower()
        level = 'ready' if lower == 'connected' or lower.startswith('connected; reading') else 'attention'
        details = message
        if platform in paused:
            level, details = 'attention', 'Paused. Resume this platform in Connections.'
        elif platform == 'twitch' and level == 'ready':
            event_message = str(statuses.get('twitch_events', ''))
            details = event_message or 'Event subscriptions have not reported readiness yet.'
            if not event_message or any(word in event_message.lower() for word in
                    ('permission', 'unavailable', 'disconnected', 'denied', 'reconnect', 'revoked')):
                level = 'attention'
        rows.append(dict(platform=platform, label=label, level=level, message=details[:700]))
    if not rows:
        return dict(level='attention', message='Activity feed is not connected.',
                    detail='Open Companion → Connections to connect your platform accounts. Saved events are history, not a live connection.', platforms=[])
    problems = [row for row in rows if row['level'] != 'ready']
    names = ', '.join(row['label'] for row in (problems or rows))
    return dict(level='attention' if problems else 'ready',
                message=('Activity connection needs attention: ' if problems else 'Activity connection ready: ')+names+'.',
                detail=('Open Connections to check status. Reconnect linked accounts in Hub, then Sync linked accounts. TikTok needs a public LIVE. ' if problems else '')+
                       'Saved events do not confirm live delivery; activity missed while disconnected is not automatically recovered.',
                platforms=rows)
