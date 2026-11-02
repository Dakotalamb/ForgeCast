#include "../../native/portrait-layout.hpp"
#include <limits>

static bool near(float a, float b) { return std::abs(a-b)<0.01f; }
int main()
{
    using fdgcast::portraitLayout;
    const auto region=fdgcast::regionLayout(1920,1080,720,384,true,2.f,1.f,0.f);
    if (!near(region.x+1920*region.scale,720)) return 8;
    const auto centered=fdgcast::regionLayout(1920,1080,720,384,false,1.f,0.f,0.f);
    if (!near(centered.x+1920*centered.scale/2,360)) return 9;
    auto fill = portraitLayout(1920,1080,true);
    auto fit = portraitLayout(1920,1080,false);
    if (!near(fill.scale*1080,1280) || fill.x>=0 || !near(fill.y,0)) return 1;
    if (!near(fit.scale*1920,720) || fit.y<=0 || !near(fit.x,0)) return 2;
    for (bool mode : {true,false}) {
        const auto exact = portraitLayout(1080,1920,mode);
        if (!near(exact.scale,2.f/3.f) || !near(exact.x,0) || !near(exact.y,0)) return 3;
        for (auto size : {0.f,-1.f,std::numeric_limits<float>::infinity()})
            if (portraitLayout(size,1080,mode).scale != 0 || portraitLayout(1920,size,mode).scale != 0) return 4;
    }
    // Ultrawide and tall sources preserve aspect and remain centered.
    for (auto width : {800.f,1920.f,3440.f}) {
        for (bool mode : {true,false}) {
            const auto p = portraitLayout(width,1440,mode);
            if (!near(p.x+width*p.scale/2,360) || !near(p.y+1440*p.scale/2,640)) return 5;
            if (mode && (width*p.scale<719.99 || 1440*p.scale<1279.99)) return 6;
            if (!mode && (width*p.scale>720.01 || 1440*p.scale>1280.01)) return 7;
        }
    }
    return 0;
}
