> これは当初の承認案と失敗診断の履歴。現在は内部IP配備・3モデルE2Eを完了しrouter内30Bで稼働中。現行手順は[運用ガイド](INTERNAL_IP_ROUTE_IMPLEMENTED.md)と[README](../README.md)を参照。

# 人間によるホスト配備・復帰の承認対象

状態: **準備のみ／未実行**。Codexは以下のDocker作成・起動・停止コマンドを実行しない。
ホストbroker・systemd-run・別セッション・UI経由の端末操作へ委譲もしない。
承認後、利用者自身が通常のホスト端末で初期配備を担当し、その後Codexは固定HTTP APIだけを使う。

## 一度に判断する具体案

- binaryはホストに存在せず、既存取得済みimage内の `/app/llama-server`。
  imageは `ghcr.io/ggml-org/llama.cpp@sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15`。
- 人間が新しい専用container `project-kiss-aceis-router` を作る。モデル子processはその同じcontainer境界内で動き、HTTP切替時にnamespace/containerを作らない。
- 元container `project-kiss-phase2-llama-server-1` は削除・再作成・設定変更せず、手動stopで保持する。
  実機の元CIDはGit除外の `agents/local_llm/.runtime/router-host-profile.json` に分離する。
- 既存internal network `project-kiss-large-coder-b3_local` を再利用し、新しいnetworkは作らない。
  外部向け公開は追加せず、既存と同じ `127.0.0.1:8080` のみ。host network、外向きbridge、firewall変更へfallbackしない。
- modelsは既存treeをread-only。presetもread-only。既存B3 runtime cacheはHIP等のcache書込み用。
  Docker socket、ホスト実行API、新しいキー、秘密ファイルはmountしない。
  手動保守時の非秘密CIDだけを `agents/local_llm/.runtime/router-host-maintenance.cid`（0600）へ記録する。
- 非root、cap_drop ALL、no-new-privileges、read-only root、RAM32GiB/swap追加なし/CPU8/PID512。
  これはB3の大モデル上限を保つが、従来無上限だった30Bにも合計上限がかかるため、起動確認が必要。
- max-one-model、要求時autoload無効。起動時は30Bだけ明示的にloadするpreset。
  120B/Next使用中は30Bをunloadし、30B APIは一時使用不可になる。
- restart=no。新しいsystemd unitやログイン/再起動時自動起動は追加しない。
  router稼働を選ぶ間、手動stopした元30Bも再起動時には自動復帰しない。
  元CIDを手動startすれば元のrestart policyの運用へ戻る。

## 変更するファイル・サービス

配備用の準備済みファイル（既存本番Composeは変更しない）:

- `agents/local_llm/integration/router-compose.PROPOSAL.yaml`: 上記container定義。
- `agents/local_llm/integration/router-presets.PROPOSAL.ini`: 固定3モデル、既存32K、30B GPU99 /120B20/Next28層。
- `agents/local_llm/integration/host_deployment_check.py`: GETと資源file読取だけ。POST/起動/生成/Dockerは行わない。

承認後にCodexが実装・反映する予定（**現在は未変更**）:

- `agents/local_llm/local_llm.py`: 元30B操作を同じ入力schemaのままrouter-awareにする。
  `/props`等を固定30Bのquery付きreadにし、autoload=false。lock/UNKNOWN/policy付与は維持。
- `agents/local_llm/model_selection.py` と `selection_extension.py`: 検証済みrouterへ固定profileを結び、限定prepareを実装。
  必要なら同directoryにHTTP-onlyの `model_runtime.py` を追加。subprocess/engine socketへ接続しない。
- `agent-orchestrator/src/mcp_adapter.py`: 既存4toolsとは別opt-inで下記3toolsを追加。
- `agent-orchestrator/scripts/poc_services.py`: 新opt-inをTunnelのadapter argvへ渡す。
- **反映が必要なのは既存 `agentorchestrator-poc-365d01e41070-tunnel.service` のみ**。
  active/lock/UNKNOWNなしと所有世代一致を確認し、既存managerで更新。daemon unitは変更・再起動しない。
- ChatGPTの既存AceISアプリを一度「ツールを更新」。新接続・新キー・権限設定全体の変更なし。

canonical policy/guard/fixture/trust/global設定/.gitignore/B1/B2/B3既存containerは変更しない。

## 追加3toolsの正確な権限案（既存4→7）

