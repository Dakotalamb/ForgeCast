#include "../../native/render-guard.hpp"
#include <cassert>
#include <thread>
int calls=0;
void accidentalCycle(){fdgcast::RenderGuard guard;if(!guard)return;++calls;accidentalCycle();}
int main(){
 accidentalCycle();assert(calls==1);
 accidentalCycle();assert(calls==2);
 {fdgcast::RenderGuard outer;assert(outer);fdgcast::RenderGuard nested;assert(!nested);
 std::thread independent([]{fdgcast::RenderGuard g;assert(g);});independent.join();}
 accidentalCycle();assert(calls==3);
}
