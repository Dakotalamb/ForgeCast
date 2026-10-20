// Exercise the actual player with a bounded in-memory DOM. Not a browser/layout test.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
class Node{
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.className='';this.style={setProperty(){}};this.classList={toggle(){}};this.textContent='';this.parent=null;this.animations=[];}
 append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node);}}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}
 querySelectorAll(selector){const cls=selector.slice(1);return this.children.filter(x=>x.className.split(' ').includes(cls));}
 addEventListener(){}setPointerCapture(){}
 getAnimations(){return this.animations;}
 animate(frames,options){const a={frames,options,finished:new Promise(()=>{}),cancel(){}};this.animations.push(a);return a;}
}
const root=new Node(),document={hidden:false,body:new Node(),getElementById:()=>root,createElement:tag=>new Node(tag),createTextNode:value=>Object.assign(new Node('text'),{textContent:value}),addEventListener(){}};
const context={document,window:{addEventListener(){}},location:{search:'?id=0123456789abcdef&preview=1',hash:'',pathname:'/overlay/studio',origin:'http://127.0.0.1:17654'},history:{replaceState(){}},URLSearchParams,Intl,performance:{now:()=>100000},innerWidth:1920,innerHeight:1080,setTimeout:()=>1,clearTimeout(){},AbortController,console,parent:{postMessage(){}},fetch(){throw Error('Unexpected fetch');}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web/studio-player.js','utf8'),context);
function evaluate(code){return vm.runInContext(code,context);}
const layer={id:'emotes',type:'emotes',name:'Effects',enabled:true,x:0,y:0,width:1920,height:1080,font:48,color:'#ffffff',background:'#000000',accent:'#ff531f',opacity:90,cooldown:0,seconds:5,max_items:4,style:'burst',platforms:['twitch']};
context.data={design:{name:'Test',enabled:true,width:1920,height:1080,low_motion:false,layers:[layer]},access:true,preview:true,messages:[{id:'m1',platform:'twitch',user:'Viewer',text:'👨‍👩‍👦 😂',fragments:[],time:Date.now()/1000}],events:[]};
evaluate('render(data)');assert.equal(evaluate("states.get('emotes').particles.length"),4,'Burst obeys per-widget cap');evaluate('render(data)');assert.equal(evaluate("states.get('emotes').particles.length"),4,'Repeated snapshot does not duplicate effects');
context.data.messages=[];evaluate('render(data)');assert.equal(root.children[0].children.filter(n=>n.className==='particle').length,0,'Removed messages remove visible effects');
context.data.design.layers=[{...layer,id:'chat',type:'chat',style:'panel',max_items:5}];context.data.messages=[{id:'m2',platform:'twitch',user:'<img>',text:'<script>evil()</script>',fragments:[{text:'<script>evil()</script>',image:'https://evil.test/image'}],time:Date.now()/1000}];evaluate('render(data)');const box=root.children[0].querySelectorAll('.chat-message')[0];assert.ok(box.children.some(n=>n.textContent==='<script>evil()</script>'));assert.equal(box.children.filter(n=>n.tag==='img').length,0,'Unapproved image URLs are not loaded');
evaluate('visibility(false)');assert.equal(root.children.length,0,'Hidden source clears renderer');assert.equal(evaluate('visible'),false);
console.log('PASS: actual player caps, dedup, deleted-message effects, text escaping, image policy and hidden-source cleanup');
