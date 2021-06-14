module;
#include "H.hpp"
export module C;

export import A;
export import B;

export namespace C {
  constexpr int constant() { return H::CONSTANT; }
}