|tool|入力|許可される操作|
|---|---|---|
|`aceis_local_model_status`|`profile`|固定profileのassets/接続/loaded状態のGET。生成・load/unloadなし|
|`aceis_local_model_generate`|`profile, task, prompt, max_tokens`|既にload済みの選択モデルに1生成。autoload/fallbackなし。NOT_EXECUTEDの助言だけ返す|
|`aceis_local_model_prepare`|`profile`|共通lock下で現在の固定モデルをunloadし、選択モデルをload。30B選択で復帰。Docker/container操作は不可|

profile enumは `qwen-coder-30b | gpt-oss-120b | qwen-coder-next` のみ。Flashは初回対象外。
任意URL/path/model文字列/command/key/ダウンロード操作は受け付けない。prepareは起動停止能力の追加なので個別承認対象。
status/generateは準備済み未登録、prepareはまだ仕様だけで、承認前には実装・公開しない。

固定上限案: prepare120秒（load開始後最大90秒）、生成は120B240秒・Next180秒・30B85秒、
MCP wallは250/190/90秒。元の30B専用toolは90秒のまま。入力16384 UTF-8 bytes、出力最大1024tokens。
共通policy全文、逐次処理、起動前RAM>=24GiB/GPU<=58GiB、稼働中RAM>=16GiB/GPU<=58GiBを維持。
UNKNOWNは再送・別profile切替・自動再loadをせず、状態照合まで止める。

## 未確定点・時間・復帰

1. **初期配備の主体:** 利用者本人の通常ホスト端末だけ。CodexがDocker操作を別経路へ流すことは承認範囲に含めない。
2. **network実動:** 既存Docker29.9.2 / internal bridgeでの新containerのlocalhost port mappingは未実測。
   B3で過去に同種mapping不成立があったため、Compose構文成功を接続成功と扱わない。
   失敗時は元CIDへ戻す。internal解除/host networking/追加proxy/daemon設定変更はしない。
3. **32GiB capとpreset実動:** 既存binaryのrouter仕様は確認済みだが、このpreset/runtimeは未起動。
   30Bを32GiB aggregate capでロードできるか、未知のcatalogが混入しないかをread-only gateで判定する。
   RAM/swap/CPU/GPUのホスト設定は変更しない。
4. **既存30B client互換:** router-aware変更のofflineテストとreviewを先に終えるまで、人間の配備を開始しない。
5. **時間:** containerを事前createした後、元30B停止からrouter上30B health確認までは見込み1〜2分。
   未実測なので保証ではない。90秒gateで不成立ならrollbackする。
   rollbackは新router stop最大20秒＋元CIDのstart/health確認最大90秒、通常約1〜2分＋人間操作時間。
   120B→Next→30B復帰のE2E中も30Bが使えない。試行全体上限900秒、各profile1生成で追加試行なし。
6. rollbackで元CID/Image/Config/HostConfigは維持できるが、StartedAt・一時KV/cache状態は再起動で変わる。
   UNKNOWN markerを勝手に削除しない。health復帰とMCPの不確実状態解消は別確認。

7. **外側MCP時間枠:** 250/190秒の同期応答回収は未実測。最初の有限E2Eで判定し、UNKNOWNなら再送せず停止する。今回の範囲で勝手にasync-job API等へ拡張しない。

## 修正版: 独立scriptで実行（旧貼付手順は撤回）

対話端末へ`set -e`付きblockを貼る旧手順は不適切だったため撤回した。
以下をbashの子processとして実行する。sourceは禁止し、wrapperでも検出して何も実行せず戻る。
親端末のshell option/PWDは変更しない。末尾の`||`は親に既にerrexitがある場合にも端末を維持するため。
実際の失敗位置・終了コードはprivate JSONLに保存され、ログpathも画面に表示する。

配備（利用者本人の通常ホスト端末でのみ）:

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/deploy_router.sh" || echo "配備は停止しました。表示されたログを確認してください。"
```

元30Bへ復帰:

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/rollback_router.sh" || echo "復帰は停止しました。表示されたログを確認してください。"
```

`host_router_maintenance.py`は固定手順の実装で、MCP/agentからは呼ばない。任意command/URL/modelは受け付けない。
元CID/name/image/config、共通lock/UNKNOWN、active仕事、既存network、固定3model preset、資源/busy slotを確認する。
新containerは配備世代の非秘密token labelと保存CIDで照合し、未知の世代は採用・停止しない。
元containerは削除・再作成・設定変更しない。元停止後の失敗では、所有routerだけを停止して元CIDの復帰を試みる。
復帰も失敗したら記録して終了し、保護緩和や無制限retryはしない。

