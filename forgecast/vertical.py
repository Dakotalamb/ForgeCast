"""Local-only scene layouts and on-demand, bounded OBS preview snapshots."""
import asyncio
import copy
import math
import re
import time
from aiohttp import web

FORMATS = ('main', 'vertical_fill', 'vertical_fit', 'vertical_studio')
PRESETS = ('fill', 'fit', 'camera_top', 'camera_bottom', 'pip', 'two_cameras', 'custom')


def identity(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value))


def number(row, key, default, low, high):
    value = row.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Invalid vertical '+key+'.')
    return value


def validate_layout(value):
    if not isinstance(value, dict): raise ValueError('Choose a vertical layout.')
    preset = value.get('preset', 'custom')
    if preset not in PRESETS: raise ValueError('Choose a supported layout preset.')
    background = value.get('background', '#000000')
    if not isinstance(background, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', background): raise ValueError('Choose a background color.')
    regions = value.get('regions')
    if not isinstance(regions, list) or not 1 <= len(regions) <= 4: raise ValueError('Use one to four picture layers.')
    clean = []
    for row in regions:
        if not isinstance(row, dict): raise ValueError('Invalid picture layer.')
        source = row.get('source', 'program')
        if source != '' and not identity(source): raise ValueError('Choose an existing OBS source.')
        name = row.get('name', 'Picture')
        if not isinstance(name, str) or len(name)>80: raise ValueError('Use a shorter layer name.')
        fit = row.get('fit', 'fill')
        if fit not in ('fill', 'fit'): raise ValueError('Choose Fill or Fit.')
        mirror = row.get('mirror', False)
        visible = row.get('visible', True)
        if type(mirror) is not bool or type(visible) is not bool: raise ValueError('Invalid layer visibility or mirror option.')
        x, y = number(row,'x',0,0,719), number(row,'y',0,0,1279)
        width, height = number(row,'width',720,20,720), number(row,'height',1280,20,1280)
        if x+width>720 or y+height>1280: raise ValueError('Keep each layer inside the vertical canvas.')
        clean.append(dict(name=name,source=source,fit=fit,mirror=mirror,visible=visible,x=x,y=y,width=width,height=height,
                          zoom=number(row,'zoom',1,1,4),pan_x=number(row,'pan_x',0,-1,1),pan_y=number(row,'pan_y',0,-1,1)))
    return dict(preset=preset,background=background,regions=clean)


def settings(s):
    return copy.deepcopy(s.config.get('vertical_studio', {'schema_version':1,'layouts':{}}))


class VerticalStudio:
    def __init__(self, state):
        self.s = state
        self.catalog = {'scenes':[], 'sources':[]}
        self.lock = asyncio.Lock()
        self.preview_lock = asyncio.Lock()
        self.last_preview = 0

    async def discover(self):
        s = self.s
        if not s.obs or not s.obs.connected: raise ValueError('Connect OBS in Connections to load scenes and live previews.')
        async with self.lock:
            rows = await s.obs.request('GetSceneList')
            inputs = await s.obs.request('GetInputList')
            scenes = [dict(id=r['sceneUuid'],name=r['sceneName']) for r in rows.get('scenes',[]) if identity(r.get('sceneUuid'))][:128]
            sources = [dict(id=r['inputUuid'],name=r['inputName']) for r in inputs.get('inputs',[]) if identity(r.get('inputUuid'))][:256]
            self.catalog = dict(scenes=scenes,sources=sources,scene_id=rows.get('currentProgramSceneUuid',''),scene_name=rows.get('currentProgramSceneName',''))
            return {**self.catalog,'settings':settings(s)}

    async def save(self, data):
        uid = data.get('scene_id')
        if uid != '*' and (not identity(uid) or uid not in {r['id'] for r in self.catalog['scenes']}):
            raise ValueError('Refresh scenes and choose an OBS scene or Default layout.')
        layout = validate_layout(data.get('layout'))
        allowed = {'','program'} | {r['id'] for r in self.catalog['sources']} | {r['id'] for r in self.catalog['scenes']}
        if any(r['source'] not in allowed for r in layout['regions']): raise ValueError('A selected OBS source is missing. Refresh sources and choose its replacement.')
        value = settings(self.s)
        if uid not in value['layouts'] and len(value['layouts'])>=129: raise ValueError('Too many saved scene layouts.')
        value['layouts'][uid] = layout
        self.s.config['vertical_studio'] = value
        self.s.save()
        return {'ok':True,'settings':value}

    async def preview(self, data):
        s = self.s
        if not s.obs or not s.obs.connected: raise ValueError('Connect OBS to see live previews.')
        selected = data.get('scene_id', '*')
        if selected != '*' and selected not in {r['id'] for r in self.catalog['scenes']}: raise ValueError('Refresh OBS scenes first.')
        sources = data.get('sources', [])
        allowed = {r['id'] for r in self.catalog['sources']} | {r['id'] for r in self.catalog['scenes']}
        if not isinstance(sources,list) or len(sources)>4 or any(not isinstance(uid,str) or uid not in allowed for uid in sources):
            raise ValueError('Choose up to four known OBS sources for preview.')
        async with self.preview_lock:
            if time.monotonic()-self.last_preview<0.45: raise ValueError('Preview is refreshing; wait a moment.')
            self.last_preview = time.monotonic()
            current = await s.obs.request('GetCurrentProgramScene')
            live = current.get('currentProgramSceneUuid','')
            if not identity(live): raise ValueError('OBS did not report the live scene. Refresh scenes.')
            chosen = live if selected=='*' else selected
            frames, missing = {}, []
            for uid in dict.fromkeys([live, chosen]+sources):
                try:
                    result = await s.obs.request('GetSourceScreenshot', {'sourceUuid':uid,'imageFormat':'jpeg','imageWidth':960,'imageHeight':540,'imageCompressionQuality':65})
                    image = result.get('imageData','')
                    if not isinstance(image,str) or len(image)>1500000 or not re.fullmatch(r'data:image/(?:jpeg|jpg);base64,[A-Za-z0-9+/=]+',image):
                        raise ValueError('Invalid OBS preview image.')
                    frames[uid] = image
                except (RuntimeError, ValueError): missing.append(uid)
            return dict(scene_id=live,scene_name=current.get('currentProgramSceneName',''),selected_id=chosen,
                        frames=frames,missing=missing,captured_at=time.time())


async def catalog(request):
    studio = request.app['state'].vertical
    result = await studio.discover()
    return web.json_response(result,headers={'Cache-Control':'no-store'})


async def preview(request):
    result = await request.app['state'].vertical.preview(await request.json())
    return web.json_response(result,headers={'Cache-Control':'no-store'})
