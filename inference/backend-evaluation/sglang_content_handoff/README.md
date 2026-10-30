# SGLang内容確認: 人間ホストCPU-only probe

準備状態: CPU fake14件PASS、独立レビューの具体的指摘なし。今回こちらでは実container・Docker・package/source import・GPU・推論を行っていない。固定imageの取得済み報告は親から受領した証拠であり、このprobeの実行済み結果ではない。

rootが `<PROJECT_ROOT>/inference/backend-evaluation/sglang_content_handoff/` へ配置してCPUテストを終えた後、人間ホストの通常TTYから1回だけ実行する。

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/sglang_content_handoff/inspect_sglang_content_host.py --inspect-human
```

フラグ無しはPREPARED表示だけ。sourceせず、対話端末へset -eを貼らない。親shellを終了する操作はない。任意image/URL/source/module path/model/socket/command入力は作らない。固定sibling host_trialの既存HOST_CONTEXT/nonrootTTY guardを使う。profileは現用 `<PROJECT_ROOT>/agents/local_llm/.runtime/router-host-profile.json` を維持する。

## 対象と範囲

対象は取得済み公式image `rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230` だけ。最初にRepoDigest/ID/linux/amd64をread-only inspectし、imageに匿名volume宣言があればCPU起動前に拒否する。imageのLabelsとSizeもreceiptへ記録する。新しいpull/buildは行わない。

CPU一時containerは256MiB（swap0）/CPU1/PIDs64/tmpfs16MiB/read-only/nonroot/privateIPC/networknone/cap_dropALL/no-new-privilegesを固定し、GPUdeviceやモデル/hostvolumeを渡さない。image由来HEALTHCHECKを `--no-healthcheck` で止め、entrypointは固定python3。モデルサーバやimageの通常startup commandは起動しない。

Pythonは `-I -S -B` を使い、site/.pthやimage作業directoryからのmodule読込を避ける。標準ライブラリimportlib.metadataで固定site-packagesと既存checkoutのdistribution metadataを読む。torch・sglang・triton・AITER等のpackageはimportしない。

取得する版情報はtorch、sglang、triton（pytorch-triton-rocmも記録）、compressed-tensors、transformers、safetensors、AITER。見つからないmetadataは未確認のままとし、推定値を埋めない。direct_urlは公開fixedrepo一致のboolと40桁commitだけを記録し、private URL/credentialを出さない。

## 選択ソースの一致範囲

source_probe_manifest.jsonは公式SGLang commit `baa9befa381511cd4d56f83980951e5a45fffc6d` の以下4本だけを固定する。公開GitHubからtextを読み、返却Git blob SHA1を再計算して一致させてからSHA256/bytesを生成した。GPU/softwareを取得・実行したものではない。

| 対象 | bytes |
|---|---:|
| compressed_tensors.py: HIP/量子化dispatch | 58,497 |
| compressed_tensors_wNa16_moe.py: WNA16 expert | 27,584 |
| qwen3_next.py: Next model entry | 46,686 |
| triton_gdn_fused_proj.py: GDN projection kernel | 23,624 |

既存editable checkout `/sgl-workspace/sglang/python` と固定site-packages候補だけを読む。全candidateが固定SHA/bytesと一致する時だけ `SELECTED_SOURCE_MATCHED_NOT_RUNTIME_PASS` とする。missing/差分は `SOURCE_DIFFERENCE_REQUIRES_REVIEW`。返却boolだけを信用せず、ホスト側でも4本の固定path/expectedhash/size/各candidate実値を照合する。

**全commit一致、全GDN backend/kernel一致、loader/JIT/GPU動作、Next実推論、license全体の内容確認とは区別する。** GDNはprojectionの選択ファイルだけ。package metadataの版が読めても実importやkernel利用の成功ではない。

## 結果と中断

結果はGit除外先 `<PROJECT_ROOT>/agents/local_llm/.runtime/backend-runtime/sglang-content-inspection/run-<UUID>/receipt.json`（owner0600）へ保存する。CPUrun前にintentを保存し、stdoutにも非秘密の結果と正確なowned container名を表示する。inspect上限15秒、CPU probe30秒。追加試行は自動で行わない。

timeout/SIGTERM/KeyboardInterruptでは直接Docker CLIのkill/waitを試すが、それはcontainer終了の証拠にはならない。`UNKNOWN_CPU_INSPECTION_NO_RETRY` とowned nameを返すので、同じ名前のCPU-only containerを正規経路で確認してから次を判断する。成功時は通常exitとDocker `--rm` による回収を要求する構成だが、このscriptは別途container inspectによる消滅監査までは行わない。UNKNOWNで盲目再実行しない。

30B unload/load、共通LLM lock、既存router/MCP/service設定には触れない。CPU metadata確認のみでGPU試験は依然未実施。

## CPU fake検証

```text
python3 -B -m unittest discover -s <PREP_DIR>/sglang-content-handoff -p 'test_*.py' -q
```

14件、実subprocess/Docker/ネットワーク/GPUを呼ばない。固定limits/nohealthcheck/-I-S、source一致/missing、private URL非表示、結果偽装拒否、guard、Popen中断reapを含む。公開source URLはmanifestへ記録している。
