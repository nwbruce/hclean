#ifndef COLLECTOR_H_
#define COLLECTOR_H_

#include <unordered_map>
#include <list>
#include <climits>
#include <map>

struct Collector {
  Collector();

  void push(double value);
  double pop();

  double sum() const;
  double avg() const;
  bool empty() const;
 private:
  std::list<double> _values;
  double _sum;
};

#endif