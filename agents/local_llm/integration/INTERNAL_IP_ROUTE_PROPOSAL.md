> 現在は配備・3モデルE2E完了。以下の設計時点の未適用記述は履歴で、現行手順は[実装済みガイド](INTERNAL_IP_ROUTE_IMPLEMENTED.md)を参照。

# 固定routerの内部IP接続案（承認・実装・配備完了の設計記録）

## 確認結果と断定範囲

12:21UTCの人間による1回のresumeで、所有CID/設定が一致しRunning=trueのrouterに対し、
requested=127.0.0.1:8080、actual={8080/tcp:null}を記録した。
Docker start完了から約10msの観測であり、この観測単独では過渡状態を否定できない。
前回の90秒GET失敗・約12秒でのモデルloaded・2回のgateway endpoint空という記録を合わせ、
internal bridge上で要求したloopback公開が成立していないことが有力な接続阻害要因。
前回90秒終了時の稼働中port情報はなく、内部IPでのGETも未実施なので、原因を過剰に断定しない。
今回22.270秒のうち20.117秒は停止待ち。journalでSIGTERMの20秒待ち後の強制停止を確認。
12:23:54UTCの独立GETで元30B health=ok/正しいalias/1slotを確認した。生成0回。

## 最小構成

既存internal network、既存router CID/image、cap/resource/mount/security設定を維持する。
routerを再作成せず、ホスト上の既存MCP helper/CLIが所有routerの検証済みbridge内部IPv4:8080へ
HTTP接続する。ネットワーク内IPの自由指定、DNS、URL、proxy、redirect、外部IPは受け付けない。
現在要求済みだが実体化していないloopback port宣言も変更せず、実公開が増えていないことを検証する。
固定endpoint契約の変更であり、承認前に接続も設定反映もしない。

## 識別確認・許可範囲

- 人間が動かす既存配備scriptだけがDocker inspect/network inspectを使用する。
  元30B CID/config fingerprint、router CID/世代label/image/名前、既存security/resource/mount契約を照合。
- network名に加え、既知のnetwork IDとInternal=trueを照合する。IPAMと所有routerのIPv4を読み取り、
  RFC1918・当該subnet内・当該endpointの値という条件を確認。API要求や任意設定値からIPを採用しない。
  別networkの接続や未知の稼働peerがあれば変更せずBLOCKEDとする。
- owner-onlyの配備receiptにCID/世代/image/network ID/subnet/正規化した数値IPv4/port8080/registry hashを保存。
  private metadataのsymlink・所有者・mode・size・schema・既存host stateとの一致を検証する。
- MCPの入力は既存3 profileのみ。host/IP/port/URLの入力を追加しない。Docker socketは公開しない。
- 接続先は同一操作の開始時に固定し、生成・status・cleanupで同じ値を使用。通信失敗時の別IP探索・
  localhost fallback・再生成をしない。IP変更は人間の再照合・receipt更新が必要。
- HTTPのalias/catalog確認は追加するが、暗号学的なCID認証にはならない。CID/IP対応の根拠は人間による
  配備時inspectと保護されたmetadata。別の管理者がcontainer/networkを再割当した場合は再確認が必要。

## 到達範囲と互換

新たな外部公開や外向き通信は追加しない。ホストおよび同一internal bridgeのpeerからrouterへ届く
既存の性質は残る。任意宛先へのネットワーク許可や、Codexの通信制約を別経路で迂回する操作はしない。

元30B運用時は127.0.0.1:8080を使う。検証済みrouter運用時は旧30B専用toolを含む全helperが同じ
保護されたreceiptを使用し、30B/120B/Nextを1モデルずつ扱う。大モデルloaded中は旧30B toolは
MODEL_NOT_LOADEDで停止し、自動loadをしない。引数・policy・出力上限・逐次lock・UNKNOWNは維持する。
不正/部分receiptがあればBLOCKED。30Bへの復帰は人間のrollbackが明示的にresident modeへ戻す。

## 変更対象

