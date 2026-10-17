#pragma once
#include <algorithm>
#include <cmath>

namespace fdgcast {
struct PortraitLayout { float scale, x, y; };
inline PortraitLayout portraitLayout(float width, float height, bool fill)
{
    if (!std::isfinite(width) || !std::isfinite(height) || width <= 0 || height <= 0)
        return {0, 0, 0};
    const float scale = fill ? std::max(720.f / width, 1280.f / height)
                             : std::min(720.f / width, 1280.f / height);
    return {scale, (720.f-width*scale)/2.f, (1280.f-height*scale)/2.f};
}
}
