> このJIT-cache profileは専用の追加承認後のみ使用する。trial用途では`fixed_jit_cache_exec_reviewed=true`が必須で、旧operatorや既存の消費済みattemptは再利用しない。取得用途にはこのキーを要求しない。

# 共用Next取得・人間ホストAPI試験の引渡し

状態: 実装とCPU fake検証の準備。**現ホストでの実配備readyではない**。固定重みは未取得、SGLang完成image未配備、既存vLLM imageのsource/dependency attestation未取得。Docker/GPU/推論/大容量取得は今回0回。

## 固定取得

`acquire_next_host.py` は `--acquire-human-approved` がないと情報表示だけで終了する。実取得にはowner0600のoperator JSONとそのSHA256、通常人間ホストTTY、既存CoordinatorのHOST_CONTEXT guardが必要。共通LLM lockはactive0/現用30B確認の短いpreflight中だけ保持し、その後解放して取得する。推論・30B unloadはせず、長時間転送で30B生成を塞がない。

対象は固定repo/revisionの20ファイル、**48,278,252,061 bytesのみ**。全20SHA256をpinned manifestで照合する。小text9件のSHA256は公開raw metadataから計算し、Git blob SHA1とバイト数が固定APIの値に一致したものだけを採用した。大ファイル11件（10shardとindex）のSHA256はLFS metadata由来。candidate.json自体もコード内SHA256で固定する。

既存保存先、既存最終file、残存partial/intentは上書き・自動再送しない。転送前intentを保存し、失敗したdirectoryをそのまま証拠として残す。HTTPリダイレクト先は固定Hub/CDN allowlistだけ。任意repo/revision/URL/filename指定やcredential引継ぎはない。7200秒全体上限、1request-chain/file、retry0。今回この取得処理は呼んでいない。

## 人間ホスト単発試験

`host_api_trial.py --run-human-approved --backend vllm|sglang` は1backendだけを担当する。`host-trial-prep/host_strata_trial.py`（repo統合時は固定sibling `host_trial/host_strata_trial.py`）のCoordinator guard/locked/idle/unload/restoreをreuseする。二つとも存在、またはどちらも無い配置は拒否する。Strata重みやengineは不要。共通policyをrequestに付加し、context4096、最大64tokens、固定ACKを1POSTだけ送る。backendを選び直して自動継続する機能はない。

既知のinternal-network localhost publish障害を再試行しない。**既存 `project-kiss-large-coder-b3_local` のinternal=trueとIDをprivate router-host-profileに照合し、そのnetworkに作った短命owned containerの内部IP・port30000だけを試す**。name/CID/imageID/owner-label/token/networkID/EndpointID/subnet/IP/peerを照合したrouteをprivate trial内にだけ保持し、各HTTP前に再確認する。任意IP/URL入力、redirect、host port publish、新network作成はない。既存router receipt/MCP/サービスは変更しない。同じinternal networkの他コンテナからAPIへ到達し得る性質は残る。

人間実行のDocker create/start/stop/kill/rmだけを固定CLIで行う。containerはnonroot（当該人間UID/GID）、memory32GiB・memory+swap32GiB（container swap0）、CPU8・PIDs512・init、cap_drop ALL/no-new-privileges、標準seccomp/専用IPC、固定GPU2device、モデルとrootfs read-only。書込は一般`/tmp`（上限2GiB、rw/noexec/nosuid/nodev）と固定`/jit-cache`（上限512MiB、rw/exec/nosuid/nodev、mode0700・当該UID/GID）の2つのtmpfsに限定する。`TRITON_CACHE_DIR=/jit-cache/triton`とし、実行可能なJIT共有objectは専用cacheだけに置く。合計tmpfs最大2.5GiBもcontainer全体32GiB制限の内側であり、追加RAMではない。匿名volumeをimageが宣言していれば起動前に拒否する。必要なGPU groupは、その人間sessionが既に所属するGPU device groupだけを渡す。group新規付与、sudo/newgrp、Docker socket mount、privileged/unconfinedはない。

開始RAM24GiB/継続16GiB/GPU58GiB/swap増加0を監視。起動90秒/生成90秒/全体900秒、cleanup45秒と30B復帰120秒を予約。32GiB capや90秒JIT制限で失敗しても自動で緩めない。

