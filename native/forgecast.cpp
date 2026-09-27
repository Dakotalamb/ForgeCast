// ForgeCast native output module. Alpha: build and validate against your OBS SDK.
// No credentials are written to OBS logs or the configuration directory.
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <QApplication>
#include <QByteArray>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPushButton>
#include <QPointer>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>
#include <map>
#include <memory>
#include <cstring>

OBS_DECLARE_MODULE()
MODULE_EXPORT const char *obs_module_description(void)
{
    return "ForgeCast by Forged Destiny Gaming: multistream output control";
}

struct Destination {
    obs_output_t *output = nullptr;
    obs_service_t *service = nullptr;
    QString name;
    bool starting = false;
    bool stopping = false;
    int startupTicks = 0;
    ~Destination()
    {
        if (output) {
            obs_output_force_stop(output);
            obs_output_release(output);
        }
        if (service)
            obs_service_release(service);
    }
};

class ForgeDock : public QWidget {
    QNetworkAccessManager network;
    QTimer timer;
    QLabel *label;
    std::map<QString, std::unique_ptr<Destination>> destinations;
    QJsonArray results;
    bool pending = false;
    QString bridgePath;
public:
    ForgeDock() : QWidget(), network(this)
    {
        setObjectName("forgecastDock");
        setStyleSheet("QWidget#forgecastDock { background: #151719; color: #f4f4f4; }"
                      "QLabel { color: #f4f4f4; padding: 10px; }"
                      "QPushButton { background: #ff531f; color: #151719; border: 0;"
                      "border-radius: 5px; padding: 10px; font-weight: 700; }"
                      "QPushButton:hover { background: #ff7549; }");
        auto *layout = new QVBoxLayout(this);
        label = new QLabel("FORGECAST · FORGED DESTINY GAMING\nStart the local companion to connect.\n"
                           "Secondary outputs reuse OBS main H.264 + AAC encoders.\n"
                           "Start the main OBS stream first. No automatic starts.", this);
        label->setWordWrap(true);
        layout->addWidget(label);
        auto *stop = new QPushButton("Stop ForgeCast secondary outputs", this);
        layout->addWidget(stop);
        connect(stop, &QPushButton::clicked, this, [this] { stopAll(); });
        layout->addStretch();
#ifdef _WIN32
        bridgePath = qEnvironmentVariable("LOCALAPPDATA") + "/ForgeCast/bridge-token";
#else
        bridgePath = qEnvironmentVariable("HOME") + "/.local/share/ForgeCast/bridge-token";
#endif
        connect(&timer, &QTimer::timeout, this, [this] { tick(); });
        timer.start(1000);
    }

    void stopAll()
    {
        for (auto &entry : destinations) {
            auto &d = *entry.second;
            obs_output_stop(d.output);
            d.starting = false;
            d.stopping = true;
        }
    }

    ~ForgeDock() override
    {
        timer.stop();
        // Prevent network callbacks while the dock is being torn down.
        for (auto *reply : network.findChildren<QNetworkReply *>()) {
            reply->disconnect(this);
            reply->abort();
        }
        destinations.clear();
    }

    QString start(const QJsonObject &obj)
    {
        QString id = obj.value("id").toString();
        QUrl url(obj.value("server").toString());
        if (id.isEmpty() || id.size() > 40 || url.host().isEmpty() ||
            (url.scheme() != "rtmp" && url.scheme() != "rtmps") ||
            !url.userInfo().isEmpty() || !url.query().isEmpty() || !url.fragment().isEmpty() ||
            obj.value("key").toString().isEmpty())
            return "invalid_destination";
        auto old = destinations.find(id);
        if (old != destinations.end()) {
            if (obs_output_active(old->second->output) || old->second->starting || old->second->stopping)
                return "already_active_or_busy";
            destinations.erase(old);
        }
        if (destinations.size() >= 8)
            return "destination_limit";
        if (!obs_frontend_streaming_active())
            return "start_main_obs_stream_first";
        obs_output_t *mainOutput = obs_frontend_get_streaming_output();
        if (!mainOutput)
            return "main_output_unavailable";
        obs_encoder_t *video = obs_output_get_video_encoder(mainOutput);
        obs_encoder_t *audio = obs_output_get_audio_encoder(mainOutput, 0);
        if (!video || !audio || std::strcmp(obs_encoder_get_codec(video), "h264") != 0 ||
            std::strcmp(obs_encoder_get_codec(audio), "aac") != 0) {
            obs_output_release(mainOutput);
            return "requires_main_h264_aac_disable_enhanced_broadcasting";
        }
        auto d = std::make_unique<Destination>();
        d->name = obj.value("name").toString();
        obs_data_t *settings = obs_data_create();
        QByteArray server = obj.value("server").toString().toUtf8();
        QByteArray key = obj.value("key").toString().toUtf8();
        obs_data_set_string(settings, "server", server.constData());
        obs_data_set_string(settings, "key", key.constData());
        obs_data_set_bool(settings, "use_auth", false);
        QByteArray name = ("ForgeCast-" + id).toUtf8();
        d->service = obs_service_create("rtmp_custom", name.constData(), settings, nullptr);
        obs_data_release(settings);
        key.fill('\0');
        if (!d->service) {
            obs_output_release(mainOutput);
            return "service_create_failed";
        }
        d->output = obs_output_create("rtmp_output", name.constData(), nullptr, nullptr);
        if (!d->output) {
            obs_output_release(mainOutput);
            return "output_create_failed";
        }
        obs_output_set_service(d->output, d->service);
        obs_output_set_video_encoder(d->output, video);
        obs_output_set_audio_encoder(d->output, audio, 0);
        obs_output_set_reconnect_settings(d->output, 10, 2);
        d->starting = obs_output_start(d->output);
        obs_output_release(mainOutput);
        if (!d->starting)
            return "start_failed_check_obs";
        destinations.emplace(id, std::move(d));
        return "start_requested_not_yet_confirmed_live";
    }

