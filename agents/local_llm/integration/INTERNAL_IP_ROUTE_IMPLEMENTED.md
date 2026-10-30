> 現在状態（2026-10-29 14:21UTC確認）: 人間配備と親ChatGPTの3モデルE2Eを完了。
> router内30B loadedへ復帰済み、UNKNOWNなし、daemon/Tunnel READY。
> 以下の初回配備・有限E2Eの手順は記録/保守参照用で、同じ試験を再実行しない。
> 現行の呼出し例・制約・実測は[README](../README.md)を参照。

# 固定router内部IP接続: 稼働中・有限E2E完了

2026-10-29の具体承認に沿い、共通HTTP client/runtime/配備gateと人間用scriptを更新した。
LLM offline/mock 101件、MCP adapter 11件、bash構文確認が成功。実機内部IP GET、3モデル切替・各1生成、router内30B復帰を確認済み。
コード反映後の元30B statusはlocalhost/32K/1slot/healthy、UNKNOWNなし。サービス再起動は0。

## 人間用の配備コマンド（初回分は実施済み）

初回配備は完了している。同じ試験を再送しない。以下は承認済みホスト保守時の参照用。sourceは禁止。
Codexによる代行、別のhost broker、namespace追加、sudo/newgrpによるエージェントの権限迂回は行わない。

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/deploy_router.sh" --resume --internal-ip || echo '配備は停止しました。追加再試行せずログを確認してください。'
```

現行の単独`--resume`は旧loopback公開確認なので使わない。`--internal-ip`が新しい承認済み経路を選ぶ。
固定の元CIDと所有routerを照合し、既存routerを再利用する。container/networkの再作成はしない。
既知network ID/Internal=true/接続peer、router CID/世代/image/security/resource/mountを検証する。
未知peer/不一致/UNKNOWN/busyなら停止し、他のcontainerや記録を勝手に消さない。

起動後は所有routerのIPv4/endpoint/network IPAMを照合してprivate candidateだけを作る。
candidateへのGETだけでhealth/固定3catalog/30B loaded/32K/1slot/idle/資源閾値を確認し、
もう一度DockerのCID/endpoint/IPが同じか照合してから正式receiptをatomic公開する。生成0回。
HTTP確認90秒、配備420秒＋失敗後復帰150秒を増やしていない。外側timeoutで復帰を中断しない。
失敗時は所有routerを停止して元CIDを復帰。Docker stopの20秒待ちが起こり得る。

成功は最終JSONのstatus=DEPLOYEDとJSONLのroute_published、失敗はfailed_step/error_code/rollbackで判定する。
表示された非秘密JSONとlog pathを共有する。成功前にprepare/generateを実行しない。

## 接続記録と許可範囲

- endpoint_config.pyがowner-only `.runtime/router-deployment.json`を検証する。任意IP/URL/port入力はない。
- registry hash/CID/世代/image/network ID/endpoint ID/subnet/IPを保護されたhost profile/stateと照合する。
- stale/不正/部分receipt、配備中にreceiptがない場合はfail closed。操作中に記録が変われば停止し、別IPへ追随しない。
- 旧30B toolも正式receiptへ追従し、120B/Next loaded中はMODEL_NOT_LOADED。自動loadなし。
- 同一操作のstatus/generation/cleanupは同じ宛先を使い、redirect/proxy/fallback/retryをしない。
- HTTPのalias/catalogはCIDの暗号学的認証ではない。別の管理者がIP/containerを再割当した場合は人間の再照合が必要。
- internalは維持し、新しい外部公開/外向きnetwork/Docker socket/MCP tool/認証は追加しない。
  ホストと同一internal bridge peerからの到達可能性は残る。

## 失敗時・復旧

自動復旧の結果を先に確認し、同じ配備を再送しない。必要な手動復旧は人間の端末で以下を使う。

```bash
bash "<PROJECT_ROOT>/agents/local_llm/integration/rollback_router.sh" || echo '復帰は停止しました。表示されたログを確認してください。'
```

自身のcandidate/receiptは世代を検証してprivate証拠として退役保存し、元30Bへ戻った後はlocalhostを使う。
UNKNOWN marker・原本・元container/model・credentialは削除しない。別世代のreceiptは採用・上書きしない。
配備と復帰は人間のscriptだけがDockerを使用し、MCPからDockerを操作する経路はない。

## 実施済みの有限E2E: 親ChatGPT担当

生成の担当は親ChatGPTコネクタに一本化する。子Codex/CLI/人間による重複生成はしない。
既存bindingのaceis_local_model_status/prepare/generateを確認し、なければ生成せず親へ報告する。
adapterは要求ごとにhelperを起動するので、schema更新・サービス再起動は今回不要。

共通開始時刻から900秒を上限とし、120B→Next→30Bを順に明示prepare、loaded状態確認、各1生成。
最大出力は各128tokens、task=draft、promptはモデルごとのACK文字列を1行で返す単純な疎通要求。
call_id・model・content・finish_reason/complete・時間・資源・policyを保存する。
ACK形式と接続成功を分け、一般的品質PASSとは扱わない。失敗/UNKNOWNなら再生成せず停止し、
読取りで状態確認して、必要なら上の人間用復旧を使う。900秒ぎりぎりに追加要求を開始しない。
親ChatGPTが3生成・再試行0回で完了済み。追加生成/切替は行わず、実測はREADMEとevidenceの完了記録を参照する。

変更前の失敗でもphase=FAILEDを記録した場合は、状態確認が済むまでAPIがBLOCKEDになる。
元30Bが正常でも勝手に記録を削除せず、必要な人間用rollbackでROLLED_BACKへ戻す。
