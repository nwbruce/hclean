
#include <collector.h>
#include <unordered_map>
#include <climits>
#include <map>

template <typename ITER>
void push_all(Collector& c, ITER start, ITER end) {
    for (; start != end; ++start) {
        c.push(*start);
    }
}

void clear(Collector& c) {
    while (!c.empty()) {
        c.pop();
    }
}
