"""Saved, scoped, read-only overlay designs and bounded renderer feeds."""
import copy
import re
import secrets
import time
import uuid
from aiohttp import web
from .entitlements import overlay_access
from .storage import atomic_json
from .suite import DEFAULT_EVENTS

ACTIONS={'overlay_design_save','overlay_design_copy','overlay_design_delete','overlay_design_link','overlay_design_rotate','overlay_design_import'}
TYPES=('chat','emotes','alerts','text','goal')
PLATFORMS=('twitch','youtube','kick','rumble','tiktok','facebook','instagram')

def integer(value,low,high,label):
    if type(value) is not int or not low<=value<=high:raise ValueError(label+' is out of range.')
    return value

def text(value,limit,label):
    if not isinstance(value,str) or len(value)>limit:raise ValueError('Invalid '+label+'.')
    return value

def validate_design(raw):
    if not isinstance(raw,dict):raise ValueError('Choose an overlay design.')
    if set(raw)-{'id','name','width','height','enabled','low_motion','layers'}:raise ValueError('Unsupported overlay fields.')
    name=text(raw.get('name',''),80,'design name').strip()
    if not name:raise ValueError('Give the overlay a name.')
    result=dict(name=name,width=integer(raw.get('width',1920),320,3840,'Canvas width'),height=integer(raw.get('height',1080),240,3840,'Canvas height'))
    for field,default in [('enabled',True),('low_motion',False)]:
        if type(raw.get(field,default)) is not bool:raise ValueError('Invalid '+field+'.')
        result[field]=raw.get(field,default)
    layers=raw.get('layers',[])
    if not isinstance(layers,list) or not 1<=len(layers)<=12:raise ValueError('Use one to twelve widgets per overlay.')
    result['layers']=[];ids=set()
    for layer in layers:
        if not isinstance(layer,dict) or set(layer)-{'id','type','name','x','y','width','height','font','color','background','accent','opacity','enabled','seconds','max_items','style','platforms','content','current','target','cooldown'}:raise ValueError('Unsupported widget fields.')
        kind=layer.get('type');uid=layer.get('id')
        if kind not in TYPES or not isinstance(uid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',uid) or uid in ids:raise ValueError('Invalid widget type or ID.')
        ids.add(uid)
        row=dict(id=uid,type=kind,name=text(layer.get('name',kind.title()),80,'widget name'))
        for field,default,low,high in [('x',0,0,result['width']-1),('y',0,0,result['height']-1),('width',480,40,result['width']),('height',320,40,result['height']),('font',28,12,96),('opacity',90,0,100),('seconds',8,2,120),('max_items',20,1,60),('cooldown',2,0,60),('current',0,0,100000000),('target',100,1,100000000)]:
            row[field]=integer(layer.get(field,min(default,high)),low,high,field)
        if row['x']+row['width']>result['width'] or row['y']+row['height']>result['height']:raise ValueError('Keep widgets inside the canvas.')
        for field,default in [('color','#ffffff'),('background','#131923'),('accent','#ff5a1f')]:
            color=layer.get(field,default)
            if not isinstance(color,str) or not re.fullmatch(r'#[a-fA-F0-9]{6}',color):raise ValueError('Choose a six-digit color.')
            row[field]=color
        if type(layer.get('enabled',True)) is not bool:raise ValueError('Invalid widget enabled state.')
        row['enabled']=layer.get('enabled',True)
        row['style']=layer.get('style','float')
        if row['style'] not in ('float','rain','burst','minimal','panel'):raise ValueError('Unsupported widget style.')
        platforms=layer.get('platforms',list(PLATFORMS))
        if not isinstance(platforms,list) or len(platforms)>len(PLATFORMS) or any(p not in PLATFORMS for p in platforms):raise ValueError('Choose supported chat platforms.')
        row['platforms']=list(dict.fromkeys(platforms));row['content']=text(layer.get('content',''),2000,'widget text')
        result['layers'].append(row)
    return result


def designs(s):return copy.deepcopy(s.config.get('overlay_designs',[]))

def save_designs(s,rows):
    new=copy.deepcopy(s.config);new['overlay_designs']=rows
    atomic_json(s.config_path,new);s.config=new

def get_design(s,uid):
    row=next((r for r in designs(s) if r['id']==uid),None)
    if not row:raise ValueError('Overlay no longer exists.')
    return row

async def studio_action(s,op,data):
    rows=designs(s);uid=data.get('id','')
    if op in ('overlay_design_save','overlay_design_import'):
        row=validate_design(data.get('design'))
        if op=='overlay_design_import':uid=''
        if uid:get_design(s,uid)
        elif len(rows)>=16:raise ValueError('At most sixteen saved overlays are supported.')
        uid=uid or uuid.uuid4().hex[:16];row['id']=uid
        save_designs(s,[r for r in rows if r['id']!=uid]+[row])
    elif op=='overlay_design_copy':
        if len(rows)>=16:raise ValueError('At most sixteen saved overlays are supported.')
        row=get_design(s,uid);uid=uuid.uuid4().hex[:16];row['id']=uid;row['name']=(row['name']+' copy')[:80];save_designs(s,rows+[row])
    elif op=='overlay_design_delete':
        get_design(s,uid);save_designs(s,[r for r in rows if r['id']!=uid]);s.vault.delete('overlay_design:'+uid)
    elif op in ('overlay_design_link','overlay_design_rotate'):
        get_design(s,uid);key=s.vault.get('overlay_design:'+uid)
        if not key or op=='overlay_design_rotate':key=secrets.token_urlsafe(32);s.vault.set('overlay_design:'+uid,key)
        base='http://127.0.0.1:17654/overlay/studio?id='+uid
        return {'id':uid,'url':base+'#'+key,'preview_url':base+'&preview=1#'+key}
    else:raise ValueError('Unknown overlay action.')
    return {'ok':True,'id':uid}

async def studio_asset(request):
    name={'/overlay/studio':'studio-player.html','/studio-player.js':'studio-player.js','/studio-player.css':'studio-player.css'}[request.path]
    response=web.FileResponse(request.app['web_path']/name)
    return response

async def studio_feed(request):
    s=request.app['state'];uid=request.match_info['id'];key=s.vault.get('overlay_design:'+uid)
    supplied=request.headers.get('Authorization','').removeprefix('Bearer ')
    if not key or not secrets.compare_digest(key,supplied):raise web.HTTPUnauthorized()
    try:profile=get_design(s,uid)
    except ValueError:raise web.HTTPNotFound()
    messages=[];events=[]
    preview=request.query.get('preview')=='1'
    permitted=overlay_access(s)
    if profile['enabled'] and (permitted or preview):
        needs_messages=any(l['enabled'] and l['type'] in ('chat','emotes') for l in profile['layers'])
        needs_events=any(l['enabled'] and l['type']=='alerts' for l in profile['layers'])
        messages=[{k:m.get(k) for k in ('id','platform','origin','user','text','fragments','color','time')} for m in s.chat_view() if not m.get('deleted') and m.get('kind','chat')=='chat' and time.time()-m.get('time',0)<120][-50:] if needs_messages else []
        events=[{k:m.get(k) for k in ('id','platform','kind','user','text','time')} for m in s.audience_history if (m.get('platform') != 'tiktok' or m.get('kind') in s.config.get('event_kinds', DEFAULT_EVENTS)) and not m.get('deleted') and time.time()-m.get('time',0)<120][-30:] if needs_events else []
        if preview:
            stamp=int(time.time()/10);messages=[dict(id='preview-chat:'+str(stamp),platform='twitch',origin='PREVIEW',user='Sample viewer',text='Preview chat 👋 😂 ❤️',fragments=[{'text':'Preview chat 👋 😂 ❤️'}],color='#8dd9f5',time=time.time())] if needs_messages else []
            events=[dict(id='preview-event:'+str(stamp),platform='twitch',kind='follow',user='SAMPLE FOLLOW',text='Preview only — no live event',time=time.time())] if needs_events else []
    return web.json_response({'design':profile,'messages':messages,'events':events,'access':permitted,'preview':preview})
