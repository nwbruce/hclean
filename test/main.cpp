#include <collector.h>
#include <collector_util.h>
#include <array>
#include <iostream>

int main() {
    const std::array<double, 5> values {1, 2, 3, 4, 5};
    Collector c;
    push_all(c, values.cbegin(), values.cend());
    
    std::cout << c.avg() << std::endl;


    return 0;
}