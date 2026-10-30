# 更新済み実測と有限GPU試験

取得済みNext全20ファイルのhost SHA照合と、実vLLM image identity/依存版/主要7ソースSHA一致を確認済み。installed full git commitは報告されていないため、7経路の同等性として記録する。新規download/installは不要。実GPUは未実施。

現用実装は`host_api_trial.py`。固定profile、context4096/output64/temperature0/seed42/POST1、whole900/start90/gen90/cleanup45/restore120。private IPC、healthcheck無効、nonroot/read-only/capdropALL/nnp、container32GiB・swap0、既存internal networkのみ。開始前にGPUdevice metadata/RWとimage/network/全20hash/coordinator idleをまとめて確認し、model-start直前に同operator SHA一回分の排他intentを予約する。起動・Docker RPC・生成を監視し、所有CID terminal/removed確認後だけ30Bを復帰。UNKNOWN再送/保護緩和なし。

以下の古いsource調査は比較基準として保存。そこにある「未取得/実image未確認」は当時の状態であり、上記更新と実receiptを優先する。正確な実行承認案は`VLLM_GPU_APPROVAL.md`参照。

# 同じNext重みをvLLMで再利用する限定確認

判定: **固定ソース上の対応経路あり / 実機未検証**。

対象はSGLang用に選んだ同じ `cyankiwi/Qwen3-Coder-Next-AWQ-4bit@c92cabfad08cadb011dc169cabb3e6da621b0719` だけ。推論用20ファイル44.9626GiBを両runtimeへread-onlyで渡せばよく、vLLM専用の重み再取得・GGUF pluginは不要。重みの実bytes/hashは未取得のため未検証。

確認したvLLM source: **`5df63a7203cdb9328d824a27b682e77c7b9928be`**。親が示した既存 `0.32.0+rocm723` の候補に対応させるが、この子ではそのimage/wheelの実ビルド内容・依存版を確認していない。version表示だけでcommitやgfx1151 kernel一致を証明しない。

## Loaderとkernelの追跡

1. `compressed_tensors.py` は通常Linearでignoreに一致した場合 `UnquantizedLinearMethod` を使い、routed expertsは `CompressedTensorsMoEMethod.get_moe_method` へ渡す。選択checkpointの非MoE397名称をBF16保持する設定をそのまま使う。
2. `compressed_tensors_moe/compressed_tensors_moe.py` のWNA16 pack-quantized分岐から `CompressedTensorsWNA16MoEMethod` へ進む。HIPのFlyDSL特別分岐はgfx950かつ明示FlyDSLだけ。gfx1151向けにはそれを選ばない。
3. WNA16 methodはINT4/group32のQuantKeyを作り、oracleが明示 `--moe-backend triton` を `TritonWNA16Experts` へ解決する。
4. そのclassはCUDA-like（ROCmを含む）を許容し、`kInt4Static32`、SiLUとBF16入力を受ける。重みはuint8 viewへrepackし、Triton W4A16 kernelで計算する。モデルの512 expertsは当該classのpadded experts<1024制限内。hidden2048/intermediate512はgroup32で割り切れる。これはソース上の条件照合であり数値精度や安定性の実測ではない。

`awq`というrepository名から `--quantization awq` へ強制しない。checkpoint内の`compressed-tensors`設定をauto-detectする。MarlinはCUDA、`rdna3` kernelはgfx1100専用なので選ばない。emulationやBF16全展開へのfallbackも今回のprofileには含めない。

## 次の有限smoke用設定（未実行）

固定HTTP server argvは `vllm-reuse-plan.json`。要点は:

```text
--load-format safetensors --safetensors-load-strategy lazy
--dtype bfloat16 --tensor-parallel-size 1
--moe-backend triton --attention-backend TRITON_ATTN
--gdn-prefill-backend triton --enforce-eager
--max-model-len 4096 --max-num-seqs 1
--max-num-batched-tokens 512 --gpu-memory-utilization 0.80
```

環境変数:

```text
VLLM_ROCM_USE_AITER=0
VLLM_GDN_DECODE_KERNEL=triton
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
VLLM_NO_USAGE_STATS=1
VLLM_DO_NOT_TRACK=1
VLLM_PLUGINS=
```

固定版のGDN prefillはROCmでTriton/FLAを選べる。decodeもTritonを指定してCUDA fused-kernel選択を避ける。AITERのCDNA/FlyDSLを使わない。通常attentionのbackendは旧 `VLLM_ATTENTION_BACKEND` envではなく、固定版に登録されたCLI `--attention-backend TRITON_ATTN` で指定する。

native実行ならhost127.0.0.1。今回の人間配備containerは内部listen0.0.0.0でhost publishをせず、既存internal networkのIDとowned container/EndpointID/IPを確認したtemporary APIだけを使う。詳細はHOST_TRIAL.md。CodexからDocker/追加namespace/権限昇格は実行しない。

## Runtime依存と資源条件

固定sourceの依存は **compressed-tensors==0.17.0**, transformers>=5.16.1,<5.20.0, safetensors>=0.6.2。SGLang gfx1151 recipeのcompressed-tensors0.15.0とはruntime環境を分離するが、重みファイルは共有できる。Triton/FLAはvLLM内の経路を使う。GGUF plugin、AutoAWQ、GPTQModel、FlyDSLの新規導入はこのprofileに必要ない。

ROCm7.2.3に対応した既存torch/Tritonとgfx1151向けvLLM native ops（MoE align/reduce・activation・GDN周辺を含む）が既存runtimeに実在するかは別確認。小さいB1の成功やsource branchだけではこのcheckpointのnative ops/JITが全て動く証明にならない。必要パッケージが既存imageに無い場合は導入不足として停止し、その場でpip installしない。

lazy loadで全ファイルCPU eager展開を避ける。重み44.93GiBに加えKV/state/一時repack/JIT資源が必要で、GPU58GiB・開始MemAvailable24GiB/継続16GiB・swap増加なしを守る。memory utilization0.80はプロセス全体のhard capではなく、container memory32GiB/swap0も指定する。両立は実機未検証。30Bと同時loadしない。

起動時には内部profiling/dummy forwardがあり得るため、API生成要求数と内部初期化を区別して記録する。実生成は親の共通runnerが1回だけ担当し、SGLangとGPU直列にする。起動90秒/生成90秒/全体900秒・再送0は維持し、実起動前の承認と人間配備が必要。今回の実起動/生成/取得/インストールは0回。

## 固定一次ソース

- [CT loader](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/quantization/compressed_tensors/compressed_tensors.py)
- [MoE dispatch](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/quantization/compressed_tensors/compressed_tensors_moe/compressed_tensors_moe.py) / [WNA16 method](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/quantization/compressed_tensors/compressed_tensors_moe/compressed_tensors_moe_wna16.py)
- [WNA16 oracle](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/fused_moe/oracle/int_wna16.py) / [Triton expert](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/fused_moe/experts/triton_moe.py)
- [GDN](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py) / [引数](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/vllm/engine/arg_utils.py) / [依存](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/requirements/common.txt)
