# vLLM固定Next単発GPU試験：具体的開始承認案

既存vLLM ROCm imageと取得済みNextを使い、起動→ACK1生成→所有container回収→30B復帰まで1回実施する。用途はgfx1151での実開通確認で、一般的coding能力の採点ではない。

- image: `vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905`。Next revision `c92cabfad08cadb011dc169cabb3e6da621b0719`、44.96GiB取得済みをread-only共有。実deps/主要7source照合済み、wholecommitやGPU成功は未証明。
- context4096、最大64出力、temperature0/seed42、API POST1・再送0。BF16/TP1、Triton MoE/attention/GDN、AITERoff、enforce-eager、GPU utilization0.80、外部model取得off。
- 全体900秒（preflightを含む）。起動90/生成90/回収45/30B復帰120秒を割当。30Bはunload〜回収/復帰の間利用不可。通常は数分、各処理の予算合計は概ね6〜7分、全体15分枠。kernel/daemon不応答時に復帰時間を保証せずUNKNOWNを保持する。
- container RAM32GiB、swap増加0、CPU8、PIDs512、privateIPC/read-only/nonroot/capdropALL/nnp/defaultseccomp。RAM開始24GiB以上、継続16GiB以下・GPU58GiB超・swap増加で中止。GPUは逐次、Strata試験と重ねない。
- 一時containerに固定 `/dev/kfd` と `/dev/dri/renderD128`、既存sessionが持つGPU groupだけを渡す。新規host権限/group/credentials、driver/package/service/security設定、外部API課金は無い。既存internal networkの所有CID/IP限定、host port公開無し。他の同network containerから到達できる性質は残る。
- 所有CID/image/token/ownerを照合してstop/kill、terminal/Pid0、remove/absenceの順で回収し、確認後だけ30Bを復帰。生存/UNKNOWNでは再loadや再送をしない。同operator SHAは一回分のintentで重複を拒否する。

既存承認は推論評価の目的、固定重み取得、既存imageのCPU確認までを支える。今回の追加確認は「この固定profileで人間hostから一時GPUcontainerを作成し、30Bを一時unload/復帰させる1回の開始」。広い権限追加やCodex内の追加隔離許可を求めるものではない。

### ユーザーへ送れる短い文面

既存vLLMで取得済みNextを1回だけ実推論していい？ context4096・最大64tokens、全体15分枠。30Bは試験中一時停止し、所有container回収後に復帰する。RAM32GiB・swap0、資源監視・再送なし。新規DL/課金/host権限追加はなく、StrataとGPUを重ねない。実行は用意したhostコマンド1つで、ソース等の追加手動照合は不要。

承認後は親が新しいowner0600 approved operatorを登録し、固定SHAの人間hostスクリプトを渡す。現時点はcandidateだけでlive operatorは未登録、実GPU0。
