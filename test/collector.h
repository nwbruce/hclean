#ifndef COLLECTOR_H_
#define COLLECTOR_H_

#include <list>
#include <climits>

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