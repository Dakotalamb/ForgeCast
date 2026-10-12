import copy
import tempfile
import time
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient,TestServer
from forgecast.server import State,create_app
from forgecast.overlay_studio import studio_action,validate_design,designs
from forgecast.entitlements import accept_entitlements,overlay_access
from forgecast.operations import suite_action

def design():return {'name':'Combined','width':1920,'height':1080,'enabled':True,'low_motion':False,'layers':[{'id':'chat1','type':'chat','name':'Chat','x':10,'y':10,'width':400,'height':300}]}
class StudioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=State(self.temp.name,demo=True)
        self.client=TestClient(TestServer(create_app(self.s)));await self.client.start_server()
        self.headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+self.s.browser_key}
        self.uid=(await studio_action(self.s,'overlay_design_save',{'design':design()}))['id']
    async def asyncTearDown(self):await self.client.close();self.temp.cleanup()
    async def feed(self,uid,key,preview=False):
        return await self.client.get('/overlay/design-feed/'+uid+('?preview=1' if preview else ''),headers={**self.headers,'Authorization':'Bearer '+key})
    async def test_saved_design_and_scoped_urls_survive_settings_changes(self):
        links=await studio_action(self.s,'overlay_design_link',{'id':self.uid});key=links['url'].split('#')[1]
        row=design();row['name']='Updated';await studio_action(self.s,'overlay_design_save',{'id':self.uid,'design':row})
        self.assertEqual(links,await studio_action(self.s,'overlay_design_link',{'id':self.uid}))
        r=await self.feed(self.uid,key,True);self.assertEqual((await r.json())['design']['name'],'Updated')
        loaded=State(self.temp.name,demo=True);self.assertEqual(designs(loaded)[0]['name'],'Updated')
    async def test_preview_is_free_and_never_exposes_real_chat(self):
        self.s.chat.add(dict(id='private',platform='twitch',origin='Real',origin_id='real',received_in='real',platform_message_id='real',user='Real viewer',user_id='real',text='LIVE CHAT CONTENT',kind='chat',time=time.time()))
        key=(await studio_action(self.s,'overlay_design_link',{'id':self.uid}))['url'].split('#')[1]
        r=await self.feed(self.uid,key);data=await r.json();self.assertFalse(data['access']);self.assertEqual(data['messages'],[])
        r=await self.feed(self.uid,key,True);body=await r.text();self.assertNotIn('LIVE CHAT CONTENT',body);self.assertIn('Preview chat',body)
    async def test_live_gate_is_enforced_in_both_overlay_endpoints(self):
        self.s.config['overlay_enabled']=True;self.s.config['overlay_mode']='all'
        self.s.chat.add(dict(id='live',platform='twitch',origin='Real',origin_id='real',received_in='real',platform_message_id='real',user='Viewer',user_id='viewer',text='Live hello',kind='chat',time=time.time()))
        key=(await studio_action(self.s,'overlay_design_link',{'id':self.uid}))['url'].split('#')[1]
        accept_entitlements(self.s,{'entitlements':{'fdgcast_overlays':True}})
        r=await self.feed(self.uid,key);self.assertEqual((await r.json())['messages'][-1]['text'],'Live hello')
        accept_entitlements(self.s,{'entitlements':{'fdgcast_overlays':False}})
        r=await self.feed(self.uid,key);self.assertEqual((await r.json())['messages'],[])
        r=await self.client.get('/overlay/feed',headers={**self.headers,'Authorization':'Bearer '+self.s.overlay_key});self.assertEqual((await r.json())['messages'],[])
        with self.assertRaises(ValueError):await suite_action(self.s,'overlay_settings',{'enabled':True,'mode':'all','seconds':30})
    async def test_keys_cannot_cross_profiles_or_control_obs(self):
        key=(await studio_action(self.s,'overlay_design_link',{'id':self.uid}))['url'].split('#')[1]
        second=(await studio_action(self.s,'overlay_design_copy',{'id':self.uid}))['id']
        await studio_action(self.s,'overlay_design_link',{'id':second})
        self.assertEqual((await self.feed(second,key)).status,401)
        self.assertEqual((await self.feed(self.uid,self.s.browser_key)).status,401)
        r=await self.client.get('/api/state',headers={**self.headers,'Authorization':'Bearer '+key});self.assertEqual(r.status,401)
        r=await self.client.post('/api/action',headers={**self.headers,'Authorization':'Bearer '+key},json={'op':'obs_command','command':'StartStream','confirmed':True});self.assertEqual(r.status,401)
        self.assertNotIn(key,str(self.s.public()));self.assertNotIn(key,str(self.s.report()))
    async def test_rotation_and_deletion_revoke_only_selected_profile(self):
        key=(await studio_action(self.s,'overlay_design_link',{'id':self.uid}))['url'].split('#')[1]
        second=(await studio_action(self.s,'overlay_design_copy',{'id':self.uid}))['id'];key2=(await studio_action(self.s,'overlay_design_link',{'id':second}))['url'].split('#')[1]
        new=(await studio_action(self.s,'overlay_design_rotate',{'id':self.uid}))['url'].split('#')[1]
        self.assertEqual((await self.feed(self.uid,key)).status,401);self.assertEqual((await self.feed(second,key2)).status,200)
        await studio_action(self.s,'overlay_design_delete',{'id':self.uid});self.assertEqual((await self.feed(self.uid,new)).status,401)
    async def test_invalid_save_is_atomic_and_import_cannot_inject_credential(self):
        before=designs(self.s);bad=design();bad['layers'][0]['width']=5000
        with self.assertRaises(ValueError):await studio_action(self.s,'overlay_design_save',{'id':self.uid,'design':bad})
        self.assertEqual(designs(self.s),before)
        bad=design();bad['token']='secret'
        with self.assertRaises(ValueError):await studio_action(self.s,'overlay_design_import',{'design':bad})
        bad=design();bad['layers'][0]['type']='script'
        with self.assertRaises(ValueError):validate_design(bad)
    async def test_expired_entitlement_and_local_config_flag_do_not_unlock(self):
        self.s.config['overlay_access']=True;self.assertFalse(overlay_access(self.s))
        accept_entitlements(self.s,{'entitlements':{'fdgcast_overlays':'true'}});self.assertFalse(overlay_access(self.s))
        accept_entitlements(self.s,{'entitlements':{'fdgcast_overlays':True}});self.assertTrue(overlay_access(self.s))
        self.s.overlay_access_until=time.monotonic()-1;self.assertFalse(overlay_access(self.s))
        loaded=State(self.temp.name,demo=True);self.assertFalse(overlay_access(loaded))
    async def test_editor_asset_and_scoped_player_csp(self):
        r=await self.client.get('/studio-editor.js',headers=self.headers);self.assertEqual(r.status,200)
        r=await self.client.get('/overlay/studio?id='+self.uid,headers=self.headers);self.assertEqual(r.status,200);self.assertIn("frame-ancestors 'self'",r.headers['Content-Security-Policy'])
        r=await self.client.get('/',headers=self.headers);self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
    async def test_layer_count_bounds_and_canvas_constraints(self):
        bad=design();bad['layers']=[dict(bad['layers'][0],id='l'+str(i)) for i in range(13)]
        with self.assertRaises(ValueError):validate_design(bad)
        bad=design();bad['layers'][0]['x']=1910
        with self.assertRaises(ValueError):validate_design(bad)
        good=design();good['layers']=[{'id':'e','type':'emotes','style':'burst'},{'id':'t','type':'text','content':'<script>alert(1)</script>'},{'id':'g','type':'goal','current':10,'target':20}]
        self.assertEqual(len(validate_design(good)['layers']),3)
