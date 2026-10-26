// Real libobs + production portrait renderer/encoder + local RTMP sinks.
#include <obs.h>
#include <util/platform.h>
#include <graphics/graphics.h>
#include <graphics/vec2.h>
#include <graphics/vec4.h>
#include <QCoreApplication>
#include <QJsonObject>
#include <QJsonArray>
#include <QColor>
#include <atomic>
#include <chrono>
#include <thread>
#include <cmath>
#include <cstring>
#include <iostream>
#include <filesystem>
#include <stdexcept>
#include "portrait-layout.hpp"
#include "vertical-render.hpp"
#include "portrait-video.hpp"
#include "vertical-canvas.hpp"
using namespace std::chrono_literals;
void check(bool ok,const char *message){if(!ok)throw std::runtime_error(message);}
struct Tone {
 obs_source_t *source;std::atomic<bool> stop{false};std::thread thread;
 Tone(obs_source_t *s):source(s),thread([this]{
  uint64_t sample=0;const uint64_t base=os_gettime_ns();const auto start=std::chrono::steady_clock::now();float left[480],right[480];
  while(!stop){const uint64_t first=sample;for(int i=0;i<480;++i){left[i]=right[i]=.2f*std::sin(2*3.141592653589793*440*(sample++)/48000);}
   obs_source_audio a{};a.data[0]=reinterpret_cast<const uint8_t*>(left);a.data[1]=reinterpret_cast<const uint8_t*>(right);
   a.frames=480;a.speakers=SPEAKERS_STEREO;a.format=AUDIO_FORMAT_FLOAT_PLANAR;a.samples_per_sec=48000;a.timestamp=base+first*1000000000ULL/48000;
   obs_source_output_audio(source,&a);std::this_thread::sleep_until(start+std::chrono::nanoseconds(sample*1000000000ULL/48000));
  }
 }){}
 ~Tone(){stop=true;thread.join();}
};
void loadModule(const std::filesystem::path &root,const char *name){
 const auto binary=(root/"obs-plugins"/"64bit"/(std::string(name)+".dll")).string();
 const auto data=(root/"data"/"obs-plugins"/name).string();obs_module_t *module=nullptr;
 check(obs_open_module(&module,binary.c_str(),data.c_str())==MODULE_SUCCESS,"OBS module open failed");
 check(obs_init_module(module),"OBS module initialization failed");
}
obs_source_t *color(const char *name,int w,int h,long long rgba){
 auto *d=obs_data_create();obs_data_set_int(d,"width",w);obs_data_set_int(d,"height",h);obs_data_set_int(d,"color",rgba);
 auto *s=obs_source_create_private("color_source_v3",name,d);obs_data_release(d);check(s,"Color source unavailable");return s;
}
obs_scene_t *scene(const char *name,long long camera){
 auto *s=obs_scene_create(name);auto *background=color("Blue background",1920,1080,0xffdd5500);
 obs_scene_add(s,background);obs_source_release(background);
 auto *cam=color("Camera color",480,360,camera);auto *item=obs_scene_add(s,cam);vec2 p{1440,720};obs_sceneitem_set_pos(item,&p);obs_source_release(cam);return s;
}
QJsonObject layout(bool bottom){
 const QJsonObject crop{{"x",.75},{"y",2.0/3},{"width",.25},{"height",1.0/3}};
 return QJsonObject{{"background","#000000"},{"regions",QJsonArray{
  QJsonObject{{"source","program"},{"fit","fit"},{"x",0},{"y",bottom?0:384},{"width",720},{"height",896}},
  QJsonObject{{"source","program"},{"fit","fill"},{"crop",crop},{"x",0},{"y",bottom?896:0},{"width",720},{"height",384}}
 }}};
}
obs_output_t *stream(const char *name,const char *url,obs_encoder_t *video,obs_encoder_t *audio){
 auto *s=obs_data_create();obs_data_set_string(s,"server",url);obs_data_set_string(s,"key","qa");
 auto *service=obs_service_create("rtmp_custom",name,s,nullptr);obs_data_release(s);check(service,"RTMP service unavailable");
 auto *output=obs_output_create("rtmp_output",name,nullptr,nullptr);check(output,"RTMP output unavailable");
 obs_output_set_service(output,service);obs_output_set_video_encoder(output,video);obs_output_set_audio_encoder(output,audio,0);
 obs_output_set_reconnect_settings(output,1,1);return output;
}
void waitActive(obs_output_t *o){
 for(int i=0;i<200;++i){if(obs_output_active(o)&&obs_output_get_total_bytes(o)>0)return;std::this_thread::sleep_for(50ms);}
 throw std::runtime_error("Output did not send bytes to local RTMP receiver");
}
void stop(obs_output_t *o){obs_output_stop(o);for(int i=0;i<200&&obs_output_active(o);++i)std::this_thread::sleep_for(50ms);check(!obs_output_active(o),"Output did not stop");}
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);
 try {
  check(argc==3,"Expected OBS runtime root and mode");const auto root=std::filesystem::absolute(argv[1]);const std::string mode=argv[2];
  check(obs_startup("en-US",nullptr,nullptr),"OBS startup failed");
  // Execute beside the official obs.dll so its normal data paths resolve.
  obs_audio_info ai{};ai.samples_per_sec=48000;ai.speakers=SPEAKERS_STEREO;check(obs_reset_audio(&ai),"Audio initialization failed");
  obs_video_info vi{};const auto graphics=(root/"bin"/"64bit"/"libobs-d3d11.dll").string();vi.graphics_module=graphics.c_str();
  vi.fps_num=30;vi.fps_den=1;vi.base_width=vi.output_width=1920;vi.base_height=vi.output_height=1080;vi.output_format=VIDEO_FORMAT_NV12;
  vi.colorspace=VIDEO_CS_709;vi.range=VIDEO_RANGE_PARTIAL;vi.gpu_conversion=true;vi.scale_type=OBS_SCALE_BILINEAR;
  check(obs_reset_video(&vi)==OBS_VIDEO_SUCCESS,"D3D11 video initialization failed");
  for(auto *name:{"obs-x264","obs-ffmpeg","obs-outputs","rtmp-services","image-source"})loadModule(root,name);
  obs_post_load_modules();registerPortraitSource();
  check(obs_get_source_output_flags("fdgcast_portrait") & OBS_SOURCE_CAP_DISABLED,"Portrait helper must be hidden");
  obs_source_info tone{};tone.id="qa_tone";tone.type=OBS_SOURCE_TYPE_INPUT;tone.output_flags=OBS_SOURCE_AUDIO;
  tone.get_name=[](void*){return "QA tone";};tone.create=[](obs_data_t*,obs_source_t *s)->void*{return new Tone(s);};tone.destroy=[](void *p){delete static_cast<Tone*>(p);};obs_register_source(&tone);
  auto *sound=obs_source_create_private("qa_tone","Tone",nullptr);check(sound,"Tone source unavailable");obs_set_output_source(1,sound);
  auto *one=scene("First",0xff0022dd),*two=scene("Second",0xff00dd22);obs_set_output_source(0,obs_scene_get_source(one));
  QJsonObject layouts{{QString::fromUtf8(obs_source_get_uuid(obs_scene_get_source(one))),layout(false)},
                      {QString::fromUtf8(obs_source_get_uuid(obs_scene_get_source(two))),layout(true)}};
  std::atomic_store(&verticalStudioConfig,std::make_shared<const QJsonObject>(QJsonObject{{"layouts",layouts}}));
  auto *settings=obs_data_create();obs_data_set_string(settings,"rate_control","CBR");obs_data_set_int(settings,"bitrate",3000);obs_data_set_int(settings,"keyint_sec",1);obs_data_set_string(settings,"preset","ultrafast");
  auto *video=obs_video_encoder_create("obs_x264","QA main",settings,nullptr);check(video,"x264 unavailable");obs_encoder_set_video(video,obs_get_video());
  obs_data_set_int(settings,"bitrate",128);auto *audio=obs_audio_encoder_create("ffmpeg_aac","QA audio",settings,0,nullptr);obs_data_release(settings);check(audio,"AAC unavailable");obs_encoder_set_audio(audio,obs_get_audio());
  std::shared_ptr<VerticalCanvasVideo> canvas;
  RtmpAudio compatibleAudio;
  if(mode=="canvas"){
   // Exercise the persistent canvas save/load path used across OBS restarts.
   canvas=std::make_shared<VerticalCanvasVideo>();
   check(canvas->attach(obs_canvas_create("FDGCast Vertical Studio",nullptr,ACTIVATE)),"Canvas setup failed");
   auto *saved=obs_save_canvas(canvas->canvas);check(saved,"Canvas was not persistent");
   const std::string uuid=obs_canvas_get_uuid(canvas->canvas);
   obs_canvas_remove(canvas->canvas);canvas.reset();
   canvas=std::make_shared<VerticalCanvasVideo>();check(canvas->attach(obs_load_canvas(saved)),"Canvas reload failed");obs_data_release(saved);
   check(uuid==obs_canvas_get_uuid(canvas->canvas),"Canvas UUID changed across restore");
   check(!(obs_canvas_get_flags(canvas->canvas)&EPHEMERAL),"Canvas would be excluded by Additional Canvas picker");
   check(compatibleAudio.create(audio),"Compatible AAC setup failed");
  }
  auto *main=stream("Main","rtmp://127.0.0.1:19350/live",video,audio);PortraitVideo portrait;
  obs_output_t *vertical=nullptr;
  for(int cycle=0;cycle<2;++cycle){
   obs_set_output_source(0,obs_scene_get_source(cycle?two:one));
   std::cout<<"READY "<<cycle<<std::endl;std::string command;std::getline(std::cin,command);check(command=="start","Missing start command");
   check(obs_output_start(main),"Main start failed");waitActive(main);
   if(!vertical){check(portrait.create(mode=="canvas"?nullptr:video,mode=="fill",mode=="studio"||mode=="canvas",canvas?canvas->canvas:nullptr),"Production portrait setup failed");
    if(canvas){check(portrait.canvas==canvas->canvas && !portrait.view,"Canvas rendering was duplicated");}
    vertical=stream("Vertical","rtmp://127.0.0.1:19351/live",portrait.encoder,mode=="canvas"?compatibleAudio.encoder:audio);}
   check(obs_output_get_video_encoder(main)==video,"Portrait setup changed main encoder");
   check(obs_encoder_get_width(video)==1920&&obs_encoder_get_height(video)==1080,"Main dimensions were changed");
   check(obs_output_start(vertical),"Vertical start failed");waitActive(vertical);
   std::this_thread::sleep_for(3500ms);
   check(obs_output_get_total_frames(main)>=60&&obs_output_get_total_frames(vertical)>=60,"Not enough real encoded frames");
   stop(vertical);stop(main);check(obs_output_get_video_encoder(main)==video,"Stopping changed main encoder");
   std::cout<<"STOPPED "<<cycle<<std::endl;
  }
  auto *vs=obs_output_get_service(vertical),*ms=obs_output_get_service(main);obs_output_release(vertical);obs_service_release(vs);obs_output_release(main);obs_service_release(ms);
  obs_encoder_release(audio);obs_encoder_release(video);obs_set_output_source(0,nullptr);obs_set_output_source(1,nullptr);obs_source_release(sound);obs_scene_release(one);obs_scene_release(two);
  // Destroy the portrait view before shutting down OBS.
  if(portrait.encoder){obs_encoder_release(portrait.encoder);portrait.encoder=nullptr;}
  if(portrait.added){obs_view_remove(portrait.view);portrait.added=false;}
  if(portrait.view){obs_view_destroy(portrait.view);portrait.view=nullptr;}
  if(portrait.canvas){obs_canvas_release(portrait.canvas);portrait.canvas=nullptr;}
  if(compatibleAudio.encoder){obs_encoder_release(compatibleAudio.encoder);compatibleAudio.encoder=nullptr;}
  if(canvas){obs_canvas_remove(canvas->canvas);canvas.reset();}
  obs_shutdown();std::cout<<"PASS native RTMP encoder lifecycle"<<std::endl;return 0;
 } catch(const std::exception &e){std::cerr<<"FAIL "<<e.what()<<std::endl;return 2;}
}
