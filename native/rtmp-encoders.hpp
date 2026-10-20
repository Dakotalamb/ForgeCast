#pragma once
#include <string>
#include <cstring>
// Keep RTMP destinations compatible when Twitch Enhanced Broadcasting uses AV1/HEVC.
// Reuse the main encoder whenever compatible; allocate a shared fallback only as needed.
inline const char *rtmpH264Encoder(obs_encoder_t *main)
{
    if(main && std::strcmp(obs_encoder_get_codec(main),"h264")==0)return obs_encoder_get_id(main);
    const std::string mainId=main?obs_encoder_get_id(main):"";
    const char *family=nullptr;
    for(auto *candidate:{"nvenc","amf","qsv","apple"})if(mainId.find(candidate)!=std::string::npos){family=candidate;break;}
    const char *id=nullptr,*software=nullptr,*hardware=nullptr;
    for(size_t i=0;obs_enum_encoder_types(i,&id);++i){
        const char *codec=obs_get_encoder_codec(id);if(!codec||std::strcmp(codec,"h264")!=0||
            (obs_get_encoder_caps(id)&OBS_ENCODER_CAP_DEPRECATED))continue;
        if(std::strcmp(id,"obs_x264")==0)software=id;
        if(family && std::string(id).find(family)!=std::string::npos)hardware=id;
    }
    return hardware?hardware:software;
}
inline obs_encoder_t *createRtmpVideo(obs_encoder_t *main,const char *name,video_t *video,int bitrate)
{
    const char *id=rtmpH264Encoder(main);if(!id||!video)return nullptr;
    auto *settings=obs_data_create();
    if(main && std::strcmp(obs_encoder_get_id(main),id)==0){
        auto *original=obs_encoder_get_settings(main);obs_data_apply(settings,original);obs_data_release(original);
    }
    obs_data_set_string(settings,"rate_control","CBR");obs_data_set_int(settings,"bitrate",bitrate);obs_data_set_int(settings,"keyint_sec",2);
    if(std::strcmp(id,"obs_x264")==0)obs_data_set_default_string(settings,"preset","veryfast");
    auto *encoder=obs_video_encoder_create(id,name,settings,nullptr);obs_data_release(settings);
    if(encoder)obs_encoder_set_video(encoder,video);
    return encoder;
}
struct RtmpVideo {
    obs_encoder_t *encoder=nullptr;
    ~RtmpVideo(){if(encoder)obs_encoder_release(encoder);}
};
struct RtmpAudio {
    obs_encoder_t *encoder=nullptr;
    bool create(obs_encoder_t *main)
    {
        if(!main)return false;
        const char *id=nullptr,*chosen=nullptr;
        for(size_t i=0;obs_enum_encoder_types(i,&id);++i){
            const char *codec=obs_get_encoder_codec(id);if(codec&&std::strcmp(codec,"aac")==0){chosen=id;if(std::strcmp(id,"ffmpeg_aac")==0)break;}
        }
        if(!chosen)return false;
        auto *settings=obs_data_create();obs_data_set_int(settings,"bitrate",160);
        encoder=obs_audio_encoder_create(chosen,"FDGCast shared AAC",settings,obs_encoder_get_mixer_index(main),nullptr);
        obs_data_release(settings);if(encoder)obs_encoder_set_audio(encoder,obs_get_audio());return encoder!=nullptr;
    }
    ~RtmpAudio(){if(encoder)obs_encoder_release(encoder);}
};
