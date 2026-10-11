#include "../../native/chat-scroll-follow.hpp"
#include <QApplication>
#include <QTextDocument>
#include <QImage>
#include <iostream>
#include <stdexcept>
static void settle() { for(int i=0;i<8;++i) QApplication::processEvents(); }
static void require(bool value, const char *message) { if(!value) throw std::runtime_error(message); }
static QString messages(int count) {
    QString html;
    for(int i=0;i<count;++i) html += QString("<p>Message %1 with enough text to wrap when the dock gets narrow.</p>").arg(i);
    return html;
}
static void wheel(QTextBrowser &feed, int delta) {
    QWheelEvent event(QPointF(40,40),QPointF(feed.viewport()->mapToGlobal(QPoint(40,40))),QPoint(),QPoint(0,delta),Qt::NoButton,Qt::NoModifier,Qt::NoScrollPhase,false);
    QApplication::sendEvent(feed.viewport(), &event); settle();
}
int main(int argc,char **argv) {
    QApplication app(argc,argv);
    try {
        QTextBrowser feed; feed.resize(420,260); feed.show();
        bool jump=false;ChatScrollFollow follow(&feed,[&](bool visible){jump=visible;});
        auto *bar=feed.verticalScrollBar();
        feed.setHtml(messages(70));follow.layoutChanged();settle();
        require(bar->maximum()>100,"Fixture must have scrollback");
        require(bar->value()==bar->maximum() && !jump,"Initial chat follows latest");
        // A late layout change after the first bottom pin used to leave the old
        // position behind. The next payload then classified it as scrollback.
        QFont larger=feed.font();larger.setPointSize(22);feed.setFont(larger);settle();
        feed.resize(160,130);settle();
        require(follow.isFollowing() && bar->value()==bar->maximum() && !jump,"Font and dock resizing must not stop following");
        feed.setHtml(messages(90));follow.layoutChanged();settle();
        require(bar->value()==bar->maximum(),"Incoming burst follows bottom after layout");
        wheel(feed,120);require(!follow.isFollowing() && jump,"Reader wheel up pauses following");
        const int reading=bar->value();feed.setHtml(messages(95));bar->setValue(reading);settle();
        require(!follow.isFollowing() && bar->value()<bar->maximum(),"Incoming chat must not pull reader out of scrollback");
        follow.resume();settle();require(bar->value()==bar->maximum() && !jump,"Jump resumes following");
        bar->triggerAction(QAbstractSlider::SliderPageStepSub);settle();require(!follow.isFollowing(),"Scrollbar page up pauses");
        bar->triggerAction(QAbstractSlider::SliderToMaximum);settle();require(follow.isFollowing() && !jump,"Scrollbar return to bottom resumes");
        QKeyEvent up(QEvent::KeyPress,Qt::Key_PageUp,Qt::NoModifier);QApplication::sendEvent(&feed,&up);settle();require(!follow.isFollowing(),"Keyboard scrollback pauses");
        QKeyEvent end(QEvent::KeyPress,Qt::Key_End,Qt::ControlModifier);QApplication::sendEvent(&feed,&end);settle();require(follow.isFollowing(),"Keyboard end resumes");
        follow.setPaused(true);feed.setHtml(messages(110));settle();require(jump,"Explicit pause remains visible during layout");
        follow.setPaused(false);settle();require(bar->value()==bar->maximum() && !jump,"Unpause returns to latest");
        feed.setHtml(messages(120)+"<img src='test:image'>");follow.layoutChanged();settle();
        QImage image(120,180,QImage::Format_RGB32);image.fill(Qt::red);
        feed.document()->addResource(QTextDocument::ImageResource,QUrl("test:image"),image);
        feed.document()->markContentsDirty(0,feed.document()->characterCount());settle();
        require(follow.isFollowing() && bar->value()==bar->maximum(),"Late image layout retains following");
        std::cout<<"PASS: native Qt follow, layout, resize, incoming bursts, wheel, scrollbar, keyboard, pause, and late images\n";
    } catch(const std::exception &error) { std::cerr<<error.what()<<'\n';return 1; }
    return 0;
}
