#!/bin/sh
# 复核者的全部独立核验，按顺序跑一遍。只读输入，不写仓库内任何文件。
set -e
cd "$(dirname "$0")/../../../.."   # loop/state/out/<dir> -> 仓库根
echo "=== 0. 源文件与切片哈希 ==="
shasum -a 256 data/cache/1063b17ca65ec1b76f30e460.docs.json
python3 -B -c "
import json,hashlib
t=json.load(open('data/cache/1063b17ca65ec1b76f30e460.docs.json'))[0]['text']
print('segment sha256:',hashlib.sha256(t[813350:817425].encode()).hexdigest())
print('starts with unit head:',t[813350:817425].startswith('第两百一十七章 许七安：我爽了'))
print('candidate sha256:',hashlib.sha256(open('loop/state/out/read_dafeng_L2_0218.candidate.json','rb').read()).hexdigest())
"
D=loop/state/out/verify_dafeng_L2_0218.w-verify
echo; echo "=== 1. 全部 194 条引文逐字+偏移 ===";            python3 -B $D/check.py
echo; echo "=== 2. 复核者重写候选 9 条判据 ===";              python3 -B $D/indep_checks.py
echo; echo "=== 3. 覆盖率重算 ===";                          python3 -B $D/coverage.py
echo; echo "=== 4. 句单元互斥（含『：』为句界）===";           python3 -B $D/sentunit.py
echo; echo "=== 5. 只作为引文存在、未被断言的句子 ===";        python3 -B $D/sent_only.py
echo; echo "=== 6. 反向验证：问答链/置信度缺失 ===";           python3 -B $D/rc_final.py
echo; echo "=== 7. 反向验证：知识差/状态缺项 ===";             python3 -B $D/reverse_confirm.py
echo; echo "=== 8. 引用抽样 5 条 + 反例引文定位 ===";          python3 -B $D/reverse.py
echo; echo "=== 9. 汇总判据（A–I）===";                       python3 -B $D/final.py
echo; echo "=== 10. 段落索引（复核者自建，用于按段核对）===";   python3 -B $D/paras.py | head -20
echo; echo "全部完成。结论见 loop/state/out/verify_dafeng_L2_0218.verdict.json"
