#pragma once
#include <QObject>
#include <functional>
#include <utility>
#include <QEvent>
#include <QKeyEvent>
#include <QWheelEvent>
#include <QAbstractSlider>
#include <QScrollBar>
#include <QTextBrowser>
#include <QTimer>

// Layout and image loading can move the scroll bar without reader input.
// Only reader actions change follow mode; document changes retain that choice.
class ChatScrollFollow : public QObject {
    QTextBrowser *feed;
    bool following = true;
    bool paused = false;
    bool pending = false;
    std::function<void(bool)> notify;
    bool nearBottom() const {
        auto *bar = feed->verticalScrollBar();
        return bar->maximum() - bar->value() <= 60;
    }
    void pin() {
        if (following && !paused)
            feed->verticalScrollBar()->setValue(feed->verticalScrollBar()->maximum());
    }
    void changed() { if (notify) notify(paused || !following); }
    void checkReaderPosition() {
        QTimer::singleShot(0, this, [this] { following = nearBottom(); changed(); });
    }
protected:
    bool eventFilter(QObject *, QEvent *event) override {
        if (event->type() == QEvent::Wheel) {
            auto *wheel = static_cast<QWheelEvent *>(event);
            const int dy = wheel->pixelDelta().isNull() ? wheel->angleDelta().y() : wheel->pixelDelta().y();
            if (dy > 0 && feed->verticalScrollBar()->maximum() > 0) { following = false; changed(); }
            else if (dy < 0) checkReaderPosition();
        } else if (event->type() == QEvent::KeyPress) {
            const int key = static_cast<QKeyEvent *>(event)->key();
            if (key == Qt::Key_Up || key == Qt::Key_PageUp || key == Qt::Key_Home) {
                if (feed->verticalScrollBar()->maximum() > 0) { following = false; changed(); }
            } else if (key == Qt::Key_Down || key == Qt::Key_PageDown || key == Qt::Key_End) checkReaderPosition();
        }
        return false;
    }
public:
    explicit ChatScrollFollow(QTextBrowser *widget, std::function<void(bool)> onChanged = {})
        : QObject(widget), feed(widget), notify(std::move(onChanged)) {
        feed->installEventFilter(this);
        feed->viewport()->installEventFilter(this);
        auto *bar = feed->verticalScrollBar();
        bar->installEventFilter(this);
        connect(bar, &QScrollBar::rangeChanged, this, [this] { layoutChanged(); });
        connect(bar, &QScrollBar::sliderMoved, this, [this](int position) {
            following = feed->verticalScrollBar()->maximum() - position <= 60; changed();
        });
        connect(bar, &QScrollBar::actionTriggered, this, [this](int action) {
            if (action == QAbstractSlider::SliderSingleStepSub || action == QAbstractSlider::SliderPageStepSub || action == QAbstractSlider::SliderToMinimum) {
                following = false; changed();
            } else if (action == QAbstractSlider::SliderSingleStepAdd || action == QAbstractSlider::SliderPageStepAdd || action == QAbstractSlider::SliderToMaximum) checkReaderPosition();
        });
    }
    bool isFollowing() const { return following; }
    void setPaused(bool value) { paused = value; changed(); if (!paused) resume(); }
    void resume() { following = true; changed(); layoutChanged(); }
    void layoutChanged() {
        pin();
        if (pending) return;
        pending = true;
        QTimer::singleShot(0, this, [this] { pending = false; pin(); });
    }
};
