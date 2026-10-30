# 次の個別承認案

## A: 共用Next重みの取得だけ

- 作者/モデル: cyankiwi/Qwen3-Coder-Next-AWQ-4bit（base Qwen/Qwen3-Coder-Next、第三者量子化）。
- 正規取得元: https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/tree/c92cabfad08cadb011dc169cabb3e6da621b0719
- revision: `c92cabfad08cadb011dc169cabb3e6da621b0719`。
- 宣言ライセンス: Apache-2.0。
- 対象: pinned manifestの20ファイル、48,278,252,061 bytes（44.962626GiB）。全20SHA256確認。weight shardsのみ48,245,164,128 bytes。
- 新規保存先: `<PROJECT_ROOT>/models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c`。Git収録なし、既存モデル上書きなし。開始時に必要bytes+2GiBの空きを要求。
- 操作: 人間ホストTTYから固定downloaderを1回。公開Hub/CDNのallowlistのみ、新credential/token/課金なし。取得中は共通LLM lock、30B unload/GPU推論なし。全体7200秒、retry0、失敗/UNKNOWNは証拠を残して停止。
- 事前準備: rootが現用coordinator runtimeの相対パスを確定し、新規owner0600のprivate operator JSONとliteral SHA256をレビューする。runtime未確認はfalse/nullのまま。正確な一コマンドは[ACQUISITION.md](ACQUISITION.md)に記載。

## B: 取得後のbackend単発実機試験（Aとは分離）

vLLMかSGLangを一つずつ選ぶ。固定sourceに合う**人間review済みlocal imageのimmutable digestとimageID、実dependency版**が必要。vLLM既存imageはattestation未完、SGLangの初回human buildは未完・image容量unknown。これらを勝手に取得/buildする処理は含まない。

承認対象は、30Bを一時unloadし、既存internalネットワーク内で所有identityを照合した短命コンテナのprivate IP:30000へ固定ACKを1POSTし、所有コンテナの停止・終了・削除を確認してから30Bへ復帰する有限試験。internal同一network内の他コンテナからtemporary APIへ到達し得る。外部公開、新network、新credential、永続サービス、任意command/URL/モデル指定はない。

nonroot、read-only rootfs/model、tmpfs2GiB、memory32GiB/swap0、CPU8/PIDs512、標準seccomp/private IPC/cap_drop ALL/no-new-privilegesを維持。RAM開始24GiB/継続16GiB/GPU58GiB/swap増加0、context4096/最大64出力tokens、起動90秒/生成90秒/全体900秒、生成1回/再送0。UNKNOWNまたは回収未確認は30B再loadを止めるため、人間による確認が残る場合がある。32GiB等の上限を失敗時に自動緩和しない。

## 現在の完成範囲

fixed downloader/API runnerとCPU fakeテスト、静的plan、承認record templateを準備。独立review後38件PASS。Docker/GPU/weight取得/推論はすべて0。実機対応・起動時間・32GiB内のロード・品質は未検証で、実行READYや能力PASSとはしていない。
