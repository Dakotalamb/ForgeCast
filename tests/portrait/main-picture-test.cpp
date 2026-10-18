#include <cassert>
#include <memory>
#include <array>
constexpr size_t MAX_OUTPUT_VIDEO_ENCODERS=3;
struct obs_encoder_t { int refs=1; };
struct obs_output_t { int refs=1; bool active=false; std::array<obs_encoder_t*,3> encoders{}; int service=42,audio=7; };
obs_encoder_t *obs_encoder_get_ref(obs_encoder_t *e) { if(e)++e->refs;return e; }
void obs_encoder_release(obs_encoder_t *e) { if(e)--e->refs; }
obs_output_t *obs_output_get_ref(obs_output_t *o) { ++o->refs;return o; }
void obs_output_release(obs_output_t *o) { --o->refs; }
bool obs_output_active(obs_output_t *o) { return o->active; }
obs_encoder_t *obs_output_get_video_encoder2(obs_output_t *o,size_t i) { return o->encoders[i]; }
obs_encoder_t *obs_output_get_video_encoder(obs_output_t *o) { for(auto *e:o->encoders)if(e)return e;return nullptr; }
void obs_output_set_video_encoder2(obs_output_t *o,obs_encoder_t *e,size_t i) { assert(!o->active);if(o->encoders[i])obs_encoder_release(o->encoders[i]);o->encoders[i]=obs_encoder_get_ref(e); }
void obs_output_set_video_encoder(obs_output_t *o,obs_encoder_t *e) { obs_output_set_video_encoder2(o,e,0); }
struct PortraitVideo { obs_encoder_t *encoder; };
#include "../../native/main-picture.hpp"
int main(){
 obs_encoder_t horizontal,vertical,other;obs_output_t output;
 obs_output_set_video_encoder(&output,&horizontal);const int refs=horizontal.refs;
 auto picture=std::make_shared<PortraitVideo>();picture->encoder=&vertical;
 MainPictureRoute route;
 assert(route.apply(&output,picture));assert(route.horizontal()==&horizontal);
 assert(output.encoders[0]==&vertical && output.service==42 && output.audio==7);
 assert(horizontal.refs==refs && output.refs==2);
 // Horizontal secondary outputs retain the original encoder; reconnect/delay
 // must not restore or destroy the vertical view while the stream is active.
 auto *secondary=obs_encoder_get_ref(route.horizontal());output.active=true;
 assert(!route.restore());assert(!route.apply(&output,picture));
 output.active=false;assert(route.restore());assert(output.encoders[0]==&horizontal);
 assert(output.refs==1 && horizontal.refs==refs+1);obs_encoder_release(secondary);
 assert(horizontal.refs==refs && picture.use_count()==1);
 // Setup failure removes video so OBS cannot silently send horizontal instead.
 assert(route.apply(&output,nullptr));assert(!obs_output_get_video_encoder(&output));
 assert(route.restore() && output.encoders[0]==&horizontal);
 // Preserve a newer binding installed by OBS during a profile/settings rebuild.
 assert(route.apply(&output,picture));obs_output_set_video_encoder(&output,&other);
 assert(route.restore() && output.encoders[0]==&other && horizontal.refs==1);
 // Block/restore every track when unsupported multitrack was selected later.
 obs_output_set_video_encoder2(&output,&horizontal,1);
 assert(route.apply(&output,nullptr));assert(!obs_output_get_video_encoder(&output));
 assert(route.restore());assert(output.encoders[0]==&other&&output.encoders[1]==&horizontal);
 obs_output_set_video_encoder2(&output,nullptr,0);obs_output_set_video_encoder2(&output,nullptr,1);
 assert(horizontal.refs==1&&vertical.refs==1&&other.refs==1);
}
