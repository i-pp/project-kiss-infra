# Strata／Flash：実RAMに基づく成立性の再調査

結論：旧開始条件は **INFEASIBLE_START_GATE**。固定ソースの既定arena／明示mmapの
どちらも **UNKNOWN_PEAK_NOT_EXECUTION_READY**。安全な上限が証明できなかったため、
host runnerは作成せず、起動・取得・推論を進めない。

## 先の誤りと、測定領域の区別

128GiBという搭載情報をOS予算と混同して64GiB空きを要求したのが誤り。
読み取り済みOS MemTotalは61.427551GiB、17:45:58 UTCのMemAvailableは48.196194GiB。
64GiBの開始条件は30Bをunloadしても達成不能であり、引き下げて実行していない。
48GiB RSS案はhard capではなく、16GiB余裕と両立する最大値の証明にもならない。

一方、追加の読み取りでAMD sysfsはVRAM総量68,719,476,736bytes（64GiB）、
GTT総量32,978,665,472bytes（約30.714GiB）を報告した。VRAM使用は約22.48GB、
GTT使用は約0.137GB。これらはOS MemTotal・RSS・cgroupと異なる指標である。
搭載UMA総量の別々の独立追加容量とは扱わず、同時に、GPU割当をすべてOSの61.43GiBへ
足して不適合とする推定もしない。予約領域・GTT・host pinの課金関係は未確定。

既存routerのmemory.maxは32GiB、memory.swap.maxは0であり、変更していない。
そのcgroupの約11.42GiBの大半はfile cache（約11.50GB）で、anonは約0.68GBだった。
file cacheの多くはMemAvailableへ既に織り込まれるため、「30Bを降ろせばcgroup分の
11GiBがそのままMemAvailableへ加算される」とも計算できない。未unloadなので増分は未測定。

## 固定ソースから確定した下限

ソースcommitは `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`。
下表は選んだcontext8192、expert-cache1024、FP16 KV、MTPなしの**部分下限**。
peak上限・実機収容性・binaryの一致を保証しない。

|領域|下限／契約|計算根拠|
|---|---:|---|
|pack expert変換の同時live配列|2,595,225,600B＝2.416992GiB以上|1層のgate/up/down backing675MiB、interleave450MiB、blobs675MiB、tobytes675MiBがwrite時点で共存|
|既定host expert arena|33,973,862,400B＝31.640625GiB|48層×512×1,382,400Bの全量copy|
|GPU expert cache|1,415,577,600B＝1.318359GiB|1024 slots×1,382,400B。arenaの代わりではない|
|GPU GDN recurrent state|117,669,888B＝0.109589GiB|36×(128×48×128＋10240×3)×4|
|GPU FP16 K/V payload|201,326,592B＝0.1875GiB以上|12層×8192cells×2heads×256dim×K/V×2B。page等は別|
|上記3 GPU部分の合計|1,734,574,080B＝1.615448GiB以上|dense／native／prefill等を含まない|

hostとGPUの列を足してOS RSS下限にしない。全UMA内の割当関係も未確定。
OS MemTotalから16GiB余裕を引いた**絶対上限**は45.427551GiBであり、他アプリを
引く前の値である。既定host arena31.640625GiBがこれより小さいことは、単独の
算術的余地を示すだけで、実行可能の証明ではない。現在のMemAvailable48.196GiBを
使えばarenaと16GiB余裕を除いた余地は約0.556GiBに過ぎず、30B unload効果も未測定。

## pack・mmap・streamingを確認できた範囲

- `pack_layer.py`は**1層ずつ**expert roleをreadして配列化し、binへ書く。全33.97GBの
  出力をPython配列で一括保持する経路ではない。ただし次層への変数生存、NumPy一時配列、
  allocator残存とdense変換・verifyは別で、2.417GiBを最大RAMと主張しない。
- `strata_pack.py`のdense変換／verifyはtensor単位にraw、codes、scales、浮動小数配列等を
  構築する。source/outputのmmap、dirty page cacheもある。最大tensorと各中間の生存を
  含む保守的peak上限は未確定で、上流の「~40GB pack／2–5分」はRAM上限ではない。
- `generate.cpp`既定は`ArenaExpertSource`で全expert copy。
  **`--mmap-experts`を明示すると**`FileExpertSource`へ分岐し、canonical packの
  experts.binをread-only `MAP_SHARED`するLinux実装を確認した。仮想mapは31.640625GiB。
  OS page cacheを使い、別の匿名full arenaを作る既定経路からは離れるが、実residentが0に
  なるわけではない。page faultや全expertに触れるprefillの性能・resident peakは未測定。
