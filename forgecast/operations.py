"""Authenticated local operations shared by Companion and native docks."""
import secrets
import time
from urllib.parse import quote
from aiohttp import web
from .chat import api, ApiError
from .suite import EVENT_KINDS, DEFAULT_EVENTS

SUITE_ACTIONS = {'preflight_settings','preflight','event_settings','event_test','event_ack','hub_select','youtube_select','youtube_refresh',
                 'hub_events_refresh','preset_save','preset_apply','preset_delete','chat_moderate','chat_send_many','highlight','overlay_settings','overlay_rotate'}


def chat_capabilities(s):
    twitch = s.adapters.get('twitch')
    scopes = twitch.scopes if twitch else set()
    return {'twitch':{'delete':'moderator:manage:chat_messages' in scopes, 'ban':'moderator:manage:banned_users' in scopes,
                      'timeout':'moderator:manage:banned_users' in scopes, 'reply':bool(twitch)},
            'youtube':{'delete':bool(s.adapters.get('youtube')), 'ban':bool(s.adapters.get('youtube')), 'timeout':bool(s.adapters.get('youtube')), 'reply':False},
            'kick':{'delete':False,'ban':False,'timeout':False,'reply':False}}


def find_message(s, uid):
    row = next((r for r in s.chat.messages if r['id'] == uid), None)
    if not row or row.get('deleted') or row.get('simulated'): raise ValueError('This message is no longer available for this action.')
    return row


async def moderate(s, data):
    from .core import ChatStore
    if data.get('confirmed') is not True: raise ValueError('Confirm the channel and moderation action first.')
    row = find_message(s, data.get('id'))
    platform, operation = row['platform'], data.get('operation')
    if operation not in ('delete','timeout','ban'): raise ValueError('Choose delete, timeout or ban.')
    if not chat_capabilities(s).get(platform,{}).get(operation): raise ValueError('This action is unavailable with the current platform permissions. Use native chat or reconnect with the required scope.')
    adapter = s.adapters.get(platform)
    if platform == 'twitch':
        # A shared message may originate elsewhere. Never silently moderate another channel.
        if str(row.get('origin_id')) != adapter.config['channel_id']:
            raise ValueError('Shared-chat moderation belongs to the original channel. Open that channel’s native chat.')
        params = {'broadcaster_id':adapter.config['channel_id'], 'moderator_id':adapter.config['user_id']}
        if operation == 'delete':
            params['message_id'] = row['platform_message_id']
            await api(s.session,'DELETE','https://api.twitch.tv/helix/moderation/chat',headers=adapter.headers,params=params)
        else:
            body = {'user_id':row['user_id'], 'reason':'Moderated by creator in FDGCast'}
            if operation == 'timeout': body['duration'] = 600
            await api(s.session,'POST','https://api.twitch.tv/helix/moderation/bans',headers=adapter.headers,params=params,json={'data':body})
    elif platform == 'youtube':
        if not adapter.config.get('live_chat_id') or row.get('origin_id') != adapter.config['live_chat_id']:
            raise ValueError('This message belongs to a different or ended YouTube broadcast.')
        headers={'Authorization':'Bearer '+adapter.token}
        if operation == 'delete':
            await api(s.session,'DELETE','https://www.googleapis.com/youtube/v3/liveChat/messages',headers=headers,params={'id':row['platform_message_id']})
        else:
            snippet={'liveChatId':adapter.config['live_chat_id'], 'bannedUserDetails':{'channelId':row['user_id']},
                     'type':'temporary' if operation=='timeout' else 'permanent'}
            if operation == 'timeout': snippet['banDurationSeconds']=600
            await api(s.session,'POST','https://www.googleapis.com/youtube/v3/liveChat/bans',headers=headers,params={'part':'snippet'},json={'snippet':snippet})
    s.chat.delete(platform, message_id=row['platform_message_id'] if operation=='delete' else None,
                  user_id=None if operation=='delete' else row['user_id'], channel=row['origin_id'])
    s.event(platform.title()+' moderation request accepted: '+operation+'.')


