import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from aiohttp.test_utils import TestClient, TestServer
from forgecast.server import State,create_app,queue_outputs
from forgecast.vertical import validate_layout


def layout():
    return dict(preset='camera_top',background='#151719',regions=[dict(name='Game',source='program',x=0,y=384,width=720,height=896),
        dict(name='Camera',source='camera',x=0,y=0,width=720,height=384,zoom=1.5,pan_x=0.2,mirror=True)])


class VerticalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=State(self.tmp.name,demo=True)
        self.client=TestClient(TestServer(create_app(self.s)));await self.client.start_server()
        self.s.obs=type('Obs',(),{'connected':True,'close':AsyncMock(),'request':AsyncMock(side_effect=self.request)})()
        self.headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+self.s.browser_key}
    async def asyncTearDown(self):
        await self.client.close();self.tmp.cleanup()
    async def request(self,kind,data=None):
        if kind=='GetSceneList':return {'currentProgramSceneUuid':'scene-one','scenes':[{'sceneUuid':'scene-one','sceneName':'Game'},{'sceneUuid':'scene-two','sceneName':'BRB'}]}
        if kind=='GetInputList':return {'inputs':[{'inputUuid':'camera','inputName':'My camera'}]}
        if kind=='GetCurrentProgramScene':return {'currentProgramSceneUuid':'scene-one','currentProgramSceneName':'Game'}
        if kind=='GetSourceScreenshot':return {'imageData':'data:image/jpeg;base64,YWJj'}
        return {}
    async def test_saved_layout_scopes_persist_and_do_not_change_obs(self):
        await self.s.vertical.discover();self.s.obs.request.reset_mock()
        await self.s.vertical.save({'scene_id':'scene-one','layout':layout()})
        fallback=layout();fallback['background']='#000000'
        await self.s.vertical.save({'scene_id':'*','layout':fallback})
        restored=State(self.tmp.name,demo=True)
        self.assertEqual(restored.config['vertical_studio']['layouts']['scene-one']['background'],'#151719')
        self.assertEqual(restored.config['vertical_studio']['layouts']['*']['background'],'#000000')
        self.assertNotIn('scene-two',restored.config['vertical_studio']['layouts']);self.s.obs.request.assert_not_awaited()
    async def test_validation_rejects_invalid_geometry_sources_and_nonfinite_values(self):
        for field,value in [('width',721),('x',700),('zoom',float('nan')),('pan_x',2),('visible','false'),('source','https://example.com')]:
            bad=layout();bad['regions'][0][field]=value
            with self.assertRaises(ValueError):validate_layout(bad)
        bad=layout();bad['regions']*=3
        with self.assertRaises(ValueError):validate_layout(bad)
        await self.s.vertical.discover();bad=layout();bad['regions'][1]['source']='removed-camera'
        with self.assertRaisesRegex(ValueError,'missing'):await self.s.vertical.save({'scene_id':'scene-one','layout':bad})
    async def test_preview_is_local_bounded_and_deduplicates_sources(self):
        await self.s.vertical.discover();self.s.obs.request.reset_mock()
        result=await self.s.vertical.preview({'scene_id':'scene-one','sources':['camera','camera']})
        self.assertEqual(set(result['frames']),{'scene-one','camera'})
        calls=[c for c in self.s.obs.request.call_args_list if c.args[0]=='GetSourceScreenshot'];self.assertEqual(len(calls),2)
        self.assertNotIn('imageData',str(self.s.report()))
        self.assertNotIn('frames',self.s.public())
        with self.assertRaisesRegex(ValueError,'refreshing'):await self.s.vertical.preview({'sources':[]})
        with self.assertRaises(ValueError):await self.s.vertical.preview({'sources':['unknown']})
    async def test_preview_bad_image_is_omitted_not_cached(self):
        await self.s.vertical.discover()
        async def request(kind,data=None):
            if kind=='GetSourceScreenshot':return {'imageData':'data:image/svg+xml;base64,YWJj'}
            return await self.request(kind,data)
        self.s.obs.request.side_effect=request
        result=await self.s.vertical.preview({'sources':[]});self.assertEqual(result['frames'],{})
        self.assertEqual(result['missing'],['scene-one'])
    async def test_preview_auth_and_no_store(self):
        r=await self.client.get('/api/vertical',headers=self.headers);self.assertEqual(r.status,200)
        r=await self.client.post('/api/vertical/preview',headers=self.headers,json={'sources':['camera']})
        self.assertEqual(r.status,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
        r=await self.client.post('/api/vertical/preview',headers={'Host':'127.0.0.1:17654'},json={});self.assertEqual(r.status,401)
    async def test_scene_crops_persist_validate_and_require_matching_native(self):
        await self.s.vertical.discover();value=layout()
        value['regions'][1]['source']='program'
        value['regions'][1]['crop']={'x':0.7,'y':0.6,'width':0.25,'height':0.35}
        await self.s.vertical.save({'scene_id':'scene-one','layout':value})
        self.assertEqual(self.s.config['vertical_studio']['layouts']['scene-one']['regions'][1]['crop'],value['regions'][1]['crop'])
        for crop in ({'x':0.9,'width':0.5},{'width':0},{'x':float('nan')},'invalid'):
            bad=layout();bad['regions'][1]['crop']=crop
            with self.assertRaises(ValueError):validate_layout(bad)
        self.s.config['destinations']=[dict(id='one',name='Test',platform='youtube',picture='vertical_studio')]
        self.s.vault.set('stream:one','KEY');self.s.native_seen=time.time();self.s.native_features={'portrait_v1','vertical_studio_v1'}
        with self.assertRaisesRegex(ValueError,'horizontal-scene crops'):queue_outputs(self.s,'start','one')
        self.s.native_features.add('vertical_crop_v1');queue_outputs(self.s,'start','one')
        self.assertEqual(self.s.commands.pop()['action'],'start')
    async def test_studio_requires_new_native_and_assignment_keeps_credentials(self):
        self.s.config['destinations']=[dict(id='one',name='Test',platform='youtube',server='rtmp://example.com/live',picture='vertical_studio')]
        self.s.vault.set('stream:one','KEEP');self.s.native_seen=time.time();self.s.native_features={'portrait_v1'}
        with self.assertRaisesRegex(ValueError,'Vertical Studio'):queue_outputs(self.s,'start','one')
        self.s.native_features.add('vertical_studio_v1');queue_outputs(self.s,'start','one')
        self.assertEqual(self.s.commands.pop()['destination']['picture'],'vertical_studio')
        self.s.demo=False
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'vertical_assign','id':'one'});self.assertEqual(r.status,200)
        self.assertEqual(self.s.vault.get('stream:one'),'KEEP')
        self.s.native_outputs=[{'id':'one','active':True}]
        r=await self.client.post('/api/action',headers=self.headers,json={'op':'vertical_assign','id':'one'});self.assertEqual(r.status,400)
        self.s.demo=True

    async def test_main_picture_uses_native_service_and_blocks_live_or_old_modules(self):
        self.s.demo=False;self.s.native_seen=time.time()
        async def choose(picture='vertical_studio'):
            return await self.client.post('/api/action',headers=self.headers,json={'op':'main_picture','picture':picture})
        r=await choose();self.assertEqual(r.status,400)
        self.s.native_features={'main_picture_v1'}
        self.s.main_output={'id':'main','name':'OBS main stream · YouTube','picture':'main','vertical_supported':True}
        r=await choose();self.assertEqual(r.status,200)
        command=self.s.commands.pop();self.assertEqual(command['action'],'main_picture');self.assertEqual(command['picture'],'vertical_studio')
        self.assertNotIn('key',str(command));self.assertNotIn('server',command)
        self.assertEqual(self.s.public()['main_output']['name'],'OBS main stream · YouTube')
        for flag in ('active','busy'):
            self.s.main_output[flag]=True;r=await choose();self.assertEqual(r.status,400);self.s.main_output.pop(flag)
        self.s.main_output['vertical_supported']=False
        r=await choose();self.assertEqual(r.status,400)
        r=await choose('main');self.assertEqual(r.status,200)
        r=await choose('bogus');self.assertEqual(r.status,400)
        self.s.native_seen=0;self.assertIsNone(self.s.public()['main_output'])

    async def test_additional_vertical_keeps_original_and_never_copies_key(self):
        self.s.demo=False
        original=dict(id='wide',name='Wide',server='rtmp://example.com/live',picture='main',platform='youtube')
        self.s.config['destinations']=[original.copy()];self.s.vault.set('stream:wide','ORIGINAL')
        async def save(**extra):
            return await self.client.post('/api/action',headers=self.headers,json=dict(op='save_destination',id='phone',name='Phone',platform='youtube',server='rtmp://example.com/live',picture='vertical_studio',paired_with='wide',**extra))
        r=await save();self.assertEqual(r.status,400)
        r=await save(key='ORIGINAL');self.assertEqual(r.status,400)
        self.assertEqual(self.s.config['destinations'],[original])
        r=await save(key='SEPARATE');self.assertEqual(r.status,200)
        self.assertEqual(self.s.config['destinations'][0],original)
        self.assertEqual(self.s.config['destinations'][1]['paired_with'],'wide')
        self.assertEqual(self.s.config['destinations'][1]['picture'],'vertical_studio')
        self.assertEqual(self.s.vault.get('stream:wide'),'ORIGINAL')
        self.assertEqual(self.s.vault.get('stream:phone'),'SEPARATE')

    async def test_add_obs_picture_alongside_existing_vertical_preserves_it(self):
        self.s.demo=False
        original=dict(id='phone',name='Phone',platform='youtube',server='rtmp://example.com/live',picture='vertical_studio')
        self.s.config['destinations']=[original.copy()];self.s.vault.set('stream:phone','PHONE')
        r=await self.client.post('/api/action',headers=self.headers,json=dict(op='save_destination',id='wide',name='Wide',platform='youtube',server='rtmp://example.com/live',picture='main',paired_with='phone',key='WIDE'))
        self.assertEqual(r.status,200,await r.text());self.assertEqual(self.s.config['destinations'][0],original)
        self.assertEqual(self.s.vault.get('stream:phone'),'PHONE');self.assertEqual(self.s.config['destinations'][1]['picture'],'main')

    async def test_platform_vertical_choices_and_legacy_start_are_guarded(self):
        from forgecast.platforms import CATALOG
        from forgecast.server import resolve_destination
        self.assertEqual({p for p,r in CATALOG.items() if r['vertical_output']}, {'youtube','tiktok','instagram','vimeo'})
        self.s.demo=False;self.s.native_seen=time.time()
        self.s.native_features={'portrait_v1','vertical_studio_v1','vertical_crop_v1'}
        for platform in ('kick','twitch','facebook','rumble','custom'):
            with self.subTest(platform=platform):
                with self.assertRaisesRegex(ValueError,'OBS picture'):
                    await resolve_destination(self.s,dict(platform=platform,server='rtmp://example.com/live',picture='vertical_studio'))
                legacy=dict(id='legacy',name='Legacy',platform=platform,server='rtmp://example.com/live',picture='vertical_studio')
                self.s.config['destinations']=[legacy];self.s.vault.set('stream:legacy','KEEP')
                for command in ('start','start_all'):
                    with self.assertRaises(ValueError):queue_outputs(self.s,command,'legacy')
                self.assertEqual(len(self.s.commands),0)
                response=await self.client.post('/api/action',headers=self.headers,json={'op':'vertical_assign','id':'legacy'})
                self.assertEqual(response.status,400)
                self.assertEqual(self.s.vault.get('stream:legacy'),'KEEP')
                # An unsupported saved picture can always be stopped or repaired.
                queue_outputs(self.s,'stop','legacy');self.s.commands.clear()
                fixed=await resolve_destination(self.s,{**legacy,'picture':'main'})
                self.assertEqual(fixed['picture'],'main')

    async def test_canvas_requires_matching_native_and_only_queues_setup(self):
        self.s.demo=False
        async def setup(value=True):
            return await self.client.post('/api/action',headers=self.headers,json={'op':'vertical_canvas','enabled':value})
        self.assertEqual((await setup()).status,400)
        self.s.native_seen=time.time();self.assertEqual((await setup()).status,400)
        self.s.native_features={'vertical_canvas_v1'}
        for value in (None,1,'true'):
            self.assertEqual((await setup(value)).status,400)
        response=await setup();self.assertEqual(response.status,200,await response.text())
        command=self.s.commands.pop();self.assertEqual(command['action'],'vertical_canvas');self.assertIs(command['enabled'],True)
        self.assertNotIn('key',command);self.assertNotIn('server',command)
        self.s.obs.request.assert_not_awaited()
        for snapshot in ({'busy':True},{'selected':True}):
            self.s.native_canvas=snapshot;self.assertEqual((await setup(False)).status,400)
        self.s.native_canvas={};self.s.main_output={'busy':True}
        self.assertEqual((await setup()).status,400);self.assertEqual(len(self.s.commands),0)
        self.s.main_output=None;self.s.demo=True;self.assertEqual((await setup()).status,400)

    async def test_canvas_telemetry_is_bounded_and_expires(self):
        headers={**self.headers,'Authorization':'Bearer '+self.s.native_key}
        response=await self.client.post('/native/poll',headers=headers,json={
            'features':['vertical_canvas_v1'], 'vertical_canvas':{'enabled':True,'registered':True,'selected':1,'busy':'false',
                'enhanced':True,'twitch_main':True,'key':'PRIVATE','error':'arbitrary PRIVATE'}})
        self.assertEqual(response.status,200)
        canvas=self.s.public()['vertical_canvas'];self.assertTrue(canvas['available']);self.assertTrue(canvas['registered'])
        self.assertFalse(canvas['selected']);self.assertFalse(canvas['busy']);self.assertNotIn('PRIVATE',str(canvas))
        self.s.native_seen=0;self.assertEqual(self.s.public()['vertical_canvas'],{})
