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

mod answer { include!("/work/rust_prefix.rs"); }
fn reference(xs: &[i32]) -> Option<Vec<i32>> {
    let mut sum=0_i64; let mut out=Vec::new();
    for &x in xs { sum+=i64::from(x); if sum<i64::from(i32::MIN)||sum>i64::from(i32::MAX) {return None} out.push(sum as i32); }
    Some(out)
}
#[test] fn edge_cases() {
    for xs in [vec![],vec![0],vec![i32::MIN],vec![i32::MAX,1,-1],vec![i32::MIN,-1,1],vec![i32::MAX,-i32::MAX],vec![-1,1,1]] {
        assert_eq!(answer::prefix_sums(&xs),reference(&xs));
    }
}
#[test] fn independent_i64_reference() {
    let mut state=42_u32;
    for n in 0..5000 { let xs:Vec<i32>=(0..n%129).map(|_|{state^=state<<13;state^=state>>17;state^=state<<5;state as i32}).collect(); assert_eq!(answer::prefix_sums(&xs),reference(&xs)); }
}
