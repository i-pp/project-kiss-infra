# SGLangで本命を1回推論するための次工程

結論: 最初の候補を **cyankiwi/Qwen3-Coder-Next-AWQ-4bit** の固定revisionに限定する。これは取得・配備前の候補選定であり、gfx1151での動作確認ではない。今回の起動・推論・重み/バイナリ取得・サービス変更はすべて0回。

## 選んだ重みと必要量

- 取得元: https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit
- revision: `c92cabfad08cadb011dc169cabb3e6da621b0719`
- 宣言ライセンス: Apache-2.0。配布元モデルカードと元Qwenのライセンス表記を保存する。これはQwen公式の量子化ではなく、cyankiwiによる変換である。
- 10 safetensors合計: **48,245,164,128 bytes (44.9318 GiB)**。
- 推論用の固定20ファイル合計: **48,278,252,061 bytes (44.9626 GiB)**。詳細と公開hashは `candidate.json`。
- 必要な追加ディスク量は最低でも上記合計。runtimeイメージ/ビルド中間物/キャッシュ/ログは別枠。二重コピーする方式なら重み分を2倍必要とする。実ディスク空き容量・runtime展開量は未測定なので、全配備の必要量が確定したとは扱わない。

公開メタデータAPIの `siblings[].size` とLFS SHA256、固定configを読んだ。重み本体もsafetensors headerも取得していない。取得対象はallowlistだけにし、リポジトリ付属のPythonプラグインやrecipe実行は不要。

このcheckpointはrouted MoEだけをsymmetric INT4/group32/pack-quantizedにし、48層のattention・linear-attention・router・shared expertとlm_headをBF16で保持する。固定configのignore397件と各層の名前を確認した。SGLangの通常Linear WNA16はCUDA Marlinへ進む一方、HIPのMoE WNA16にはTriton経路があるため、この区別が選定理由になる。`--quantization awq`へ強制変換せず、元のcompressed-tensors設定を使う。

## 他候補を先行しない理由

| 対象 | 今回確認した候補 | 判定 |
|---|---|---|
| Next | 上記cyankiwi INT4 MoE/BF16非MoE | 固定版HIP MoE経路へ対応付け可能。実機未検証だが最初の1候補に選ぶ |
| Next | qtum AWQ / Intel AutoRound | 前者はdense INT4/ignoreの整合確認が残り、後者はGPTQ packingのHIP経路が未確立。軽さだけで採用しない |
| gpt-oss-120b | openai公式MXFP4 safetensors | rootの15 shardだけで65,248,893,184 bytes (60.7678 GiB)、GPU58GiBを重みだけで超える。original/の別形式も重複取得しない。既存MXFP4のSGLang AMD説明はCDNA向けで、gfx1151の根拠にならない |
| Flash-Next | nvidia NVFP4参照export | root11 shardで132,680,249,378 bytes (123.5681 GiB)、licenseはNVIDIA Open Model License。GPU58GiBに収まらず、N-gram表を退避しても公式説明のresident部分約78GiBが超過。既存Q2 GGUFをこの形式の代用にはできない |

120B参照revision: `b5c939de8f754692c1647ca79fbf85e8c1e70f8a`。Flash参照revision: `fc694b54fb0174e0913e6adf86691ef85a4ead47`。これらは今回取得しない。

## 固定runtimeと残る依存

SGLang `v0.5.22`のannotated tagが指す実commitは **`baa9befa381511cd4d56f83980951e5a45fffc6d`**。その後、公式gfx1151完成imageを発見した。[固定digest・圧縮容量・未確認事項](SGLANG_RUNTIME_FINDINGS.md)を参照。まず公式imageの個別取得承認とsource/実依存照合を候補とし、以下の固定Dockerfile build案は代替案として保持する。

- base: `rocm/pytorch@sha256:7fe531fa185af260352fe7fbb3fa64ad749abe72adf0600a648c4692801b125a`（ROCm7.2.4/PyTorch2.9.1）。
- compressed-tensors0.15.0、AITER commit `c16d44b93a528b2a4bfd6d8d3409116d465872a9`。AITERのCDNA AOT kernelsは使用しない。
- 公式recipeのgfx1151 kernel patchとTriton経路を使い、`SGLANG_USE_AITER=0`。
- recipe内のRust取得・apt/pip依存は新規ソフト取得に当たる。自前buildのtransitive依存全体のlockと完成イメージdigest/サイズは未確定。公式公開imageには固定digestと圧縮容量があるが、展開容量とsource完全一致は未確認。完成imageのdigestと展開量を配備receiptへ記録するまで実行可とはしない。
- 公式例の`seccomp=unconfined`、`ipc=host`、public bindは採用しない。draftは標準seccomp、cap_drop ALL、no-new-privileges、専用IPC、read-only rootfs/tmpfs2GiB、nonroot、memory32GiB/swap0、CPU8/PIDs512。既存internal networkの確認済owned IPだけを使い、host portを公開しない。これで起動可能かは未検証であり、失敗時に保護を緩めない。