- native packでexperts.binがない場合にGGUF spanを読む分岐もある。しかし今回のcanonical
  Q2_0 packを、その未生成のnative packへ勝手に置換して「pack不要」とは扱わない。
  `STRATA_ARENA_MMAP`は別のpadding/生成を伴う分岐なので、同じものとも扱わない。
- PLEはdefault direct。自動RAM化はtable＋expert arena＋8GiB余裕でadmissionする。
  明示`--ple-io direct`はこの自動化に優先することをソース確認済み。shard2約28.8GBを
  常駐コピーしない候補にできるが、row cache等は追加である。
- GPU dense poolは生成indexとnative skip一覧から計算してcudaMallocする。未生成index、
  native tensor割当、prefill/staging、HIP library/allocator、GTT/host pinまでの総上限は未確定。
  先の設定例にはexpert profileがないため、prefill cache borrowingも当然あるとは扱えない。
- `--memory-limit-mib`はアプリのavailable-memory/admission等へ伝える値であり、OSの
  cgroup hard capを作成する操作ではない。これで48GiB上限を実装したことにはならない。

よってmmap＋明示PLE directは**根拠のある調査候補**だが、安全な最小構成の成立とは
判定しない。任意に余裕や既存capを緩める、他アプリを停止する、host権限へ迂回する、
試験実行で不足を埋めることはしない。ソフト実行の個別承認も引き続き未取得。

## 既存重みでの代替を限定確認

- SGLang固定0.5.22はAMD GGUFが非対応で、HIP分岐に対応GGUF kernel importもない。
  既存のNext Q4_K_M、Flash Q2_0、120B MXFP4 GGUFで直ちに試せる経路は得られない。
- vLLM本体の固定文書はGGUFをOOT pluginへ移した。公式pluginをcommit
  `e454affe0ca23c9dc8754ec3033270cb30622ed5`で限定確認すると、Q4_K系のopsとgeneric
  MoE/transformers adapterは存在する。ただし既存image内pluginの有無・対応version、
  Nextのtensor mapping／split GGUF／HIP kernelの一致は未確認。Flash Q2_0や120B MXFP4も
  確認したdispatchから対応を証明できず、「vLLM一般モデル対応」をGGUF対応としない。
  **既存Next Q4_K_Mを追加重みなしで使う案は条件付候補に留まり、実行READYではない。**
- 既存1.5B BF16は過去vLLM B1成功証拠があるが、再実行して本命の証明には数えない。
  必要なplugin/runtime inventoryを現Docker権限拒否の迂回で取得しない。
- 追加safetensors取得案は実施しない。120Bの固定公式重み下限60.768GiBは58GiB GPU上限を
  超え、OS側に全常駐させても16GiB余裕を確保できない。CPU/GPU分割は別途対応検証が必要。
  Next／Flash BF16全常駐はそれぞれ148.414／335.276GiBの重みだけで非現実的。

## 成果と停止点

`resource_review.py`は部分下限・達成不能条件・unknownを分けるオフライン計算だけ。
6 testsで「64GiB条件拒否」「mmap＝zero RSSとしない」「下限fitだけで起動許可しない」等を
確認した。外部ソースはテキストとして読むだけでimport/executeしていない。

旧カードとmemory補足は上書きしていない。旧`first_trial`の64GiB条件はこの判定で無効。
安全な収容性が成立しなかったためhost runnerは未作成。次段階は、実行レビューに加えて
生成pack/indexと固定binaryの割当対応を得てhost/GPUそれぞれの保守的peakを確立すること。
それを今の「binary取得・実行禁止」の範囲で満たせず、今回は **UNKNOWN/BLOCKED**で終了。
生成・切替・Docker・新namespace・制限／service変更・binary/重みDL・commit/pushは0。

## 一次資料

- [pack layer](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/pack_layer.py#L59)
- [dense pack/verify](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/tools/strata_pack.py#L109)
- [mmap/default分岐](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/program/generate.cpp#L6455)
- [Linux mmap実装](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/core/expert_source.cpp#L1491)
- [PLE policy](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/program/generate.cpp#L4659)
- [GPU session](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/core/session.cpp#L45)、[KV](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/core/layer.cpp#L774)
- [GPU dense pool](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/program/generate.cpp#L4448)
- [vLLM固定GGUF文書](https://github.com/vllm-project/vllm/blob/5df63a7203cdb9328d824a27b682e77c7b9928be/docs/features/quantization/gguf.md)
- [固定plugin](https://github.com/vllm-project/vllm-gguf-plugin/tree/e454affe0ca23c9dc8754ec3033270cb30622ed5)
- [SGLang固定GGUF実装](https://github.com/sgl-project/sglang/blob/v0.5.22/python/sglang/srt/layers/quantization/gguf.py)
