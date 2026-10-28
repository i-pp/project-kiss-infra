# GNU assembler feedbackフィルター：比較結果の確定

2026-10-28 JST。**診断抽出改善はPASS、コード修正成功率改善は未確認**。
既存の[承認前計画](feedback-filter-assembler-plan.md)に従った1課題・2ペアの比較であり、一般的な精度改善は主張しない。
今回の確定作業ではモデル推論・取得・起動、NEON拡張、ホスト設定変更を行っていない。

## 評価器の識別と保護範囲

変更は`evaluation/coder/repair/feedback.py`、同`test_feedback.py`と本結果・計画文書のみ。
独立テスト、fixture、参照実装、7課題、合否判定、runner/sandbox、30B/B1/B2の実行設定は変更していない。
ここで更新したのはモデルへ返す診断の抽出器であり、独立検証の採点基準ではない。

|版|取得方法|feedback.py SHA-256|
|---|---|---|
|旧|commit `570960cc5bcf650e33c2abdd561598ad2b11136f`の同ファイル|`3095a85afa6a17fcc8180487ba20344ec580778d79c0a7a2bedf28470c27b659`|
|新|本結果文書と同じコミットの同ファイル|`20078138eef5712aa352debb627eb922c52d2309f8857110890a119e8e390436`|

独立verifier imageは引き続き`sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c`。
旧評価結果は旧版の履歴として保持し、修正版で過去の合否やモデル入力を再ラベル・上書きしない。

保護条件をコードとテストで再確認した。

- 大小文字を無視するのはseverityのみ。候補basenameと`/candidate/`はcase-sensitiveな完全一致、regex文字はescapeする。
- 候補単体のcompile診断だけを抽出し、候補以外のパス、ソース抜粋、fixture、参照値を転送しない。
- 診断本文にパス区切り・C0/DEL制御文字があれば行を非開示にする。Rustの位置なしerrorも直後に同じ候補の位置が必要。
- runtime/linkerの生出力は従来どおり分類情報だけにする。診断本文は最大16件・合計4,000文字を維持する（定型の前後文は別）。
- モデル・課題別の分岐は追加していない。

任意の文字列の機密性を意味的に判定するフィルターではない。候補だけのcompileと位置allowlistが入力境界である。
保守的な本文検査により、演算子`/`を含む正当な診断も落とす可能性は残る。

## オフライン再検証

確定前に以下を再実行し、**26件すべてPASS**。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/coder/repair -p test_feedback.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evaluation/coder/diagnostic -p test_diagnosis.py -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-gpt-oss-b2-unit.py -v
```

内訳はfeedback 14件、診断分離7件、B2 offline safety/解析5件。
保存済みB2の失敗66候補を旧・新へ再入力し、前回保存された出力と全件一致した。
18件だけで候補のGNU assembler `Error:`行が追加され、他48件は同一。合否やコードは変更していない。
再検証証跡はGit除外の`logs/git-feedback-filter/20261028T025132854737Z/`に新規保存した。

旧版は`git show 570960cc5bcf650e33c2abdd561598ad2b11136f:evaluation/coder/repair/feedback.py`から取得できる。
ローカルに保存済みログがある場合、以下で旧・新の66件をモデルやcompilerを使わず比較できる。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import importlib.util, json, subprocess
from pathlib import Path
legacy = {}
source = subprocess.check_output(['git', 'show',
    '570960cc5bcf650e33c2abdd561598ad2b11136f:evaluation/coder/repair/feedback.py'])
exec(compile(source, 'feedback-before.py', 'exec'), legacy)
spec = importlib.util.spec_from_file_location('new', 'evaluation/coder/repair/feedback.py')
new = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new)
tasks = {t['id']: t for t in json.loads(Path('evaluation/coder/tasks.json').read_text())}
archive = Path('logs/gpt-oss-b2/20261027T164036147397Z')
total = changed = 0
for path in sorted(archive.glob('execution-*/ctx-*/*/*/verification.json')):
    verdict = json.loads(path.read_text())
    if verdict.get('status') != 'FAIL':
        continue
    filename = tasks[path.parent.parent.name]['file']
    total += 1
    changed += legacy['feedback'](verdict, filename) != new.feedback(verdict, filename)
assert (total, changed) == (66, 18), (total, changed)
print('PASS: 66 candidates, 18 changed, 48 unchanged')
PY
```

## 承認済み最小実験の結果（再推論なしで確定）

実験は2026-10-28 JSTに実施済み。ログは`logs/feedback-filter-experiment/20261027T175855762083Z/`。
保存済み32Kの同一失敗候補から、旧→新／新→旧の順、各1修正、計4生成要求だけを行った。
gpt-oss-20b MXFP4、reasoning low、temperature 0、seed 42、max_tokens 2048、cache_prompt=falseを固定。
同じpolicyのwire入力は完全一致し、policy間もfeedback以外のpayload・Harmony入力は一致した。
全応答cache_n=0。手作業の原因説明、正解、参照コード、非公開テストはモデル入力へ追加していない。

|順序|条件|実際の変更|assembler|独立実行テスト|候補最終判定|API秒|総token|
|---|---|---|---|---|---|---:|---:|
|1|ペア1 旧|`.p2align 2`追加、問題命令そのまま|FAIL|SKIP|FAIL|17.354|1,615|
|2|ペア1 新|問題命令に`lsl #0`追加|FAIL|SKIP|FAIL|6.587|906|
|3|ペア2 新|同じLSL形式へ変更、コメント差|FAIL|SKIP|FAIL|6.794|922|
|4|ペア2 旧|`.align 2`追加、問題命令そのまま|FAIL|SKIP|FAIL|19.520|1,760|

1. **診断転送**：新は2/2で候補の`Error:`行がwire入力・Harmony入力に含まれた。旧は2/2で欠落を再現。抽出改善PASS。
2. **assembler**：旧0/2、新0/2。旧は`missing extend operator at operand 3`が継続し、新は`LSL operator not allowed at operand 3`へ遷移した。
3. **独立実行テスト**：全4件compile_candidate失敗で未到達のSKIP。未実行を合格に数えず、候補は全てFAILとする。
4. **診断と変更の関係**：新は2/2で指摘オペランドを変更したが、誤ったLSL形式を選択。旧は整列指定のみ。コード差分とcompiler出力が根拠であり、モデルの自己申告で採点しない。
5. **同一条件の差**：旧は整列directive、新はコメントに差があった。新の問題命令は同じ。合否差・修正成功率改善は観測されなかった。

生成合計5,203 token（prompt 1,898 / completion 3,305）、controller実行53.912秒。
旧平均API18.437秒、新6.690秒だが生成量も異なり、一般的な速度改善は示さない。
GPU総使用量の観測最大32.787 GiB（既存30B込み）、Linux MemAvailable最小45.133 GiB。
約1秒間隔の観測値であり瞬間ピークは保証しない。1課題・2ペアだけでは一般化できず、ABI・境界・計算結果は未検証。

実験時の各入力、抽出診断、生成コード、差分、compiler/独立検証結果は各候補ディレクトリに保存済み。
`summary.json`は構造化結果、`protection.json`は保全照合、`memory.jsonl`は資源観測。
`report.json`のPASSはプロトコル完了を指し、コード品質の合格を意味しない。
実験終了時にB2停止・8082閉鎖、既存30B healthy・StartedAt/設定不変、B1停止・設定不変を確認した。
元ログはGit管理せずローカルに保持し、本確定作業でも上書きしない。
