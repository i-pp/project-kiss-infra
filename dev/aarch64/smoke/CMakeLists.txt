# KISS Open License Version 1.0 (KOL-v1)
#
# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1
#
# Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
# Contributors may add copyright notices for their own original modifications.
# Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
#
# Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
# without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
#
# Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
# KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
#
# This header is a summary, not a separate license or an amendment to KOL-v1.
# All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

cmake_minimum_required(VERSION 3.20)
project(kiss_environment_validation LANGUAGES C ASM)
if(NOT CMAKE_C_COMPILER_VERSION VERSION_EQUAL "21.1.8")
  message(FATAL_ERROR "Require Clang 21.1.8")
endif()
if(NOT DEFINED VALIDATION_CONFIG OR NOT DEFINED VALIDATION_LINKER)
  message(FATAL_ERROR "Use scripts/test-dev-aarch64.py to validate the DTB first")
endif()
add_executable(c-smoke.elf start.S main.c uart.c reference.c simd.c)
target_include_directories(c-smoke.elf PRIVATE "${VALIDATION_CONFIG}")
target_compile_options(c-smoke.elf PRIVATE $<$<COMPILE_LANGUAGE:C>:-O2;-Wall;-Wextra;-Werror>)
set_source_files_properties(reference.c PROPERTIES COMPILE_OPTIONS "-fno-vectorize;-fno-slp-vectorize")
target_link_options(c-smoke.elf PRIVATE "-Wl,-T,${VALIDATION_LINKER}" "-Wl,--build-id=none")
set_property(TARGET c-smoke.elf APPEND PROPERTY LINK_DEPENDS "${VALIDATION_LINKER}")
