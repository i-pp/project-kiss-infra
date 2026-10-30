# 親へ：実行前の具体的な承認・人間操作（まだ未実施）

現時点はコード準備・CPU fake試験まで。ここに挙げる取得／実行を既に承認されたとは扱わない。
Codex内からDocker、namespace追加、sudo/newgrp、host brokerで実行しない。

## A. Strata固定ソフトを取得し、条件を満たせば段階測定＋1生成

対象はNiko1221/Strata source commit `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d` と
engine0.1.52 Linux HIP-halo。archiveは169,966,238bytes、SHA256
`8e95a086515face5ce3a4d34d9ac3c485e45be5ff84a614e5b4ed66fc5efe18a`。
取得元は `https://github.com/Niko1221/Strata/releases/download/v0.2.7/strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz`。
署名済公開feedをEd25519検証済み。公開feed上の展開file容量は730,955,483bytes、
build IDは`a42cc3d7df70+rocm`、manifest SHA256は`abd7ecedc07f5dddc1d4f5bd5e5ac0f4912bf279cd6becef4306c5b5d7fad2fa`。
engine source commitは`a42cc3d7df70d1940de82cd0882f03e1f5dfc741`。選択Python sourceの
`5e8a4cca…`とはcommitが異なるが、pack/tokenizer/frontend/engine/geometry等主要12fileのGit blob一致を確認した。
実archiveのmanifestと同梱物は未取得で、全binary構成の再現確認をしたわけではない。

追加sourceはStrata固定commitと、upstreamが指定するggml-org/llama.cpp commit
`3cf03257f219afbe7334045ff7c6a06ac68c627d`（gguf-pyだけを実行時利用）。圧縮sourceは各64MiB上限、
展開source上限は256/512MiB。engine展開は4GiB上限。既存モデルの追加DLは0。
Python3.14用の最小依存wheel6件は合計 **18,547,900bytes**、SHA付きlockを同梱。
NumPy2.5.3/Jinja2 3.1.6/regex2026.9.10/PyYAML6.0.3/tqdm4.70.1/MarkupSafe3.0.3を
**新しい専用venvのみ**へoffline installし、system package/既存venvは更新しない。
ソフト取得の最大圧縮予算は約323MB、bootstrap開始空き8GiB。pipの依存自動取得/sdistは使わない。

出所の認知が未確定なStrataについては**取得・コード実行の個別承認が必要**。
project LICENSEはMIT、同梱HIP等のnoticeとsigned manifestの実内容は未取得のため未読。
取得後、人間が正式manifest/署名/notice/entrypointを確認して記録するまではengineを起動しない。
取得後は`publisher_verify.py`が既存OpenSSLで固定公開鍵のmanifest署名と全file hashを検証する。
新private key/credentialやOS trust設定は作らない。署名の真正性確認はソフトの安全性や人間の実行承認の代わりではない。
Flash派生カードのApache表示と元Qwen Community License1.0は区別し、商用提供の許可とは扱わない。

承認後の処理：人間の通常ホスト端末で取得→manifest/notice確認→private review record→
既存routerの30Bモデルのみ一時unload→新規1層pilot pack（denseは全層）とverify→別の新規48層packとverify→
mmap/direct PLEのraw engine→正規chat templateでACKを1生成→所有プロセス停止→30B load/health確認。
元30Bコンテナ・router・daemon/Tunnelは削除/停止しない。GPU推論は1本だけ。

新しい生成物用の追加ディスク予算80GiB（bootstrapとrunを合わせた計画値）、run成長70GiBで中止、
pack開始空き100GiB。開始MemAvailable24GiB、継続16GiB以下／VRAM使用58GiB超／swap増加／
所有tree RSS32GiB超で中止するsoft監視（0.5秒間隔）。GPU VRAMとOS RAMは別々に測定し、合算して空きを作らない。
旧「OS空き64GiB」「48GiB RSS」を使わず、既存router32GiB hard capも変更しない。

試験本体の全体枠40分、pilot build300s/verify180s、full build900s/verify300s、
index30s/tokenizer60s/encode30s/decode30s、native起動90s/生成90s、停止45s、30B復帰120s。取得・venv準備・notice確認中は30Bを停止しない。
原本SHAの再計算は今回の調査ではしていない。将来の標準pack buildが行うsource hashを固定期待値と照合する。
raw GEN最大1回/128tokens、warmup/再送0。完了不明はUNKNOWNとして照合し、保護を緩めて通さない。

監視はhard capや瞬間OOM防止の保証ではない。未観測の短命な孫プロセスやSIGKILLされたcontrollerからの
自動復帰も保証しない。所有停止未確認なら30Bとの競合を避けて復帰を保留し、UNKNOWNを残す。
この限定的な測定リスクと最大40分の30B停止枠を含めて判断してほしい。

