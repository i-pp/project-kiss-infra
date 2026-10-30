# ユーザーへ提示する承認内容（未実施）

## Strata：固定software取得と、人間hostでの段階試験

- **対象**：Niko1221/Strata v0.2.7 source commit `5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d`。
  source URL: https://github.com/Niko1221/Strata/tree/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d
- **実行binary**：engine0.1.52、Linux x86_64 HIP-halo/gfx1151、entrypoint `strata`。
  URL: https://github.com/Niko1221/Strata/releases/download/v0.2.7/strata-engine-0.1.52-linux-x86_64-hip-halo.tar.gz
  SHA256: `8e95a086515face5ce3a4d34d9ac3c485e45be5ff84a614e5b4ed66fc5efe18a`。
  archive169,966,238bytes。署名済feedの展開容量は730,955,483bytes（実展開は未実施）。
  build ID `a42cc3d7df70+rocm`、build source `a42cc3d7df70d1940de82cd0882f03e1f5dfc741`。
  選択sourceとはcommitが違うが、pack/tokenizer/frontend/engine等主要12fileのGit blob一致を確認。
- **出所検証**：公開feedのEd25519を固定sourceの公開鍵で検証済み。取得後も固定manifest SHA、署名、全fileを既存OpenSSLで照合する。
  これは安全性や実行承認の証明ではない。Strataは未認知sourceとして個別取得・実行承認が必要。
- **license**：Strata sourceはMIT。bundled HIP等の個別noticeはarchive未取得なので未読で、確認前に実行しない。
  使用する既存Flash派生GGUFはApache-2.0表示、元FlashはQwen Community License1.0。商用外部提供の承認には含めない。
- **追加取得**：上記engine、固定Strata/llama.cpp source archive各64MiB以内、最小wheel6件18,547,900bytes。
  llama.cpp sourceは `3cf03257f219afbe7334045ff7c6a06ac68c627d`：
  https://github.com/ggml-org/llama.cpp/tree/3cf03257f219afbe7334045ff7c6a06ac68c627d
  圧縮payloadの計画上限322,731,866bytes。重み追加DL0、既存Flash2shardを再利用。
  新しいPython3.14専用venvだけに固定wheelをoffline installし、global packagesや既存venvを変えない。
- **生成物・disk**：48層fullpack約40GBをCPU生成。pilotはexpert1層だがdense/embeddingは全量で、別の約6〜7GBが目安。
  原本・既存packは上書きせず、新規pilotとfullを別保存。追加disk予算80GiB、run成長70GiBで中止、pack開始時100GiB空きを要求。
  これはhard quotaではない。bootstrapの空き条件8GiB、engine/source展開上限4GiB/256MiB/512MiB。
- **RAM/GPU**：OS認識RAM61.43GiBとdriver VRAM64GiBを別指標として計測。開始MemAvailable24GiB以上、
  継続16GiB以下、VRAM58GiB超、swap増加、所有tree RSS32GiB超で中止。0.5秒soft監視。
  native StrataのRSSはsoft停止値で、既存routerの32GiB hard capとは別。既存capは変えず、追加sandbox/cgroupも作らない。
- **試験**：新source import確認→1層pilot build/verify→別48層build/verify→index/tokenizer→
  `--mmap-experts --ple-io direct --expert-cache 1024 --max-context 8192 --prefill 512`、MTP/vision off。
  正規template/明示EOSで最大1生成・128tokens、temperature0/seed42、再送・warmup0。
- **時間・30B**：取得/venv準備中は30Bを止めない。試験時のみ30Bモデルをunloadし、全体40分枠。
  native起動90秒/生成90秒、所有停止45秒、30B復帰120秒を予約。元container/router/daemon/Tunnelは保持。
  停止/復帰未確認はUNKNOWNで中止。GPU hang等で40分以内の復帰を保証するものではない。
- **保存先（新規、Git除外）**：software=`<PROJECT_ROOT>/.cache/backend-evaluation/strata-v027-e0152`、
  pack/log=`<PROJECT_ROOT>/agents/local_llm/.runtime/backend-trials/<RUN_ID>`。

