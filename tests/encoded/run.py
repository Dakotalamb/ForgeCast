"""Capture actual libobs RTMP streams; decode dimensions, framing and AAC tone."""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']


def pixel(path,x,y):
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss','1','-i',str(path),'-vf',f'crop=2:2:{x}:{y},scale=1:1','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    assert len(raw)==3,(path,len(raw));return tuple(raw)


def color(path,x,y,expected):
    got=pixel(path,x,y)
    assert all(abs(a-b)<55 for a,b in zip(got,expected)),(str(path),(x,y),got,expected)


def verify(path,mode,vertical,cycle):
    streams=probe(path);v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    assert v['codec_name']=='h264' and a['codec_name']=='aac',streams
    assert (v['width'],v['height'])==((720,1280) if vertical else (1920,1080)),v
    assert float(v.get('avg_frame_rate','0/1').split('/')[0])>0,v
    blue=(0,85,221);cam=(34,221,0) if cycle else (221,34,0)
    if not vertical:color(path,100,100,blue);color(path,1800,1000,cam)
    elif mode=='fit':color(path,360,100,(0,0,0));color(path,100,500,blue);color(path,680,800,cam)
    elif mode=='fill':color(path,360,100,blue);color(path,360,1100,blue)
    elif mode=='studio':
        color(path,360,1100 if cycle else 192,cam)
        color(path,100,400 if cycle else 700,blue)
    audio=subprocess.check_output(['ffmpeg','-v','error','-ss','1','-i',str(path),'-t','0.5','-vn','-ac','1','-ar','8000','-f','f32le','-'])
    import array
    values=array.array('f');values.frombytes(audio);assert len(values)>3000
    rms=math.sqrt(sum(x*x for x in values)/len(values));assert rms>.01,(path,rms)
    # A real audible 440Hz source must survive AAC encode/transport/decode.
    crossings=sum(1 for x,y in zip(values,values[1:]) if x<=0<y)
    hz=crossings/(len(values)/8000);assert 410<hz<470,(path,hz)
    return {'file':path.name,'width':v['width'],'height':v['height'],'audio_hz':round(hz),'rms':round(rms,3)}


def run(exe,runtime,out,mode):
    lines=queue.Queue();log=(out/(mode+'-libobs.log')).open('w',encoding='utf-8')
    env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen'
    native=subprocess.Popen([str(exe),str(runtime),mode],cwd=exe.parent,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=env)
    def pump():
        for line in native.stdout:log.write(line);log.flush();lines.put(line.strip())
        lines.put('EXIT')
    threading.Thread(target=pump,daemon=True).start()
    receivers=[]
    def until(expected):
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            line=lines.get(timeout=max(.1,deadline-time.monotonic()))
            if line==expected:return
            if line=='EXIT':raise RuntimeError(f'Native process exited before {expected}; see {mode}-libobs.log')
        raise TimeoutError(expected)
    result=[]
    try:
        for cycle in range(2):
            until('READY '+str(cycle));receivers=[]
            for port,name in [(19350,'main'),(19351,'vertical')]:
                path=out/f'{mode}-{cycle}-{name}.flv';err=(out/f'{mode}-{cycle}-{name}-receiver.log').open('wb')
                p=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','warning','-listen','1','-i',f'rtmp://127.0.0.1:{port}/live/qa','-c','copy',str(path)],stdout=subprocess.DEVNULL,stderr=err)
                receivers.append((p,err,path,name))
            time.sleep(1);native.stdin.write('start\n');native.stdin.flush();until('STOPPED '+str(cycle))
            for p,err,path,name in receivers:
                p.wait(timeout=20);err.close();assert path.exists() and path.stat().st_size>10000,path
                result.append(verify(path,mode,name=='vertical',cycle))
        until('PASS native RTMP encoder lifecycle');assert native.wait(timeout=15)==0
    finally:
        if native.poll() is None:native.kill()
        for p,err,*_ in receivers:
            if p.poll() is None:p.kill()
            err.close()
        log.close()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--exe',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);result=[]
    for mode in ('fit','fill','studio'):result+=run(a.exe.resolve(),a.runtime.resolve(),a.out.resolve(),mode)
    (a.out/'results.json').write_text(json.dumps(result,indent=2))
    print('PASS: real libobs -> local RTMP -> decoded H.264/AAC, simultaneous landscape/portrait, fit/fill/crop, scene changes and stop/restart; no public broadcasts.')

if __name__=='__main__':main()
