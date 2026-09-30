// FDGCast native output module. Alpha: build and validate against your OBS SDK.
// No credentials are written to OBS logs or the configuration directory.
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <QApplication>
#include <QByteArray>
#include <QColor>
#include <QComboBox>
#include <QDateTime>
#include <QDockWidget>
#include <QDialog>
#include <QDialogButtonBox>
#include <QFile>
#include <QFormLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMainWindow>
#include <QMessageBox>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPushButton>
#include <QPointer>
#include <QSettings>
#include <QSizePolicy>
#include <QStringList>
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
    return "FDGCast by Forged Destiny Gaming: multistream output control";
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
    QComboBox *sendTo;
    QLineEdit *compose;
    QPushButton *sendButton;
    QLabel *sendStatus;
    QString pendingText;
    std::function<void(const QJsonObject &)> send;
    QByteArray lastMessages;
public:
    explicit ChatDock(std::function<void(const QJsonObject &)> submit) : QWidget(), send(std::move(submit))
    {
        setStyleSheet("QWidget { background: #151719; color: #f4f4f4; }"
                      "QTextBrowser { background: #1d2022; border: 0; padding: 8px; }"
                      "QLabel { color: #ff7549; padding: 8px; }");
        auto *layout = new QVBoxLayout(this);
        connection = new QLabel("FDGCAST CHAT · Start FDGCast to connect", this);
        connection->setWordWrap(true);
        connection->setMinimumWidth(0);
        connection->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        feed = new QTextBrowser(this);
        feed->setOpenExternalLinks(false);
        feed->setMinimumWidth(0);
        layout->addWidget(connection);
        layout->addWidget(feed);
        auto *composer = new QHBoxLayout();
        sendTo = new QComboBox(this);
        sendTo->addItem("Twitch", "twitch");
        sendTo->addItem("YouTube", "youtube");
        sendTo->addItem("Kick", "kick");
        sendTo->setToolTip("Replies go to your connected channel on this platform.");
        compose = new QLineEdit(this);
        compose->setPlaceholderText("Message your channel…");
        compose->setMaxLength(200);
        compose->setMinimumWidth(0);
        compose->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        sendButton = new QPushButton("Send", this);
        sendTo->setSizePolicy(QSizePolicy::Minimum, QSizePolicy::Fixed);
        composer->addWidget(sendTo);
        composer->addWidget(compose, 1);
        composer->addWidget(sendButton);
        layout->addLayout(composer);
        sendStatus = new QLabel("Choose a connected channel to reply.", this);
        sendStatus->setWordWrap(true);
        sendStatus->setMinimumWidth(0);
        sendStatus->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        layout->addWidget(sendStatus);
        auto submitMessage = [this] {
            const auto value = compose->text().trimmed();
            if (value.isEmpty() || !sendButton->isEnabled()) return;
            pendingText = compose->text();
            sendButton->setEnabled(false);
            sendStatus->setText("Sending to " + sendTo->currentText() + "…");
            send(QJsonObject{{"action", "chat_send"}, {"platform", sendTo->currentData().toString()},
                             {"text", value}});
        };
        connect(sendButton, &QPushButton::clicked, this, submitMessage);
        connect(compose, &QLineEdit::returnPressed, this, submitMessage);
    }

    void sendResult(bool success, const QString &error)
    {
        sendButton->setEnabled(true);
        if (success && compose->text() == pendingText) compose->clear();
        sendStatus->setText(success ? "Message sent to your selected channel." :
                            (error.isEmpty() ? "Message could not be sent. Check your connection." : error));
        pendingText.clear();
    }

    void disconnected()
    {
        connection->setText("FDGCAST CHAT · Companion offline");
    }

    void update(const QJsonObject &payload)
    {
        const auto statuses = payload.value("statuses").toObject();
        connection->setText("FDGCAST CHAT · Twitch: " + statuses.value("twitch").toString("offline") +
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

class EventsDock : public QWidget {
    QTextBrowser *feed;
    QByteArray lastEvents;
public:
    EventsDock() : QWidget()
    {
        setStyleSheet("QWidget { background:#151719;color:#f4f4f4; }"
                      "QTextBrowser { background:#1d2022;border:0;padding:8px; }"
                      "QLabel { color:#ff7549;padding:5px; }");
        auto *layout = new QVBoxLayout(this);
        auto *heading = new QLabel("FDGCAST EVENTS", this);
        heading->setStyleSheet("font-weight:700");
        feed = new QTextBrowser(this);
        feed->setOpenExternalLinks(false);
        auto *note = new QLabel("Twitch/YouTube activity · OBS status · Stream Doctor. "
                                "Kick alerts and Twitch follows need additional platform support.", this);
        note->setWordWrap(true);
        layout->addWidget(heading);
        layout->addWidget(feed);
        layout->addWidget(note);
        disconnected();
    }
    void disconnected() { feed->setHtml("<p>Start the FDGCast app to see activity.</p>"); }
    void update(const QJsonObject &payload)
    {
        const auto events = payload.value("events").toArray();
        const auto bytes = QJsonDocument(events).toJson(QJsonDocument::Compact);
        if (bytes == lastEvents) return;
        lastEvents = bytes;
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>";
        for (const auto &entry : events) {
            const auto row = entry.toObject();
            const auto source = row.value("source").toString().toHtmlEscaped();
            const auto description = row.value("text").toString().toHtmlEscaped();
            const auto timestamp = QDateTime::fromSecsSinceEpoch(static_cast<qint64>(row.value("time").toDouble()))
                                       .toLocalTime().toString("h:mm AP");
            html += "<p style='margin:0 0 12px'><b style='color:#ff7549'>" + source +
                    "</b> · <span style='color:#a9adb0'>" + timestamp +
                    "</span><br>" + description + "</p>";
        }
        if (events.isEmpty()) html += "<p>Activity from your connected platforms will appear here.</p>";
        feed->setHtml(html + "</div>");
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
        auto *heading = new QLabel("STREAM DOCTOR · FDGCAST", this);
        heading->setStyleSheet("color:#ff7549;font-weight:700;padding:8px");
        report = new QTextBrowser(this);
        report->setOpenExternalLinks(false);
        layout->addWidget(heading);
        layout->addWidget(report);
        disconnected();
    }

    void disconnected()
    {
        report->setHtml("<p>Start the FDGCast companion to see OBS frame diagnostics.</p>");
    }

    void update(const QJsonObject &payload)
    {
        if (!payload.value("obs_connected").toBool()) {
            report->setHtml("<p>OBS telemetry is disconnected. Open FDGCast setup in the Control dock "
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
    QPushButton *startButton;
    QPushButton *stopButton;
    QPushButton *removeButton;
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
                      "QListWidget { background:#1d2022;border:1px solid #363a3e;border-radius:5px;padding:3px; }"
                      "QListWidget::item { padding:7px; }"
                      "QListWidget::item:selected { background:#453126;color:#ffffff; }"
                      "QPushButton { background:#ff531f;color:#151719;border:0;border-radius:4px;"
                      "padding:6px;font-weight:600; }"
                      "QPushButton:disabled { background:#34383b;color:#909497; }"
                      "QPushButton#secondary { background:#34383b;color:#f4f4f4; }"
                      "QPushButton#stopAll { background:#342421;color:#ff9576; }"
                      "QLabel { padding:3px; }");
        auto *layout = new QVBoxLayout(this);
        auto *heading = new QLabel("FDGCAST MULTISTREAM", this);
        heading->setStyleSheet("color:#ff7549;font-weight:700");
        status = new QLabel("Start the FDGCast app to connect.", this);
        status->setWordWrap(true);
        list = new QListWidget(this);
        list->setMinimumHeight(95);
        list->setMaximumHeight(220);
        layout->addWidget(heading);
        layout->addWidget(status);
        layout->addWidget(list);
        auto *add = new QPushButton("+ Add stream", this);
        removeButton = new QPushButton("Remove", this);
        removeButton->setObjectName("secondary");
        startButton = new QPushButton("Start selected", this);
        stopButton = new QPushButton("Stop selected", this);
        stopButton->setObjectName("secondary");
        auto *stopAll = new QPushButton("Stop all", this);
        stopAll->setObjectName("stopAll");
        auto *management = new QHBoxLayout();
        management->addWidget(add);
        management->addWidget(removeButton);
        layout->addLayout(management);
        auto *controls = new QHBoxLayout();
        controls->addWidget(startButton);
        controls->addWidget(stopButton);
        layout->addLayout(controls);
        layout->addWidget(stopAll);
        layout->addStretch();
        startButton->setEnabled(false);
        stopButton->setEnabled(false);
        removeButton->setEnabled(false);
        connect(list, &QListWidget::currentItemChanged, this, [this] {
            const bool selected = !selectedId().isEmpty();
            startButton->setEnabled(selected);
            stopButton->setEnabled(selected);
            removeButton->setEnabled(selected);
        });
        connect(add, &QPushButton::clicked, this, [this] {
            QDialog dialog(this);
            dialog.setWindowTitle("Add FDGCast destination");
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
        connect(startButton, &QPushButton::clicked, this, [this] {
            if (!selectedId().isEmpty()) send(QJsonObject{{"action", "start"}, {"id", selectedId()}});
        });
        connect(stopButton, &QPushButton::clicked, this, [this] {
            if (!selectedId().isEmpty()) send(QJsonObject{{"action", "stop"}, {"id", selectedId()}});
        });
        connect(stopAll, &QPushButton::clicked, this, [this] {
            send(QJsonObject{{"action", "stop_all"}});
        });
        connect(removeButton, &QPushButton::clicked, this, [this] {
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
                auto *item = new QListWidgetItem(dest.value("name").toString() + "   " + state, list);
                item->setData(Qt::UserRole, dest.value("id").toString());
                if (state == "LIVE") item->setForeground(QColor("#80d6a0"));
                else if (state == "RECONNECTING") item->setForeground(QColor("#ff9576"));
                if (item->data(Qt::UserRole).toString() == selected) list->setCurrentItem(item);
            }
        }
        if (destinations.isEmpty())
            status->setText("No extra streams yet. Add a destination to get started.");
        else if (!payload.value("stream_active").toBool())
            status->setText("Main stream offline · Start OBS streaming first (H.264/AAC).");
        else
            status->setText("Main stream live · Select a destination to control it.");
    }
};

static QPointer<ChatDock> chatDock;
static QPointer<EventsDock> eventsDock;
static QPointer<DoctorDock> doctorDock;
static QPointer<MultistreamDock> multistreamDock;
static void arrangeFDGCastDocks();
static bool tryArrangeFDGCastDocks();

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
        label = new QLabel("FDGCAST · FORGED DESTINY GAMING\nStart the local companion to connect.\n"
                           "Secondary outputs reuse OBS main H.264 + AAC encoders.\n"
                           "Start the main OBS stream first. No automatic starts.", this);
        label->setWordWrap(true);
        layout->addWidget(label);
        auto *stop = new QPushButton("Stop FDGCast secondary outputs", this);
        layout->addWidget(stop);
        connect(stop, &QPushButton::clicked, this, [this] { stopAll(); });
        auto *setup = new QPushButton("Open FDGCast app", this);
        layout->addWidget(setup);
        connect(setup, &QPushButton::clicked, this, [this] {
            sendAction(QJsonObject{{"action", "focus"}});
        });
        auto *arrange = new QPushButton("Arrange FDGCast docks", this);
        layout->addWidget(arrange);
        connect(arrange, &QPushButton::clicked, this, [] { arrangeFDGCastDocks(); });
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
            if (action.value("action") == "chat_send" && chatDock)
                chatDock->sendResult(false, "Start the FDGCast app before sending chat.");
            if (multistreamDock) multistreamDock->message("Start the FDGCast companion first.");
            return;
        }
        QNetworkRequest request(QUrl("http://127.0.0.1:17654/native/action"));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setRawHeader("Authorization", "Bearer " + tokenFile.readAll().trimmed());
        request.setTransferTimeout(3000);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        auto *reply = network.post(request, QJsonDocument(action).toJson());
        const bool focusing = action.value("action").toString() == "focus";
        const bool sendingChat = action.value("action").toString() == "chat_send";
        connect(reply, &QNetworkReply::finished, this, [this, reply, focusing, sendingChat] {
            const bool success = reply->error() == QNetworkReply::NoError;
            const auto error = success ? QString() :
                QJsonDocument::fromJson(reply->readAll()).object().value("error").toString();
            if (sendingChat && chatDock)
                chatDock->sendResult(success, error);
            if (multistreamDock) {
                if (!success) {
                    if (focusing) label->setText(error.isEmpty() ? "Open FDGCast from the Start menu." : error);
                    else if (!sendingChat) multistreamDock->message(error.isEmpty() ? "Action failed. Check FDGCast connection." : error);
                } else if (!focusing && !sendingChat) multistreamDock->message("Request accepted. Waiting for OBS output status.");
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
        QByteArray name = ("FDGCast-" + id).toUtf8();
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
            if (eventsDock) eventsDock->disconnected();
            if (doctorDock) doctorDock->disconnected();
            if (multistreamDock) multistreamDock->message("Start the FDGCast companion to manage destinations.");
            label->setText("FDGCAST · Companion not running\n"
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
                if (chatDock) chatDock->update(payload);
                if (eventsDock) eventsDock->update(payload);
                if (doctorDock) doctorDock->update(payload);
                if (multistreamDock) multistreamDock->update(payload);
                for (const auto &value : payload.value("commands").toArray())
                    command(value.toObject());
                label->setText("FDGCAST · Companion connected\n"
                               "Control destinations and read diagnostics in your FDGCast browser dock.\n"
                               "Stopping the main OBS stream also stops secondary outputs.");
            } else {
                if (chatDock) chatDock->disconnected();
                if (eventsDock) eventsDock->disconnected();
                if (doctorDock) doctorDock->disconnected();
                if (multistreamDock) multistreamDock->message("FDGCast companion disconnected.");
                label->setText("FDGCAST · Companion disconnected\n"
                               "Active streams are not stopped by a dashboard outage. Use the button below.");
            }
            reply->deleteLater();
        });
    }
};

static QPointer<ForgeDock> dock;
static QDockWidget *dockHost(QWidget *content)
{
    for (QWidget *parent = content; parent; parent = parent->parentWidget())
        if (auto *host = qobject_cast<QDockWidget *>(parent)) return host;
    return nullptr;
}
static void showDocked(QWidget *content)
{
    // OBS registers new docks hidden and floating; show the existing host.
    auto *host = dockHost(content);
    if (host) {
        host->setAllowedAreas(Qt::AllDockWidgetAreas);
        host->show();
    }
}
static QDockWidget *findObsDock(QMainWindow *main, const QStringList &names)
{
    for (auto *candidate : main->findChildren<QDockWidget *>()) {
        for (const auto &name : names)
            if (candidate->windowTitle().compare(name, Qt::CaseInsensitive) == 0)
                return candidate;
    }
    return nullptr;
}
static void placeBeside(QMainWindow *main, QDockWidget *anchor, QDockWidget *target)
{
    if (!anchor || !target || anchor == target) return;
    const auto area = main->dockWidgetArea(anchor);
    if (area == Qt::NoDockWidgetArea) return;
    target->setFloating(false);
    main->removeDockWidget(target);
    main->addDockWidget(area, target);
    main->splitDockWidget(anchor, target, Qt::Horizontal);
    target->show();
}
static bool tryArrangeFDGCastDocks()
{
    auto *main = static_cast<QMainWindow *>(obs_frontend_get_main_window());
    auto *chat = dockHost(chatDock.data());
    auto *activity = dockHost(eventsDock.data());
    auto *doctor = dockHost(doctorDock.data());
    auto *streams = dockHost(multistreamDock.data());
    auto *control = dockHost(dock.data());
    blog(LOG_INFO, "[FDGCast] Arrange docks: main=%d chat=%d events=%d doctor=%d streams=%d control=%d",
         main != nullptr, chat != nullptr, activity != nullptr, doctor != nullptr, streams != nullptr, control != nullptr);
    if (!main || !chat || !activity || !doctor || !streams || !control) return false;
    main->setDockNestingEnabled(true);
    QDockWidget *hosts[] = {chat, activity, doctor, streams, control};
    for (auto *host : hosts) {
        host->setAllowedAreas(Qt::AllDockWidgetAreas);
        host->setFeatures(QDockWidget::DockWidgetClosable | QDockWidget::DockWidgetMovable | QDockWidget::DockWidgetFloatable);
        host->setFloating(false);
        host->show();
    }
    // Match the OBS workspace: Doctor beside Sources, FDGCast Events in the
    // existing Event List area with Chat next to it, and Multistream by Outputs.
    auto *sources = findObsDock(main, {"Sources"});
    auto *events = findObsDock(main, {"Event List"});
    auto *outputs = findObsDock(main, {"Outputs"});
    if (sources && main->dockWidgetArea(sources) != Qt::NoDockWidgetArea)
        placeBeside(main, sources, doctor);
    else main->addDockWidget(Qt::BottomDockWidgetArea, doctor);
    if (events && main->dockWidgetArea(events) != Qt::NoDockWidgetArea) {
        placeBeside(main, events, chat);
        main->removeDockWidget(activity);
        main->addDockWidget(main->dockWidgetArea(events), activity);
        main->tabifyDockWidget(events, activity);
    } else {
        main->addDockWidget(Qt::RightDockWidgetArea, activity);
        placeBeside(main, activity, chat);
    }
    if (outputs && main->dockWidgetArea(outputs) != Qt::NoDockWidgetArea)
        placeBeside(main, outputs, streams);
    else main->addDockWidget(Qt::BottomDockWidgetArea, streams);
    main->addDockWidget(main->dockWidgetArea(streams), control);
    main->tabifyDockWidget(streams, control);
    doctor->show(); activity->show(); chat->show(); streams->show();
    activity->raise(); streams->raise();
    blog(LOG_INFO, "[FDGCast] Arrange docks completed (sources=%d event-list=%d outputs=%d)",
         sources != nullptr, events != nullptr, outputs != nullptr);
    return true;
}
static void arrangeFDGCastDocks()
{
    auto *retry = new QTimer(qApp);
    retry->setInterval(250);
    auto attempts = std::make_shared<int>(0);
    QObject::connect(retry, &QTimer::timeout, retry, [retry, attempts] {
        if (tryArrangeFDGCastDocks()) {
            QSettings settings("Forged Destiny Gaming", "ForgeCast");
            settings.setValue("arranged-layout-0.3.3", true);
            retry->stop(); retry->deleteLater();
        } else if (++*attempts >= 12) {
            retry->stop(); retry->deleteLater();
            blog(LOG_WARNING, "[FDGCast] Could not arrange docks: one or more hosts are unavailable.");
            QMessageBox::warning(static_cast<QWidget *>(obs_frontend_get_main_window()), "FDGCast docks",
                "OBS could not find all five FDGCast docks. Open them from the Docks menu and try Arrange again. "
                "The OBS log lists which docks were found.");
        }
    });
    retry->start();
}
static void frontendEvent(enum obs_frontend_event event, void *)
{
    if (event == OBS_FRONTEND_EVENT_STREAMING_STOPPING && dock)
        dock->stopAll();
    if (event == OBS_FRONTEND_EVENT_EXIT && dock) {
        obs_frontend_remove_dock("forgecast-chat");
        obs_frontend_remove_dock("forgecast-events");
        obs_frontend_remove_dock("forgecast-doctor");
        obs_frontend_remove_dock("forgecast-multistream");
        if (chatDock) delete chatDock.data();
        if (eventsDock) delete eventsDock.data();
        if (doctorDock) delete doctorDock.data();
        if (multistreamDock) delete multistreamDock.data();
        chatDock.clear();
        eventsDock.clear();
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
    chatDock = new ChatDock([](const QJsonObject &action) {
        if (dock) dock->sendAction(action);
    });
    if (!obs_frontend_add_dock_by_id("forgecast-chat", "FDGCast Chat", chatDock.data())) {
        delete chatDock.data();
        chatDock.clear();
    } else showDocked(chatDock.data());
    eventsDock = new EventsDock();
    if (!obs_frontend_add_dock_by_id("forgecast-events", "FDGCast Events", eventsDock.data())) {
        delete eventsDock.data();
        eventsDock.clear();
    } else showDocked(eventsDock.data());
    doctorDock = new DoctorDock();
    if (!obs_frontend_add_dock_by_id("forgecast-doctor", "FDGCast Stream Doctor", doctorDock.data())) {
        delete doctorDock.data();
        doctorDock.clear();
    } else showDocked(doctorDock.data());
    dock = new ForgeDock();
    if (!obs_frontend_add_dock_by_id("forgecast-control", "FDGCast Control", dock.data())) {
        delete dock.data();
        dock.clear();
        return;
    }
    showDocked(dock.data());
    multistreamDock = new MultistreamDock([](const QJsonObject &action) {
        if (dock) dock->sendAction(action);
    });
    if (!obs_frontend_add_dock_by_id("forgecast-multistream", "FDGCast Multistream", multistreamDock.data())) {
        delete multistreamDock.data();
        multistreamDock.clear();
    } else showDocked(multistreamDock.data());
    // OBS retains the historical dock IDs so existing workspace layouts survive upgrades.
    // Apply the FDG shield when a dock is floated into its own window.
    char *iconPath = obs_module_file("FDGCast.ico");
    if (iconPath) {
        const QIcon icon(QString::fromUtf8(iconPath));
        bfree(iconPath);
        QWidget *contents[] = {chatDock.data(), eventsDock.data(), doctorDock.data(),
                               multistreamDock.data(), dock.data()};
        for (QWidget *content : contents) {
            if (content && content->parentWidget()) content->parentWidget()->setWindowIcon(icon);
        }
    }
    QSettings settings("Forged Destiny Gaming", "ForgeCast");
    if (!settings.value("arranged-layout-0.3.3", false).toBool()) {
        QTimer::singleShot(0, [] {
            arrangeFDGCastDocks();
        });
    }
    obs_frontend_add_tools_menu_item("FDGCast: Arrange docks", [](void *) {
        arrangeFDGCastDocks();
    }, nullptr);
    obs_frontend_add_event_callback(frontendEvent, nullptr);
}

void obs_module_unload(void)
{
    obs_frontend_remove_event_callback(frontendEvent, nullptr);
    // OBS normally emits EXIT first. Do not access frontend UI after Qt shutdown.
}
