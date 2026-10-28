# GNU assembler診断フィルター：修正案と最小比較計画

> 本書は承認前の計画を保存した履歴文書。承認後の実験と再検証は完了し、
> [確定結果](feedback-filter-assembler-results.md)に記録した。以下の「未実施」「承認待ち」は計画作成時点の状態を示す。

2026-10-28 JST。**この段階ではモデル要求・モデル起動・候補コードの再コンパイル/実行を行っていない。**
今回実施したのはB2結果のcommit/push、フィルターの作業ツリー修正、offline unit/replay、次の実験計画。
フィルター修正案・テスト・この計画は未commit/未pushのレビュー対象である。

## B2結果の確定

推論基盤PASS・コード品質FAILを記録したB2の新規8ファイルとREADME追記6行のみをcommitした。

- commit `570960cc5bcf650e33c2abdd561598ad2b11136f`
- message `feat: add gpt-oss MXFP4 runtime and repair validation`
- 9ファイル、967行追加。承認済みB2レビューのSHA-256と全ファイル一致、秘密情報/モデル/ログ/生成物の混入を再検査。
- 既存SSH鍵で署名し、メモリ上のallowed-signersで検証PASS。鍵・恒久署名設定は変更していない。
- 旧remoteが親commitと一致することを確認し通常push。HEAD、origin/main、remote/mainは同じSHA。
- push直後の作業ツリーはclean。その後のdirty状態は以下のフィルター案と計画だけである。
- commit証跡：`logs/git-gpt-oss-b2/20261027T174017006072Z/`。

## 修正案

対象は`evaluation/coder/repair/feedback.py`と`test_feedback.py`だけ。
既存7課題、fixture、参照実装、runner/sandbox、判定基準、各推論Compose・実行設定は変更しない。

1. `fatal error/error/warning/note`の**severity部分だけ**をscoped `(?i:...)`にする。
   regex全体へIGNORECASEを適用せず、Linuxファイル名・`/candidate/`の位置照合をcase-sensitiveに維持する。
2. 任意の候補basenameを引数として照合し、regex文字をescapeする。モデル名・課題ID・特定のISAエラーを分岐条件にしない。
3. `/candidate/`は位置prefixだけを除去。候補以外のファイル、source excerpt、include stack、fixtureの診断は返さない。
4. 本文に`/`・`\`・C0/DEL制御文字がある診断は、部分redactではなく行ごと非開示とする。
   これは保守的な保護であり、演算子`/`を含む正常な診断も落とし得る。必要な情報が欠ける場合でも合格を偽らない。
5. Rustの位置なしerror headerもseverityのcaseを許容する。ただし直後の`-->`が**同じ候補の位置**と一致する場合だけ返す。
   別ファイルや位置を確認できないheaderは返さない。これは従来より厳しい転送条件であり、Rust対応そのものは維持する。
6. `compile_candidate`限定、最大16診断・4000文字、runtime/linker情報の分類化は維持する。

ここでの保護は「候補だけのコンパイル」という入力境界と位置のallowlistを前提とする。
任意の本文から秘密文字列の意味を判別する仕組みではなく、独立テストの生出力や不明なログを入力として転送してよいという意味ではない。
今回、既存ログの保存内容や過去のモデル入力は書き換えない。

## offline検証結果

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/coder/repair -p test_feedback.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/coder/diagnostic -p test_diagnosis.py -v
```

- フィルター14テストPASS（既存3＋追加11）。GNU形式の列番号なしError、大小文字、位置case、regex文字、本文path/control、Rust位置、16件/4000文字等。
- 診断分離側7テストPASS。fixture/runtime/linker/assert/期待値を渡さない既存境界を確認した。
- 証跡：`logs/feedback-filter/20261027T174731340070Z/`。
- commit `570960c`の旧policy SHA-256：`3095a85afa6a17fcc8180487ba20344ec580778d79c0a7a2bedf28470c27b659`。
- 作業ツリーの新policy SHA-256：`20078138eef5712aa352debb627eb922c52d2309f8857110890a119e8e390436`。

B2失敗66候補の保存済みverificationを旧/新filterへ入力した。**モデル・compiler・独立runnerは実行していない。**
18件だけで出力が変化し、全てAArch64 sumの候補位置付き`Error:`が追加された。他48件は同一。
このB2データでは、本文path保護/Rust位置厳格化による別の差は生じていない。
`offline-replay.json`に全比較、旧/新feedbackとdiff、次のseedのhashを保存した。
これは診断抽出の修正確認であり、モデル修正成功率の改善を示す結果ではない。