保存先は`<PROJECT_ROOT>/.cache/backend-evaluation/strata-v027-e0152`（新規）。
packとrunログは`<PROJECT_ROOT>/agents/local_llm/.runtime/backend-trials/<RUN_ID>`（新規）。
どちらも既存Git除外に一致し、現在まだ作成していない。

## B. Next共用checkpointを1セット取得してvLLM/SGLangを順番に1生成ずつ

`cyankiwi/Qwen3-Coder-Next-AWQ-4bit`（Qwen公式checkpointの第三者量子化）、revision
`c92cabfad08cadb011dc169cabb3e6da621b0719`。推論用20file合計 **48,278,252,061bytes（44.96GiB）**。
公開者/量子化作者はHugging Face handle `cyankiwi`、元モデル作者はQwen。
取得元は`https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/resolve/c92cabfad08cadb011dc169cabb3e6da621b0719/<MANIFEST_FILENAME>`。
全file SHA256とApache-2.0表示を固定metadata・元/派生モデルカードで確認。
カード参照先のLICENSE本文URLは404だったので、条項本文を同URLから取得できたとは主張しない。重みは両backendへread-only共有し、2セット取得しない。
通常層はBF16、routed MoEだけsymmetric INT4/group32なので、両backendのHIP Triton MoE経路がある。

取得と、人間ホストでの固定runtime配備・各1回の推論/回収/30B復帰が必要。
vLLMは既存B1imageをまずCPUだけでinspectし再利用可否を判定。SGLangは固定0.5.22 gfx1151専用buildが必要。
vLLM compressed-tensors0.17.0 とSGLang0.15.0は混ぜない。runtime依存/source/image一致は別の確認条件。
実機のGDN/native kernelとロード時ピークは未確認で、重み取得だけを実行PASSと扱わない。
保存先は`<PROJECT_ROOT>/models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c`（新規、Git除外）。
取得上限は固定20fileの全48,278,252,061bytesのみ、空きはそれに2GiB以上、全体7200秒、
認証なしpublic HTTPS、warmup/生成なし、retry/resumeなし。partial/intentが残る失敗時は照合してから次工程を決める。

新runtime完成サイズが未確定なので、未知のimage大量取得・host ROCm変更を包括承認したとは扱わない。

初回CPU-only vLLM metadata checkは既存固定imageをpullせず、GPU device/ネットワーク/モデルmountなし、
256MiB上限の短命containerを人間ホストで1回だけ起動するもの。現用30Bのunloadは不要。
その結果からruntime再利用に必要な具体差分を確定する。

全操作は人間ホストで実行。新APIキー、外部公開、MCPのDocker/任意コマンド追加、security緩和、
systemd常駐、課金API、commit/pushは対象外。


## 63件のStrata準備検証と、復旧失敗時

以前報告した54件は、所有process/stdio/timeout/資源監視23、asset/coordinator18、
取得archive4、prompt/EOS5、CPU-onlyvLLMコマンド2、GGUFheader2のCPU fixture試験。
実Strata/実Docker/実backend HTTP/実GPUを動かしていない。
追加3件は公開feedの実署名と改ざん拒否、追加2件はread-only復旧証拠、追加1件はsigned entrypoint固定、
追加2件はcoordinator状態schema/identity、追加1件はroot実行拒否。合計63件。

通常失敗は所有停止を確認して30Bを120秒枠でload/health確認する。停止確認不能、
結果不明lifecycle、復旧失敗、controller終了時はUNKNOWNを保持し、次の生成/起動を再送しない。
復旧失敗時の人間手順:

1. 同じtrial/acquisitionを再実行せず、`summary.json`とprogressのrun IDを保存する。
2. `python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/inspect_trial_recovery.py --run-id <RUN_ID>`
   はsaved owned PID/starttime/cleanup、UNKNOWN印、既存router statusを読むだけで復帰や削除はしない。
3. 所有プロセスが残る/未証明なら、その対象だけを照合して停止する具体操作を用意する。
   他のモデルやアプリを広くkillせず、UNKNOWN markerを先に消さない。
4. GPU/RAM・全モデル状態・owned停止を確認し、結果不明操作の照合が済んだ後に、
   既存routerの30Bだけを復旧する。既存`model_selection.py prepare --profile qwen-coder-30b`も
   UNKNOWN印があれば拒否するため、これを迂回しない。自動解除や未知のservice restartは含めない。
5. router自体が壊れた場合の旧container切戻しは、このtrialの自動fallbackではない。
   preserved original ID/構成とGPU非競合を確認して、別の具体操作として判断する。
