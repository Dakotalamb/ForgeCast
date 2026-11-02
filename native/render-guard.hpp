#pragma once
namespace fdgcast {
class RenderGuard {
    inline static thread_local bool rendering=false;
    bool entered=false;
public:
    RenderGuard() { if(!rendering){rendering=true;entered=true;} }
    explicit operator bool() const {return entered;}
    ~RenderGuard(){if(entered)rendering=false;}
    RenderGuard(const RenderGuard&)=delete;
    RenderGuard& operator=(const RenderGuard&)=delete;
};
}