|対象（<PROJECT_ROOT>/agents/local_llm/ 配下）|変更|
|---|---|
|local_llm.py|HttpApiの固定localhost定数を、検証済みreceiptの内部IPまたはresident modeへ結ぶ。任意宛先引数は公開しない|
|model_runtime.py|receiptのendpoint/CID/network検証、同一endpointの生成・cleanupへの注入、loopback-only契約をinternal-IP契約へ変更|
|model_selection.py / extension.py / selection_extension.py|旧30Bと選択3profileの接続選択・BLOCKED分類を整合。MCP schemaは変えない|
|integration/host_router_maintenance.py|人間によるowned CID/network/IP検証、候補endpointでのGET gate、成功後receiptのatomic公開、復帰時の自身のreceipt失効|
|integration/host_deployment_check.py|router modeだけ検証済み候補IPへGET。preflight/residentはlocalhost。GET以外なし|
|対応する既存testファイル|以下のオフライン回帰試験を追加|
|.runtime/のhost profile/state/receipt|人間の配備scriptで検証した非秘密metadataだけ追加。credential変更なし|

agent-orchestratorの7tool schema/権限・daemon/Tunnel設定は変更不要。
adapterは各要求でhelperを新しいPython subprocessとして実行しており、この経路差替えでは
サービス再起動やChatGPTアプリのツール再登録も予定しない。

## 準備したテスト項目（未実装の計画）

1. 公開IP/loopback/link-local/DNS/URL/IPv6/可変port、許可network外IP、別CID/世代/imageを拒否。
2. 任意MCP endpoint入力、symlink/non-owner/world-readable/部分/古いschemaのreceiptを拒否。
3. runtime/旧30B/生成/cleanupが同じ検証済み宛先を使い、失敗時に別宛先へfallbackしない。
4. resident modeでは従来localhostを維持。routerで120B/Next loaded中に30Bを自動loadしない。
5. 未知peer、別network、過渡状態、不明なcatalog/alias/context、busy/UNKNOWNでdispatchを止める。
6. human scriptの部分失敗で既存routerだけを停止し、元CID復帰・自分のreceipt失効。原本/UNKNOWNを保持。
7. readonly gateはGETだけ、モデル管理は固定3aliasだけ、全操作のdeadline/資源上限を維持。

## 承認後の実施順と人間の操作

1. エージェントが上記の差分とoffline/mock試験を完了。サービス・Docker・接続先の実適用はしない。
2. 人間へ、検証済み修正版scriptの1コマンドを渡す。現行scriptの同じresumeは再実行しない。
3. 人間のhost scriptでactive0/lock/UNKNOWN/identity/資源を再確認し、既存routerを1回再開する。
   candidate内部IPを検証し、GET gateで固定3catalog/30B loaded/32K/1slot/idleを確認してreceipt公開。
   失敗時は元30Bへ復帰。配備420秒、別枠復帰150秒、GET確認90秒を増やさない。
4. 成功したらChatGPT/Codexの既存7toolでstatusを確認。
   承認済みの120B→Next→30B復帰を各1生成・全体900秒で実施。生成の再送・追加推論なし。
5. rollback scriptは人間が実行し、共通lock下で自身のrouterを停止、元CIDをstart、localhost health確認、
   routeをresidentへ戻す。停止中IPへの自動追随やUNKNOWN解除はしない。

承認対象はこの固定内部IPへの接続契約とowner-only receipt更新、旧30Bを含むhelperの追従、
人間による1回の配備・失敗時復帰、既承認の有限E2E。新network/proxy/host networking、
firewall/daemon/security変更、新しいキー・権限・大型download、commit/pushは含めない。


## 承認後の実装状態

固定内部IP方式の実装・offline/mock112件とbash構文検証を完了した。
実配備は人間待ち、追加生成0回。現在の手順は[実装済み配備手順](INTERNAL_IP_ROUTE_IMPLEMENTED.md)を使う。
旧単独--resumeではなく、--resume --internal-ipの1回だけを人間が実行する。
