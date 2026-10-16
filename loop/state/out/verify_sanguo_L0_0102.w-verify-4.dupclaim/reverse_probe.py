#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""w-verify-4 的反向验证探针（**修正版**）。

⚠️ 我第一版有仪器错误，如实记录：
   我用 text.find(frag) 取**全文首次**出现位置来判「是否被引用」。
   '将在外，君命有所不受。' 在全文 607191 码点里有 5 处出现（108271/332139/527452/
   574452/594189），首次出现在第 38 回、**不在本区间**，于是被判 MISS —— 假阳性。
   这与被复核者 T4 判据（find(quote)==declared start）要防的是同一类错：
   **拿全文搜索的结果去代理切片内的定位**。
   修法：只认落在 [S,E) 内的出现位置；区间外的一律不参与判定。

判据：片段在切片内**至少有一处**出现，且该处被某个引文区间覆盖 ⇒ covered。
"""
import json, os, sys

ROOT = "/Users/carmen/Desktop/星系"
text = json.loads(open(os.path.join(ROOT, "data/cache/fe42d01f3826fe8096f86614.docs.json"),
                       "rb").read().decode())[0]["text"]
S, E = 522662, 528484
cand = json.load(open(os.path.join(ROOT, "loop/state/out/read_sanguo_L0_0102.candidate.json")))


def walk(n):
    if isinstance(n, dict):
        if isinstance(n.get("quote"), str) and "start" in n:
            yield n
        for v in n.values():
            yield from walk(v)
    elif isinstance(n, list):
        for v in n:
            yield from walk(v)


refs = [(q["start"], q["end"]) for q in walk(cand)]


def occurrences_in_slice(frag):
    out, i = [], text.find(frag)
    while i != -1:
        if S <= i and i + len(frag) <= E:
            out.append(i)
        i = text.find(frag, i + 1)
    return out


def covered(frag):
    """返回 (状态, 证据)。状态 ∈ covered / uncovered / not-in-slice"""
    occ = occurrences_in_slice(frag)
    if not occ:
        return "not-in-slice", None
    for o in occ:
        for a, b in refs:
            if a <= o and o + len(frag) <= b:
                return "covered", (o, a, b)
    return "uncovered", occ


PROBES = [
    ("司马懿弃盔方向误导（叙述者的解释句）", "原来司马懿把金盔弃于林东，却反向西走去了。"),
    ("廖化拾盔献功、录为头功", "廖化献上金盔，录为头功。"),
    ("魏延怨言 / 孔明只做不知", "魏延心中不悦，口出怨言。孔明只做不知。"),
    ("满宠夜袭吴水寨的提议", "今夜可乘虚劫其水寨，必得全胜。"),
    ("魏主采纳并派张球带火具", "即令骁将张球领五千兵，各带火具"),
    ("陆逊表文被魏军伏路截获", "不期被魏军伏路的捉住"),
    ("曹睿叹陆逊妙算", "东吴陆逊真妙算也！"),
    ("司马懿放归蜀兵的政治用意（吕蒙取荆州之计）", "此吕蒙取荆州之计也。"),
    ("孔明以巾帼女衣辱懿（书信）", "今遣人送巾帼素衣至"),
    ("懿问使者寝食之烦简", "孔明寝食及事之烦简若何？"),
    ("杨顒引丙吉/陈平典故", "昔丙吉忧牛喘，而不问横道死人；陈平不知钱谷之数"),
    ("孔明自陈受先帝托孤之重", "但受先帝托孤之重，惟恐他人不似我尽心也！"),
    ("辛毗识破懿之本意", "司马懿本无战心，必因诸葛亮耻辱"),
    ("懿暗谓辛毗『公真知我心也』", "公真知我心也！"),
    ("孔明识破请战是安三军之法", "此乃司马懿安三军之法也。"),
    ("将在外君命有所不受（孔明引以释懿之请战）", "将在外，君命有所不受。"),
    ("费祎报吴兵无功而退", "吴兵无功而退。"),
    ("孔明昏倒于地", "长叹一声，不觉昏倒于地"),
    ("三台星客星倍明主星幽隐", "客星倍明，主星幽隐"),
    ("七日内主灯不灭可增一纪", "若七日内主灯不灭，吾寿可增一纪"),
    ("本命灯一盏 / 七盏大灯四十九盏小灯", "内安本命灯一盏"),
    ("姜维披发仗剑踏罡步斗压镇将星", "披发仗剑，踏罡步斗，压镇将星"),
    ("魏延脚步急扑灭主灯", "延脚步急，竟将主灯扑灭"),
    ("孔明弃剑而叹死生有命", "死生有命，不可得而禳也！"),
    ("姜维拔剑欲杀魏延", "姜维忿怒，拔剑欲杀魏延。"),
    ("司马懿以手加额谢魏主洪福", "司马懿以手加额曰：“大魏皇帝之洪福也！”"),
    ("孔明预言若出武功则魏危", "孔明若出武功，依山而东，我等皆危矣"),
    ("郭淮提醒孔明将择地安营", "近日孔明引兵巡哨，必将择地安营。"),
    # ── 以下为候选/被复核者**都没有**提到的原文事实（我的反向追加）──
    ("孔明分拨已毕自引一军近上方谷下营（部署落点）", "孔明分拨已毕，自引一军近上方谷下营。"),
    ("懿令张虎、乐綝各引五千兵在后救应", "令张虎、乐綝各引五千兵，在后救应。"),
    ("蜀兵虚作救应之势以诱懿", "蜀兵四下一齐呐喊奔走，虚作救应之势。"),
    ("懿烧断浮桥据住北岸（战场收束）", "懿烧断浮桥，据住北岸。"),
    ("魏兵在祁山闻败军心慌乱", "听知司马懿大败，失了渭南营寨，军心慌乱"),
    ("孔明见火光甚喜、以为懿必死", "心中甚喜，以为司马懿此番必死。"),
    ("孔明叹谋事在人成事在天", "谋事在人，成事在天。不可强也！"),
    ("孔明自此自觉神思不宁、诸将未敢进兵", "自此孔明自觉神思不宁。诸将因此未敢进兵。"),
    ("司马懿看毕心中大怒乃佯笑", "心中大怒，乃佯笑曰：“孔明视我为妇人耶！”"),
    ("懿顾谓诸将『孔明食少事烦其能久乎』", "孔明食少事烦，其能久乎？"),
    ("孔明叹『彼深知我也』", "孔明叹曰：“彼深知我也！”"),
    ("日则计议军机夜则步罡踏斗", "日则计议军机，夜则步罡踏斗。"),
    ("姜维引甲士四十九人各执皂旗穿皂衣", "各执皂旗，穿皂衣，环绕帐外"),
    ("亮自陈承三顾之恩托孤之重", "承昭烈皇帝三顾之恩，托孤之重"),
]


def main():
    miss = []
    for label, frag in PROBES:
        st, ev = covered(frag)
        if st == "uncovered":
            miss.append((label, frag, ev))
        print("  %-9s %-44s %r" % (st.upper(), label, frag[:38]))
    print("\n未被任何引文覆盖：%d / %d" % (len(miss), len(PROBES)))
    for label, frag, ev in miss:
        print("  MISS %-40s %r  切片内偏移=%s" % (label, frag[:50], ev))
    json.dump({"total": len(PROBES), "uncovered": [{"label": l, "quote": f, "inSliceOffsets": e}
                                                   for l, f, e in miss]},
              open(os.path.join(os.environ["AGENT_ARTIFACTS"],
                                "verify-sanguo-0102-w-verify-4-dupclaim", "reverse_probe.json"), "w"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
