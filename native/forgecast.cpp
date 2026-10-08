// FDGCast native output module. Alpha: build and validate against your OBS SDK.
// No credentials are written to OBS logs or the configuration directory.
#include <obs-module.h>
#include <obs-audio-controls.h>
#include <obs-frontend-api.h>
#include <QApplication>
#include <QDesktopServices>
#include <QByteArray>
#include <QColor>
#include <QBuffer>
#include <QCursor>
#include <QClipboard>
#include <QMap>
#include <QInputDialog>
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
#include <QCheckBox>
#include <QDateTime>
#include <QDockWidget>
#include <QDialog>
#include <QDialogButtonBox>
#include <QFile>
#include <QFileInfo>
#include <QProcess>
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
#include <QMenu>
#include <QAction>
#include <QScrollArea>
#include <QToolButton>
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
#include <atomic>
#include <chrono>
#include <cmath>

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

static qint64 audioClock()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct AudioMeter {
    obs_source_t *source;
    obs_volmeter_t *meter;
    std::atomic<qint64> lastMeter{0}, lastSignal{0}, hotSince{0};
    explicit AudioMeter(obs_source_t *input) : source(obs_source_get_ref(input)), meter(obs_volmeter_create(OBS_FADER_LOG))
    {
        if (source && meter) { obs_volmeter_add_callback(meter, updated, this); obs_volmeter_attach_source(meter, source); }
    }
    static void updated(void *data, const float *, const float *, const float inputPeak[MAX_AUDIO_CHANNELS])
    {
        auto *self = static_cast<AudioMeter *>(data);
        const auto now = audioClock(); self->lastMeter.store(now);
        bool hot=false;
        for (size_t channel=0; channel<MAX_AUDIO_CHANNELS; ++channel) {
            if(std::isfinite(inputPeak[channel]) && inputPeak[channel]>-60.0f) self->lastSignal.store(now);
            if(std::isfinite(inputPeak[channel]) && inputPeak[channel]>=-1.0f)hot=true;
        }
        if(!hot)self->hotSince.store(0);else {qint64 expected=0;self->hotSince.compare_exchange_strong(expected,now);}
    }
    ~AudioMeter()
    {
        if (meter) { obs_volmeter_remove_callback(meter, updated, this); obs_volmeter_destroy(meter); }
        if (source) obs_source_release(source);
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

// Each dock keeps its own visual preferences; no OBS layout or stream settings change.
static void openCompanionWindow();

class DockView : public QObject {
    QWidget *owner;
    QWidget *body;
    QVBoxLayout *content;
    QString prefix;
    bool defaultControls;
    std::function<void()> changed;
    void save(const QString &key, const QVariant &value) {
        QSettings settings("Forged Destiny Gaming", "ForgeCast");
        settings.setValue(prefix+key,value);
        apply();
        if (changed) changed();
    }
    void toggle(QMenu *menu,const QString &label,const QString &key,bool current) {
        auto *action=menu->addAction(label);
        action->setToolTip(key=="origins"?"Show the original broadcaster beside messages. Hover the platform icon to see this without adding text.":key=="compact"?"Reduce message and control spacing so more fits in the dock.":key=="times"?"Show the local time beside each chat message or event.":key=="controls"?"Show less-used buttons in the dock. They remain available in this menu when hidden.":"Change this dock appearance; the choice is saved on this PC.");
        action->setCheckable(true); action->setChecked(current);
        connect(action,&QAction::triggered,owner,[this,key](bool value) { save(key,value); });
    }
public:
    bool compact=true, showStatus=true, showControls=true, showOrigins=false, showTimes=false, userColors=true, showAvatars=true, showFilters=true, alternate=false, showBadges=true;
    int iconPixels=18;
    int pixels=13;
    QMenu *menu;
    QPushButton *openButton;
    void setConnected(bool value) { openButton->setVisible(!value); }
    DockView(QWidget *dock,QVBoxLayout *layout,const QString &id,bool controls,std::function<void()> refresh)
        : QObject(dock),owner(dock),content(layout),prefix("dock-ui/"+id+"/"),defaultControls(controls),changed(std::move(refresh)) {
        QSettings settings("Forged Destiny Gaming", "ForgeCast");
        showControls=settings.value(prefix+"controls",controls).toBool();
        body=new QWidget(dock);
        body->setLayout(content); // Qt transfers the existing layout from the dock.
        auto *outer=new QVBoxLayout(dock); outer->setContentsMargins(0,0,0,0); outer->setSpacing(0);
        auto *bar=new QHBoxLayout;bar->setContentsMargins(2,0,2,0);bar->addStretch();
        auto *options=new QToolButton(dock);options->setText("⋮");options->setToolTip("Dock appearance and controls");
        options->setFixedSize(22,20);menu=new QMenu(options);options->setMenu(menu);options->setPopupMode(QToolButton::InstantPopup);
        openButton=new QPushButton("Open app",dock);
        openButton->setToolTip("FDGCast Companion is offline. Open it to reconnect your docks.");
        connect(openButton,&QPushButton::clicked,dock,[] { openCompanionWindow(); });
        bar->insertWidget(0,openButton);bar->addWidget(options);outer->addLayout(bar);
        auto *scroll=new QScrollArea(dock);scroll->setFrameShape(QFrame::NoFrame);scroll->setWidgetResizable(true);
        scroll->setWidget(body);scroll->setMinimumSize(0,0);scroll->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);
        outer->addWidget(scroll,1);dock->setMinimumSize(100,60);
        connect(menu,&QMenu::aboutToShow,dock,[this,id] {
            menu->clear();
            toggle(menu,"Compact spacing","compact",compact);
            if (id!="events") {
                toggle(menu,"Show connection status","status",showStatus);
                toggle(menu,"Show extra controls","controls",showControls);
            }
            if (id=="chat") {
                toggle(menu,"Show original channel names","origins",showOrigins);
                toggle(menu,"Color viewer names","userColors",userColors);
                toggle(menu,"Show channel avatars","avatars",showAvatars);
                toggle(menu,"Show chat filters","filters",showFilters);
                toggle(menu,"Alternating message backgrounds","alternate",alternate);
                toggle(menu,"Show badge labels","badges",showBadges);
                auto *icons=menu->addMenu("Platform icon size");
                for (int size : {16,18,22,26}) {
                    auto *item=icons->addAction(QString::number(size)+" px");item->setCheckable(true);item->setChecked(size==iconPixels);
                    connect(item,&QAction::triggered,owner,[this,size] { save("icon",size); });
                }
            }
            if (id=="chat" || id=="events") toggle(menu,"Show timestamps","times",showTimes);
            auto *sizes=menu->addMenu("Text size");
            for (int size : {11,13,15,17}) {
                auto *item=sizes->addAction(QString::number(size)+" px");item->setCheckable(true);item->setChecked(size==pixels);
                connect(item,&QAction::triggered,owner,[this,size] { save("font",size); });
            }
            menu->addSeparator();
            auto *reset=menu->addAction("Reset this dock appearance");
            connect(reset,&QAction::triggered,owner,[this] { QSettings settings("Forged Destiny Gaming","ForgeCast"); settings.remove(prefix);apply();if(changed)changed(); });
            // Controls remain reachable even when hidden from the compact dock.
            for (auto *button : body->findChildren<QPushButton *>()) {
                if (button->property("dockMenuAction").toBool()) {
                    auto *item=menu->addAction(button->text());item->setEnabled(button->isEnabled());item->setToolTip(button->toolTip());
                    connect(item,&QAction::triggered,button,[button] { button->click(); });
                }
            }
        });
        dock->setContextMenuPolicy(Qt::CustomContextMenu);
        connect(dock,&QWidget::customContextMenuRequested,dock,[this](const QPoint &point) { menu->popup(owner->mapToGlobal(point)); });
        menu->setToolTipsVisible(true);
        apply();
    }
    void apply() {
        QSettings settings("Forged Destiny Gaming", "ForgeCast");
        compact=settings.value(prefix+"compact",true).toBool();
        showStatus=settings.value(prefix+"status",true).toBool();
        showControls=settings.value(prefix+"controls",defaultControls).toBool();
        showOrigins=settings.value(prefix+"origins",false).toBool();
        showTimes=settings.value(prefix+"times",false).toBool();
        userColors=settings.value(prefix+"userColors",true).toBool();
        showAvatars=settings.value(prefix+"avatars",true).toBool();
        showFilters=settings.value(prefix+"filters",true).toBool();
        alternate=settings.value(prefix+"alternate",false).toBool();
        showBadges=settings.value(prefix+"badges",true).toBool();
        iconPixels=qBound(16,settings.value(prefix+"icon",18).toInt(),26);
        pixels=qBound(11,settings.value(prefix+"font",13).toInt(),17);
        QFont font=owner->font();font.setPixelSize(pixels);owner->setFont(font);
        content->setContentsMargins(compact?4:9,compact?2:9,compact?4:9,compact?2:9);
        content->setSpacing(compact?3:7);
    }
};

class ChatDock : public QWidget {
    DockView *view;
    QWidget *composerRow;
    QJsonObject lastPayload;
    QLabel *connection;
    ChatFeed *feed;
    QComboBox *sendTo;
    QLineEdit *compose;
    QPushButton *sendButton;
    QLabel *sendStatus;
    QString pendingText;
    QString replyId;
    QComboBox *platformFilter, *channelFilter;
    QWidget *filterRow;
    QPushButton *jumpLatest;
    QCheckBox *pauseFeed;
    std::function<void(const QJsonObject &)> send;
    QByteArray lastMessages;
public:
    explicit ChatDock(std::function<void(const QJsonObject &)> submit) : QWidget(), send(std::move(submit))
    {
        setStyleSheet("QWidget { background: #151719; color: #f4f4f4; }"
                      "QTextBrowser { background:#25303c; border:1px solid #556779; border-radius:4px; padding:6px; }"
                      "QLabel { color:#ff7549; padding:3px; }"
                      "QLineEdit { background:#090f17; color:#ffffff; border:1px solid #667b91; border-radius:4px; padding:5px; }"
                      "QLineEdit:focus { border:2px solid #ff7549; }"
                      "QComboBox { background:#1b2530; border:1px solid #556779; border-radius:4px; padding:4px; }");
        auto *layout = new QVBoxLayout(this);
        connection = new QLabel("Companion offline", this);
        connection->setWordWrap(false);
        connection->setMinimumWidth(0);
        connection->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        feed = new ChatFeed(this);
        feed->setOpenExternalLinks(false);
        feed->setMinimumSize(0,0);
        feed->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);
        layout->addWidget(connection);
        auto *filters=new QHBoxLayout();
        platformFilter=new QComboBox(this);platformFilter->addItem("All platforms","");
        for(const auto &name : {QString("twitch"),QString("youtube"),QString("kick")}) platformFilter->addItem(name,name);
        channelFilter=new QComboBox(this);channelFilter->addItem("All channels","");
        platformFilter->setMinimumWidth(0);channelFilter->setMinimumWidth(0);
        platformFilter->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Fixed);channelFilter->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Fixed);
        platformFilter->setAccessibleName("Filter chat platform");channelFilter->setAccessibleName("Filter source channel");
        platformFilter->setToolTip("Choose which incoming platforms to read. This does not change outgoing messages.");
        channelFilter->setToolTip("Choose the original channel, including Twitch Shared Chat sources.");
        filters->addWidget(platformFilter);filters->addWidget(channelFilter);
        filterRow=new QWidget(this);filterRow->setLayout(filters);filters->setContentsMargins(0,0,0,0);layout->addWidget(filterRow);
        layout->addWidget(feed,1);
        auto *reading=new QHBoxLayout();pauseFeed=new QCheckBox("Pause",this);pauseFeed->setToolTip("Pause incoming display while you read. Connections keep receiving messages.");
        jumpLatest=new QPushButton("Jump to latest",this);jumpLatest->hide();
        reading->addWidget(pauseFeed);reading->addWidget(jumpLatest);layout->addLayout(reading);
        connect(pauseFeed,&QCheckBox::toggled,this,[this](bool paused){jumpLatest->setVisible(paused);if(!paused){lastMessages.clear();if(!lastPayload.isEmpty())update(lastPayload);}});
        connect(jumpLatest,&QPushButton::clicked,this,[this]{pauseFeed->setChecked(false);lastMessages.clear();if(!lastPayload.isEmpty())update(lastPayload);feed->verticalScrollBar()->setValue(feed->verticalScrollBar()->maximum());jumpLatest->hide();});
        connect(feed->verticalScrollBar(),&QScrollBar::valueChanged,this,[this](int value){jumpLatest->setVisible(pauseFeed->isChecked() || value<feed->verticalScrollBar()->maximum()-60);});
        for(auto *filter : {platformFilter,channelFilter}) connect(filter,&QComboBox::currentIndexChanged,this,[this]{lastMessages.clear();if(!lastPayload.isEmpty())update(lastPayload);});
        feed->setContextMenuPolicy(Qt::CustomContextMenu);
        connect(feed,&QWidget::customContextMenuRequested,this,[this](const QPoint &point){messageMenu(point);});
        auto *composer = new QHBoxLayout();
        sendTo = new QComboBox(this);
        sendTo->addItem("Twitch", "twitch");
        sendTo->addItem("YouTube", "youtube");
        sendTo->addItem("Kick", "kick");
        sendTo->addItem("All connected platforms", "all");
        sendTo->setToolTip("Send to your own linked channel. All connected platforms sends separately with per-platform results.");
        compose = new QLineEdit(this);
        compose->setPlaceholderText("Message your channel…");
        compose->setMaxLength(200);
        compose->setMinimumWidth(0);
        compose->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        sendButton = new QPushButton("Send", this);
        sendTo->setMinimumWidth(0);sendTo->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        layout->addWidget(sendTo);
        composer->addWidget(compose, 1);
        composer->addWidget(sendButton);
        composerRow=new QWidget(this);composerRow->setLayout(composer);composer->setContentsMargins(0,0,0,0);
        layout->addWidget(composerRow);
        sendStatus = new QLabel(this);sendStatus->hide();
        sendStatus->setWordWrap(true);
        sendStatus->setMinimumWidth(0);
        sendStatus->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        layout->addWidget(sendStatus);
        auto submitMessage = [this] {
            const auto value = compose->text().trimmed();
            if (value.isEmpty() || !sendButton->isEnabled()) return;
            pendingText = compose->text();
            sendButton->setEnabled(false);
            sendStatus->show();
            sendStatus->setText("Sending to " + sendTo->currentText() + "…");
            const QString platform=sendTo->currentData().toString();
            if(platform=="all") {
                QJsonArray platforms;const auto statuses=lastPayload.value("statuses").toObject();
                for(const auto &name : {QString("twitch"),QString("youtube"),QString("kick")}) if(statuses.value(name).toString()=="connected") platforms.append(name);
                if(platforms.isEmpty()){sendResult(false,"No platforms are connected.");return;}
                if(QMessageBox::question(this,"Send to multiple channels","Send this message to: "+QString::fromUtf8(QJsonDocument(platforms).toJson(QJsonDocument::Compact))+"?")!=QMessageBox::Yes){sendButton->setEnabled(true);pendingText.clear();sendStatus->hide();return;}
                send(QJsonObject{{"action","chat_send_many"},{"platforms",platforms},{"text",value}});
            } else send(QJsonObject{{"action", "chat_send"}, {"platform", platform}, {"text", value},{"reply_id",replyId}});
        };
        connect(sendButton, &QPushButton::clicked, this, submitMessage);
        connect(compose, &QLineEdit::returnPressed, this, submitMessage);
        view=new DockView(this,layout,"chat",true,[this] {
            connection->setVisible(view->showStatus);composerRow->setVisible(view->showControls);sendTo->setVisible(view->showControls);filterRow->setVisible(view->showFilters);
            lastMessages.clear();if(!lastPayload.isEmpty()) update(lastPayload);
        });
        connection->setVisible(view->showStatus);composerRow->setVisible(view->showControls);sendTo->setVisible(view->showControls);filterRow->setVisible(view->showFilters);
    }

    void sendResult(bool success, const QString &error)
    {
        sendButton->setEnabled(true);
        if (success && compose->text() == pendingText) compose->clear();
        sendStatus->setVisible(!success);
        sendStatus->setText(success ? "Sent" :
                            (error.isEmpty() ? "Message could not be sent. Check your connection." : error));
        pendingText.clear();if(success)replyId.clear();
    }

    void disconnected()
    {
        view->setConnected(false);
        lastPayload=QJsonObject();
        connection->setText("Companion offline");
    }

    void messageMenu(const QPoint &point)
    {
        const QString anchor=feed->anchorAt(point);
        if(!anchor.startsWith("msg:")) {auto *menu=feed->createStandardContextMenu();menu->exec(feed->mapToGlobal(point));delete menu;return;}
        const QString id=QUrl::fromPercentEncoding(anchor.mid(4).toUtf8());QJsonObject row;
        for(const auto &entry:lastPayload.value("messages").toArray())if(entry.toObject().value("id").toString()==id){row=entry.toObject();break;}
        if(row.isEmpty())return;
        QMenu menu(this);const QString platform=row.value("platform").toString(),user=row.value("user").toString(),origin=row.value("origin").toString();
        menu.addAction(user+" · "+platform+" · "+origin)->setEnabled(false);
        auto *copy=menu.addAction("Copy message");connect(copy,&QAction::triggered,this,[row]{QApplication::clipboard()->setText(row.value("text").toString());});
        auto *history=menu.addAction("Recent messages from this account");connect(history,&QAction::triggered,this,[this,row,platform,user]{QStringList lines;for(const auto &entry:lastPayload.value("messages").toArray()){auto r=entry.toObject();if(r.value("platform").toString()==platform && r.value("user_id")==row.value("user_id"))lines.append(r.value("text").toString());}QMessageBox box(this);box.setWindowTitle(user+" · "+platform);box.setTextFormat(Qt::PlainText);box.setText(lines.mid(qMax(0,int(lines.size())-15)).join("\n"));box.exec();});
        auto *reply=menu.addAction("Reply in my "+platform+" channel");connect(reply,&QAction::triggered,this,[this,row,user,platform]{sendTo->setCurrentIndex(sendTo->findData(platform));compose->setText("@"+user+" ");compose->setFocus();replyId=platform=="twitch"?row.value("platform_message_id").toString():QString();});
        auto *highlight=menu.addAction("Show on selected-message overlay");connect(highlight,&QAction::triggered,this,[this,id]{send(QJsonObject{{"action","highlight"},{"id",id}});});
        QString profile;
        if(platform=="youtube" && QRegularExpression("^[A-Za-z0-9_-]{1,100}$").match(row.value("user_id").toString()).hasMatch())profile="https://www.youtube.com/channel/"+row.value("user_id").toString();
        else if(QRegularExpression("^[A-Za-z0-9_]{1,40}$").match(user).hasMatch())profile=(platform=="kick"?"https://kick.com/":"https://www.twitch.tv/")+user;
        if(!profile.isEmpty()){auto *open=menu.addAction("Open platform profile");connect(open,&QAction::triggered,this,[profile]{QDesktopServices::openUrl(QUrl(profile));});}
        const auto capabilities=lastPayload.value("capabilities").toObject().value(platform).toObject();
        menu.addSeparator();
        for(const auto &op:{QString("delete"),QString("timeout"),QString("ban")}){
            auto *item=menu.addAction(op=="timeout"?"Timeout 10 minutes":op=="delete"?"Delete message":"Ban account");item->setEnabled(capabilities.value(op).toBool() && !row.value("deleted").toBool());
            item->setToolTip("Applies to the original channel only, subject to platform permissions. Kick actions are available in native chat.");
            connect(item,&QAction::triggered,this,[this,id,op,user,platform,origin]{if(QMessageBox::question(this,"Confirm moderation",op+" "+user+" in "+origin+" on "+platform+"?") == QMessageBox::Yes)send(QJsonObject{{"action","chat_moderate"},{"id",id},{"operation",op},{"confirmed",true}});});
        }
        menu.exec(feed->mapToGlobal(point));
    }

    void update(const QJsonObject &payload)
    {
        view->setConnected(true);
        const auto statuses = payload.value("statuses").toObject();
        lastPayload=payload;
        QStringList shortStates,details;
        for (const auto &platform : {QString("twitch"),QString("youtube"),QString("kick")}) {
            const QString full=statuses.value(platform).toString("offline");
            const QString state=full=="connected"?"✓":full.contains("waiting",Qt::CaseInsensitive)||full.contains("ready",Qt::CaseInsensitive)?"waiting":full.contains("connecting",Qt::CaseInsensitive)?"connecting":full=="not connected"||full=="disconnected"?"offline":"attention";
            shortStates.append(platform.left(1).toUpper()+platform.mid(1)+" "+state);
            details.append(platform+": "+full);
        }
        connection->setText(shortStates.join(" · "));connection->setToolTip(details.join("\n"));
        const auto messages = payload.value("messages").toArray();
        const QString selected=channelFilter->currentData().toString();
        QMap<QString,QString> channels;
        for(const auto &entry:messages){const auto r=entry.toObject();channels[r.value("platform").toString()+":"+r.value("origin_id").toString()]=r.value("origin").toString()+" · "+r.value("platform").toString();}
        QStringList keys=channels.keys();keys.prepend("");QStringList previous;
        for(int i=0;i<channelFilter->count();++i) previous.append(channelFilter->itemData(i).toString());
        if(previous!=keys){channelFilter->blockSignals(true);channelFilter->clear();channelFilter->addItem("All channels","");for(auto it=channels.begin();it!=channels.end();++it)channelFilter->addItem(it.value(),it.key());const int index=channelFilter->findData(selected);channelFilter->setCurrentIndex(index>=0?index:0);channelFilter->blockSignals(false);}
        if(pauseFeed->isChecked())return;
        const auto bytes = QJsonDocument(messages).toJson(QJsonDocument::Compact);
        if (bytes == lastMessages) return;
        lastMessages = bytes;
        const bool atBottom = feed->verticalScrollBar()->maximum()-feed->verticalScrollBar()->value() < 60;
        const int scroll = feed->verticalScrollBar()->value();
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>";
        QSet<QUrl> visible;
        int shown=0;
        for (const auto &entry : messages) {
            const auto row = entry.toObject();
            if(!platformFilter->currentData().toString().isEmpty() && row.value("platform").toString()!=platformFilter->currentData().toString())continue;
            const QString channel=row.value("platform").toString()+":"+row.value("origin_id").toString();
            if(!channelFilter->currentData().toString().isEmpty() && channel!=channelFilter->currentData().toString())continue;
            ++shown;
            const QString platform = row.value("platform").toString();
            const QString name = row.value("user").toString();
            const QString shortName = name.size() > 22 ? name.left(21)+"…" : name;
            QString color = row.value("color").toString("#d3baff");
            if (!QRegularExpression("^#[a-fA-F0-9]{6}$").match(color).hasMatch()) color = "#d3baff";
            if (!view->userColors) color="#f4f4f4";
            QString avatar;
            const auto avatarPath = row.value("origin_avatar").toString(row.value("avatar").toString());
            if (view->showAvatars && avatarPath.startsWith("/media/")) {
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
            const QString channelTip=QString::fromUtf8(QUrl::toPercentEncoding(platform+" · "+row.value("origin").toString()+"'s channel"));
            const QString timestamp=view->showTimes ? "<small style='color:#a8afb8'>"+QDateTime::fromSecsSinceEpoch(static_cast<qint64>(row.value("time").toDouble())).toLocalTime().toString("h:mm AP")+" </small>" : QString();
            QString badges;
            if(view->showBadges) for(const auto &badge:row.value("badges").toArray()) {
                const QString name=badge.isObject()?badge.toObject().value("set_id").toString(badge.toObject().value("type").toString()):badge.toString();
                if(!name.isEmpty())badges+="<small style='color:#b5c7d9'>["+name.toHtmlEscaped()+"] </small>";
            }
            const QString messageLink="msg:"+QString::fromUtf8(QUrl::toPercentEncoding(row.value("id").toString()));
            const QString reply=row.value("reply_to").toString();
            const QString paid=row.value("kind").toString();
            const QString extra=(reply.isEmpty()?QString():"<small> ↪ "+reply.toHtmlEscaped()+"</small>")+(paid!="chat"?"<small> ["+paid.toHtmlEscaped()+"]</small>":QString());
            const QString background=row.value("highlighted").toBool()?"background:#533323;":view->alternate && shown%2==0?"background:#1e2935;":QString();
            html += "<p style='"+background+"margin:0 0 "+QString::number(view->compact?4:12)+"px'>"+timestamp+"<a href='identity:"+channelTip+"'><img width='"+QString::number(view->iconPixels)+"' height='"+QString::number(view->iconPixels)+"' src='platform:"+platform.toHtmlEscaped()+"'></a> "+avatar+
                    badges+"<a href='"+messageLink+"' style='text-decoration:none;color:"+color+"'><b>"+shortName.toHtmlEscaped()+"</b></a>"+extra+
                    (view->showOrigins ? "<small style='color:#a8afb8'> · "+row.value("origin").toString().toHtmlEscaped()+"</small>" : QString())+(view->compact?": ":"<br>")+body+"</p>";
        }
        if (shown==0) html += "<p style='color:#a8afb8'>No messages yet.</p>";
        feed->setVisibleImages(visible);
        feed->setHtml(html + "</div>");
        feed->verticalScrollBar()->setValue(atBottom ? feed->verticalScrollBar()->maximum() : scroll);
    }
};

