// ForgeCast native output module. Alpha: build and validate against your OBS SDK.
// No credentials are written to OBS logs or the configuration directory.
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <QApplication>
#include <QByteArray>
#include <QDesktopServices>
#include <QDialog>
#include <QDialogButtonBox>
#include <QFile>
#include <QFormLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPushButton>
#include <QPointer>
#include <QTextBrowser>
#include <QTextCursor>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>
#include <map>
#include <memory>
#include <cstring>
#include <functional>

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

class ChatDock : public QWidget {
    QLabel *connection;
    QTextBrowser *feed;
    QByteArray lastMessages;
public:
    ChatDock() : QWidget()
    {
        setStyleSheet("QWidget { background: #151719; color: #f4f4f4; }"
                      "QTextBrowser { background: #1d2022; border: 0; padding: 8px; }"
                      "QLabel { color: #ff7549; padding: 8px; }");
        auto *layout = new QVBoxLayout(this);
        connection = new QLabel("FORGECAST CHAT · Start ForgeCast to connect", this);
        feed = new QTextBrowser(this);
        feed->setOpenExternalLinks(false);
        layout->addWidget(connection);
        layout->addWidget(feed);
    }

    void disconnected()
    {
        connection->setText("FORGECAST CHAT · Companion offline");
    }

    void update(const QJsonObject &payload)
    {
        const auto statuses = payload.value("statuses").toObject();
        connection->setText("FORGECAST CHAT · Twitch: " + statuses.value("twitch").toString("offline") +
                            " · YouTube: " + statuses.value("youtube").toString("offline") +
                            " · Kick: " + statuses.value("kick").toString("offline"));
        const auto messages = payload.value("messages").toArray();
        const auto bytes = QJsonDocument(messages).toJson(QJsonDocument::Compact);
        if (bytes == lastMessages) return;
        lastMessages = bytes;
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>";
        for (const auto &entry : messages) {
            const auto row = entry.toObject();
            const auto platform = row.value("platform").toString().toUpper().toHtmlEscaped();
            const auto origin = row.value("origin").toString().toHtmlEscaped();
            const auto user = row.value("user").toString().toHtmlEscaped();
            const auto message = row.value("text").toString().toHtmlEscaped();
            const auto shared = row.value("shared").toBool() ? " · SHARED CHAT" : "";
            html += "<p style='margin:0 0 12px'><b style='color:#ff7549'>" + platform +
                    " · " + origin + "'s channel" + shared + "</b><br><b>" + user +
                    ":</b> " + message + "</p>";
        }
        if (messages.isEmpty()) html += "<p>Messages will appear here when accounts are connected and live.</p>";
        feed->setHtml(html + "</div>");
        feed->moveCursor(QTextCursor::End);
    }
};

class DoctorDock : public QWidget {
    QTextBrowser *report;
public:
    DoctorDock() : QWidget()
    {
        setStyleSheet("QWidget { background: #151719; color: #f4f4f4; }"
                      "QTextBrowser { background: #1d2022; border: 0; padding: 8px; }");
        auto *layout = new QVBoxLayout(this);
        auto *heading = new QLabel("STREAM DOCTOR · FORGECAST", this);
        heading->setStyleSheet("color:#ff7549;font-weight:700;padding:8px");
        report = new QTextBrowser(this);
        report->setOpenExternalLinks(false);
        layout->addWidget(heading);
        layout->addWidget(report);
        disconnected();
    }

    void disconnected()
    {
        report->setHtml("<p>Start the ForgeCast companion to see OBS frame diagnostics.</p>");
    }

    void update(const QJsonObject &payload)
    {
        if (!payload.value("obs_connected").toBool()) {
            report->setHtml("<p>OBS telemetry is disconnected. Open ForgeCast setup in the Control dock "
                            "and connect OBS WebSocket.</p>");
            return;
        }
        const auto stats = payload.value("stats").toObject();
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>"
                       "<p>Scene: <b>" + payload.value("scene").toString().toHtmlEscaped() + "</b></p>";
        html += "<p>OBS FPS: " + QString::number(stats.value("activeFps").toDouble(), 'f', 1) +
                " · CPU: " + QString::number(stats.value("cpuUsage").toDouble(), 'f', 1) + "%</p>";
        const auto issues = payload.value("issues").toArray();
        if (issues.isEmpty()) html += "<p style='color:#80d6a0'>No frame drops detected in the latest sample.</p>";
        for (const auto &entry : issues) {
            const auto row = entry.toObject();
            html += "<p><b style='color:#ff7549'>" + row.value("title").toString().toHtmlEscaped() +
                    "</b><br>" + row.value("evidence").toString().toHtmlEscaped() +
                    "<br>Try: " + row.value("suggestion").toString().toHtmlEscaped() + "</p>";
        }
        html += "<p style='color:#a9adb0'>Counter-based diagnosis; the faulty process or network hop "
                "cannot be proven from OBS statistics alone.</p></div>";
        report->setHtml(html);
    }
};

