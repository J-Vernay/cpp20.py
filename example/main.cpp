
import C;

import <cstdio>;

static_assert(C::constant() == 42);

int main() {
  A_hello();
  B_hello();
  int a = std::hash<std::string_view>{}("Hi!");
  std::printf("Hash of 'Hi!' is %d.\n", a);
}
