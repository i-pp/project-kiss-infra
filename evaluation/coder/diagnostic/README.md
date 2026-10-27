# Repair Loop v2 — 診断分離方式

入口は `scripts/repair-coder-diagnostic.py`。既存 `scripts/repair-coder.py` を変更せず、そのAPI呼出し・固定情報・隔離実行・診断フィルター・ハッシュ検査を再利用する。
`diagnosis.py` はモデル向けの入力生成とJSON検査だけ、`assessment.py` は独立検証後の差分・結果評価だけを担当する。
フレームワークや追加パッケージは使用しない。

## 比較方法

- baselineは保存済み `logs/repair/20261027T084214958944Z/`。再実行・上書きしない。
- diagnosticは同じ初回候補7件から開始し、全件を既存テストで再検証する。合否が再現しなければ新しい推論を開始せず停止する。
- モデル、32Kコンテキスト、生成時のtemperature 0 / seed 42 / max_tokens 2048 / cache_prompt false、独立テスト、検証イメージ、最大修正3回は同じ。
- 不合格で修正余地がある場合にだけ診断を1回呼び、その方針を生成役に渡す。合格したら修正を止める。
- 診断は同じモデルの新しい2メッセージ会話。temperature 0 / seed 42 / max_tokens 1024 / cache_prompt false。生成役の会話履歴は診断へ渡さない。
- 診断のJSONが不正、出力が打切り、環境条件・ハッシュ・サーバー状態が変化した場合は実験を止め、未完了のまま記録する。手修正や非記録の再試行は行わない。

## 入力と判定の境界

診断役の入力は `public_specification`、`candidate_code`、`filtered_verification_feedback` の3項目だけ。
具体的な既知原因・正解をsystem promptに埋め込まない。Phase A分析、非公開テスト、参照実装、assert、期待値、生の実行ログは入力しない。
コンパイラ情報と実行失敗分類には既存 `feedback.py` と同じフィルターを適用する。

診断は `hypotheses` と `repair_plan` のJSONで、候補の修正コードを書かせない。コードの置換は生成役の応答からのみ行う。
診断仮説は未検証として生成役へ渡し、独立テストの合否を診断役の自己申告で置き換えない。
モデルが引用した `code_evidence` が入力コードに実在しない場合も、その事実を事後評価に残す。

## 各修正の構造化記録

`logs/repair-v2/<UTC run-id>/<課題>/attempt-1`〜`attempt-3` に以下を保存する。

| ファイル | 内容 |
|---|---|
| `diagnosis-api.json` | 診断へ実際に送った全入力、生応答、usage、API時間 |
| `diagnosis.json` | 原因仮説・候補コードの引用・確信度・修正方針 |
| `generator-api.json` | 修正依頼、生成コード、生応答、usage、API時間 |
| 候補ソース | 生成役のコードブロックをそのまま抽出 |
| `sandbox.json` | 既存の隔離設定・時間/RAM/PID/出力量制限と終了状態 |
| `verification.json` | 独立テストの実測結果・コンパイラ/サニタイザ等の生診断。モデルへは送信しない |
| `post-assessment.json` | コード差分、ハッシュ、消えた/追加/残存compiler error、検証段階の遷移、各仮説の証拠存在と独立判定 |
| `revision.json` | 仮説→方針→実変更→独立結果→事後評価と、役割別トークン・時間をまとめた記録 |

事後評価は通常のプログラム処理で、独立テスト結果とソース差分を比較する。事後評価用のモデル呼出しはない。
候補全体のPASSと各仮説の真偽は区別する。複数変更がある場合、PASSだけで全ての原因仮説が個別に正しいとは証明しない。
コード不変、引用不存在、compileだけ改善して実行は不合格、といった状態も明示する。

`attempt-0` は保存済み初回候補の再検証であり、新規の生成APIを呼ばない。元の応答への参照と再検証結果を `replay.json` に残す。
全体の `manifest.json` / `report.json` にbaseline全ログのハッシュ、既存実装・テスト・新規実装のハッシュ、サーバー設定とStartedAtの照合結果を残す。
`baseline-transitions.json` は元の20候補を差分とともに整理した人向けの資料で、モデル入力ではない。

## コストの扱い

- `actual_api_usage`: 今回実際に呼んだ診断＋修正生成の入力/出力/総トークン。
- `diagnosis_usage` / `diagnosis_seconds`: 診断役だけの追加コスト。
- `reused_initial_api_usage`: baseline初回生成7件の履歴上の使用量。今回の新規消費ではない。
- `normalized_api_usage`: 実消費＋再利用初回生成分。元baselineの初回を含む総量との比較用。
- `actual_wall_seconds`: 初回候補の再検証、診断・修正・独立検証等の実測時間。
- `normalized_wall_seconds`: 実測時間＋再利用した初回生成API時間。初回の旧検証時間を二重加算しない。

baselineは過去の測定であり、同時実験ではない。初回候補を揃えても、時刻・熱状態・キャッシュ等の時間要因を完全には統制していない。
7課題1回だけの結果を一般化しない。合格は固定した独立テストの範囲での確認。

## 再現手順

既存baseline、モデル、推論サーバー、隔離プローブ・control検証のPASS記録が必要。サーバーを再設定/再起動するコマンドは含めない。

```sh
python3 -m unittest discover -s evaluation/coder/diagnostic -p test_diagnosis.py
python3 -m unittest discover -s evaluation/coder/repair -p test_feedback.py
python3 scripts/repair-coder-diagnostic.py
```

新規ログディレクトリを毎回作り、既存ログは上書きしない。元baselineのサーバーfingerprintやテストが一致しない場合は停止するため、その条件を変更して強制続行しない。
実装を再実行する際も、各課題で修正回数は最大3回。生成コードの実行は既存の通信なし・GPUなし・ホスト書込みなしの隔離コンテナに限定する。
