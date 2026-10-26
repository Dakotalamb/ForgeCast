#pragma once
#include <algorithm>
#include <cmath>

namespace fdgcast {
struct PortraitLayout { float scale, x, y; };
inline PortraitLayout regionLayout(float width, float height, float tw, float th, bool fill, float zoom, float panX, float panY)
{
    if (width <= 0 || height <= 0) return {0,0,0};
    const float scale=(fill ? std::max(tw/width,th/height) : std::min(tw/width,th/height))*zoom;
    return {scale,(tw-width*scale)/2-std::max(0.f,width*scale-tw)/2*panX,
                  (th-height*scale)/2-std::max(0.f,height*scale-th)/2*panY};
}
inline PortraitLayout portraitLayout(float width, float height, bool fill)
{
    if (!std::isfinite(width) || !std::isfinite(height) || width <= 0 || height <= 0)
        return {0, 0, 0};
    const float scale = fill ? std::max(720.f / width, 1280.f / height)
                             : std::min(720.f / width, 1280.f / height);
    return {scale, (720.f-width*scale)/2.f, (1280.f-height*scale)/2.f};
}
}
