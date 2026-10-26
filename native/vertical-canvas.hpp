#pragma once
// A persistent OBS canvas with the same production renderer used by RTMP outputs.
// The frontend owns registration; this class owns one strong canvas reference.
struct VerticalCanvasVideo {
    obs_canvas_t *canvas = nullptr;
    obs_source_t *source = nullptr;
    bool attach(obs_canvas_t *owned)
    {
        canvas = owned;
        if (!canvas || obs_canvas_removed(canvas) || (obs_canvas_get_flags(canvas) & EPHEMERAL)) return false;
        obs_video_info info{}, current{};
        if (!obs_get_video_info(&info)) return false;
        info.base_width = info.output_width = 720;
        info.base_height = info.output_height = 1280;
        info.output_format = VIDEO_FORMAT_NV12;
        info.colorspace = VIDEO_CS_709;
        info.range = VIDEO_RANGE_PARTIAL;
        const bool matching = obs_canvas_get_video_info(canvas, &current) &&
            current.base_width == 720 && current.base_height == 1280 &&
            current.output_width == 720 && current.output_height == 1280 &&
            current.fps_num == info.fps_num && current.fps_den == info.fps_den;
        if (!matching && !obs_canvas_reset_video(canvas, &info)) return false;
        auto *settings = obs_data_create();
        obs_data_set_bool(settings, "studio", true);
        source = obs_source_create_private("fdgcast_portrait", "FDGCast canvas picture", settings);
        obs_data_release(settings);
        if (!source || !obs_canvas_get_video(canvas)) return false;
        obs_canvas_set_channel(canvas, 0, source);
        return true;
    }
    ~VerticalCanvasVideo()
    {
        if (canvas && source) {
            auto *current = obs_canvas_get_channel(canvas, 0);
            if (current == source) obs_canvas_set_channel(canvas, 0, nullptr);
            if (current) obs_source_release(current);
        }
        if (source) obs_source_release(source);
        if (canvas) obs_canvas_release(canvas);
    }
    VerticalCanvasVideo() = default;
    VerticalCanvasVideo(const VerticalCanvasVideo &) = delete;
    VerticalCanvasVideo &operator=(const VerticalCanvasVideo &) = delete;
};
