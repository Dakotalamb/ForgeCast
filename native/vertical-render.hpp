#pragma once
#include <memory>
#include <map>
#include <atomic>
#include <mutex>
#include <QJsonObject>
#include <QJsonArray>
#include <QColor>
#include <QSet>
#include "portrait-layout.hpp"

static std::shared_ptr<const QJsonObject> verticalStudioConfig=std::make_shared<const QJsonObject>();
struct PortraitData {
    bool fill, studio;
    obs_source_t *self;
    QJsonObject layout;
    std::map<QString,obs_source_t *> children;
    std::recursive_mutex mutex;
    PortraitData(bool f,bool s,obs_source_t *source):fill(f),studio(s),self(source) {}
    void clearChild(obs_source_t *source) {
        obs_source_remove_active_child(self,source);obs_source_dec_showing(source);obs_source_release(source);
    }
    ~PortraitData() { for (auto &e:children) clearChild(e.second); }
    void tick() {
        if (!studio) return;
        std::lock_guard<std::recursive_mutex> lock(mutex);
        auto *program=obs_get_output_source(0);if (!program) return;
        auto *scene=obs_source_get_type(program)==OBS_SOURCE_TYPE_TRANSITION ? obs_transition_get_active_source(program) : obs_source_get_ref(program);
        const auto snapshot=std::atomic_load(&verticalStudioConfig);
        const auto layouts=snapshot->value("layouts").toObject();
        const QString id=scene?QString::fromUtf8(obs_source_get_uuid(scene)):QString();
        layout=layouts.value(id).toObject();if(layout.isEmpty())layout=layouts.value("*").toObject();
        if(layout.isEmpty())layout=QJsonObject{{"background","#000000"},{"regions",QJsonArray{QJsonObject{{"source","program"},{"fit","fill"},{"x",0},{"y",0},{"width",720},{"height",1280}}}}};
        if(scene)obs_source_release(scene);obs_source_release(program);
        QSet<QString> wanted;
        for(const auto &e:layout.value("regions").toArray()){
            const auto r=e.toObject();const QString uid=r.value("source").toString();
            if(r.value("visible").toBool(true)&&!uid.isEmpty()&&uid!="program")wanted.insert(uid);
        }
        for(auto it=children.begin();it!=children.end();){
            if(!wanted.contains(it->first)){clearChild(it->second);it=children.erase(it);}else ++it;
        }
        for(const auto &uid:wanted)if(!children.count(uid)){
            const auto bytes=uid.toUtf8();auto *source=obs_get_source_by_uuid(bytes.constData());if(!source)continue;
            if(source==self||!(obs_source_get_output_flags(source)&OBS_SOURCE_VIDEO)||!obs_source_add_active_child(self,source)){obs_source_release(source);continue;}
            obs_source_inc_showing(source);children[uid]=source;
        }
    }
    void render(obs_source_t *program){
        std::lock_guard<std::recursive_mutex> lock(mutex);
        const QColor bg(layout.value("background").toString("#000000"));
        vec4 color;vec4_set(&color,static_cast<float>(bg.redF()),static_cast<float>(bg.greenF()),static_cast<float>(bg.blueF()),1.f);
        // The private source is the only source on its own 720x1280 view.
        gs_clear(GS_CLEAR_COLOR,&color,0.f,0);
        for(const auto &e:layout.value("regions").toArray()){
            const auto r=e.toObject();if(!r.value("visible").toBool(true))continue;
            const QString uid=r.value("source").toString();const auto found=children.find(uid);
            auto *source=uid=="program"?program:found==children.end()?nullptr:found->second;if(!source)continue;
            const int w=r.value("width").toInt(720),h=r.value("height").toInt(1280);if(w<20||h<20)continue;
            const float sw=static_cast<float>(obs_source_get_width(source)),sh=static_cast<float>(obs_source_get_height(source));
            const auto p=fdgcast::regionLayout(sw,sh,static_cast<float>(w),static_cast<float>(h),r.value("fit").toString()!="fit",static_cast<float>(r.value("zoom").toDouble(1)),static_cast<float>(r.value("pan_x").toDouble()),static_cast<float>(r.value("pan_y").toDouble()));
            if(p.scale<=0)continue;const bool mirror=r.value("mirror").toBool();
            gs_viewport_push();gs_projection_push();gs_matrix_push();
            gs_set_viewport(r.value("x").toInt(),r.value("y").toInt(),w,h);
            gs_ortho(0.f,static_cast<float>(w),0.f,static_cast<float>(h),-100.f,100.f);
            gs_matrix_identity();gs_matrix_translate3f(p.x+(mirror?sw*p.scale:0.f),p.y,0.f);
            gs_matrix_scale3f(mirror?-p.scale:p.scale,p.scale,1.f);obs_source_video_render(source);
            gs_matrix_pop();gs_projection_pop();gs_viewport_pop();
        }
    }
};
