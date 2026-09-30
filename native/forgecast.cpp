// FDGCast native output module. Alpha: build and validate against your OBS SDK.
// No credentials are written to OBS logs or the configuration directory.
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <QApplication>
#include <QByteArray>
#include <QColor>
#include <QBuffer>
#include <QCursor>
#include <QHash>
#include <QImage>
#include <QMovie>
#include <QPainter>
#include <QPolygon>
#include <QRegularExpression>
#include <QScrollBar>
#include <QSet>
#include <QTextDocument>
#include <QToolTip>
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
    bool wasLive = false;
    QString error;
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

// Images are supplied by Companion's restricted public-image cache. No remote
// URL or account credential is handed to the text widget.
class ChatFeed : public QTextBrowser {
    QNetworkAccessManager network;
    QHash<QUrl, QImage> images;
    QHash<QUrl, QMovie *> movies;
    QSet<QUrl> loading;
    QSet<QUrl> visibleImages;
    void publish(const QUrl &url, const QImage &image)
    {
        if (image.isNull()) return;
        if (images.size() >= 200 && !images.contains(url)) images.erase(images.begin());
        images.insert(url, image);
        document()->addResource(QTextDocument::ImageResource, url, image);
        document()->markContentsDirty(0, document()->characterCount());
        viewport()->update();
    }
    static QImage platformIcon(const QString &platform)
    {
        QImage image(32,32,QImage::Format_ARGB32_Premultiplied); image.fill(Qt::transparent);
        QPainter painter(&image); painter.setRenderHint(QPainter::Antialiasing); painter.setPen(Qt::NoPen);
        if (platform == "youtube") {
            painter.setBrush(QColor("#ff0033")); painter.drawRoundedRect(QRectF(1,5,30,22),6,6);
            painter.setBrush(Qt::white); painter.drawPolygon(QPolygon{{13,10},{13,22},{23,16}});
        } else if (platform == "kick") {
            painter.setBrush(QColor("#53fc18"));
            painter.drawRect(3,3,7,26); painter.drawRect(10,12,7,8);
            painter.drawRect(17,3,7,9); painter.drawRect(17,20,7,9);
            painter.drawRect(24,3,5,5); painter.drawRect(24,24,5,5);
        } else {
            painter.setBrush(QColor("#9146ff")); painter.drawPolygon(QPolygon{{3,1},{31,1},{31,22},{22,31},{15,31},{15,26},{3,26}});
            painter.setBrush(Qt::white); painter.drawPolygon(QPolygon{{7,4},{28,4},{28,19},{21,26},{15,26},{15,22},{7,22}});
            painter.setBrush(QColor("#9146ff")); painter.drawRect(14,8,3,9); painter.drawRect(22,8,3,9);
        }
        return image;
    }
public:
    explicit ChatFeed(QWidget *parent) : QTextBrowser(parent), network(this)
    {
        setOpenLinks(false); setOpenExternalLinks(false);
        connect(this, &QTextBrowser::highlighted, this, [](const QUrl &url) {
            if (url.scheme() == "identity") QToolTip::showText(QCursor::pos(), QUrl::fromPercentEncoding(url.path().toUtf8()));
            else QToolTip::hideText();
        });
    }
    void setVisibleImages(const QSet<QUrl> &urls)
    {
        visibleImages = urls;
        for (auto it = movies.begin(); it != movies.end();) {
            if (!urls.contains(it.key())) { it.value()->stop(); it.value()->deleteLater(); it = movies.erase(it); }
            else ++it;
        }
    }
    QVariant loadResource(int type, const QUrl &url) override
    {
        if (type != QTextDocument::ImageResource) return {};
        if (url.scheme() == "platform") return platformIcon(url.path());
        if (images.contains(url)) return images.value(url);
        if (url.scheme() != "http" || url.host() != "127.0.0.1" || url.port() != 17654 ||
            !QRegularExpression("^/media/[a-f0-9]{64}$").match(url.path()).hasMatch()) return {};
        if (!loading.contains(url)) {
            loading.insert(url);
            QNetworkRequest request(url); request.setTransferTimeout(5000);
            request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
            auto *reply = network.get(request);
            connect(reply, &QNetworkReply::finished, this, [this, reply, url] {
                loading.remove(url);
                const QByteArray bytes = reply->readAll();
                if (reply->error() == QNetworkReply::NoError && bytes.size() <= 1048576) {
                    publish(url, QImage::fromData(bytes));
                    if (bytes.startsWith("GIF") && visibleImages.contains(url) && movies.size() < 40) {
                        auto *movie = new QMovie(this);
                        auto *buffer = new QBuffer(movie); buffer->setData(bytes); buffer->open(QIODevice::ReadOnly);
                        movie->setDevice(buffer); movie->setScaledSize(QSize(28,28));
                        movies.insert(url, movie);
                        connect(movie, &QMovie::frameChanged, this, [this, movie, url](int) { publish(url, movie->currentImage()); });
                        movie->start();
                    }
                }
                reply->deleteLater();
            });
        }
        return {};
    }
};

