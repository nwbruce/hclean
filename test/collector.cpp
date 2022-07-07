#include <collector.h>
#include <unordered_map>
#include <climits>
#include <map>

Collector::Collector() : _sum(0.0) {}

void Collector::push(double value) {
    _sum += value;
    _values.push_back(value);
}

double Collector::pop() {
    double value = _values.front();
    _values.pop_front();
    _sum -= value;
    return value;
}

double Collector::sum() const {
    return _sum;
}

double Collector::avg() const {
    return _sum / _values.size();
}
