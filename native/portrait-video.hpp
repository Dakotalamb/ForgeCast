#pragma once
#include "render-guard.hpp"
#include "rtmp-encoders.hpp"
static const char *portraitName(void *) { return "FDGCast portrait picture"; }
static void *portraitCreate(obs_data_t *settings, obs_source_t *source)
{
    return new PortraitData(obs_data_get_bool(settings,"fill"),obs_data_get_bool(settings,"studio"),source);
}
static void portraitRender(void *data, gs_effect_t *)
{
    fdgcast::RenderGuard guard;
    if (!guard) return; // Prevent an accidental source-in-program render cycle.
    auto *program = obs_get_output_source(0);
    if (!program) return;
    auto *picture=static_cast<PortraitData *>(data);
    if(picture->studio){picture->render(program);obs_source_release(program);return;}
    const auto layout = fdgcast::portraitLayout(static_cast<float>(obs_source_get_width(program)),
                                               static_cast<float>(obs_source_get_height(program)),
                                               picture->fill);
    if (layout.scale > 0) {
        gs_matrix_push();
        gs_matrix_translate3f(layout.x, layout.y, 0.f);
        gs_matrix_scale3f(layout.scale, layout.scale, 1.f);
        obs_source_video_render(program);
        gs_matrix_pop();
    }
    obs_source_release(program);
}

struct PortraitVideo {
    obs_canvas_t *canvas = nullptr;
    obs_view_t *view = nullptr;
    obs_encoder_t *encoder = nullptr;
    bool added = false;
    bool create(obs_encoder_t *main, bool fill, bool studio=false, obs_canvas_t *sharedCanvas=nullptr)
    {
        obs_video_info info{};
        if (!obs_get_video_info(&info)) return false;
        info.base_width = info.output_width = 720;
        info.base_height = info.output_height = 1280;
        info.output_format = VIDEO_FORMAT_NV12;
        info.colorspace = VIDEO_CS_709;
        info.range = VIDEO_RANGE_PARTIAL;
        video_t *video = nullptr;
        if (studio && sharedCanvas && !obs_canvas_removed(sharedCanvas)) {
            canvas = obs_canvas_get_ref(sharedCanvas);
            video = obs_canvas_get_video(canvas);
            if (!video) return false;
        } else {
        view = obs_view_create();
        if (!view) return false;
        auto *settings = obs_data_create();
        obs_data_set_bool(settings, "fill", fill);
        obs_data_set_bool(settings, "studio", studio);
        auto *source = obs_source_create_private("fdgcast_portrait", "FDGCast portrait", settings);
        obs_data_release(settings);
        if (!source) return false;
        obs_view_set_source(view, 0, source);
        obs_source_release(source);
        video = obs_view_add2(view, &info);
        if (!video) return false;
        added = true;
        }
        encoder = createRtmpVideo(main,"FDGCast shared portrait H.264",video,4500);
        if (!encoder) return false;
        return true;
    }
    ~PortraitVideo()
    {
        if (encoder) obs_encoder_release(encoder);
        if (added) obs_view_remove(view);
        if (view) obs_view_destroy(view);
        if (canvas) obs_canvas_release(canvas);
    }
};


inline void registerPortraitSource()
{
    obs_source_info portrait{};
    portrait.id = "fdgcast_portrait";
    portrait.type = OBS_SOURCE_TYPE_INPUT;
    portrait.output_flags = OBS_SOURCE_VIDEO | OBS_SOURCE_CUSTOM_DRAW | OBS_SOURCE_CAP_DISABLED | OBS_SOURCE_DO_NOT_DUPLICATE;
    portrait.get_name = portraitName;
    portrait.create = portraitCreate;
    portrait.destroy = [](void *data) { delete static_cast<PortraitData *>(data); };
    portrait.video_tick = [](void *data,float) {static_cast<PortraitData *>(data)->tick();};
    portrait.enum_active_sources = [](void *data,obs_source_enum_proc_t callback,void *param) {
        auto *p=static_cast<PortraitData *>(data);std::lock_guard<std::recursive_mutex> lock(p->mutex);
        for(const auto &entry:p->children)callback(p->self,entry.second,param);
    };
    portrait.get_width = [](void *) -> uint32_t { return 720; };
    portrait.get_height = [](void *) -> uint32_t { return 1280; };
    portrait.video_render = portraitRender;
    obs_register_source(&portrait);
}