    void command(const QJsonObject &cmd)
    {
        QString action = cmd.value("action").toString();
        QString result = "unsupported_command";
        if (action == "start") {
            result = start(cmd.value("destination").toObject());
        } else if (action == "stop_all") {
            stopAll();
            result = "stop_all_requested";
        } else if (action == "stop") {
            auto it = destinations.find(cmd.value("destination").toObject().value("id").toString());
            if (it != destinations.end()) {
                obs_output_stop(it->second->output);
                it->second->starting = false;
                it->second->stopping = true;
                result = "stop_requested";
            } else {
                result = "output_not_created";
            }
        }
        results.append(QJsonObject{{"id", cmd.value("id")}, {"status", result}});
        while (results.size() > 30)
            results.removeAt(0);
    }

    void tick()
    {
        // Main-stream stop always stops these shared-encoder outputs too.
        if (!obs_frontend_streaming_active())
            stopAll();
        if (pending)
            return;
        QFile tokenFile(bridgePath);
        if (!tokenFile.open(QIODevice::ReadOnly)) {
            label->setText("FORGECAST · Companion not running\n"
                           "Secondary streams, if active, can be stopped below.");
            return;
        }
        QByteArray token = tokenFile.readAll().trimmed();
        if (token.size() < 32 || token.size() > 128)
            return;
        QJsonArray outputs;
        for (auto &entry : destinations) {
            auto &d = *entry.second;
            bool active = obs_output_active(d.output);
            if (active) d.starting = false;
            if (!active && d.stopping) d.stopping = false;
            // A timed-out asynchronous start must be stopped before being retried.
            if (d.starting && ++d.startupTicks > 30) {
                obs_output_force_stop(d.output);
                d.starting = false;
                d.stopping = true;
                results.append(QJsonObject{{"status", "start_timeout_stopped"}});
            }
            outputs.append(QJsonObject{{"id", entry.first}, {"name", d.name}, {"active", active},
                {"busy", d.starting || d.stopping}, {"reconnecting", obs_output_reconnecting(d.output)},
                {"dropped", obs_output_get_frames_dropped(d.output)},
                {"frames", obs_output_get_total_frames(d.output)},
                {"bytes", static_cast<double>(obs_output_get_total_bytes(d.output))}});
        }
        QNetworkRequest request(QUrl("http://127.0.0.1:17654/native/poll"));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setRawHeader("Authorization", "Bearer " + token);
        request.setTransferTimeout(3000);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        const int sentResults = results.size();
        auto *reply = network.post(request, QJsonDocument(QJsonObject{{"outputs", outputs}, {"results", results}}).toJson());
        pending = true;
        connect(reply, &QNetworkReply::finished, this, [this, reply, sentResults] {
            pending = false;
            if (reply->error() == QNetworkReply::NoError) {
                for (int i = 0; i < sentResults && !results.isEmpty(); ++i) results.removeAt(0);
                auto payload = QJsonDocument::fromJson(reply->readAll()).object();
                for (const auto &value : payload.value("commands").toArray())
                    command(value.toObject());
                label->setText("FORGECAST · Companion connected\n"
                               "Control destinations and read diagnostics in your ForgeCast browser dock.\n"
                               "Stopping the main OBS stream also stops secondary outputs.");
            } else {
                label->setText("FORGECAST · Companion disconnected\n"
                               "Active streams are not stopped by a dashboard outage. Use the button below.");
            }
            reply->deleteLater();
        });
    }
};

static QPointer<ForgeDock> dock;
static void frontendEvent(enum obs_frontend_event event, void *)
{
    if (event == OBS_FRONTEND_EVENT_STREAMING_STOPPING && dock)
        dock->stopAll();
    if (event == OBS_FRONTEND_EVENT_EXIT && dock) {
        obs_frontend_remove_dock("forgecast-control");
        if (dock) delete dock.data();
        dock.clear();
    }
}

bool obs_module_load(void)
{
    return true;
}

void obs_module_post_load(void)
{
    dock = new ForgeDock();
    if (!obs_frontend_add_dock_by_id("forgecast-control", "ForgeCast Control", dock.data())) {
        delete dock.data();
        dock.clear();
        return;
    }
    obs_frontend_add_event_callback(frontendEvent, nullptr);
}

void obs_module_unload(void)
{
    obs_frontend_remove_event_callback(frontendEvent, nullptr);
    // OBS normally emits EXIT first. Do not access frontend UI after Qt shutdown.
}
