// Stream a Spike instruction log without retaining multi-gigabyte trace files.
// The simulator and binaries are unmodified. Counts cover the whole program.
#include <array>
#include <cstdlib>
#include <iostream>
#include <string>

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);
  std::string line;
  unsigned long long total = 0, unknown = 0, measured = 0;
  bool has_measurement = false;
  std::array<unsigned long long, 128> functions{};
  while (std::getline(std::cin, line)) {
    if (line.rfind("core", 0) == 0 && line.find(": 0x") != std::string::npos)
      ++total;
    if (line.find("unknown") != std::string::npos) {
      ++unknown;
      auto pos = line.find("(0x");
      if (pos != std::string::npos) {
        auto instruction = std::strtoull(line.c_str() + pos + 3, nullptr, 16);
        if ((instruction & 0x7f) == 0x7b)
          ++functions[(instruction >> 25) & 0x7f];
      }
    }
    auto pos = line.find("Cycles taken: ");
    if (!has_measurement && pos != std::string::npos) {
      measured = std::strtoull(line.c_str() + pos + 14, nullptr, 10);
      has_measurement = true;
    }
  }
  std::cout << "{\"traced_instructions_total\":" << total
            << ",\"rocc_unknown_total\":" << unknown
            << ",\"measured_instructions\":" << measured
            << ",\"custom3_funct7_zero_total\":" << functions[0]
            << ",\"custom3_funct7_counts\":{";
  bool first = true;
  for (unsigned i = 0; i < functions.size(); ++i) {
    if (!functions[i]) continue;
    if (!first) std::cout << ',';
    first = false;
    std::cout << '"' << i << "\":" << functions[i];
  }
  std::cout << "}}\n";
  return has_measurement && total > 0 ? 0 : 1;
}
