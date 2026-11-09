# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

cmake_minimum_required(VERSION 3.20)
project(kiss_llvm_api_validation LANGUAGES C CXX)
find_package(LLVM 21.1.8 EXACT REQUIRED CONFIG
  PATHS /usr/lib/llvm-21/lib/cmake/llvm NO_DEFAULT_PATH)
add_executable(llvm-api-smoke llvm-api-smoke.cpp)
target_compile_features(llvm-api-smoke PRIVATE cxx_std_17)
target_include_directories(llvm-api-smoke SYSTEM PRIVATE ${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})
target_link_libraries(llvm-api-smoke PRIVATE LLVM)
target_link_options(llvm-api-smoke PRIVATE -fuse-ld=/usr/bin/ld.lld-21)
