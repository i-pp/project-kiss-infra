# Repair Loop v2 — Phase A: baseline 20候補の分析

対象は `logs/repair/20261027T084214958944Z/` の `report.json`、各候補ソース、`verification.json`、`feedback.txt`、`api.json`。
本資料は人向けの事後分析で、診断役・生成役のプロンプトへ入力しない。
対象baselineは7課題、初回7＋修正13＝20候補。初回2/7、最終3/7、入力14,600＋出力6,413＝21,013 tokens、127.26秒。

## 20候補の遷移

候補0は初回、1〜3は修正。証拠パスは対象ディレクトリからの相対パス。

| 課題・候補 | 観測結果 / 分類 | 前候補から解消・追加・未変化の点 |
|---|---|---|
| c_parse / 0 | compile失敗: NULL未定義 | 必須ヘッダ不足。API契約の実行検証へ未到達 |
| c_parse / 1 | 実行assert失敗 / API契約 | stddef.h追加でcompile解消。NULL出力ポインタを成功扱いする契約違反が顕在化 |
| c_parse / 2 | 同じassert失敗 | 候補1とバイト単位で同一。問題未変化 |
| c_parse / 3 | 同じassert失敗 | 候補2と同一。問題未変化 |
| cpp_alias / 0 | PASS | 98,020ケース＋範囲境界・ASan/UBSan・debug modeを通過 |
| posix_write / 0 | compile失敗: SSIZE_MAX未定義 | limits.h不足。POSIX挙動の実行検証へ未到達 |
| posix_write / 1 | PASS | limits.hだけ追加。独立したwriteシナリオと実pipe/EPIPE検査を通過 |
| rust_prefix / 0 | PASS | i64参照比較と途中オーバーフロー検査を通過 |
| aarch64_sum / 0 | 参照結果assert失敗 / ゼロ要素境界 | コード上、n=0分岐がx3初期化より前。分岐先でx3を返す |
| aarch64_sum / 1 | 同じassert失敗 | uxtwとコメントを追加。n=0経路は未変化 |
| aarch64_sum / 2 | 同じassert失敗 | 候補1と同一 |
| aarch64_sum / 3 | 同じassert失敗 | 候補2と同一 |
| neon_sad / 0 | compile失敗: abs宣言なし | stdlib.h不足。境界条件の実行検証へ未到達 |
| neon_sad / 1 | SIGSEGV / 境界・範囲外アクセス | stdlib.h追加でcompile解消。n-16を使うループ条件は未変化 |
| neon_sad / 2 | SIGSEGV継続 | NULL判定追加。短い非空配列のループ条件は未変化 |
| neon_sad / 3 | SIGSEGV継続 | NULL判定を戻し、scalar tailのabsを三項演算へ変更。ベクトルループの条件は未変化 |
| neon_dot / 0 | compile失敗 / ISA intrinsic APIの型不整合 | vmull_p8へsigned vector、vcombine_s64へint32x2_tを渡す |
| neon_dot / 1 | 同じcompile失敗 | 候補0と同一 |
| neon_dot / 2 | 別のcompile失敗を追加 | vmull_p8を除去したが、8-lane値を16-lane向けreinterpretへ渡す新たな不整合。vcombine不整合は残る |
| neon_dot / 3 | compile失敗継続 | 4-lane結果を8-lane変数へ代入する不整合とunused variableを追加。vcombine不整合は残る |

集計はcompile失敗7候補、実行失敗10候補、PASS 3候補。13修正中5修正は直前のコードとバイト単位で同一だった。
各行の実測根拠は `<課題>/attempt-<番号>/verification.json`。変更根拠は同階層の候補ソース同士のdiff。
同一コードはSHA256比較でも確認した。検査が後の段階へ進んだことを、新たな不具合を修正が作った証拠とは扱わない。

## 継続失敗の分類と証拠の限界

### AArch64 sum

全候補で `cbz x1, 2f` が `mov x3, #0` より前にあり、ラベル2で `mov x0, x3` を実行する。
ゼロ要素経路でx3の値が設定されないことはコードから直接確認できる。独立検証の `got.sum==ref` assertも全候補で失敗した。
修正1のuxtw追加はこの経路を変えておらず、修正2・3は同一コードだった。
これはアセンブリの未設定レジスタと戻り値契約の問題として分類し、ISO Cの未初期化変数UBと同一視しない。
`.size` が本体より前に置かれる点も残るが、観測されたassert失敗の原因と断定しない。

### NEON SAD

compile可能な候補1〜3は全て、unsigned size_tの `i <= n - 16` を用いる。
0<n<16で減算がwrapすることと、そこから16-byteロードを許してしまう問題はコードから確認できる。
unsigned減算のwrap自体は未定義動作ではない。その後の配列外アクセスがCの安全性問題となる。
実行記録は保護ページを使う既存検証でSIGSEGV。今回のbaselineログにはfault PCの完全なトレースはないため、ログ単独が特定命令のfaultまで証明するとは主張しない。
NULLチェックやscalar tailの変更では、この短い非空配列のベクトル経路は修正されなかった。

### NEON dot

全4候補がcompile段階で停止している。したがって、実行時の算術一致・範囲外アクセス・性能はこのrunでは未検証。
compilerはsigned vectorとpolynomial intrinsicの引数型、lane数とvector型の不整合を具体的に報告している。
候補2・3では不適切な型操作を別の型操作に置き換えており、vcombine_s64の不整合も一貫して残る。
これはintrinsic APIの理解・型幅の誤りであり、生成済み命令のillegal-instruction発生を観測したものではない。

## フィードバックと未確定の仮説

compilerの具体的なエラー情報によって、C/POSIX/SADのヘッダ不足は解消した。
実行失敗に対して送信した情報は、既存filterの一般的な契約不一致または不正メモリアクセス分類に限定されていた。
モデル内部の思考過程は観測していない。「情報が粗いため根本原因を特定できなかった」「別コンテキストなら改善する」は、現時点では仮説である。
Phase B/Cでは同じ公開入力だけを使った独立診断を追加し、その仮説を小規模に比較する。
本資料の具体的な原因、assert、参照結果は、その診断入力へ混ぜない。
