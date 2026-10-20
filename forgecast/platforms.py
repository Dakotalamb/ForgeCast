"""Streaming destinations; chat support is separate from ingest support."""
PLATFORMS = [
    dict(id='twitch', name='Twitch', server='rtmp://live.twitch.tv/app', help='Server is selected automatically. Paste your Twitch stream key. Twitch dual format uses OBS Enhanced Broadcasting with an Additional Canvas, rather than a second ordinary output. FDGCast Vertical Studio is not yet integrated with that feature.'),
    dict(id='youtube', name='YouTube', server='rtmps://a.rtmps.youtube.com:443/live2', help='Server is selected automatically. Paste your YouTube stream key.'),
    dict(id='kick', name='Kick', server='', requires_server=False, help='Uses your linked Kick account to find its server. If unavailable, paste the server from your Kick dashboard.'),
    dict(id='facebook', name='Facebook Live', server='rtmps://rtmp-api.facebook.com:443/rtmp/', help='The standard Facebook server is selected automatically. In Live Producer choose Streaming software and paste its stream key. Override the server under Advanced if Facebook supplies a different address. Check the preview and any Go live confirmation in Facebook. Connect Facebook chat separately through Hub in Connections.'),
    dict(id='rumble', name='Rumble', help='Create a Rumble livestream, then Get the streamer configuration. Paste its stream URL and key. Connect the separate Live Stream API in Connections to read chat.'),
    dict(id='tiktok', name='TikTok LIVE', help='Requires TikTok encoder access with a server URL and stream key. LIVE or LIVE Studio access alone may not provide a key. Chat can connect separately while you go live elsewhere. Choose Same as OBS or a Vertical picture format below.'),
    dict(id='x', name='X Live', help='Paste the RTMP server URL and key provided by your X broadcasting tools. Account access is required. Combined chat is not connected.'),
    dict(id='instagram', name='Instagram Live', help='Paste the server URL and key from Instagram Live Producer if available to your account. Finish publishing in Instagram. Choose a Vertical picture format below for 9:16 video. Connect Instagram chat separately through Hub in Connections.'),
    dict(id='linkedin', name='LinkedIn Live', help='Paste the server URL and key from your eligible LinkedIn Live broadcast. Complete setup and publishing on LinkedIn. Combined chat is not connected.'),
    dict(id='dlive', name='DLive', help='Paste the server URL and stream key from your DLive dashboard. Combined chat is not connected.'),
    dict(id='vimeo', name='Vimeo Live', help='Paste the server URL and stream key from your Vimeo live event. Account access is required. Combined chat is not connected.'),
    dict(id='custom', name='Other / Custom RTMP', help='Paste the RTMP or RTMPS server URL and stream key from your streaming service. Combined chat is separate.'),
]
for row in PLATFORMS:
    row.setdefault('server', '')
    row.setdefault('requires_server', not bool(row['server']))
CATALOG = {row['id']: row for row in PLATFORMS}

