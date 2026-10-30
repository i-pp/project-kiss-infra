# 固定Next取得の初回準備（未実行）

公開元は第三者量子化作者[cyankiwi](https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit)、baseはQwen/Qwen3-Coder-Next。revisionは`c92cabfad08cadb011dc169cabb3e6da621b0719`、宣言ライセンスはApache-2.0。公式Qwen配布の量子化とは区別する。[固定config](https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/blob/c92cabfad08cadb011dc169cabb3e6da621b0719/config.json)と[candidate.json](candidate.json)の20ファイルだけを対象とする。

取得量は48,278,252,061 bytes（44.962626GiB）、うち10重みshardは48,245,164,128 bytes。固定保存先は`<PROJECT_ROOT>/models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c`。別に最低2GiBの空きを要求する。runtime image/build cacheの容量は含まれず、SGLang完成image容量は未確認。

## 初回のprivate recordを準備する担当者向け

取得承認とrootによるrepo配置・CPUテストが終わってから行う。現時点で人間へ実行依頼する完成コマンドではない。

1. 配置後の`operator-private.template.json`を読み、`project_root`を既存projectの絶対パス、`model_dir`を上記固定保存先にする。`coordinator_runtime_relative`は既存router-host-profileが指すorchestratorの**現在のcontrol socketを持つruntimeへの相対パス**を、稼働daemonの承認済み設定から照合して記入する。過去のruntime名やdirectoryの存在だけで推定しない。この値は今回まだ未確認なので、rootが最終コマンド提示前に確定する。
2. 取得だけを承認する初回は`review.fixed_weight_acquisition_reviewed`だけtrueにする。他の三つのreview、各runtimeの`source_dependency_match_reviewed`と`bootstrap_complete_reviewed`はfalse、image_ref/image_idはnullのままにする。未確認dependencyのplaceholderも取得段階では残せる。source_commitはtemplateの固定値を維持する。これで取得だけを許可し、Docker試験は拒否される。
3. 記入内容をレビュー後、既存のGit除外private `.runtime`内の**新規**`next-shared-operator.json`へowner0600で保存する。通常の`>`リダイレクトや既存ファイルの上書きは使わず、Pythonの`os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)`等で新規作成する。親directoryと全祖先にsymlinkがないこと、current ownerであることを照合する。既存recordがあれば別の明示的なレビュー対象名を使い、上書きしない。この文書は未reviewの新helperを追加しない。
4. `sha256sum <PRIVATE_JSON>`で最終保存bytesのSHA256を取得し、レビュー記録に固定する。後でJSONを編集したら旧承認digestは無効。実行コマンドへは**確認した64桁のliteral SHA256**を渡し、`$(sha256sum ...)`等で実行直前の変更を自動承認しない。

model保存先の親directoryがまだ無くても、人間guardと空き容量確認を通ったdownloader自身が固定親と新規対象を作る。手動mkdirや汎用path指定を追加する必要はない。既存の保存先・partial・intentを見つけた場合は拒否し、自動再送しない。

## 人間端末の最小コマンド

上記準備後、担当者が実パスとliteral digestを埋めて渡す1コマンドだけを、通常の人間ホストTTYで子プロセスとして実行する。source、対話端末への`set -e`貼付、Codexによる代行は行わない。

```text
python3 -B <PROJECT_ROOT>/agents/local_llm/integration/next_shared/acquire_next_host.py --acquire-human-approved --operator-json <PROJECT_ROOT>/agents/local_llm/.runtime/next-shared-operator.json --operator-sha256 <REVIEWED_LITERAL_SHA256>
```

これは標準Pythonの固定downloaderで、hf CLIの導入やloginは不要。全20ファイルのSHA256/bytesを照合し、retry0/全体7200秒/一要求chainずつ、共通LLM lockとidle確認の下で取得する。30BのunloadやGPU実行はしない。中断・失敗時は`acquisition.json`と残存intent/partialを保存し、同じコマンドを再実行しない。結果を照合して次の対応を決める。

## 取得後に残るruntime準備

vLLMは既存imageが固定source`5df63a7203cdb9328d824a27b682e77c7b9928be`と実dependencyに一致するかの人間attestationが必要。SGLangは固定source`baa9befa381511cd4d56f83980951e5a45fffc6d`のgfx1151公式recipeを人間がレビュー・buildする工程そのものが未完了で、完成image digest/展開容量はunknown。base digestを完成image digestとして流用しない。

runtimeごとにimageID/digestと実dependency版を照合し、新しいレビュー済みprivate recordへ記録してから別の有限試験承認を行う。重み取得成功だけでGPU実行READYとしない。API試験は[HOST_TRIAL.md](HOST_TRIAL.md)の固定owned internal IPを使い、localhost publish、新network、任意IP、Compose手動二重起動は行わない。起動90秒/生成90秒/全体900秒/1生成/再送0、回収後30B復帰という既存上限を維持する。

補足: 本実行はrepoの `inference/backend-evaluation/next_shared/` 配置のみ対応し、operator project_rootをそのrepoへ固定する。別repoのPython helperを選択できない。取得中は共通LLM lockを解放済みで、試験本体だけ全期間lockを保持する。