class EventsDock : public QWidget {
    DockView *view;
    QJsonObject lastPayload;
    QTextBrowser *feed;
    QByteArray lastEvents;
public:
    EventsDock() : QWidget()
    {
        setStyleSheet("QWidget { background:#151719;color:#f4f4f4; }"
                      "QTextBrowser { background:#25303c;border:1px solid #556779;border-radius:4px;padding:6px; }"
                      "QLabel { color:#ff7549;padding:5px; }");
        auto *layout = new QVBoxLayout(this);
        feed = new QTextBrowser(this);feed->setOpenExternalLinks(false);
        feed->setMinimumSize(0,0);feed->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);
        feed->setToolTip("Twitch follows, channel point redeems and incoming raids. Connect your own channel in the Hub.");
        layout->addWidget(feed,1);
        view=new DockView(this,layout,"events",false,[this] { lastEvents.clear();if(!lastPayload.isEmpty()) update(lastPayload); });
        disconnected();
    }
    void disconnected() { view->setConnected(false); lastPayload=QJsonObject();lastEvents.clear();feed->setHtml("<p>Companion offline</p>"); }
    void update(const QJsonObject &payload)
    {
        view->setConnected(true);
        lastPayload=payload;
        const auto events = payload.value("events").toArray();
        QJsonArray signature=events;signature.append(payload.value("statuses"));
        const auto bytes = QJsonDocument(signature).toJson(QJsonDocument::Compact);
        if (bytes == lastEvents) return;
        lastEvents = bytes;
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>";
        for (const auto &entry : events) {
            const auto row = entry.toObject();
            const QString kind=row.value("kind").toString();
            const QString title=(row.value("simulated").toBool()?"TEST · ":"")+kind.left(1).toUpper()+kind.mid(1)+(row.value("acknowledged").toBool()?" ✓":"");
            const QString color=kind=="follow"?"#94e6b0":kind=="redeem"?"#ffb891":"#d3baff";
            const auto description = row.value("text").toString().toHtmlEscaped();
            const QString timestamp=view->showTimes ? " · "+QDateTime::fromSecsSinceEpoch(static_cast<qint64>(row.value("time").toDouble())).toLocalTime().toString("h:mm AP") : QString();
            html += "<p style='margin:0 0 "+QString::number(view->compact?6:12)+"px'><b style='color:"+color+"'>"+title+"</b><small>"+timestamp+"</small>"+(view->compact?" · ":"<br>")+description+"<small style='color:#a8afb8'> · "+row.value("source").toString().toHtmlEscaped()+"</small></p>";
        }
        feed->setToolTip(payload.value("statuses").toObject().value("twitch_events").toString("Connect Twitch in the Hub for follows, redeems and incoming raids."));
        if (events.isEmpty()) html += "<p style='color:#a8afb8'>Waiting for Twitch events.</p>";
        feed->setHtml(html + "</div>");
    }
};