- `.runtime/host-maintenance-<UTC>-<id>.jsonl`:0600、非秘密の段階/診断/終了コード。
- `.runtime/router-host-state.json`:0600、元CID/新CID/世代/phase。
- 旧保存CIDがある場合は上書きせず照合待ちで停止する。
- 未知router、元CID/config不一致、busy、UNKNOWNでは変更せず停止する。
- create結果不明でも世代labelで照合し、同じcontainerを二重作成しない。
- 前回失敗を記録済みなら通常deployは再送せず停止する。ログを確認し原因を解決した後だけ、
  利用者が`bash .../deploy_router.sh --resume`を明示して部分配備を再開できる。強制採用はない。
- 配備420秒、独立復帰150秒で打ち切る。通常1〜2分の見込みだが、実機配備は未検証。
- UNKNOWN marker、原本ログ、元container、model、credentialは削除しない。

10:37UTCの失敗後読取りでは元30Bが同CIDでhealthy、routerと旧保存CIDはなかった。
container作成前の停止と判断できるが、旧手順は失敗commandを保存しておらず、正確な理由は不明。
必要なら最後のエラー1〜3行だけを確認し、shell history全文は求めない。
この修正は、初回配備をCodexが代行する許可ではない。

## 可搬版とホスト専用値

この文書とComposeはGit収録用テンプレート。`<PROJECT_ROOT>`と`<ORCHESTRATOR_ROOT>`は
利用者がホスト端末で実値へ置換する。コンテナ内の `/app` / `/models` / `/config` / `/cache`
およびLinux device pathsはportable runtime contractで、個人のホスト実パスではない。
実機パス・元CIDは既存Git除外 `.runtime/router-host-profile.json` のみに保存する。
このprofileは非秘密metadataであり、実行権限・承認・自動配備機能を持たない。


## 10:56UTC実行の権限診断

元30Bの最初のinspectで、固定Docker socketへのpermission deniedが発生した。
router not-foundの扱いではない。state/CID記録は未作成で、create/start/stopには到達していない。
30BのHTTP healthは正常。Docker APIが拒否されるため、現在のcontainer identity/router有無は
独立に再取得できていない。最後の確実なDocker観測と区別する。
NSS上のユーザーはdocker所属だが、現プロセスにsocketが要求するGIDが反映されていない。
同じセッションのまま再実行せず、既存権限が反映された通常ホストsessionを先に確認する。
sudo、socket chmod、group追加、別Docker endpoint、自動sg/newgrpで迂回しない。
ログアウトは既存user daemon/Tunnelの存続へ影響し得るので、必要なら親側と復帰を調整する。
codeは権限拒否/not-foundを別分類し、15件のmock回帰試験が成功した。

## 11:56UTC実行: router HTTP確認失敗・元30B復帰

状態: **再配備保留**。ユーザーによる実行ではDocker所属の反映とcreate/startが成功したが、
routerのGET確認が90.042秒でTimeoutErrorとなり、元30Bへ復帰した。全体92.566秒、
rollbackのidentity確認開始から完了まで1.920秒。モデル自身はrouter内で約11.976秒でloadedを記録した。
12:01UTCの独立GETでも元30B health/model identityを確認した。生成要求は0。

既存診断は例外名のみでendpointを保存しておらず、失敗したGETのpathやTCP/NATの根因は
当該ログだけでは確定できない。過去B3では同じinternal bridgeのhost port mapping不成立を
実測しているため、同じ問題が有力候補。今回も同じと断定しない。
エージェントのDocker inspectは引き続きpermission denied。sudo/newgrp等では再試行しない。

修正: 各段階の経過秒・HTTP確認の最大90秒を対話端末に表示し、各commandの所要秒を記録する。
GETエラーはendpointとHTTP_TIMEOUT等の分類を保持し、最後のdeadline例外で原因を上書きしない。
router起動直後にDockerの実公開portをread-only inspectし、要求したloopback8080が実体化して
いなければ90秒のHTTP待ちへ進まず元30Bへ復帰する。timeout/資源/隔離設定は緩めない。

利用者本人のDockerが読める端末での追加確認（**配備・再起動ではない**）:

```bash
docker --host unix:///var/run/docker.sock inspect --format '{{.Name}} status={{.State.Status}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}} requested={{json .HostConfig.PortBindings}} actual={{json .NetworkSettings.Ports}} networks={{json .NetworkSettings.Networks}}' project-kiss-phase2-llama-server-1 project-kiss-aceis-router
docker --host unix:///var/run/docker.sock network inspect --format 'internal={{.Internal}} options={{json .Options}}' project-kiss-large-coder-b3_local
```