class MultistreamDock : public QWidget {
    QLabel *status;
    QListWidget *list;
    QByteArray lastDestinations;
    std::function<void(const QJsonObject &)> send;
    QString selectedId() const
    {
        return list->currentItem() ? list->currentItem()->data(Qt::UserRole).toString() : QString();
    }
public:
    explicit MultistreamDock(std::function<void(const QJsonObject &)> submit) : QWidget(), send(std::move(submit))
    {
        setStyleSheet("QWidget { background:#151719;color:#f4f4f4; }"
                      "QListWidget { background:#1d2022;border:0; }"
                      "QPushButton { background:#ff531f;color:#151719;border:0;padding:8px; }"
                      "QLabel { padding:8px; }");
        auto *layout = new QVBoxLayout(this);
        auto *heading = new QLabel("FORGECAST MULTISTREAM", this);
        heading->setStyleSheet("color:#ff7549;font-weight:700");
        status = new QLabel("Start the ForgeCast companion to manage destinations.", this);
        status->setWordWrap(true);
        list = new QListWidget(this);
        layout->addWidget(heading);
        layout->addWidget(status);
        layout->addWidget(list);
        auto *add = new QPushButton("Add destination", this);
        auto *start = new QPushButton("Start selected", this);
        auto *stop = new QPushButton("Stop selected", this);
        auto *stopAll = new QPushButton("Stop all secondary streams", this);
        auto *remove = new QPushButton("Remove selected", this);
        for (auto *button : {add, start, stop, stopAll, remove}) layout->addWidget(button);
        connect(add, &QPushButton::clicked, this, [this] {
            QDialog dialog(this);
            dialog.setWindowTitle("Add ForgeCast destination");
            QFormLayout form(&dialog);
            QLineEdit name(&dialog), server(&dialog), key(&dialog);
            key.setEchoMode(QLineEdit::Password);
            server.setPlaceholderText("rtmps://example.com/live");
            form.addRow("Name", &name);
            form.addRow("RTMP(S) server", &server);
            form.addRow("Stream key", &key);
            QDialogButtonBox buttons(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, &dialog);
            form.addRow(&buttons);
            connect(&buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
            connect(&buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
            if (dialog.exec() == QDialog::Accepted)
                send(QJsonObject{{"action", "save"}, {"name", name.text()},
                                 {"server", server.text()}, {"key", key.text()}});
            key.clear();
        });
        connect(start, &QPushButton::clicked, this, [this] {
            if (!selectedId().isEmpty()) send(QJsonObject{{"action", "start"}, {"id", selectedId()}});
        });
        connect(stop, &QPushButton::clicked, this, [this] {
            if (!selectedId().isEmpty()) send(QJsonObject{{"action", "stop"}, {"id", selectedId()}});
        });
        connect(stopAll, &QPushButton::clicked, this, [this] {
            send(QJsonObject{{"action", "stop_all"}});
        });
        connect(remove, &QPushButton::clicked, this, [this] {
            if (!selectedId().isEmpty()) send(QJsonObject{{"action", "delete"}, {"id", selectedId()}});
        });
    }

    void message(const QString &value) { status->setText(value); }

    void update(const QJsonObject &payload)
    {
        const auto destinations = payload.value("destinations").toArray();
        const auto outputs = payload.value("outputs").toArray();
        QJsonArray snapshot = destinations;
        for (const auto &output : outputs) snapshot.append(output);
        const auto bytes = QJsonDocument(snapshot).toJson(QJsonDocument::Compact);
        if (bytes != lastDestinations) {
            lastDestinations = bytes;
            const QString selected = selectedId();
            list->clear();
            for (const auto &entry : destinations) {
                const auto dest = entry.toObject();
                QString state = "ready";
                for (const auto &output : outputs) {
                    const auto row = output.toObject();
                    if (row.value("id") == dest.value("id")) {
                        state = row.value("active").toBool() ? "LIVE" :
                                row.value("busy").toBool() ? "connecting/stopping" : "stopped";
                        if (row.value("reconnecting").toBool()) state = "RECONNECTING";
                    }
                }
                auto *item = new QListWidgetItem(dest.value("name").toString() + " · " + state, list);
                item->setData(Qt::UserRole, dest.value("id").toString());
                if (item->data(Qt::UserRole).toString() == selected) list->setCurrentItem(item);
            }
        }
        if (destinations.isEmpty())
            status->setText("Add Twitch, YouTube or Kick using each platform's RTMP server and stream key.");
        else if (!payload.value("stream_active").toBool())
            status->setText("Start the main OBS stream with H.264/AAC before starting extra outputs.");
        else
            status->setText("Main OBS stream active. Select a destination and press Start.");
    }
};

static QPointer<ChatDock> chatDock;
static QPointer<DoctorDock> doctorDock;
static QPointer<MultistreamDock> multistreamDock;

class ForgeDock : public QWidget {
    QNetworkAccessManager network;
    QTimer timer;
    QLabel *label;
    std::map<QString, std::unique_ptr<Destination>> destinations;
    QJsonArray results;
    bool pending = false;
    QString bridgePath;
    QUrl setupUrl;
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
        auto *setup = new QPushButton("Open ForgeCast connection setup", this);
        layout->addWidget(setup);
        connect(setup, &QPushButton::clicked, this, [this] {
            if (setupUrl.isValid()) QDesktopServices::openUrl(setupUrl);
            else label->setText("Start the ForgeCast companion, then try setup again.");
        });
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

    void sendAction(const QJsonObject &action)
    {
        QFile tokenFile(bridgePath);
        if (!tokenFile.open(QIODevice::ReadOnly)) {
            if (multistreamDock) multistreamDock->message("Start the ForgeCast companion first.");
            return;
        }
        QNetworkRequest request(QUrl("http://127.0.0.1:17654/native/action"));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setRawHeader("Authorization", "Bearer " + tokenFile.readAll().trimmed());
        request.setTransferTimeout(3000);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        auto *reply = network.post(request, QJsonDocument(action).toJson());
        connect(reply, &QNetworkReply::finished, this, [reply] {
            if (multistreamDock) {
                if (reply->error() != QNetworkReply::NoError) {
                    QString error = QJsonDocument::fromJson(reply->readAll()).object().value("error").toString();
                    multistreamDock->message(error.isEmpty() ? "Action failed. Check ForgeCast connection." : error);
                } else multistreamDock->message("Request accepted. Waiting for OBS output status.");
            }
            reply->deleteLater();
        });
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
            if (chatDock) chatDock->disconnected();
            if (doctorDock) doctorDock->disconnected();
            if (multistreamDock) multistreamDock->message("Start the ForgeCast companion to manage destinations.");
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
                setupUrl = QUrl(payload.value("setup_url").toString());
                if (chatDock) chatDock->update(payload);
                if (doctorDock) doctorDock->update(payload);
                if (multistreamDock) multistreamDock->update(payload);
                for (const auto &value : payload.value("commands").toArray())
                    command(value.toObject());
                label->setText("FORGECAST · Companion connected\n"
                               "Control destinations and read diagnostics in your ForgeCast browser dock.\n"
                               "Stopping the main OBS stream also stops secondary outputs.");
            } else {
                setupUrl = QUrl();
                if (chatDock) chatDock->disconnected();
                if (doctorDock) doctorDock->disconnected();
                if (multistreamDock) multistreamDock->message("ForgeCast companion disconnected.");
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
        obs_frontend_remove_dock("forgecast-chat");
        obs_frontend_remove_dock("forgecast-doctor");
        obs_frontend_remove_dock("forgecast-multistream");
        if (chatDock) delete chatDock.data();
        if (doctorDock) delete doctorDock.data();
        if (multistreamDock) delete multistreamDock.data();
        chatDock.clear();
        doctorDock.clear();
        multistreamDock.clear();
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
    chatDock = new ChatDock();
    if (!obs_frontend_add_dock_by_id("forgecast-chat", "ForgeCast Chat", chatDock.data())) {
        delete chatDock.data();
        chatDock.clear();
    }
    doctorDock = new DoctorDock();
    if (!obs_frontend_add_dock_by_id("forgecast-doctor", "ForgeCast Stream Doctor", doctorDock.data())) {
        delete doctorDock.data();
        doctorDock.clear();
    }
    dock = new ForgeDock();
    if (!obs_frontend_add_dock_by_id("forgecast-control", "ForgeCast Control", dock.data())) {
        delete dock.data();
        dock.clear();
        return;
    }
    multistreamDock = new MultistreamDock([](const QJsonObject &action) {
        if (dock) dock->sendAction(action);
    });
    if (!obs_frontend_add_dock_by_id("forgecast-multistream", "ForgeCast Multistream", multistreamDock.data())) {
        delete multistreamDock.data();
        multistreamDock.clear();
    }
    obs_frontend_add_event_callback(frontendEvent, nullptr);
}

void obs_module_unload(void)
{
    obs_frontend_remove_event_callback(frontendEvent, nullptr);
    // OBS normally emits EXIT first. Do not access frontend UI after Qt shutdown.
}