class HubDock : public QWidget {
    DockView *view;
    QComboBox *selection;
    QTextBrowser *details;
    QJsonObject current;
    std::function<void(const QJsonObject &)> send;
public:
    explicit HubDock(std::function<void(const QJsonObject &)> submit) : QWidget(),send(std::move(submit)) {
        setStyleSheet("QWidget {background:#151719;color:#f4f4f4;} QTextBrowser {background:#25303c;border:1px solid #556779;padding:5px;} QComboBox {padding:4px;}");
        auto *layout=new QVBoxLayout(this);selection=new QComboBox(this);selection->setMinimumWidth(0);selection->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Fixed);
        selection->setToolTip("Choose an event for preflight. Selecting does not start a stream or change platform titles.");selection->setAccessibleName("Selected Hub event");
        details=new QTextBrowser(this);details->setMinimumSize(0,0);details->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);details->setOpenExternalLinks(true);
        layout->addWidget(selection);layout->addWidget(details,1);
        auto *refresh=new QPushButton("Refresh events",this);layout->addWidget(refresh);refresh->setProperty("dockMenuAction",true);
        connect(refresh,&QPushButton::clicked,this,[this]{send(QJsonObject{{"action","hub_events_refresh"}});});
        connect(selection,&QComboBox::currentIndexChanged,this,[this]{send(QJsonObject{{"action","hub_select"},{"id",selection->currentData().toString()}});});
        view=new DockView(this,layout,"hub",false,[this,refresh]{refresh->setVisible(view->showControls);});refresh->setVisible(view->showControls);
    }
    void disconnected(){view->setConnected(false);details->setPlainText("Companion offline. Open app to load your schedule.");}
    void update(const QJsonObject &payload){
        view->setConnected(true);current=payload.value("coordination").toObject();
        const auto events=current.value("events").toArray();selection->blockSignals(true);selection->clear();selection->addItem("No event selected","");
        QString html="<small>"+current.value("status").toString().toHtmlEscaped()+"</small>";
        const auto today=QDateTime::currentDateTime().date();
        for(const auto &entry:events){const auto row=entry.toObject();selection->addItem(row.value("title").toString(),row.value("id").toString());
            const auto stamp=row.value("starts_at_unix");const auto when=QDateTime::fromSecsSinceEpoch(static_cast<qint64>(stamp.toDouble())).toLocalTime();
            if(!stamp.isNull() && when.date()!=today && row.value("id")!=current.value("selected_id"))continue;
            html+="<p><b>"+row.value("title").toString().toHtmlEscaped()+"</b><br>"+(stamp.isNull()?"Time unavailable":when.toString("ddd h:mm AP"))+" · "+row.value("game").toString().toHtmlEscaped()+"<br>";
            QStringList names;for(const auto &person:row.value("participants").toArray())names.append(person.toString());
            if(!names.isEmpty())html+="<small>Accepted RSVPs: "+names.join(", ").toHtmlEscaped()+" (live status unverified)</small><br>";
            html+=row.value("instructions").toString().toHtmlEscaped();const auto url=row.value("url").toString();
            if(!url.isEmpty())html+="<br><a href='"+url.toHtmlEscaped()+"'>Open in Hub</a>";html+="</p>";
        }
        const int selected=selection->findData(current.value("selected_id").toString());selection->setCurrentIndex(selected<0?0:selected);selection->blockSignals(false);
        if(events.isEmpty())html+="<p>No commitments returned by your Hub. Pair and Sync in Companion Connections.</p>";
        details->setHtml(html);
    }
};
static QPointer<HubDock> hubDock;