async def suite_action(s, op, data):
    from .server import preflight, sync_hub_accounts, send_chat
    if op == 'preflight_settings':
        if not isinstance(data.get('recording_expected'),bool): raise ValueError('Recording expectation must be true or false.')
        s.config['recording_expected']=data['recording_expected']
    elif op == 'preflight': return {'checks':preflight(s),'blocks_streaming':False}
    elif op == 'chat_moderate': await moderate(s,data)
    elif op == 'chat_send_many':
        platforms = data.get('platforms')
        if not isinstance(platforms,list) or not 1 <= len(platforms) <= 3 or len(set(platforms)) != len(platforms) or any(p not in ('twitch','youtube','kick') for p in platforms):
            raise ValueError('Select one to three different platforms.')
        results=[]
        for platform in platforms:
            try:
                await send_chat(s,platform,data.get('text',''))
                results.append({'platform':platform,'sent':True})
            except (ApiError,ValueError,ConnectionError,TimeoutError) as exc:
                results.append({'platform':platform,'sent':False,'error':str(exc)})
        return {'ok':all(r['sent'] for r in results),'deliveries':results}
    elif op == 'event_settings':
        kinds=data.get('kinds')
        if not isinstance(kinds,list) or any(k not in EVENT_KINDS for k in kinds): raise ValueError('Choose supported event categories.')
        if not isinstance(data.get('merge',False),bool): raise ValueError('Merge must be true or false.')
        s.config['event_kinds']=list(dict.fromkeys(kinds));s.config['merge_events']=data.get('merge',False)
        twitch=s.adapters.get('twitch')
        if twitch:
            twitch.config['event_kinds']=s.config['event_kinds'];twitch.events_retry_at=time.monotonic()
    elif op == 'event_test':
        kind=data.get('kind','follow')
        if kind not in EVENT_KINDS: raise ValueError('Unknown event category.')
        s.chat.add({'id':'test:'+secrets.token_hex(8),'platform':'twitch','kind':kind,'origin':'SIMULATION',
            'origin_id':'test','received_in':'test','platform_message_id':'test','user':'TEST EVENT','user_id':'test',
            'text':'Simulated '+kind+' — no real platform event was received.','simulated':True,'time':time.time()})
    elif op == 'event_ack':
        if not any(r['id']==data.get('id') and r.get('kind') in EVENT_KINDS for r in list(s.chat.messages)+list(s.audience_history)): raise ValueError('Event no longer available.')
        s.event_ack.add(data['id'])
        s.event_ack &= {r['id'] for r in list(s.chat.messages)+list(s.audience_history)}
    elif op == 'hub_events_refresh':
        from .server import fetch_hub_events
        if not s.config.get('hub_url') or not s.vault.get('hub_token'): raise ValueError('Pair with the Hub in Companion Connections first.')
        await fetch_hub_events(s)
    elif op == 'hub_select':
        uid=str(data.get('id',''))
        if uid and not any(e['id']==uid for e in s.coordination()['events']): raise ValueError('This event is no longer in your schedule.')
        s.config['selected_event_id']=uid
    elif op == 'youtube_refresh':
        await sync_hub_accounts(s,retry_events=True)
    elif op == 'youtube_select':
        uid=str(data.get('id',''))
        selected=next((b for b in s.youtube_broadcasts if b['id']==uid),None)
        if uid and not selected: raise ValueError('Refresh broadcasts and choose an active broadcast.')
        s.config['youtube_broadcast_id']=uid
        adapter=s.adapters.get('youtube')
        if adapter: adapter.config['live_chat_id']=selected['live_chat_id'] if selected else ''
    elif op in ('preset_save','preset_apply','preset_delete'):
        name=str(data.get('name','')).strip()
        if not name or len(name)>60: raise ValueError('Enter a preset name of 1–60 characters.')
        presets=dict(s.config.get('output_presets',{}))
        if op=='preset_save':
            if name not in presets and len(presets)>=20: raise ValueError('Up to twenty presets are supported.')
            presets[name]=[d['id'] for d in s.config.get('destinations',[]) if d.get('enabled',True)]
        elif op=='preset_delete': presets.pop(name,None)
        else:
            if name not in presets: raise ValueError('Preset no longer exists.')
            for dest in s.config.get('destinations',[]): dest['enabled']=dest['id'] in presets[name]
        s.config['output_presets']=presets
    elif op == 'highlight':
        row=find_message(s,data.get('id'))
        if not s.config.get('overlay_enabled') or s.config.get('overlay_mode','selected')!='selected': raise ValueError('Enable Selected messages overlay in Companion Help first.')
        if data.get('immediate') is True:
            s.highlight_current=row['id'];s.highlight_started=time.time()
        elif row['id'] != getattr(s,'highlight_current',None) and row['id'] not in s.highlight_ids:
            if len(s.highlight_ids)>=20:raise ValueError('Highlight queue is full. Wait for displayed messages to finish.')
            s.highlight_ids.append(row['id'])
    elif op == 'overlay_settings':
        if not isinstance(data.get('enabled'),bool) or data.get('mode') not in ('all','selected'): raise ValueError('Choose an overlay mode and enable or disable it.')
        seconds=data.get('seconds',30)
        if isinstance(seconds,bool) or not isinstance(seconds,int) or not 5<=seconds<=120: raise ValueError('Overlay duration must be 5–120 seconds.')
        theme=data.get('theme','dark');font=data.get('font',22);spacing=data.get('spacing','comfortable')
        if theme not in ('dark','minimal') or font not in (18,22,28) or spacing not in ('compact','comfortable'): raise ValueError('Choose supported overlay appearance options.')
        s.config.update(overlay_theme=theme,overlay_font=font,overlay_spacing=spacing)
        s.config['overlay_enabled']=data['enabled'];s.config['overlay_mode']=data['mode']
        if not data['enabled']:s.highlight_ids.clear();s.highlight_current=None
        s.config['overlay_seconds']=seconds
    elif op == 'overlay_rotate':
        s.overlay_key=secrets.token_urlsafe(32);s.vault.set('overlay_key',s.overlay_key)
    s.save()
    return {'ok':True}


