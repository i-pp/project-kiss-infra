# SGLang監視設計のレビューと単一の有限案

**未承認・未統合。ホスト実行コマンドは発行しない。既存guardは変更しない。**

## 確認した事実

対象runは`sglang-1627dfedc60b4d59a1cabf6dcb26273c`。88.072秒、assets検証中にhost swap純増134,410,240bytesで旧128MiB条件が作動した。RAM availableは51,948,109,824→52,294,778,880bytesへ増加。記録した約87.318秒間のpswpinは不変、pswpout差113,127,424bytes、memory full-stall total差65,797us（区間約0.07535%）。表示avg10=0は瞬間stall皆無を意味しないが、保存値は持続的な強い全体stallの証拠ではない。

30B停止・モデルコンテナ作成・生成は0。環境NOT_RUN/品質UNASSESSED。元GPU attemptは未作成、source intentとasset-resume intentは保存、共有UNKNOWNなし。モデルcontainerが存在しないため、そのcgroup/JIT sample_count0は正常。単一loaderの効果は依然未検証。

取得時のACQUIRED_ALL20_SHA256_VERIFIED receiptは固定manifest全20件と一致。今回の先頭4shardは各SHA一致、合計20,010,148,032bytes。保存した読取前identityと現在statも一致する。第5shardの途中、最後のprogress総読取23,440,040,128bytes。これを「今回全20件検証成功」とは扱わない。次案も全20SHAを新たに一巡し、partial/metadata-onlyへの省略はしない。成功した同一fixed-image静的receiptだけはhash固定＋fresh image ID照合で再利用する。

## 四つの問題を分離

| 項目 | 判定と対応 |
|---|---|
| Asset同一性 | 全20SHA/固定manifest/読取前後identity/原本保全を維持。今回4file一致と過去全照合は別の証拠。 |
| 通常reclaimと実圧迫 | host全swap残量の純増は対象のOOMやthrashingの証明ではない。cold-page reclaim、hashのcache作用、他workerの寄与はいずれも未確定。PSI totalの差とswap I/O、RAM余裕を時刻付きで合わせる。 |
| 試験自身 | native hasherのRSS/swap、CPU、I/O、faultsと所属cgroupを記録。共有cgroupは共有と明記し対象専用と扱わない。モデル起動後は固定CID/PID/starttimeの専用cgroupを確認しmemory.current/peak/max、swap.max、OOM、pressureを別記録。読めない情報は欠測であり0ではない。 |
| Monitor自身 | resource_samples67,614/88.072s≒767.7回/s。1MiB読取の前後＋各pacing待機でcheck→system_probeが走る構造がほぼ3×256=768回/sと一致する。各probeは/proc/meminfo読取とGPU sysfsのglob/resolve/VRAM/GTT読取を行う。chunk処理と物理probeを結び付けた実装は過剰だった。 |

現在の同じprobeを200回だけ読取測定した結果は、平均約0.172ms、合計wall0.0345s/CPU0.0345s、major fault0。同条件なら67,614回はprobe単体で約11.6CPU秒相当。ただしこれは後日のexecutor視点のmicrobenchからの推定で、元runのCPU測定値でもswap原因の証明でもない。Codexから見えるPID一覧はexecutor内に限られ、他ホストworkerの帰属は判明していない。NPU記録調査など別workerを停止しない。

## 単一の次案（この未消費GPU枠だけ）

1. 共有された物理probeを最大5Hz（200ms）へ統一。chunkごとの期限/中断確認は軽いまま継続し、境界ではfresh sampleを強制する。最初のhost baselineは固定し、hash完了時にも更新しない。physical sample、logical check、probe CPU/wall時間を別々に記録。欠測、counter reset、boot変化、1秒超のstaleは停止。モデルcgroupは1Hz以上で鮮度確認。
2. 全20SHA、1MiB/256MiB/s/asset240秒、image実ID照合、起動300秒、生成90秒/1回64tokens、全体900秒、所有回収後30B復帰を維持。240+300+90+185復帰予約=815秒、その他の時間も900秒に含める。
3. Assets・create/start直前のRAM24GiB、稼働中RAM16GiB、GPU58GiB、container memory32GiB/swap0、既存security/network/mount条件は維持。モデルの所有cgroup/制限/鮮度が確認できない場合やOOMイベント時は停止して回収。
4. **今回の1枠だけ、host swap純増128MiB単独停止を次へ置換する。**
   - host net swap純増が**1GiBを超えたら緊急停止**（起点固定）。
   - 実時間の非重複5秒窓で、**swap-out>=16MiB/sかつmemory PSI full-stall>=1%が2窓連続**なら停止。
   - swap有無にかかわらず**PSI full-stall>=10%が1つの5秒窓**なら停止。
   - PSI窓はavg10で代用せず、full total_usの差÷実elapsedで計算する。
5. 旧失敗結果・消費済intent・未消費GPU枠を改ざんしない。新しい監査付き継続intentで元の同じGPU枠へつなぎ、再送なし。失敗しても自動的な上限引上げ/別試行追加はしない。

## 必要な承認とリスク

必要なのは上記4の**この試行限定の資源判定変更**。1GiBは旧128MiBの8倍で、他アプリのcold pagesが追加でswapされる余地を広げる。値は実機校正済みの安全保証ではなく、有限の試験方針。5Hz化にも最大約200msの検知間隔がある。RAM/GPU/32GiB制限などは独立して残すが、OOMや他作業への影響を完全保証しない。

新しい権限、資格情報、ホスト設定、swapclear/dropcache、cgroup作成、namespace、service変更、他worker停止は不要。現段階はoffline候補17tests＋独立レビューまで。現在のactive guardは旧128MiBのままで、実hash、モデル起動、再開は行っていない。

## 承認文の案

「今回の未消費SGLang1枠だけ、監視を5Hzへ整理し、swap純増128MiB単独停止を、1GiB緊急上限＋継続的なswap I/O/PSI判定へ変更して進めていい？ 許容する追加swap量は8倍になる。全20SHA、RAM/GPU/container制限、15分・生成1回・30B保全は維持し、ホスト設定や他workerは変更しない。」

根拠：PSIはresource stallの時間割合とtotalを提供し、cgroup値はscopeごとに解釈する。上記数値thresholdは資料の推奨値ではなく今回の提案値。
- https://docs.kernel.org/accounting/psi.html
- https://docs.kernel.org/admin-guide/cgroup-v2.html


## 後続の明示指示による更新

ユーザーSentinel_42154944411881919615f516183bbf1fの「swapは8GBまでつかっていい」に基づき、今回の未消費SGLang枠にはホスト総使用量8,000,000,000bytes（実容量以下）を適用する。上記1GiB純増案と追加PSI数値案を承認済みとは扱わない。新run用の共有5Hz監視と専用adapterを配置・検証し、旧guard/旧証拠は保全。現時点はNPU hash完了を親が調整中で、まだ開始しない。TOTAL_SWAP_8GB_RUN.mdを参照。
