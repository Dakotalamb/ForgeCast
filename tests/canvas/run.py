"""Run a test-only module in a temporary portable OBS frontend, then restart it."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--module',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
runtime=a.runtime.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
config=runtime/'config'/'obs-studio';profile=config/'basic'/'profiles'/'FDGCastQA';profile.mkdir(parents=True,exist_ok=True)
(config/'global.ini').write_text('[General]\nLastVersion=537001986\nLanguage=en-US\n',encoding='utf-8')
(config/'user.ini').write_text('[General]\nFirstRun=true\n[Basic]\nProfile=FDGCastQA\nProfileDir=FDGCastQA\nSceneCollection=FDGCastQA\nSceneCollectionFile=FDGCastQA\n',encoding='utf-8')
(profile/'basic.ini').write_text('[General]\nName=FDGCastQA\n[Video]\nBaseCX=1920\nBaseCY=1080\nOutputCX=1920\nOutputCY=1080\nFPSType=0\nFPSCommon=30\n[Output]\nMode=Simple\n[SimpleOutput]\nStreamEncoder=x264\nStreamAudioEncoder=aac\nVBitrate=3000\nABitrate=160\n',encoding='utf-8')
(profile/'service.json').write_text(json.dumps({'type':'rtmp_common','settings':{'service':'Twitch','server':'auto','key':'QA-NOT-A-REAL-KEY'}}),encoding='utf-8')
(runtime/'portable_mode.txt').touch()
(runtime/'data'/'obs-plugins'/'fdgcast-canvas-qa').mkdir(parents=True,exist_ok=True)
module=runtime/'obs-plugins'/'64bit'/'fdgcast-canvas-qa.dll';shutil.copy2(a.module,module)
try:
    for stage in (1,2):
        report=out/f'frontend-canvas-{stage}.json';env=os.environ.copy();env.pop('QT_QPA_PLATFORM',None);env.update(QT_LOGGING_TO_CONSOLE='1',FDGCAST_CANVAS_QA_STAGE=str(stage),FDGCAST_CANVAS_QA_REPORT=str(report))
        with (out/f'frontend-canvas-{stage}.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([str(runtime/'bin'/'64bit'/'obs64.exe'),'--portable','--disable-updater','--disable-shutdown-check','--disable-missing-files-check','--profile','FDGCastQA','--collection','FDGCastQA'],cwd=runtime/'bin'/'64bit',env=env,stdout=log,stderr=subprocess.STDOUT)
            try:code=process.wait(timeout=75)
            except subprocess.TimeoutExpired:
                title=subprocess.run(['powershell','-NoProfile','-Command',f'(Get-Process -Id {process.pid}).MainWindowTitle'],capture_output=True,text=True).stdout.strip()
                (out/f'frontend-window-{stage}.txt').write_text(title,encoding='utf-8')
                process.kill();process.wait();raise RuntimeError(f'OBS frontend did not exit; see stage {stage} log')
        assert report.exists(),f'Missing OBS frontend report for stage {stage}; exit={code}'
        result=json.loads(report.read_text());assert result.get('success'),result
        assert code==0,('OBS exit',stage,code)
    print('PASS: real OBS frontend registered one selectable canvas; selection and UUID survived restart; selected-canvas removal blocked; main video unchanged.')
finally:
    for folder in ('logs','crashes'):
        source=config/folder
        if source.exists():shutil.copytree(source,out/('obs-'+folder),dirs_exist_ok=True)
    module.unlink(missing_ok=True)