Dockerクライアントtimeoutを停止成功とは扱わない。所有権が一致するCIDだけstop→必要ならkill→inspectのRunning=false/PID0/terminal state→owned CID rm→再discoverで不存在を確認して回収完了とする。UNKNOWN createの現時点の不存在だけでは成功にしない。owner/image/token不一致や残存、endpoint変化、結果不明POSTはUNKNOWN/no-retryで共通uncertain markerへ記録。回収未確認なら30Bの再loadも止め、競合を作らない。

通常成功・品質FAIL・既知失敗は回収後に同じ共通lock内で30Bを復帰する。再帰的Runtime.prepareは使わない。元30B/container/原本を削除せず、復帰処理は既存router HTTP管理経路で行う。APIのACK成功は環境疎通だけで、品質一般PASSにしない。

## 必要な個別承認・記録

1. 固定44.96GiBの新規取得と保存先。runtime未完成でも取得だけの承認は分離できる。
2. 既存vLLMまたは人間build済SGLangのimageID/digest、固定source/dependency一致を人間が確認して記録。新runtimeの取得/buildはこのscriptに含めない。
3. **既存internal同一network内の所有IPを使うtemporary API**、GPU deviceを渡す人間ホスト配備、現用30Bの一時unload→1生成→復帰の停止枠。外部公開・新認証・永続自動起動はない。

`operator-private.template.json` は全承認false、image未設定の記入例。実パス/実imageを記録したowner0600のファイルをGit除外先で人間が作り、そのSHA256をコマンド引数へ固定する。未確認事項をtrueにしない。現在このoperator記録は存在せず、本適用はpending。初回作成は[ACQUISITION.md](ACQUISITION.md)の手順で行う。取得だけならruntimeの未確認項目はfalse/nullのままでよく、runtimeが完成したことにはならない。

人間への起動形は以下。`set -e`を対話端末へ貼らず、sourceもしない。

```text
python3 -B <PREP_DIR>/acquire_next_host.py --acquire-human-approved --operator-json <PRIVATE_JSON> --operator-sha256 <REVIEWED_SHA256>
python3 -B <PREP_DIR>/host_api_trial.py --run-human-approved --backend vllm --operator-json <PRIVATE_JSON> --operator-sha256 <REVIEWED_SHA256>
```

SGLangを行う場合は1回目が確定・回収・30B復帰してから別の承認済み有限実行として `--backend sglang` を使う。UNKNOWNなら実行しない。rootによる配置・レビュー・guard依存パス統合とoperator receiptが終わるまで、上の実行を依頼しない。

検証は `python3 -B -m unittest -v test_host_api_trial.py test_inspect_plan.py`。testsのdriver/probe/HTTP/coordinatorはすべてCPU fakeで、Docker/network/GPUに触れない。

補足: 本実行はrepoの `inference/backend-evaluation/next_shared/` 配置のみ対応し、operator project_rootをそのrepoへ固定する。別repoのPython helperを選択できない。取得中は共通LLM lockを解放済みで、試験本体だけ全期間lockを保持する。

## 現在の実行準備更新

取得済みNext・実vLLM image/versions/7criticalsource一致を再利用する。vLLM GPU stageは新しい具体的開始承認待ち。新規DL/host設定変更は無い。初期preflightは一つの実行内に集約し、人間へ追加read-onlyコマンドを分割して渡さない。seed42送信/healthcheck無効/privateIPCを実装・inspect契約で確認。RPC中は.2sec callback、起動HTTP待ちは.2sec watcher/90secでabort、生成は.05sec watcher/90sec。同承認operator SHAの一回分をread-only成功後・unload直前にO_EXCL/fsync予約し、既存intentのあるCLIを早期拒否する。回収では監視callbackを解除して、pressureがstop/killを阻害しない。API壁時間とsampled extremaは記録し、decode benchmark/hard memory capとは扱わない。server logはterminal後だけ読み、120行の保存末尾131072文字に制限する。Docker stdout/stderrのサイズ判定はcommunicate後であり、入力メモリのstrict boundではない。