class DoctorDock : public QWidget {
    DockView *view;
    QJsonObject lastPayload;
    QPushButton *snooze;
    QPushButton *ack;
    QPushButton *details;
    QTextBrowser *report;
    QLabel *audioStatus;
    QLabel *audioFeedback;
    QPushButton *fixButton;
    QJsonObject audioIssue;
    std::function<void(const QJsonObject &)> send;
public:
    explicit DoctorDock(std::function<void(const QJsonObject &)> submit) : QWidget(), send(std::move(submit))
    {
        setStyleSheet("QWidget { background: #151719; color: #f4f4f4; }"
                      "QTextBrowser { background: #1d2022; border: 0; padding: 8px; }");
        auto *layout = new QVBoxLayout(this);

        report = new QTextBrowser(this);
        report->setOpenExternalLinks(false);
        report->setMinimumSize(0,0);report->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);
        audioStatus = new QLabel("Audio Guard · Connect Companion", this);
        audioStatus->setWordWrap(false); audioStatus->setMinimumWidth(0);
        audioStatus->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Preferred);
        layout->addWidget(audioStatus);
        audioFeedback = new QLabel(this); audioFeedback->setWordWrap(true);
        audioFeedback->setMinimumWidth(0); audioFeedback->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Preferred);
        layout->addWidget(audioFeedback);
        fixButton = new QPushButton("Fix audio", this); fixButton->setEnabled(false);
        layout->addWidget(fixButton);
        auto *quiet = new QHBoxLayout();
        snooze = new QPushButton("Snooze 10 min", this);
        ack = new QPushButton("I Know", this);
        quiet->addWidget(snooze); quiet->addWidget(ack); layout->addLayout(quiet);
        connect(fixButton,&QPushButton::clicked,this,[this] {
            send(QJsonObject{{"action","audio_fix"},{"source_uuid",audioIssue.value("source_uuid")},{"fix",audioIssue.value("action")}});
        });
        connect(snooze,&QPushButton::clicked,this,[this] { send(QJsonObject{{"action","audio_snooze"}}); });
        connect(ack,&QPushButton::clicked,this,[this] { send(QJsonObject{{"action","audio_ack"}}); });
        details = new QPushButton("Open Companion", this);
        layout->addWidget(details);
        connect(details,&QPushButton::clicked,this,[this] { send(QJsonObject{{"action","focus"}}); });
        layout->addWidget(report,1);
        for (auto *button : {snooze,ack,details}) button->setProperty("dockMenuAction",true);
        audioFeedback->hide();fixButton->hide();
        view=new DockView(this,layout,"doctor",false,[this] {
            snooze->setVisible(view->showControls);ack->setVisible(view->showControls);details->setVisible(view->showControls);
            audioStatus->setVisible(view->showStatus);if(!lastPayload.isEmpty()) update(lastPayload);
        });
        snooze->setVisible(view->showControls);ack->setVisible(view->showControls);details->setVisible(view->showControls);
        audioStatus->setVisible(view->showStatus);
        disconnected();
    }

    void message(const QString &text) { audioFeedback->setText(text); audioFeedback->setToolTip(text); audioFeedback->show(); QTimer::singleShot(8000,audioFeedback,[this] { audioFeedback->hide(); }); }

    void disconnected()
    {
        view->setConnected(false);
        lastPayload=QJsonObject();
        audioStatus->setText("Audio · offline");
        fixButton->setEnabled(false);fixButton->hide();
        report->setHtml("<p>Companion offline</p>");
    }

    void update(const QJsonObject &payload)
    {
        view->setConnected(true);
        lastPayload=payload;
        const auto audio = payload.value("audio_guard").toObject();
        const auto audioIssues = audio.value("issues").toArray();
        audioStatus->setText("Audio · "+audio.value("state").toString("setup"));
        audioStatus->setToolTip(audio.value("title").toString("Choose your microphone in Companion."));
        audioStatus->setStyleSheet(audio.value("state").toString() == "warning" ? "color:#ffd166" : "color:#a8afb8");
        audioIssue = QJsonObject();
        for (const auto &issue : audioIssues)
            if (!issue.toObject().value("action").toString().isEmpty()) { audioIssue=issue.toObject(); break; }
        fixButton->setEnabled(!audioIssue.isEmpty());fixButton->setVisible(!audioIssue.isEmpty());
        const bool unmute=audioIssue.value("action").toString() == "unmute";
        fixButton->setText(unmute ? "UNMUTE" : "FIX STREAM ROUTING");
        fixButton->setToolTip(audioIssue.value("source_name").toString()+" · "+audioIssue.value("evidence").toString());
        const bool statsConnected = payload.value("stats_connected").toBool();
        const auto stats = payload.value("stats").toObject();
        QString html = "<div style='font-family:sans-serif;color:#f4f4f4'>"
                       ;
        if (!view->compact) html += "<p>Scene: <b>"+payload.value("scene").toString().toHtmlEscaped()+"</b></p>";
        if (!statsConnected) html += "<p>OBS readings unavailable · reconnecting</p>";
        for (const auto &entry : payload.value("destination_health").toArray()) {
            const auto health=entry.toObject();
            html += "<p><b>"+health.value("name").toString().toHtmlEscaped()+"</b> · "+health.value("state").toString().toHtmlEscaped()+"</p>";
        }
        if (statsConnected) html += "<p>OBS FPS: " + QString::number(stats.value("activeFps").toDouble(), 'f', 1) +
                " · CPU: " + QString::number(stats.value("cpuUsage").toDouble(), 'f', 1) + "%</p>";
        const auto issues = payload.value("issues").toArray();
        if (issues.isEmpty() && statsConnected) html += "<p style='color:#80d6a0'>Frames ✓</p>";
        for (const auto &entry : issues) {
            const auto row = entry.toObject();
            html += "<p><b style='color:#ff7549'>" + row.value("title").toString().toHtmlEscaped() +
                    "</b>"+(view->compact?QString():"<br>"+row.value("evidence").toString().toHtmlEscaped()+"<br>Try: "+row.value("suggestion").toString().toHtmlEscaped())+"</p>";
        }
        if (!view->compact) html += "<p style='color:#a9adb0'>Counter-based diagnosis; the faulty process or network hop "
                "cannot be proven from OBS statistics alone.</p>";
        report->setHtml(html+"</div>");
        QStringList tips;for(const auto &entry : issues) {const auto row=entry.toObject();tips.append(row.value("title").toString()+"\n"+row.value("evidence").toString()+"\n"+row.value("suggestion").toString());}
        report->setToolTip(tips.join("\n\n"));
    }
};