class ChatDock : public QWidget {
    QLabel *connection;
    ChatFeed *feed;
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
        feed = new ChatFeed(this);
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
        const bool atBottom = feed->verticalScrollBar()->maximum()-feed->verticalScrollBar()->value() < 60;
        const int scroll = feed->verticalScrollBar()->value();
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>";
        QSet<QUrl> visible;
        for (const auto &entry : messages) {
            const auto row = entry.toObject();
            const QString platform = row.value("platform").toString();
            const QString name = row.value("user").toString();
            const QString shortName = name.size() > 22 ? name.left(21)+"…" : name;
            QString color = row.value("color").toString("#d3baff");
            if (!QRegularExpression("^#[a-fA-F0-9]{6}$").match(color).hasMatch()) color = "#d3baff";
            QString avatar;
            const auto avatarPath = row.value("avatar").toString();
            if (row.value("is_creator").toBool() && avatarPath.startsWith("/media/")) {
                const QUrl url("http://127.0.0.1:17654"+avatarPath); visible.insert(url);
                avatar = "<img width='22' height='22' src='"+url.toString().toHtmlEscaped()+"'> ";
            }
            QString body;
            for (const auto &fragment : row.value("fragments").toArray()) {
                const auto part = fragment.toObject();
                const auto path = part.value("image").toString();
                if (path.startsWith("/media/")) {
                    const QUrl url("http://127.0.0.1:17654"+path); visible.insert(url);
                    body += "<img width='28' height='28' src='"+url.toString().toHtmlEscaped()+
                            "' alt='"+part.value("text").toString().toHtmlEscaped()+"'>";
                } else body += part.value("text").toString().toHtmlEscaped();
            }
            if (row.value("fragments").toArray().isEmpty()) body = row.value("text").toString().toHtmlEscaped();
            body.replace("\n", "<br>");
            const QString identity = QString::fromUtf8(QUrl::toPercentEncoding(name+" · "+platform+" · "+row.value("origin").toString()+"'s channel"));
            html += "<p style='margin:0 0 12px'><img width='18' height='18' src='platform:"+platform.toHtmlEscaped()+"'> "+avatar+
                    "<a href='identity:"+identity+"' style='text-decoration:none;color:"+color+"'><b>"+shortName.toHtmlEscaped()+"</b></a>"+
                    (row.value("is_creator").toBool() ? " <small>CREATOR</small>" : "")+
                    "<br><small style='color:#a8afb8'>"+row.value("origin").toString().toHtmlEscaped()+"'s channel"+
                    (row.value("shared").toBool() ? " · SHARED" : "")+"</small><br>"+body+"</p>";
        }
        if (messages.isEmpty()) html += "<p>Messages will appear here when accounts are connected and live.</p>";
        feed->setVisibleImages(visible);
        feed->setHtml(html + "</div>");
        feed->verticalScrollBar()->setValue(atBottom ? feed->verticalScrollBar()->maximum() : scroll);
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
    QLabel *actionStatus;
    QListWidget *list;
    QPushButton *startButton;
    QPushButton *stopButton;
    QPushButton *removeButton;
    QByteArray lastDestinations;
    bool updating = false;
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
        actionStatus = new QLabel(this);
        actionStatus->setWordWrap(true);
        actionStatus->setMinimumWidth(0);
        actionStatus->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        layout->addWidget(actionStatus);
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
        auto *startAll = new QPushButton("START ALL", this);
        auto *bulk = new QHBoxLayout(); bulk->addWidget(startAll); bulk->addWidget(stopAll);
        stopAll->setText("STOP ALL");
        startAll->setToolTip("Starts the main OBS stream, then every checked destination.");
        stopAll->setToolTip("Stops the main OBS stream and all secondary destinations.");
        layout->insertLayout(2, bulk);
        connect(startAll, &QPushButton::clicked, this, [this] { send(QJsonObject{{"action", "start_all"}}); });
        connect(list, &QListWidget::itemChanged, this, [this](QListWidgetItem *item) {
            if (!updating) send(QJsonObject{{"action", "destination_enabled"}, {"id", item->data(Qt::UserRole).toString()},
                                         {"enabled", item->checkState() == Qt::Checked}});
        });
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

    void message(const QString &value) { actionStatus->setText(value); }