## 承認後の最小実験（未実施）

対象は**AArch64 sumだけ**。同じ失敗候補からの**1回の修正**を旧/新で比較する。
モデルの初回新規生成、他6課題、診断分離方式、追加モデル、設定変更は含めない。

### 固定するseedと環境

- seed：`logs/gpt-oss-b2/20261027T164036147397Z/execution-20261027T165336700287Z/ctx-32768/aarch64_sum/attempt-0/`。
- 候補source SHA-256 `9f072622fcc2b4cabf3b406f8c5952548ff9006b3f7638e242cd556134ae9ebf`。
- 旧verification SHA-256 `459f0fcfcb166495773e26436465f492ef1683a5b49370851c9fbbd4a69ee54d`。
- 次回開始時に元ログを変更せずhashを確認し、固定verifierで候補のcompile FAILを1回再確認する。
  既存fixture・runner・sandbox・image IDもhashで固定する。policyは独立した旧/新hashとして記録する。
- 推論は既存B2のgpt-oss-20b MXFP4、image/model hash・**現在の保存済み32K設定**を維持する。
  `GPT_OSS_CONTEXT`のデフォルト8Kでcompose upして再構成しない。
- 現在B2は停止中。モデル実験承認後にのみ、同じcontainerの保存済み設定を検証してstartする案。
  CID/Config/HostConfigが変われば停止し再確認する。B1は停止を維持し、旧30Bは停止/再起動しない。
- 既存B2はlocalhost8082・parallel1・fit off・ngl99・batch256/ubatch128・F16 KV・Flash Attention on・reasoning low。
- 要求はtemperature0、seed42、max_tokens2048（reasoning含む）、cache_prompt=false、stream=false。

### ペア比較と予算

1. 旧A/新Bの**2ペア**を実施し、実行順をペア1はA→B、ペア2はB→Aとする。
2. 各armは新しい会話で、同じ公開仕様・同じseed最終コード・旧または新のfiltered compiler情報だけを与える。
   過去の会話、事前分析、手作業の原因説明・正解・参照コード・独立テストを加えない。
3. **1修正/arm、合計最大4 API要求**。後続の多段修正はこの最小比較には含めない（従来の最大3修正上限も増やさない）。
4. seedに対する旧/新feedback差分を事前確認し、追加情報が候補自身のseverity-case診断だけであることを確認する。
   不明な内部情報や差分があれば送信せず停止する。今回のseedでは新filterが既存compilerのError行を1行追加する。
5. strictな単一コードブロックを最終contentから抽出し、既存の同一独立runnerでcompile/link/ISA/実行検査する。
   analysisからコードを救済せず、失敗を合格に変更しない。

### 記録と採点

- 各要求の公開仕様/候補/filtered feedback/payload hash、model/engine/設定、順序、usage、時間を保存。
- 修正前後のコード・diff、compiler診断、元のErrorが解消/継続/新規errorへ遷移したかを記録。
- **コンパイル成功**と**独立テスト最終合格**は別指標。assemblyが通っても境界/ABI/結果検査で落ちればFAIL。
- 旧/新各2候補の初回修正後合否・token数・時間と、GPU/RAM、旧30B/B1の状態を比較する。
- 課題1件・2ペアの探索的比較であり、既知の同一payload出力差もあるため因果効果や一般的な精度向上を断定しない。
  過去B2の旧結果だけを新結果と比べる方式は使わない。
- 新規ログは`logs/feedback-filter-experiment/<UTC-run>/`。元のB2ログとbaselineを書き換えない。

### 安全・終了条件

- 事前に旧30B healthy、B1/B2停止、GPU空き/利用可能RAM各24 GiB以上を確認。
- GPU58 GiB超/available16 GiB未満の継続、available8 GiB未満、OOM/reset、既存30Bの異常でB2だけ停止。
- 全体10分・API180秒・候補sandbox120秒/step30秒などの上限を設ける。未完のペアを効果改善として集計しない。
- 候補sandboxは既存network none/GPUなし/nonroot/RO/RAM2 GiB/PID128/出力量制限を維持。
- B2のstart/stop以外の既存runtime設定、ホスト、driver、GPU割当は変更せず、同時高負荷試験はしない。
- 成否にかかわらず承認した実験で起動したB2のみ停止し、旧30B/B1/B2の保存済み設定・fixtureを照合する。

**現段階ではこの実験を開始しない。修正差分と計画のレビューを待つ。**
