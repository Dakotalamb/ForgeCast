// Test-only OBS module: execute production canvas registration in the real frontend.
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <util/config-file.h>
#include <graphics/graphics.h>
#include <graphics/vec4.h>
#include <QApplication>
#include <QDialog>
#include <QFile>
#include <QEvent>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSettings>
#include <QTimer>
#include <QUrl>
#include <QWidget>
#include <memory>
#include <stdexcept>
#include "vertical-render.hpp"
#include "portrait-video.hpp"
#include "vertical-canvas-frontend.hpp"
OBS_DECLARE_MODULE()
MODULE_EXPORT const char *obs_module_description(void){return "FDGCast canvas frontend QA (test only)";}
static void require(bool ok,const char *message){if(!ok)throw std::runtime_error(message);}
static void verifyCanvas()
{
    QJsonObject report;const int stage=qEnvironmentVariableIntValue("FDGCAST_CANVAS_QA_STAGE");report["stage"]=stage;
    try {
        verticalCanvasLoading=false;
        obs_video_info before{},after{};require(obs_get_video_info(&before),"Main video not initialized");
        QSettings settings("Forged Destiny Gaming","ForgeCast");
        const QString saved=settings.value(canvasCollectionKey()+"/uuid").toString();
        if(stage==2){require(!saved.isEmpty(),"Saved binding missing");restoreVerticalCanvas();}
        else require(setVerticalCanvas(true)=="vertical_canvas_ready","Frontend registration failed");
        require(verticalCanvas && !obs_canvas_removed(verticalCanvas->canvas),"Canvas unavailable");
        const QString uuid=QString::fromUtf8(obs_canvas_get_uuid(verticalCanvas->canvas));
        if(stage==2)require(uuid==saved,"Canvas UUID changed after OBS restart");
        obs_frontend_canvas_list canvases{};obs_frontend_get_canvases(&canvases);int found=0;
        for(size_t i=0;i<canvases.canvases.num;++i){auto *c=canvases.canvases.array[i];
            if(QString::fromUtf8(obs_canvas_get_name(c))==verticalCanvasName){++found;require(!(obs_canvas_get_flags(c)&EPHEMERAL),"Canvas excluded from OBS picker");}}
        obs_frontend_canvas_list_free(&canvases);require(found==1,"Duplicate or missing frontend canvas");
        auto *profile=obs_frontend_get_profile_config();require(profile,"Missing OBS profile");
        if(stage==2)require(canvasSelected(),"Additional Canvas selection not retained after restart");
        config_set_bool(profile,"Stream1","EnableMultitrackVideo",true);
        config_set_string(profile,"Stream1","MultitrackExtraCanvas",uuid.toUtf8().constData());
        const auto state=verticalCanvasTelemetry();require(state.value("selected").toBool()&&state.value("enhanced").toBool(),"OBS selection not detected");
        require(setVerticalCanvas(false)=="vertical_canvas_selected","Selected canvas could be removed");
        if(stage==1){
            config_set_string(profile,"Stream1","MultitrackExtraCanvas","");
            require(setVerticalCanvas(false)=="vertical_canvas_disabled","Canvas disable failed");
            QCoreApplication::sendPostedEvents(nullptr,QEvent::MetaCall);
            require(setVerticalCanvas(true)=="vertical_canvas_ready","Canvas re-enable failed");
            config_set_string(profile,"Stream1","MultitrackExtraCanvas",obs_canvas_get_uuid(verticalCanvas->canvas));
        }
        require(obs_get_video_info(&after)&&before.base_width==after.base_width&&before.output_width==after.output_width&&before.output_height==after.output_height,"Canvas registration changed main video");
        require(config_save(profile)==CONFIG_SUCCESS,"Profile save failed");obs_frontend_save();
        report["success"]=true;report["registered_count"]=found;report["selected"]=true;
        report["uuid"]=QString::fromUtf8(obs_canvas_get_uuid(verticalCanvas->canvas));
    } catch(const std::exception &e){report["success"]=false;report["error"]=QString::fromUtf8(e.what());}
    QFile output(qEnvironmentVariable("FDGCAST_CANVAS_QA_REPORT"));
    if(output.open(QIODevice::WriteOnly))output.write(QJsonDocument(report).toJson());
    QTimer::singleShot(1000,qApp,[]{
        for(auto *widget:qApp->topLevelWidgets())if(auto *dialog=qobject_cast<QDialog *>(widget))dialog->reject();
        if(auto *window=static_cast<QWidget *>(obs_frontend_get_main_window()))window->close();
    });
}
static void event(enum obs_frontend_event value,void *)
{
    if(value==OBS_FRONTEND_EVENT_FINISHED_LOADING)QTimer::singleShot(1000,qApp,verifyCanvas);
    if(value==OBS_FRONTEND_EVENT_EXIT){verticalCanvasClosing=true;verticalCanvas.reset();}
}
bool obs_module_load(void){registerPortraitSource();return true;}
void obs_module_post_load(void){obs_frontend_add_event_callback(event,nullptr);}
void obs_module_unload(void){obs_frontend_remove_event_callback(event,nullptr);verticalCanvas.reset();}