停止済みrouterのactual portは解除後の値なので、それだけで起動中の不成立を証明したとは扱わない。
既存ログ・上記読取りを照合して原因を判断し、接続設計の変更が必要なら対象と影響を具体化して
再確認する。container IPへの差替え、proxy追加、internal解除、host networking、daemon設定変更へ
自動fallbackしない。同じ配備commandや`--resume`の再実行はまだ案内しない。


## 12:08UTC追加証拠と診断の限定

ユーザー端末のinspectで、元30Bはrunning/oom=false/exit=0、実公開loopback8080も確認。
routerはexited/oom=false/exit=0。停止後のactual portsとendpointは空だが、
これは停止時の解除でも生じるため、稼働中のport mapping失敗の証明には使用しない。
networkはinternal=true、host_binding_ipv4=127.0.0.1。

当該時刻のdocker.service journalを直接read-only確認した。router join時の
`gwep4 ''->'', gwep6 ''->''`と、元30B復帰時の非空IPv4gateway endpointを記録。
port/NAT失敗を明示したerrorはなく、一般的なsecurity option区切り文字の非推奨warningのみ。
このwarningを90秒Timeoutの原因とは扱わず、security設定は変更しない。

上流[Moby v28.5.2 endpoint.go](https://github.com/moby/moby/blob/v28.5.2/libnetwork/endpoint.go#L661-L670)
にはinternal networkでProgramExternalConnectivityを呼ばない条件がある。
ただし実機はdockerd --versionで29.9.2/build0367cbe。該当tag/buildのソースは取得できず、
上流旧版の挙動をそのまま実機の確定原因とはしない。internal networkと要求したloopback
公開経路の不整合は有力仮説のまま。生成/起動/停止/namespace追加/権限変更は0。

同じ配備の再実行は保留する。接続設計を変更する場合は、固定接続先・モデル到達範囲・
外部通信遮断・既存30Bの復帰方法を具体化して確認し、保護を緩める自動fallbackはしない。


## 12:13UTC明示再開ガードと次の限定診断

人間による通常deploy再実行は0.033秒でEXPLICIT_RESUME_REQUIREDとなった。
元CID/image/config fingerprintとrouter世代label/CID/security/resource/mount契約は
inspectで一致確認され、その後のガードで停止。create/start/stopは0、metadata phaseだけFAILED更新。
ガードと元の世代を維持する。state削除、token置換、container再作成はしない。

次の限定診断を人間が行う場合だけ、既存の明示再開を1回使う:

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/deploy_router.sh" --resume || echo "診断は停止しました。追加再試行せずログを確認してください。"
```

目的は新規実装済みの稼働中port inspectで、前回欠けていたrequested/actualの成立情報を取ること。
不成立ならROUTER_PORT_UNPUBLISHEDを記録しHTTPの90秒待ちに進まず元30Bを復帰。
成立ならGETだけの確認へ進み、失敗endpoint/HTTPエラー分類/経過秒を記録して復帰。
モデル生成は0、既存所有router再利用、network/host/security変更なし。
HTTP確認は最大90秒。配備の既存期限420秒、失敗後の独立復帰期限150秒を維持する。
外側timeoutで強制終了せず、復帰処理を完了させる。同じ診断を繰り返さない。

稼働中port不成立が確定した場合の変更候補は、internal networkを保ったまま、
検証済み所有routerのbridge内IPへHTTP接続する方式。client/gate/receiptのlocalhost固定契約が
変わるため、CID/network/IPを検証して任意URLを拒否する具体案と30B復帰をレビュー・確認してから
実装する。現時点では未適用。internal解除、host network、外向きbridge、daemon/firewall変更をしない。


## 12:21UTC限定診断の完了・再試行停止

稼働中routerで8080/tcp:nullを記録し、約22.270秒で元30Bへ復帰した。
start完了から約10msの単発観測なので過渡状態を単独では排除できない。
前回90秒GET失敗とgateway endpointなしの記録を合わせて接続案を見直す。
20.117秒はrouter停止待ちで、daemon journalにSIGTERM20秒後の強制停止を確認。
12:23:54UTCの独立GETで元30B health=ok・正しいalias・1slotを確認した。
現在の同じresumeは再実行しない。
[内部IP接続の具体案](INTERNAL_IP_ROUTE_PROPOSAL.md)を作成したが、接続先許可・receipt契約の変更は承認待ちで未適用。
エージェントによるDocker変更・追加生成・network/security/サービス変更は行っていない。