    void update(const QJsonObject &payload)
    {
        const auto destinations = payload.value("destinations").toArray();
        const auto outputs = payload.value("outputs").toArray();
        QJsonArray snapshot = destinations;
        snapshot.append(payload.value("output_errors"));
        for (const auto &output : outputs) snapshot.append(output);
        const auto bytes = QJsonDocument(snapshot).toJson(QJsonDocument::Compact);
        if (bytes != lastDestinations) {
            lastDestinations = bytes;
            const QString selected = selectedId();
            updating = true;
            list->clear();
            for (const auto &entry : destinations) {
                const auto dest = entry.toObject();
                QString state = "OFFLINE";
                QString error = payload.value("output_errors").toObject().value(dest.value("id").toString()).toString();
                for (const auto &output : outputs) {
                    const auto row = output.toObject();
                    if (row.value("id") == dest.value("id")) {
                        state = row.value("active").toBool() ? "LIVE" :
                                row.value("busy").toBool() ? "CONNECTING / STOPPING" : "OFFLINE";
                        if (!row.value("error").toString().isEmpty()) error = row.value("error").toString();
                        if (row.value("reconnecting").toBool()) state = "RECONNECTING";
                    }
                }
                if (!error.isEmpty()) state = "ERROR";
                auto *item = new QListWidgetItem("● "+dest.value("name").toString() + "   " + state, list);
                item->setFlags(item->flags() | Qt::ItemIsUserCheckable);
                item->setCheckState(dest.value("enabled").toBool(true) ? Qt::Checked : Qt::Unchecked);
                item->setToolTip(error.isEmpty() ? "Checked destinations are included in the next Start All. Changing this does not stop a live stream." : error);
                item->setData(Qt::UserRole, dest.value("id").toString());
                if (state == "LIVE") item->setForeground(QColor("#80d6a0"));
                else if (state == "ERROR") item->setForeground(QColor("#ff6b6b"));
                else if (state != "OFFLINE") item->setForeground(QColor("#ffd166"));
                else item->setForeground(QColor("#a8afb8"));
                if (item->data(Qt::UserRole).toString() == selected) list->setCurrentItem(item);
            }
            updating = false;
        }
        if (destinations.isEmpty())
            status->setText("No extra streams yet. Add a destination to get started.");
        else if (!payload.value("stream_active").toBool())
            status->setText("Main stream offline · START ALL starts OBS and checked destinations (H.264/AAC).");
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
    QJsonArray bulkStarts;
    int bulkTicks = 0;
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
        bulkStarts = QJsonArray();
        bulkTicks = 0;
        for (auto &entry : destinations) {
            auto &d = *entry.second;
            obs_output_stop(d.output);
            d.starting = false;
            d.stopping = true;
            d.wasLive = false;
            d.error.clear();
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
        } else if (action == "start_all") {
            if (!bulkStarts.isEmpty()) result = "already_active_or_busy";
            else {
                bulkStarts = cmd.value("destinations").toArray(); bulkTicks = 0;
                if (!obs_frontend_streaming_active()) obs_frontend_streaming_start();
                result = "start_all_requested";
            }
        } else if (action == "stop_all") {
            stopAll();
            obs_frontend_streaming_stop();
            result = "stop_all_requested";
        } else if (action == "stop") {
            auto it = destinations.find(cmd.value("destination").toObject().value("id").toString());
            if (it != destinations.end()) {
                obs_output_stop(it->second->output);
                it->second->starting = false;
                it->second->stopping = true;
                it->second->wasLive = false;
                it->second->error.clear();
                result = "stop_requested";
            } else {
                result = "output_not_created";
            }
        }
        results.append(QJsonObject{{"id", cmd.value("id")}, {"destination_id", cmd.value("destination").toObject().value("id")}, {"status", result}});
        while (results.size() > 30)
            results.removeAt(0);
    }

    void tick()
    {
        if (!bulkStarts.isEmpty()) {
            if (obs_frontend_streaming_active()) {
                const auto selected = bulkStarts; bulkStarts = QJsonArray(); bulkTicks = 0;
                for (const auto &entry : selected) {
                    const auto dest = entry.toObject();
                    results.append(QJsonObject{{"destination_id", dest.value("id")}, {"status", start(dest)}});
                }
            } else if (++bulkTicks >= 60) {
                for (const auto &entry : bulkStarts)
                    results.append(QJsonObject{{"destination_id", entry.toObject().value("id")}, {"status", "main_start_timeout"}});
                bulkStarts = QJsonArray(); bulkTicks = 0;
            }
        }
        // A pending explicit Start All waits for OBS. Other inactive-main states stop secondary streams.
        if (!obs_frontend_streaming_active() && bulkStarts.isEmpty()) stopAll();
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
            if (active) { d.starting = false; d.wasLive = true; d.error.clear(); }
            if (!active && d.wasLive && !d.stopping && !d.starting) {
                d.error = "Destination disconnected and stopped. Check its settings and OBS log.";
                d.wasLive = false;
            }
            if (!active && d.stopping) d.stopping = false;
            // A timed-out asynchronous start must be stopped before being retried.
            if (d.starting && ++d.startupTicks > 30) {
                obs_output_force_stop(d.output);
                d.starting = false;
                d.stopping = true;
                d.error = "Destination did not start within 30 seconds.";
                results.append(QJsonObject{{"destination_id", entry.first}, {"status", "start_timeout_stopped"}});
            }
            outputs.append(QJsonObject{{"id", entry.first}, {"name", d.name}, {"active", active},
                {"error", d.error}, {"busy", d.starting || d.stopping}, {"reconnecting", obs_output_reconnecting(d.output)},
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
