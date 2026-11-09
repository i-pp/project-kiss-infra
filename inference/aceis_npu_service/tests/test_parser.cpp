/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

// Test the production worker parser without creating an ORT session/device.
#define main aceis_worker_main
#include "../worker.cpp"
#undef main
#include <limits>
int main() {
  std::vector<float> values(3072);
  std::string line="0 1.40129846e-45 3.40282347e+38";
  for (int i=3;i<3072;++i) line+=" 0";
  parse_input(line,values);
  if (values[0]!=0 || values[1]!=std::numeric_limits<float>::denorm_min() ||
      values[2]!=std::numeric_limits<float>::max()) return 1;
  try { parse_input("nan",values); return 2; } catch (const std::runtime_error&) {}
  try { parse_input("1e99",values); return 3; } catch (const std::runtime_error&) {}
  return 0;
}
