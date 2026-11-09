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

# Environment-validation toolchain; not an AceIS/Abiss ABI specification.
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(CMAKE_C_COMPILER /usr/bin/clang-21)
set(CMAKE_ASM_COMPILER /usr/bin/clang-21)
set(CMAKE_C_COMPILER_TARGET aarch64-none-elf)
set(CMAKE_ASM_COMPILER_TARGET aarch64-none-elf)
set(CMAKE_LINKER /usr/bin/ld.lld-21)
set(CMAKE_AR /usr/bin/llvm-ar-21)
set(CMAKE_RANLIB /usr/bin/llvm-ranlib-21)
set(CMAKE_OBJDUMP /usr/bin/llvm-objdump-21)
set(CMAKE_C_FLAGS_INIT "-mcpu=cortex-a53 -mstrict-align -ffreestanding -fno-stack-protector -fno-pic -g")
set(CMAKE_ASM_FLAGS_INIT "-mcpu=cortex-a53 -g")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-nostdlib -static -fuse-ld=/usr/bin/ld.lld-21")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
