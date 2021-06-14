module;
#include "H.hpp"
module B;

import A;

void B_hello() {
  if (B_CONSTANT == 0)
    A_hello();
}
