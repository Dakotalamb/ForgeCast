'use strict';
const overlayKey=location.hash.slice(1);history.replaceState(null,'','/overlay');
async function refresh(){
 try{
  const response=await fetch('/overlay/feed',{headers:{Authorization:'Bearer '+overlayKey}});
  if(!response.ok)throw Error('Unavailable');
  const data=await response.json(),root=document.getElementById('messages');
  root.replaceChildren(...data.messages.map(m=>{
   const box=document.createElement('article');box.className='message';
   const origin=document.createElement('div');origin.className='origin';origin.textContent=m.platform.toUpperCase()+' · '+m.origin;
   const user=document.createElement('span');user.className='user';user.textContent=m.user+': ';
   if(/^#[a-f0-9]{6}$/i.test(m.color||''))user.style.color=m.color;
   const body=document.createElement('p');body.append(user);
   for(const f of m.fragments||[{text:m.text}]){
    if(/^\/media\/[a-f0-9]{64}$/.test(f.image||'')){const img=document.createElement('img');img.src=f.image;img.alt=f.text;body.append(img);}
    else body.append(document.createTextNode(f.text||''));
   }
   box.append(origin,body);return box;
  }));
 }catch{document.getElementById('messages').replaceChildren();}
 setTimeout(refresh,1000);
}
if(overlayKey)refresh();
