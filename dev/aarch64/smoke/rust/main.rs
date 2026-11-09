// KISS Open License Version 1.0 (KOL-v1)
//
// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1
//
// Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
// Contributors may add copyright notices for their own original modifications.
// Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
//
// Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
// without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
//
// Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
// KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
//
// THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
//
// This header is a summary, not a separate license or an amendment to KOL-v1.
// All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.

// Infrastructure validation only. No runtime/ABI for AceIS or Abiss is defined.
#![no_std]
#![no_main]
use core::panic::PanicInfo;
include!(concat!(env!("VALIDATION_CONFIG"), "/uart_config.rs"));

fn put(text: &[u8]) {
    for &byte in text {
        unsafe {
            while core::ptr::read_volatile((UART_BASE + 0x18) as *const u32) & (1 << 5) != 0 {}
            core::ptr::write_volatile(UART_BASE as *mut u32, byte as u32);
        }
    }
}
#[no_mangle]
pub extern "C" fn smoke_main() {
    let el: u64;
    let cpacr: u64;
    unsafe {
        core::arch::asm!("mrs {0}, CurrentEL", out(reg) el);
        core::arch::asm!("mrs {0}, CPACR_EL1", out(reg) cpacr);
    }
    if el != 4 || cpacr & 0x300000 != 0x300000 { panic!("EL/FP"); }
    // Runtime computation via volatile input ensures this is not only a string printer.
    let input = [1u64, 3, 5, 7];
    let mut sum = 0u64;
    for x in &input { sum = sum.wrapping_add(unsafe { core::ptr::read_volatile(x) }); }
    if sum != 16 { panic!("sum"); }
    put(b"RUST PASS no_std core EL1 FP\nSMOKE DONE\n");
}
#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    put(b"RUST FAIL panic\n");
    loop { unsafe { core::arch::asm!("wfi"); } }
}
