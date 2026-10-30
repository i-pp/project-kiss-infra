# 本命モデルと別backend：検証済み準備単位のチェックポイント

この表はsource/asset/runtimeを分けた進行表であり、実機成功表ではない。
今回はbinary/重み取得、GPU起動、生成、モデル切替、Docker、service/security変更、commit/pushは0。
既存llama.cpp3モデルの実利用成果は保持する。

|backend|Coder Next|Flash-Next|gpt-oss-120B|
|---|---|---|---|
|vLLM|既存Q4_K_M GGUFのplugin/mapping/HIPは未実証。代わりに共有MoE-only INT4/BF16の固定checkpointでHIP Triton経路をsource確認。取得/runtime review/実機待ち|手元Q2_0 GGUFのplugin/kernel適合は未証明。新しい大型checkpointを先行取得しない|手元MXFP4 GGUFのplugin/kernel適合は未証明。native safetensorsは重み60.77GiBだけでGPU58GiB上限超、offload/kernel検証が必要|
|SGLang0.5.22|同じ共有INT4/BF16 checkpointが候補。通常LinearのCUDA専用Marlin経路を避け、routed MoEのみHIP Tritonへ。実機待ち|AMD GGUF非対応。参照NVFP4 recipeをgfx1151実証と扱わず、Nextを先行|AMD GGUF非対応。文書化native MXFP4はCDNA3/4で、gfx1151の実行経路は別検証が必要|
|Strata固定版|**固定sourceのfamily guard外**。実ファイルarch=qwen3next、対応familyに含まれないので無意味に起動しない|実ファイルarch=qwen4exp。固定GGUF再利用、段階pack/mmap/direct PLE/rawserve1GEN runnerを実装・54offline tests成功。個別software reviewと人間実行待ち|**固定sourceのfamily guard外**。実ファイルarch=gpt-oss、対応familyに含まれないので起動しない|

boundedGGUFheaderだけを読取り、Next/Flash/120Bのarchを確認した。tensor bodyは未読、fullSHA再計算なし。
Strata固定source `model_family.hpp` はqwen4expとqwen35moeを認識し、現3対象ではFlashだけが合う。
https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/include/strata/artifact/model_family.hpp

## 検証済み単位

`host_trial/`にStrataの固定資産取得準備、review記録、source/asset照合、shared lock、
段階pack/verify、mmapログ確認、正規template/tokenizer、EOS明示、GEN1回、監視/所有停止/30B復帰を実装。
54testsはfake coordinators/tokenizers/ordinary Python childrenによるもので、Strata/GPU/Dockerは実行していない。
UNKNOWN保全、未確認cleanupでの復帰禁止、Ctrl+C後の遅延POST防止を含む。

`next_shared/candidate.json`は推論用20file/48,278,252,061bytesの固定manifest。
cyankiwi/Qwen3-Coder-Next-AWQ-4bit @ c92cabfad08cadb011dc169cabb3e6da621b0719、Apache-2.0表示。
MoE INT4/group32、その他BF16。vLLM/SGLangそれぞれにsource対応経路があるが、依存は別に保つ。

## 次の具体操作と未完部分

1. `host_trial/APPROVAL_REQUEST.md`の固定Strata engine/source/deps取得・人間実行の個別承認。
   engine169,966,238bytes、Python3.14 wheel6件18,547,900bytes、追加main weight0。
   元カードの64GiB start gate/48GiB RSS案は使わず、soft RSS32GiB/開始RAM24/継続RAM16/GPU58、
   pack disk開始100GiB/成長70GiBで中止し、全体40分の有限試験と120秒の30B復帰枠。
2. 人間hostで既存固定B1imageのCPU-only metadata check。GPU/model/networkなし、pullなし。
3. 共用Next44.96GiBの新規取得承認。単一snapshotを両backendへread-only共有する。
4. 子 `/root/sglang_feasibility` が現在、共用downloaderと人間host API trialを実装中。
   これらはまだ実行readyとして配布しない。known internal-network port-publication failureを避け、
   所有CID/image/network/endpoint/IPを照合したtemporary internal APIでの1POSTに修正している。
   最新fake tests/routeガード確認後に次の単位として統合する。

既存モデル状態のMCP read-only確認は30Bのみloaded/READY、Nextと120Bはunloaded、
blocked_uncertain=false、swap使用0（確認callはprivate検証ログに保存）。この調査から生成/切替は送っていない。
