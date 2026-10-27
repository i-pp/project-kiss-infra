# コーディング評価の手順

モデルに送信する課題は `tasks.json`。独立テストと参照実装をモデルへの出題前に作成し、`logs/coder/fixtures-before-generation.sha256` にハッシュを保存する。
モデルには課題の仕様だけを送信し、テスト、参照コード、正解コードは送信しない。

各課題はtemperature 0、seed 42、最大2048出力トークン、キャッシュ無効、1回のみ生成。
応答のコードブロックをそのまま抽出し、手修正・再質問・モデル自身のテストによる加点は行わない。
JSON形式の2課題は形式検証に加えて、仕様に基づく意味のレビューを別に実施する。

| 課題 | 独立した採点根拠 |
|---|---|
| Cのuint32解析 | `std::from_chars`との比較、最大値・桁あふれ・無効文字・長い先頭ゼロ・NULL |
| C++自己参照append | 元配列の別コピーによる参照結果、範囲全探索、SIZE_MAX、再確保、libstdc++ debug mode |
| POSIX非同期write | 事前に決めたsyscall応答列（短いwrite、EINTR、EAGAIN、0、hard error）、本物の非同期pipeとEPIPE |
| Rust prefix sum | i64での参照計算、途中だけ桁あふれする入力、5000列、unsafe禁止、overflow-checks有効 |
| AArch64 scalar sum | uint64の参照和、unsigned上位ビット、保護ページ、x19〜x29の保存を独立ASMで確認 |
| NEON SAD | scalar参照和、0対255、ランダム、百万要素、全末尾長・未整列バイト、保護ページ、NEON命令の存在 |
| NEON signed dot | int64参照積和、-128×-128、正負極値、百万要素、保護ページ、baseline Armv8-Aでのビルドと実行 |
| 不明仕様への対応 | wire format・型・エンディアン・失敗時の扱いを勝手に決めず確認事項として提示するか |
| C11のUBレビュー | NULL/範囲、alignment、effective type、shift count、signed left shift、signed additionの条件説明 |

ネイティブC/C++はGCC/G++、AddressSanitizer、UndefinedBehaviorSanitizerで実行する（リーク検査は対象外）。
AArch64は `-march=armv8-a` で静的クロスコンパイルし、QEMU `cortex-a53` で実行する。エミュレーション結果は実機性能の証明ではない。
テストケースを全て通過しても、あらゆる入力での安全性・ABI要件・性能を保証するものではない。

`make-controls.py` は評価者が用意した正しい実装と意図的な誤実装を生成する。これを先に採点し、テスト自体の検出能力を確認する。
生成コードの実行は `scripts/test-coder-output.sh` により、ネットワークなし、非root、rootfs読み取り専用、capability全削除、no-new-privileges、CPU/RAM/PID制限付きの別Dockerコンテナに限定する。
GPU、Dockerソケット、モデルデータはこのコンテナに渡さない。

参照する仕様・資料:

- [POSIX write](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html): partial write、EINTR、EAGAIN等。
- [C11委員会ドラフト N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf): 6.3.2.3、6.5、6.5.7等。
- [C++ working draft / sequence container requirements](https://eel.is/c++draft/sequence.reqmts): 自己範囲のinsertの制約。
- [Rust checked_add](https://doc.rust-lang.org/std/primitive.i32.html#method.checked_add)。
- [Arm NEON Intrinsics Reference](https://arm-software.github.io/acle/neon_intrinsics/advsimd.html)。
- [AAPCS64](https://github.com/ARM-software/abi-aa/blob/main/aapcs64/aapcs64.rst)。

再実行時は既存の `logs/coder/eval` と結果を別名で保管してから実行する。生の応答と生成コード、実行バイナリは `logs/` 内に置き、Gitに含めない。