class MultistreamDock : public QWidget {
    DockView *view;
    QJsonObject lastPayload;
    QPushButton *addButton;
    QPushButton *startAllButton;
    QPushButton *stopAllButton;
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

        status = new QLabel("Companion offline", this);
        status->setWordWrap(false);status->setMinimumWidth(0);status->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Preferred);
        list = new QListWidget(this);
        list->setMinimumSize(0,0);list->setSizePolicy(QSizePolicy::Ignored,QSizePolicy::Ignored);
        layout->addWidget(status);
        layout->addWidget(list,1);
        actionStatus = new QLabel(this);
        actionStatus->setWordWrap(true);
        actionStatus->setMinimumWidth(0);
        actionStatus->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
        actionStatus->hide();
        layout->addWidget(actionStatus);
        auto *add = new QPushButton("+ Add stream", this);addButton=add;
        removeButton = new QPushButton("Remove", this);
        removeButton->setObjectName("secondary");
        startButton = new QPushButton("Start selected", this);
        stopButton = new QPushButton("Stop selected", this);
        stopButton->setObjectName("secondary");
        auto *stopAll = new QPushButton("Stop all", this);stopAllButton=stopAll;
        stopAll->setObjectName("stopAll");
        auto *management = new QHBoxLayout();
        management->addWidget(add);
        management->addWidget(removeButton);
        layout->addLayout(management);
        auto *controls = new QHBoxLayout();
        controls->addWidget(startButton);
        controls->addWidget(stopButton);
        layout->addLayout(controls);
        auto *startAll = new QPushButton("START ALL", this);startAllButton=startAll;
        auto *bulk = new QHBoxLayout(); bulk->addWidget(startAll); bulk->addWidget(stopAll);
        stopAll->setText("STOP ALL");
        startAll->setToolTip("Starts the main OBS stream, then every checked destination.");
        stopAll->setToolTip("Stops the main OBS stream and all secondary destinations.");
        layout->insertLayout(1, bulk);
        connect(startAll, &QPushButton::clicked, this, [this] { send(QJsonObject{{"action", "start_all"}}); });
        connect(list, &QListWidget::itemChanged, this, [this](QListWidgetItem *item) {
            if (!updating) send(QJsonObject{{"action", "destination_enabled"}, {"id", item->data(Qt::UserRole).toString()},
                                         {"enabled", item->checkState() == Qt::Checked}});
        });
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
            QComboBox platform(&dialog);
            platform.addItem("Twitch", "twitch");platform.addItem("YouTube", "youtube");
            platform.addItem("Kick", "kick");platform.addItem("Other / Custom", "custom");
            QCheckBox advanced("Use a custom server address", &dialog);
            QLabel help(&dialog);help.setWordWrap(true);
            key.setEchoMode(QLineEdit::Password);
            server.setPlaceholderText("Paste your platform's server address");
            form.addRow("Platform", &platform);
            form.addRow("Stream key", &key);
            form.addRow("Name (optional)", &name);
            form.addRow(&advanced);
            form.addRow("Server address", &server);
            form.addRow(&help);
            auto updatePlatform = [&] {
                const QString selected=platform.currentData().toString();
                const bool custom=selected=="custom";
                server.setVisible(custom||advanced.isChecked());
                form.labelForField(&server)->setVisible(custom||advanced.isChecked());
                advanced.setVisible(!custom);
                name.setPlaceholderText(platform.currentText());
                help.setText(custom?"Paste the server address and key from your platform.":selected=="kick"?
                    "Uses your connected Kick account. If unavailable, choose a custom server address from your Kick dashboard.":
                    "The server is selected automatically. Just paste your stream key.");
                dialog.adjustSize();
            };
            connect(&platform, &QComboBox::currentIndexChanged, &dialog, [&](int) { advanced.setChecked(false);server.clear();updatePlatform(); });
            connect(&advanced, &QCheckBox::toggled, &dialog, [&](bool checked) { if(!checked)server.clear();updatePlatform(); });
            updatePlatform();
            QDialogButtonBox buttons(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, &dialog);
            form.addRow(&buttons);
            connect(&buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
            connect(&buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
            if (dialog.exec() == QDialog::Accepted)
                send(QJsonObject{{"action", "save"}, {"platform",platform.currentData().toString()}, {"name", name.text()},
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
        for (auto *button : {addButton,removeButton,startButton,stopButton}) button->setProperty("dockMenuAction",true);
        view=new DockView(this,layout,"multistream",false,[this] {
            for(auto *button : {addButton,removeButton,startButton,stopButton})button->setVisible(view->showControls);
            status->setVisible(view->showStatus);
            list->setStyleSheet(QString("QListWidget::item { padding:%1px; }").arg(view->compact?3:7));
        });
        for(auto *button : {addButton,removeButton,startButton,stopButton})button->setVisible(view->showControls);
        connect(view->menu,&QMenu::aboutToShow,this,[this]{
            auto *presets=view->menu->addMenu("Destination presets");
            auto *save=presets->addAction("Save checked destinations…");connect(save,&QAction::triggered,this,[this]{bool ok=false;const auto name=QInputDialog::getText(this,"Save destination preset","Preset name",QLineEdit::Normal,QString(),&ok);if(ok&&!name.trimmed().isEmpty())send(QJsonObject{{"action","preset_save"},{"name",name}});});
            const auto choices=lastPayload.value("output_presets").toObject();for(auto it=choices.begin();it!=choices.end();++it){const QString name=it.key();auto *item=presets->addAction("Use "+name);connect(item,&QAction::triggered,this,[this,name]{send(QJsonObject{{"action","preset_apply"},{"name",name}});});}
        });
        status->setVisible(view->showStatus);list->setStyleSheet(QString("QListWidget::item { padding:%1px; }").arg(view->compact?3:7));
    }

    void disconnected() { view->setConnected(false);
        status->setText("Companion offline");actionStatus->hide();lastDestinations.clear();
        startAllButton->setEnabled(true);stopAllButton->setEnabled(true);updating=true;
        for (int i=0;i<list->count();++i) {
            auto *item=list->item(i);item->setText(item->text().section("   ",0,0)+"   UNKNOWN");
            item->setForeground(QColor("#a8afb8"));item->setToolTip("Companion offline. Output health is unknown.");
        }
        updating=false;
    }

    void message(const QString &value) { actionStatus->setText(value);actionStatus->setToolTip(value);actionStatus->show();QTimer::singleShot(6000,actionStatus,[this] { actionStatus->hide(); }); }

    void update(const QJsonObject &payload)
    {
        view->setConnected(true);lastPayload=payload;
        startAllButton->setEnabled(true);stopAllButton->setEnabled(true);
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
            status->setText("No destinations");
        else if (!payload.value("stream_active").toBool())
            status->setText("Main · offline");
        else
            status->setText("Main · live");
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
    QJsonObject audioSettings;
    std::map<QString, std::unique_ptr<AudioMeter>> audioMeters;
    bool pending = false;
    QString bridgePath;
    QPushButton *updateButton;
    QJsonObject updateInfo;
    QJsonObject pendingSafeAction;
    qint64 pendingUntil=0;
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
        updateButton=new QPushButton("Update available",this);updateButton->hide();layout->addWidget(updateButton);
        updateButton->setToolTip("View release notes and download the newer Windows installer. Nothing installs automatically.");
        connect(updateButton,&QPushButton::clicked,this,[this] {
            const auto latest=updateInfo.value("latest").toObject();
            QMessageBox box(this);box.setWindowTitle("FDGCast update");
            box.setTextFormat(Qt::PlainText);
            box.setText("Installed: "+updateInfo.value("installed").toString()+"\nLatest: "+latest.value("version").toString()+"\n\nClose OBS and Companion before installing.");
            box.setDetailedText(latest.value("notes").toString());
            auto *download=box.addButton("Download installer",QMessageBox::AcceptRole);
            auto *later=box.addButton("Later",QMessageBox::RejectRole);
            box.addButton(QMessageBox::Close);box.exec();
            if (box.clickedButton()==download) QDesktopServices::openUrl(QUrl(latest.value("download_url").toString()));
            else if (box.clickedButton()==later) sendAction(QJsonObject{{"action","update_later"}});
        });
        auto *preflight=new QPushButton("Run pre-stream checks",this);layout->addWidget(preflight);
        connect(preflight,&QPushButton::clicked,this,[this]{sendAction(QJsonObject{{"action","preflight"}});});
        preflight->setToolTip("Checks connections, audio, destinations, storage and selected Hub event. Never starts your stream.");
        layout->addStretch();
#ifdef _WIN32
        bridgePath = qEnvironmentVariable("LOCALAPPDATA") + "/ForgeCast/bridge-token";
#else
        bridgePath = qEnvironmentVariable("HOME") + "/.local/share/ForgeCast/bridge-token";
#endif
        connect(&timer, &QTimer::timeout, this, [this] { tick(); });
        timer.start(1000);
        QTimer::singleShot(0, this, [this] { openCompanionIfNeeded(); });
    }

    void openCompanionIfNeeded()
    {
#ifdef _WIN32
        // Probe first: opening OBS must not launch a duplicate Companion.
        QNetworkRequest request(QUrl("http://127.0.0.1:17654/"));
        request.setTransferTimeout(1500);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        auto *reply = network.get(request);
        connect(reply, &QNetworkReply::finished, this, [this, reply] {
            if (reply->error() != QNetworkReply::NoError) {
                QSettings install("HKEY_LOCAL_MACHINE\\Software\\Forged Destiny Gaming\\FDGCast", QSettings::NativeFormat);
                const QString exe = install.value("CompanionPath").toString();
                if (exe.isEmpty() || !QFileInfo::exists(exe) || !QProcess::startDetached(exe, QStringList{}))
                    label->setText("FDGCast Companion could not start. Open it from the Start menu or repair the FDGCast installation.");
                else label->setText("FDGCast Companion is starting…");
            }
            reply->deleteLater();
        });
#endif
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

    void companionRequired(const QJsonObject &action) {
        if (action.value("action")=="chat_send" && chatDock) chatDock->sendResult(false,"Companion is offline. Your draft is kept; send it after reconnecting.");
        const auto choice=QMessageBox::question(this,"Open FDGCast Companion","FDGCast Companion is required for this feature. Open Companion App now?",QMessageBox::Yes|QMessageBox::No);
        if (choice!=QMessageBox::Yes) return;
        const QString operation=action.value("action").toString();
        if (operation=="focus" || operation=="audio_settings" || operation=="audio_snooze" || operation=="audio_ack") {
            pendingSafeAction=action;pendingUntil=QDateTime::currentSecsSinceEpoch()+20;
        }
        openCompanionIfNeeded();
        if (multistreamDock) multistreamDock->message("Companion is starting. Broadcast actions can be retried when connected.");
    }

    void sendAction(const QJsonObject &action)
    {
        const bool requestFocus = action.value("action").toString() == "focus";
        QFile tokenFile(bridgePath);
        if (!tokenFile.open(QIODevice::ReadOnly)) {
            if (requestFocus) { pendingSafeAction=action;pendingUntil=QDateTime::currentSecsSinceEpoch()+20;openCompanionIfNeeded(); return; }
            companionRequired(action);
            return;
        }
        QNetworkRequest request(QUrl("http://127.0.0.1:17654/native/action"));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setRawHeader("Authorization", "Bearer " + tokenFile.readAll().trimmed());
        request.setTransferTimeout(60000);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        auto *reply = network.post(request, QJsonDocument(action).toJson());
        const bool focusing = action.value("action").toString() == "focus";
        const bool sendingChat = action.value("action").toString() == "chat_send" || action.value("action").toString() == "chat_send_many";
        const bool audioAction = action.value("action").toString().startsWith("audio_");
        connect(reply, &QNetworkReply::finished, this, [this, reply, focusing, sendingChat, audioAction, action] {
            const auto body=QJsonDocument::fromJson(reply->readAll()).object();
            bool success = reply->error() == QNetworkReply::NoError;
            QString error = success ? QString() : body.value("error").toString();
            if(action.value("action").toString()=="chat_send_many" && success){
                QStringList results;for(const auto &entry:body.value("deliveries").toArray()){auto r=entry.toObject();results.append(r.value("platform").toString()+": "+(r.value("sent").toBool()?"sent":r.value("error").toString()));}
                success=body.value("ok").toBool();error=results.join("\n");
                if(success){QMessageBox box(this);box.setWindowTitle("Message delivery");box.setTextFormat(Qt::PlainText);box.setText(error);box.exec();}
                else error+="\nRetry only the failed platform to avoid sending twice.";
            }
            if(action.value("action").toString()=="preflight" && success){
                QStringList lines;for(const auto &entry:body.value("checks").toArray()){auto r=entry.toObject();lines.append(r.value("label").toString()+": "+r.value("result").toString());}
                QMessageBox box(this);box.setWindowTitle("FDGCast pre-stream checks");box.setTextFormat(Qt::PlainText);box.setText(lines.join("\n\n"));box.exec();
            }
            if(!success && (action.value("action").toString()=="chat_moderate" || action.value("action").toString()=="hub_select")){QMessageBox box(this);box.setWindowTitle("FDGCast action needs attention");box.setTextFormat(Qt::PlainText);box.setText(error);box.exec();}
            if (sendingChat && chatDock)
                chatDock->sendResult(success, error);
            if (audioAction && doctorDock) doctorDock->message(success ? "Audio Guard request accepted. Waiting for updated OBS readings." : error);
            if (multistreamDock) {
                if (!success) {
                    if (focusing) { label->setText(error.isEmpty() ? "Opening FDGCast Companion…" : error); openCompanionIfNeeded(); }
                    else if (!sendingChat) multistreamDock->message(error.isEmpty() ? "Action failed. Check FDGCast connection." : error);
                } else if (!focusing && !sendingChat) multistreamDock->message("Request accepted. Waiting for OBS output status.");
            }
            if (!success && error.isEmpty() && !focusing) companionRequired(action);
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

    QJsonObject audioSnapshot()
    {
        QJsonArray rows;
        QSet<QString> selected, seen;
        if (audioSettings.value("enabled").toBool(true))
            for (const auto &row : audioSettings.value("sources").toArray()) selected.insert(row.toObject().value("uuid").toString());
        struct Scan { ForgeDock *self; QJsonArray *rows; QSet<QString> *selected; QSet<QString> *seen; } scan{this, &rows, &selected, &seen};
        obs_enum_sources([](void *data, obs_source_t *source) {
            auto &scan = *static_cast<Scan *>(data);
            if (!(obs_source_get_output_flags(source) & OBS_SOURCE_AUDIO) || obs_source_removed(source)) return true;
            const QString uuid = QString::fromUtf8(obs_source_get_uuid(source));
            scan.seen->insert(uuid);
            auto &meters = scan.self->audioMeters;
            if (scan.selected->contains(uuid) && meters.find(uuid) == meters.end()) meters.emplace(uuid, std::make_unique<AudioMeter>(source));
            QJsonObject row{{"uuid",uuid},{"name",QString::fromUtf8(obs_source_get_name(source))},
                {"active",obs_source_active(source)},{"muted",obs_source_muted(source)},
                {"mixers",static_cast<int>(obs_source_get_audio_mixers(source))},
                {"volume",obs_source_get_volume(source)},
                {"monitor_only",obs_source_get_monitoring_type(source) == OBS_MONITORING_TYPE_MONITOR_ONLY}};
            auto found = meters.find(uuid);
            if (found != meters.end()) {
                const auto now = audioClock(), sample = found->second->lastMeter.load(), signal = found->second->lastSignal.load();
                const auto hot=found->second->hotSince.load();row.insert("hot_duration",hot?QJsonValue((now-hot)/1000.0):QJsonValue(0));
                row.insert("meter_age", sample ? QJsonValue((now-sample)/1000.0) : QJsonValue());
                row.insert("signal_age", signal ? QJsonValue((now-signal)/1000.0) : QJsonValue());
            }
            if (scan.rows->size() < 128) scan.rows->append(row);
            return true;
        }, &scan);
        for (auto it=audioMeters.begin(); it!=audioMeters.end();)
            if (!seen.contains(it->first) || !selected.contains(it->first)) it=audioMeters.erase(it); else ++it;
        int track = 0;
        auto *output = obs_frontend_get_streaming_output();
        if (output) {
            auto *encoder = obs_output_get_audio_encoder(output,0);
            if (encoder) track = static_cast<int>(obs_encoder_get_mixer_index(encoder))+1;
            obs_output_release(output);
        }
        auto *scene = obs_frontend_get_current_scene();
        const QString sceneName = scene ? QString::fromUtf8(obs_source_get_name(scene)) : QString();
        if (scene) obs_source_release(scene);
        return QJsonObject{{"sources",rows},{"stream_track",track},{"track_verified",obs_frontend_streaming_active() && track>=1 && track<=6},
            {"stream_active",obs_frontend_streaming_active()},{"scene",sceneName}};
    }

    QString fixAudio(const QJsonObject &cmd)
    {
        const QString uuid = cmd.value("source_uuid").toString();
        bool selected=false;
        for (const auto &row : audioSettings.value("sources").toArray())
            if (row.toObject().value("uuid").toString() == uuid) selected=true;
        if (!selected) return "audio_source_not_selected";
        auto *source = obs_get_source_by_uuid(uuid.toUtf8().constData());
        if (!source) return "audio_source_missing";
        const auto action = cmd.value("fix").toString();
        QString result="audio_action_unsupported";
        if (action == "unmute") { obs_source_set_muted(source,false); result="audio_unmute_applied"; }
        else if (action == "route") {
            auto *output = obs_frontend_get_streaming_output();
            auto *encoder = output ? obs_output_get_audio_encoder(output,0) : nullptr;
            const size_t mix = encoder ? obs_encoder_get_mixer_index(encoder) : 6;
            if (encoder && mix<6) {
                obs_source_set_audio_mixers(source,obs_source_get_audio_mixers(source) | (1u << mix));
                if (obs_source_get_monitoring_type(source) == OBS_MONITORING_TYPE_MONITOR_ONLY)
                    obs_source_set_monitoring_type(source,OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT);
                result="audio_stream_routing_applied";
            } else result="audio_stream_track_unavailable";
            if (output) obs_output_release(output);
        }
        obs_source_release(source); return result;
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
        if (action == "audio_fix") {
            result = fixAudio(cmd);
            if (doctorDock) {
                QString message;
                if (result == "audio_unmute_applied") message="Audio source unmuted. Check the meter for signal.";
                else if (result == "audio_stream_routing_applied") message="Source enabled on the current stream track. Other tracks preserved.";
                else if (result == "audio_stream_track_unavailable") message="OBS stream track is unavailable. Start streaming and try again.";
                else message="Audio fix could not be applied. Check your selected source in Companion.";
                doctorDock->message(message);
            }
        } else if (action == "start") {
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
            if (hubDock) hubDock->disconnected();
            if (chatDock) chatDock->disconnected();
            if (eventsDock) eventsDock->disconnected();
            if (doctorDock) doctorDock->disconnected();
            if (multistreamDock) multistreamDock->disconnected();
            label->setText("FDGCAST · Companion not running\n"
                           "Secondary streams, if active, can be stopped below.");
            return;
        }
        QByteArray token = tokenFile.readAll().trimmed();
        if (token.size() < 32 || token.size() > 128)
            return;
        QJsonObject mainTelemetry;
        auto *mainStream = obs_frontend_get_streaming_output();
        if (mainStream) {
            mainTelemetry = QJsonObject{{"id","main"},{"name","OBS main"},{"active",obs_frontend_streaming_active()},
                {"reconnecting",obs_output_reconnecting(mainStream)},
                {"dropped",obs_output_get_frames_dropped(mainStream)},{"frames",obs_output_get_total_frames(mainStream)},
                {"bytes",static_cast<double>(obs_output_get_total_bytes(mainStream))}};
            obs_output_release(mainStream);
        }
        QJsonArray outputs;
        for (auto &entry : destinations) {
            auto &d = *entry.second;
            bool active = obs_output_active(d.output);
            const bool intentionalStop = d.stopping;
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
                {"intentional_stop", intentionalStop}, {"error", d.error}, {"busy", d.starting || d.stopping}, {"reconnecting", obs_output_reconnecting(d.output)},
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
        auto *reply = network.post(request, QJsonDocument(QJsonObject{{"outputs", outputs}, {"main_output", mainTelemetry}, {"results", results}, {"audio", audioSnapshot()}}).toJson());
        pending = true;
        connect(reply, &QNetworkReply::finished, this, [this, reply, sentResults] {
            pending = false;
            if (reply->error() == QNetworkReply::NoError) {
                for (int i = 0; i < sentResults && !results.isEmpty(); ++i) results.removeAt(0);
                auto payload = QJsonDocument::fromJson(reply->readAll()).object();
                updateInfo=payload.value("updates").toObject();
                updateButton->setVisible(updateInfo.value("show_notice").toBool());
                updateButton->setText("Update to "+updateInfo.value("latest").toObject().value("version").toString());
                if (!pendingSafeAction.isEmpty()) {
                    auto queued=pendingSafeAction;pendingSafeAction=QJsonObject();
                    if (QDateTime::currentSecsSinceEpoch()<=pendingUntil) sendAction(queued);
                }
                audioSettings = payload.value("audio_settings").toObject();
                if (hubDock) hubDock->update(payload);
                if (chatDock) chatDock->update(payload);
                if (eventsDock) eventsDock->update(payload);
                if (doctorDock) doctorDock->update(payload);
                if (multistreamDock) multistreamDock->update(payload);
                for (const auto &value : payload.value("commands").toArray())
                    command(value.toObject());
                label->setText("FDGCAST · Companion connected\n"
                               "Your FDGCast docks are ready.\n"
                               "Stopping the main OBS stream also stops secondary outputs.");
            } else {
                if (hubDock) hubDock->disconnected();
            if (chatDock) chatDock->disconnected();
                if (eventsDock) eventsDock->disconnected();
                if (doctorDock) doctorDock->disconnected();
                if (multistreamDock) multistreamDock->disconnected();
                label->setText("FDGCAST · Companion disconnected\n"
                               "Active streams are not stopped by a dashboard outage. Use the button below.");
            }
            reply->deleteLater();
        });
    }
};

static QPointer<ForgeDock> dock;
static void openCompanionWindow() { if (dock) dock->sendAction(QJsonObject{{"action","focus"}}); }
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
        obs_frontend_remove_dock("fdgcast-hub");if(hubDock)delete hubDock.data();hubDock.clear();
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
    doctorDock = new DoctorDock([](const QJsonObject &action) { if (dock) dock->sendAction(action); });
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
    hubDock=new HubDock([](const QJsonObject &action){if(dock)dock->sendAction(action);});
    if(!obs_frontend_add_dock_by_id("fdgcast-hub","FDGCast Today’s Events",hubDock.data())){delete hubDock.data();hubDock.clear();}
    else {QSettings preferences("Forged Destiny Gaming","ForgeCast");if(!preferences.value("hub-dock-introduced",false).toBool()){if(hubDock->parentWidget())hubDock->parentWidget()->hide();preferences.setValue("hub-dock-introduced",true);}}
    // OBS retains the historical dock IDs so existing workspace layouts survive upgrades.
    // Apply the FDG shield when a dock is floated into its own window.
    char *iconPath = obs_module_file("FDGCast.ico");
    if (iconPath) {
        const QIcon icon(QString::fromUtf8(iconPath));
        bfree(iconPath);
        QWidget *contents[] = {chatDock.data(), eventsDock.data(), doctorDock.data(),
                               multistreamDock.data(), hubDock.data(), dock.data()};
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