async def refresh_origin_avatars(s):
    twitch=s.adapters.get('twitch')
    if not twitch: return
    ids={str(r.get('origin_id','')) for r in s.chat.messages if r['platform']=='twitch' and str(r.get('origin_id','')).isdigit()}
    ids.add(twitch.config['channel_id'])
    missing=[uid for uid in ids if 'twitch:'+uid not in s.origin_avatars][:100]
    if not missing:return
    try:
        result=await api(s.session,'GET','https://api.twitch.tv/helix/users',headers=twitch.headers,params=[('id',uid) for uid in missing])
        for row in result.get('data',[]): s.origin_avatars['twitch:'+str(row['id'])]=row.get('profile_image_url','')
    except (ApiError,ConnectionError,TimeoutError): pass


async def overlay_page(request): return web.FileResponse(request.app['web_path']/'overlay.html')
async def overlay_script(request): return web.FileResponse(request.app['web_path']/'overlay.js')
async def overlay_style(request): return web.FileResponse(request.app['web_path']/'overlay.css')
async def overlay_link(request):
    s=request.app['state']
    return web.json_response({'url':'http://127.0.0.1:17654/overlay#'+s.overlay_key})
async def overlay_feed(request):
    s=request.app['state']
    supplied=request.headers.get('Authorization','').removeprefix('Bearer ')
    if not secrets.compare_digest(supplied,s.overlay_key): raise web.HTTPUnauthorized()
    rows=[]
    if s.config.get('overlay_enabled'):
        if s.config.get('overlay_mode','selected') == 'selected':
            available={r['id']:r for r in s.chat_view() if not r.get('deleted')}
            current=getattr(s,'highlight_current',None)
            if current not in available or time.time()-getattr(s,'highlight_started',0)>=s.config.get('overlay_seconds',30):
                s.highlight_current=None
                while s.highlight_ids:
                    candidate=s.highlight_ids.popleft()
                    if candidate in available:
                        s.highlight_current=candidate;s.highlight_started=time.time();break
            if getattr(s,'highlight_current',None) in available: rows=[available[s.highlight_current]]
        else:
            rows=[r for r in s.chat_view() if r.get('kind','chat') in {'chat','superchat','supersticker'} and not r.get('deleted') and time.time()-r['time']<s.config.get('overlay_seconds',30)][-8:]
    return web.json_response({'appearance':{'theme':s.config.get('overlay_theme','dark'),'font':s.config.get('overlay_font',22),'spacing':s.config.get('overlay_spacing','comfortable')},'messages':[{k:r.get(k) for k in ('id','platform','origin','user','text','fragments','color')} for r in rows]})