承認後の人間による最初の1コマンド（sourceせず、通常の非rootホスト端末で）：

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/acquire_strata_host.py --acquire-human-approved --output <PROJECT_ROOT>/.cache/backend-evaluation/strata-v027-e0152
```

これは取得・照合・専用venv準備まで。engineは起動しない。noticeと署名report確認後、こちらでprivate review recordを準備し、別の明示run commandを渡す。

## Next：両backendで共有する重みの取得

- **モデル/公開者**：`cyankiwi/Qwen3-Coder-Next-AWQ-4bit`、量子化公開者cyankiwi、元モデルQwen/Qwen3-Coder-Next。
  Qwen公式の配布そのものではなく**第三者量子化**。
- **固定revision**：`c92cabfad08cadb011dc169cabb3e6da621b0719`。
  一覧: https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/tree/c92cabfad08cadb011dc169cabb3e6da621b0719
  各file URL: `https://huggingface.co/cyankiwi/Qwen3-Coder-Next-AWQ-4bit/resolve/c92cabfad08cadb011dc169cabb3e6da621b0719/<FIXED_MANIFEST_FILENAME>`。
- **全取得容量**：推論に必要な固定20file合計48,278,252,061bytes（44.96GiB）、うち重み48,245,164,128bytes。
  manifestに全file名/byte数/SHA256を固定。両backendはこの1セットをread-only共有し、二重取得しない。
- **license**：元/派生の固定モデルカードはApache-2.0表示。カードが参照するLICENSE本文URLは404で、本文をそこで取得できたとは主張しない。
- **形式**：routed MoEのみsymmetric INT4/group32 compressed-tensors、通常層BF16。
  vLLM/SGLangの固定sourceにHIP Triton経路があるが、実機成功はまだない。
- **取得処理**：新規固定dirへ20fileだけ、公開HTTPS/認証なし、全SHA照合、既存file上書き・resume・自動retryなし。
  空きは取得量＋2GiB、全体7200秒上限。取得だけではGPU/モデルunloadはしない。
- **保存先（新規、Git除外）**：`<PROJECT_ROOT>/models/backend-next-int4/cyankiwi-Qwen3-Coder-Next-AWQ-4bit-c92cabfad08c`。
- **runtime/GPUは別の条件**：既存vLLM B1imageのsource/依存照合をCPU-onlyで先行。
  SGLang gfx1151完成imageとその容量は未確定。依存版もvLLM compressed-tensors0.17.0とSGLang0.15.0に分ける。
  weight取得承認を、未知の大量runtime取得・新image build・GPU実行の包括承認と扱わない。

承認後こちらでowner0600の新規private JSON（取得reviewだけtrue、runtimeはfalse/nullのまま）とliteral SHAを作り、
`next_shared/acquire_next_host.py --acquire-human-approved --operator-json <PRIVATE_JSON> --operator-sha256 <LITERAL_SHA256>`
の人間用1行を渡す。未承認の今は実値recordを登録しない。

## 認証・ホスト設定・検証と復旧

新APIキー・既存キー変更・権限/group追加・sudo/newgrp・OS trust store・system packages・ROCm/driver/BIOS・
systemd/自動起動・MCP catalog・外部公開は変更しない。新規localファイル、専用venv、承認後の短命containerのみ。
native Strataは通常ユーザー権限で動くため、soft監視は追加sandboxや完全なアクセス封鎖の代わりではない。

既報54 testsは全てfixture/fakeか通常のCPU子processで、実engine/GPU/Docker/backend HTTPではない。
追加9件（公開署名3、復旧読取2、signed entrypoint1、coordinator status2、root拒否1）を加えStrata63件。
API/downloaderの独立reviewとCPU fake試験は別途記録する。ACK成功も一般的なcoding品質PASSとは扱わない。

復旧失敗時は同じrunを再実行せず、summary/run ID/UNKNOWNを保持。
`inspect_trial_recovery.py --run-id <RUN_ID>`でsaved ownership/cleanup・router状態をread-only確認する。
所有停止未確認なら30Bを再loadせず、対象PID/CID・状態・RAM/GPUを照合してから具体的復旧操作を判断。
UNKNOWN削除、無関係process kill、未知service再起動はしない。自動復旧が保証できない場合は対象/理由を報告する。
