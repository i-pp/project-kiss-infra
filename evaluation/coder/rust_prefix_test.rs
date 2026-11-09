// SPDX-FileCopyrightText: 2026 I-plusplus Inc.
// SPDX-License-Identifier: LicenseRef-KOL-v1

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