現在のCodex境界にGPUデバイスがなくruntimeも未確認。エージェントからDocker/newgrp/sudoやホストbrokerを使って迂回しない。初回build/配備は人間が通常ホスト端末で行い、Codexは出来上がった限定HTTP経路だけを使う。

## 次の確認を一度で判断するための操作案

1. 固定revisionの上記44.96GiBファイル一式の取得と保存場所、runtimeの新規取得・ビルド（容量は完成前に別測定）が必要。
2. 人間が固定runtimeへGPU2デバイスを渡す一時配備を行う。Docker socket、privileged、host IPC、seccomp無効化、外部公開、新credential、永続自動起動は含まない。`compose.draft.yaml`はレビュー用で、まだ実行しない。
3. activeジョブ0を確認し、既存管理経路でrouterの30Bを一時unload。既存container・設定・重みは保持する。単発後に同じ経路で30Bへ戻す。この間30B推論は使えない。unload/restoreを担当する共通runnerと人間の役割を配備前に固定する。
4. 起動90秒・生成90秒、1起動/生成要求1回/再送0、全体900秒（回収・30B復帰を含む）を上限とする。超過は環境FAILとして追加試行しない。JITが90秒を超える可能性は残る。

## 静的profileと最小E2E

`launch-plan.json`は固定checkpointをread-onlyで載せ、TP1/context4096/parallel1/最大64出力tokensで疎通だけを確かめる案。意味的な品質試験は含めない。startup warmupをskipし、HTTP生成を1要求だけにする。モデル内部の初回kernel compile等はその1要求内の処理として記録する。

GPU表示64GiBとOSの61.43GiBを独立した無制限メモリとは数えない。重み44.93GiBは58GiB以下だが、KV/GDN state、repack、runtime、loaderのCPU stagingが加わる。static fraction0.80は約51.2GiBの目安で**全プロセス使用量の保証上限ではない**。共通runnerが開始MemAvailable24GiB/継続16GiB、GPU58GiB、swap増加なしを監視し、container自体にmemory32GiB/swap0を指定する。全量CPU stagingはreserveを割り得る。10分割safetensorsの実image既定は並列loadであり、AITER修正版の試行は重みload中のhost swap増加で停止した。単一スレッドload案は未適用（SGLANG_LOADER_PRESSURE.md参照）。32GiB capとの実機両立も未検証。ホスト設定や閾値を緩めない。

人間配備後の順序は、immutable image/config/hashと対象endpointの照合→30B停止枠と回復経路確認→起動→read-only `/v1/models`（推論を起こすhealth_generateは使わない）→保存済み `request.json` を**1回だけ**送信→応答/finish_reason/timing/資源を回収→所有する一時runtimeだけ停止→router30Bを復帰→通常のread-only health/stateで確認。

リクエストがtimeout/UNKNOWNなら監査で実行有無を照合し、再送しない。成功は「Next INT4のAPI推論一往復が成立」の意味に限定し、既存Next GGUFの修正品質PASS/formatFAILやB1小モデルをSGLang本命品質の証拠に混ぜない。

## 一次ソース

- [重みmetadata](https://huggingface.co/api/models/cyankiwi/Qwen3-Coder-Next-AWQ-4bit?blobs=true) / [固定config](https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/blob/c92cabfad08cadb011dc169cabb3e6da621b0719/config.json)
- [固定HIP scheme選択](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/python/sglang/srt/layers/quantization/compressed_tensors/compressed_tensors.py) / [固定TritonMoE](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/python/sglang/srt/layers/quantization/compressed_tensors/schemes/compressed_tensors_wNa16_moe.py)
- [固定gfx1151 recipe](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/docker/rocm-gfx1151.Dockerfile)
- [公式量子化対応表](https://docs.sglang.io/docs/advanced_features/quantization) / [Flash資源説明](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-Flash-Next)
- [120B metadata](https://huggingface.co/api/models/openai/gpt-oss-120b?blobs=true) / [Flash metadata](https://huggingface.co/api/models/nvidia/Qwen3.8-Flash-Next-NVFP4?blobs=true)

## ローカルで今すぐ使える確認

`python3 -B inspect_plan.py` はmanifestの集計と手順の静的検査だけを行う。`python3 -B -m unittest -v test_inspect_plan.py` は誤ったrevision/量子化/リモートコード/宛先拡大の検出を試験する。ネットワークやSGLangをimportせず、サービス起動機能を持たない。
