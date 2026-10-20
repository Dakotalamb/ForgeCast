#pragma once
#include "vertical-canvas.hpp"
static std::shared_ptr<VerticalCanvasVideo> verticalCanvas;
static QString verticalCanvasError;
static bool verticalCanvasClosing=false;
static bool verticalCanvasLoading=true;
static constexpr const char *verticalCanvasName = "FDGCast Vertical Studio";

static QString canvasCollectionKey()
{
    char *collection = obs_frontend_get_current_scene_collection();
    const auto key = QString::fromLatin1(QUrl::toPercentEncoding(QString::fromUtf8(collection ? collection : "Default")));
    if (collection) bfree(collection);
    return "vertical-canvas/collections/" + key;
}
static bool canvasSelected()
{
    if (!verticalCanvas || !verticalCanvas->canvas || obs_canvas_removed(verticalCanvas->canvas)) return false;
    auto *profile = obs_frontend_get_profile_config();
    return profile && QString::fromUtf8(config_get_string(profile,"Stream1","MultitrackExtraCanvas")) ==
        QString::fromUtf8(obs_canvas_get_uuid(verticalCanvas->canvas));
}
static QString setVerticalCanvas(bool enabled)
{
    // Canvas mixes must never be reset while any encoder/recording is consuming video.
    if (obs_video_active()) return "vertical_canvas_busy";
    if (!enabled && canvasSelected()) return "vertical_canvas_selected";
    QSettings settings("Forged Destiny Gaming","ForgeCast");
    if (!enabled) {
        if (verticalCanvas) {
            auto *canvas = obs_canvas_get_ref(verticalCanvas->canvas);
            if(!obs_frontend_remove_canvas(canvas)){obs_canvas_release(canvas);return "vertical_canvas_setup_failed";}
            verticalCanvas.reset();
            obs_canvas_release(canvas);
        }
        settings.setValue(canvasCollectionKey()+"/enabled", false);
        verticalCanvasError.clear();
        obs_frontend_save();
        return "vertical_canvas_disabled";
    }
    obs_video_info info{}, current{};
    if (!obs_get_video_info(&info)) return "vertical_canvas_setup_failed";
    if (verticalCanvas && !obs_canvas_removed(verticalCanvas->canvas) &&
        obs_canvas_get_video_info(verticalCanvas->canvas,&current) && current.fps_num==info.fps_num && current.fps_den==info.fps_den)
        {
            settings.setValue(canvasCollectionKey()+"/uuid",QString::fromUtf8(obs_canvas_get_uuid(verticalCanvas->canvas)));
            settings.setValue(canvasCollectionKey()+"/enabled",true);
            verticalCanvasError.clear();return "vertical_canvas_ready";
        }
    verticalCanvas.reset();
    const QString saved = settings.value(canvasCollectionKey()+"/uuid").toString();
    obs_canvas_t *owned = nullptr;
    obs_frontend_canvas_list list{};
    obs_frontend_get_canvases(&list);
    for (size_t i=0;i<list.canvases.num;++i) {
        auto *candidate=list.canvases.array[i];
        if (!saved.isEmpty() && saved==QString::fromUtf8(obs_canvas_get_uuid(candidate)) &&
            !(obs_canvas_get_flags(candidate)&EPHEMERAL) && !obs_canvas_removed(candidate)) {
            owned=obs_canvas_get_ref(candidate);break;
        }
    }
    obs_frontend_canvas_list_free(&list);
    const bool created = !owned;
    if (!owned) owned=obs_frontend_add_canvas(verticalCanvasName,nullptr,ACTIVATE);
    if (!owned) return "vertical_canvas_setup_failed";
    // A persistent canvas is included in OBS's Additional Canvas dropdown.
    auto next = std::make_shared<VerticalCanvasVideo>();
    if (!next->attach(owned)) {
        if(created)obs_frontend_remove_canvas(owned);
        return "vertical_canvas_setup_failed";
    }
    settings.setValue(canvasCollectionKey()+"/uuid",QString::fromUtf8(obs_canvas_get_uuid(owned)));
    settings.setValue(canvasCollectionKey()+"/enabled",true);
    verticalCanvas=std::move(next);
    verticalCanvasError.clear();
    obs_frontend_save();
    return "vertical_canvas_ready";
}
static void restoreVerticalCanvas()
{
    if(verticalCanvasClosing||verticalCanvasLoading)return;
    QSettings settings("Forged Destiny Gaming","ForgeCast");
    if (!verticalCanvas && !settings.value(canvasCollectionKey()+"/enabled",false).toBool()) return;
    const QString result=setVerticalCanvas(true);
    if(result!="vertical_canvas_ready")verticalCanvasError=result;
}
static QJsonObject verticalCanvasTelemetry()
{
    QSettings settings("Forged Destiny Gaming","ForgeCast");
    const bool registered=verticalCanvas && !obs_canvas_removed(verticalCanvas->canvas);
    auto *profile=obs_frontend_get_profile_config();
    auto *service=obs_frontend_get_streaming_service();
    auto *serviceSettings=service?obs_service_get_settings(service):nullptr;
    const QString serviceName=serviceSettings?QString::fromUtf8(obs_data_get_string(serviceSettings,"service")):QString();
    if(serviceSettings)obs_data_release(serviceSettings);
    return QJsonObject{{"enabled",settings.value(canvasCollectionKey()+"/enabled",false).toBool()},
        {"registered",registered},{"selected",registered&&canvasSelected()},
        {"enhanced",profile&&config_get_bool(profile,"Stream1","EnableMultitrackVideo")},
        {"twitch_main",serviceName.contains("Twitch",Qt::CaseInsensitive)},
        {"busy",obs_video_active()},{"error",verticalCanvasError}};
}
