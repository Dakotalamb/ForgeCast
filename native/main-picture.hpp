#pragma once
#include <array>
#include <memory>

// Own only the temporary stream-video binding. OBS keeps its service, audio,
// recording encoders and main canvas. Borrowed OBS getters need explicit refs.
struct MainPictureRoute {
    obs_output_t *output = nullptr;
    std::array<obs_encoder_t *, MAX_OUTPUT_VIDEO_ENCODERS> originals{};
    std::shared_ptr<PortraitVideo> portrait;
    bool apply(obs_output_t *target, std::shared_ptr<PortraitVideo> picture)
    {
        if (!target || obs_output_active(target) || output) return false;
        output = obs_output_get_ref(target);
        for (size_t i=0; i<originals.size(); ++i) {
            originals[i] = obs_encoder_get_ref(obs_output_get_video_encoder2(target,i));
            if (originals[i]) obs_output_set_video_encoder2(target,nullptr,i);
        }
        portrait = std::move(picture);
        // A null picture intentionally blocks startup after a setup failure.
        // Never fall back to broadcasting the wrong picture.
        obs_output_set_video_encoder(target,portrait ? portrait->encoder : nullptr);
        return true;
    }
    bool restore()
    {
        if (!output) return true;
        if (obs_output_active(output)) return false;
        auto *current = obs_output_get_video_encoder(output);
        // OBS may already have rebuilt its output after a profile/settings change.
        if (!current || (portrait && current==portrait->encoder)) {
            for (size_t i=0; i<originals.size(); ++i)
                if (originals[i] || i==0) obs_output_set_video_encoder2(output,originals[i],i);
        }
        for (auto *&encoder : originals) { if(encoder) obs_encoder_release(encoder); encoder=nullptr; }
        obs_output_release(output); output=nullptr; portrait.reset();
        return true;
    }
    obs_encoder_t *horizontal() const { return originals[0]; }
    ~MainPictureRoute() { restore(); }
};
