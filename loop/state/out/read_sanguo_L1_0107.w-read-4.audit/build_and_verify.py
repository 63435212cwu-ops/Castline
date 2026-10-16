#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""read:sanguo:L1:0107 候选构建 + 自证脚本（w-read-4）。

设计原则（与 loop/ROLES/READER.md 一致）：
  · 引文一律以**精确子串**在 docs[0].text 上定位，偏移由脚本算出，不手工填写。
  · 每条引文必须：全文命中数 == 1，且区间 [548616,552680) 内命中数 == 1。
    命中数 > 1 的引文一律拒绝（否则偏移不可判）。
  · 同一任务五栏（objective/obstacle/action/result/cost）**禁止共用同一引文**。
  · 某栏写 null 时，同名字段 <栏位>Note 必须非空（未标注的未知 != 已确认无）。
  · 内容分区键一律存在（本区间没有就写空数组）。

可复现命令：
  python3 -B -s loop/state/out/read_sanguo_L1_0107.w-read-4.audit/build_and_verify.py
产物：
  loop/state/out/read_sanguo_L1_0107.candidate.json
  loop/state/out/read_sanguo_L1_0107.w-read-4.audit/AUDIT-REPORT.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
OUT_CAND = ROOT / "loop/state/out/read_sanguo_L1_0107.candidate.json"
OUT_REPORT = ROOT / "loop/state/out/read_sanguo_L1_0107.w-read-4.audit/AUDIT-REPORT.json"

START, END = 548616, 552680            # 任务声明的原文区间（全文 codepoint 偏移）
PROMPT_SOURCE_HASH = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"
TASK_JSON_SOURCE_HASH = "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff"

# --------------------------------------------------------------------------- 原文
def load_text():
    doc = json.loads(DOCS.read_text(encoding="utf-8"))
    return doc[0]["text"] if isinstance(doc, list) else doc["docs"][0]["text"]


TEXT = load_text()
SEG = TEXT[START:END]
FILE_SHA = hashlib.sha256(DOCS.read_bytes()).hexdigest()
TEXT_SHA = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
SEG_SHA = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

CONTENT_END = SEG.find("------------------")
BODY = SEG if CONTENT_END < 0 else SEG[:CONTENT_END]
BODY_ABS_END = START + len(BODY)

# --------------------------------------------------------------------------- 引文表
# 每条引文都必须是 docs[0].text 的逐字子串，且在 [START,END) 内唯一命中。
Q = {
    # ── 姜维取雍州 / 司马师拦截 ──────────────────────────────────────────────
    "q_jw_quyongzhou": "原来姜维取雍州之时，郭淮飞报入朝",
    "q_wei_zengyuan": "懿遣长子司马师引兵五万，前来雍州助战；",
    "q_shi_banlu": "师料蜀兵势弱，就来半路击之。",
    "q_jw_lannu": "却说姜维正走，遇着司马师引兵拦截。",
    "q_liannu": "却被姜维用武侯所传连弩法，于两边暗伏连弩百余张，一弩发十矢，皆是药箭",
    "q_liannu_qi": "两边弩箭齐发",
    "q_wei_si_shu": "前军连人带马射死不知其数。",
    "q_shi_taoming": "司马师于乱军之中，逃命而回。",
    "q_ju_an_jiang": "却说麴山城中蜀将句安，见援兵不至，乃开门降魏。",
    "q_jw_zhebing": "姜维折兵数万，领败兵回汉中屯扎。",
    "q_shi_huan_luoyang": "司马师自还洛阳。",

    # ── 司马懿之死与托孤 ────────────────────────────────────────────────────
    "q_yi_bing": "至嘉平三年秋八月，司马懿染病，渐渐沉重",
    "q_yi_huan_erzi": "乃唤二子至榻前嘱曰：",
    "q_yi_shiming": "吾死之后，汝二人善理国政。",
    "q_yi_kongju": "人皆疑吾有异志，吾尝怀恐惧。",
    "q_yi_shen_zhi": "慎之！慎之！",
    "q_yi_wang": "言讫而亡。",
    "q_erzi_shenzou": "长子司马师，次子司马昭，二人申奏魏主曹芳。",
    "q_fang_feng": "芳厚加祭葬，优锡赠谥；封师为大将军，总领尚书机密大事，昭为骠骑上将军。",
    "q_feng_shi": "封师为大将军，总领尚书机密大事",
    "q_feng_zhao": "昭为骠骑上将军",

    # ── 孙权之死与托孤 ──────────────────────────────────────────────────────
    "q_deng_wang": "先有太子孙登，乃徐夫人所生，于吴赤乌四年身亡",
    "q_he_fei": "和因与全公主不睦，被公主所谮，权废之，和忧恨而死，又立三子孙亮为太子，乃潘夫人所生。",
    "q_shiliang_taizi": "又立三子孙亮为太子，乃潘夫人所生。",
    "q_shiwu_gui_ke": "此时陆逊、诸葛瑾皆亡，一应大小事务，皆归于诸葛恪。",
    "q_dafeng": "太元元年秋八月初一日，忽起大风，江海涌涛，平地水深八尺。",
    "q_songbai": "吴主先陵所种松柏，尽皆拔起，直飞到建业城南门外，倒卓于道上。",
    "q_quan_jing": "权因此受惊成病。",
    "q_quan_shu_houshi": "乃召太傅诸葛恪、大司马吕岱至榻前，嘱以后事。",
    "q_quan_hong": "嘱讫而薨。",
    "q_quan_zaiwei": "在位二十四年，寿七十一岁，乃蜀汉延熙十五年也。",

    # ── 魏议伐吴 ────────────────────────────────────────────────────────────
    "q_ke_li_shuLiang": "孙权既亡，诸葛恪立孙亮为帝，大赦天下，改元建兴元年；谥权曰大皇帝，葬于蒋陵。",
    "q_lidijiang": "诸葛恪立孙亮为帝",
    "q_zang_jiangling": "谥权曰大皇帝，葬于蒋陵。",
    "q_xizuo": "早有细作探知其事，报入洛阳。",
    "q_shi_faWU": "司马师闻孙权已死，遂议起兵伐吴。",
    "q_fuGu_jian": "吴有长江之险，先帝屡次征伐，皆不遂意；不如各守边疆，乃为上策。",
    "q_shi_tiandao": "天道三十年一变，岂得常为鼎峙乎？吾欲伐吴。",
    "q_zhao_xinke": "今孙权新亡，孙亮幼懦，其隙正可乘也。",
    "q_sanlu": "遂令征南大将军王昶引兵十万攻南郡，征东将军胡遵引兵十万攻东兴，镇南都督毋丘俭引兵十万攻武昌：三路进发。",
    "q_zhao_dudu": "又遣弟司马昭为大都督，总领三路军马。",
    "q_gong_nanjun": "征南大将军王昶引兵十万攻南郡",
    "q_gong_wuchang": "镇南都督毋丘俭引兵十万攻武昌",

    # ── 司马昭东兴部署 ──────────────────────────────────────────────────────
    "q_zhao_dongxing_yao": "东吴最紧要处，惟东兴郡也。",
    "q_zhao_dike": "今他筑起大堤，左右又筑两城，以防巢湖后面攻击，诸公须要仔细。",
    "q_chaoHu": "以防巢湖后面攻击",
    "q_zhao_liangyi": "遂令王昶、毋丘俭各引一万兵，列在左右：“且勿进发；待取了东兴郡，那时一齐进兵。”",
    "q_zhao_huZun": "昭又令胡遵为先锋，总领三路兵前去：“先搭浮桥，取东兴大堤；若夺得左右二城，便是大功。”",
    "q_da_qiao": "先搭浮桥，取东兴大堤；若夺得左右二城，便是大功。",
    "q_zun_daqiao": "遵领兵来搭浮桥。",
    "q_zun_duqiao": "却说胡遵渡过浮桥，屯军于堤上，差桓嘉、韩综攻打二城。",
    "q_erCheng_shou": "左城中乃吴将全端守把，右城中乃吴将留略守把。",
    "q_erCheng_jiangu": "此二城高峻坚固，急切攻打不下。",
    "q_quanliu_shousi": "全、留二人见魏兵势大，不敢出战，死守城池。",
    "q_xutang": "胡遵在徐塘下寨。",
    "q_daxue_yanhan": "时值严寒，天降大雪，胡遵与众将设席高会。",
    "q_gaohui": "胡遵与众将设席高会。",

    # ── 吴方议救东兴 / 丁奉奋短兵 ───────────────────────────────────────────
    "q_ke_wen_sanlu": "却说吴太傅诸葛恪，听知魏兵三路而来，聚众商议。",
    "q_dingfeng_yaodi": "平北将军丁奉曰：“东兴乃东吴紧要处所，若有失，则南郡、武昌危矣。”",
    "q_dongxing_yaodi": "东兴乃东吴紧要处所，若有失，则南郡、武昌危矣。",
    "q_nanjun_wuchang_wei": "若有失，则南郡、武昌危矣。",
    "q_ke_ling_dingfeng": "公可就引三千水兵从江中去，吾随后令吕据、唐咨、留赞各引一万马步兵，分三路来接应。但听连珠炮响，一齐进兵。吾自引大兵后至。",
    "q_lianzhu_hao": "但听连珠炮响，一齐进兵。",
    "q_dingfeng_chuan": "丁奉得令，即引三千水兵，分作三十只船，望东兴而来。",
    "q_zhanchuan_dao": "忽报水上有三十只战船来到。",
    "q_zuZhong_yibai": "遵出寨视之，见船将次傍岸，每船上约有百人。",
    "q_huZun_qingdi": "遂还帐中，谓诸将曰：“不过三千人耳，何足惧哉！”",
    "q_qingdi_ju": "不过三千人耳，何足惧哉！",
    "q_reng_qian_yinjiu": "只令部将哨探，仍前饮酒。",
    "q_dingfeng_gongming": "大丈夫立功名，取富贵，正在今日！",
    "q_tuo_yijia": "遂令众军脱去衣甲，卸了头盔，不用长枪大戟，止带短刀。",
    "q_wei_daxiao": "魏兵见之大笑，更不准备。",
    "q_lianzhu_sansheng": "忽然连珠炮响了三声，丁奉扯刀当先，一跃上岸。",
    "q_ba_duandao": "众军皆拔短刀，随奉上岸，砍入魏寨，魏兵措手不及。",
    "q_hanZong_si": "韩综急拔帐前大戟迎之，早被丁奉抢入怀内，手起刀落，砍翻在地。",
    "q_huanJia_qiang": "桓嘉从左边转出，忙绰枪刺丁奉，被奉挟住枪杆。",
    "q_jia_qiqiang": "嘉弃枪而走，奉一刀飞去，正中左肩，嘉望后便倒。",
    "q_feng_yiqiang": "奉赶上，就以枪刺之。",
    "q_sanqian_chong": "三千吴兵，在魏寨中左冲右突。",
    "q_huZun_zou": "胡遵急上马夺路而走。",
    "q_fuqiao_duan": "魏兵齐奔上浮桥，浮桥已断，大半落水而死；杀倒在雪地者，不知其数。",
    "q_fuqiao_yi_duan": "浮桥已断，大半落水而死；杀倒在雪地者，不知其数。",
    "q_huo_chezhang": "车仗马匹军器，皆被吴兵所获。",
    "q_zhao_tui": "司马昭、王昶、毋丘俭听知东兴兵败，亦勒兵而退。",

    # ── 诸葛恪乘势伐中原 ────────────────────────────────────────────────────
    "q_ke_chengshi": "却说诸葛恪引兵至东兴，收兵赏劳了毕，乃聚诸将曰：“司马昭兵败北归，正好乘势进取中原。”",
    "q_chengshi_qu": "司马昭兵败北归，正好乘势进取中原。",
    "q_shou_dongxing": "却说诸葛恪引兵至东兴，收兵赏劳了毕",
    "q_qibing_ershiwan": "遂一面遣人赍书入蜀，求姜维进兵攻其北，许以平分天下；一面起大兵二十万，来伐中原。",
    "q_fa_zhongyuan": "一面起大兵二十万，来伐中原。",
    "q_qiu_jiangwei": "求姜维进兵攻其北，许以平分天下；",
    "q_baiqi": "临行时，忽见一道白气，从地而起，遮断三军，对面不见。",
    "q_jiangyan_jian": "此气乃白虹也，主丧兵之兆。太傅只可回朝，不可伐魏。",
    "q_ke_nu_jiangyan": "汝安敢出不利之言，以慢吾军心！",
    "q_bian_jiangyan": "叱武士斩之。众皆告免，恪乃贬蒋延为庶人，仍催兵前进。",
    "q_dingfeng_xincheng": "魏以新城为总隘口，若先取得此城，司马师破胆矣。",
    "q_ke_zhi_xincheng": "恪大喜，即趱兵直至新城。",
    "q_zhangte_shou": "守城牙门将军张特，见吴兵大至，闭门坚守。",
    "q_wei_si_mian": "恪令兵四面围定。",
    "q_liuxing_ma": "早有流星马报入洛阳。",
    "q_yusong_jian": "今诸葛恪困新城，且未可与战。吴兵远来，人多粮少，粮尽自走矣。待其将走，然后击之，必得全胜。但恐蜀兵犯境，不可不防。",
    "q_shi_ran_qiyan": "师然其言，遂令司马昭引一军助郭淮防姜维；毋丘俭、胡遵拒住吴兵。",
    "q_juzhu_wubing": "毋丘俭、胡遵拒住吴兵。",

    # ── 新城之围与张特缓兵 ──────────────────────────────────────────────────
    "q_ke_lianyue": "却说诸葛恪连月攻打新城不下，下令众将：“并力攻城，怠慢者立斩。”",
    "q_jinGong_ling": "并力攻城，怠慢者立斩。",
    "q_zhujiang_fenli": "于是诸将奋力攻打。城东北角将陷。",
    "q_cheng_jiao_xian": "城东北角将陷。",
    "q_zhangte_dingji": "张特在城中定下一计：乃令一舌辩之士，赍捧册籍，赴吴寨见诸葛恪，告曰：",
    "q_ceji": "乃令一舌辩之士，赍捧册籍，赴吴寨见诸葛恪",
    "q_wei_guo_zhi_fa": "魏国之法：若敌人困城，守城将坚守一百日，而无救兵至，然后出城降敌者，家族不坐罪。",
    "q_jiushi_yuri": "今将军围城已九十余日；望乞再容数日，某主将尽率军民出城投降。",
    "q_ceji_chengshang": "今先具册籍呈上。",
    "q_ke_shenxin": "恪深信之，收了军马，遂不攻城。",
    "q_huanbing_zhiji": "原来张特用缓兵之计，哄退吴兵，遂拆城中房屋，于破城处修补完备，乃登城大骂曰：",
    "q_chai_fangwu": "遂拆城中房屋，于破城处修补完备",
    "q_zhangte_dama": "吾城中尚有半年之粮，岂肯降吴狗耶！尽战无妨！",
    "q_ke_cuibing": "恪大怒，催兵打城。城上乱箭射下。",
    "q_liangjian_xia": "城上乱箭射下。",
    "q_ke_zhongjian": "恪额上正中一箭，翻身落马。",
    "q_jinchuang": "诸将救起还寨，金疮举发。",
    "q_wuzhanxin": "众军皆无战心；又因天气亢炎，军士多病。",
    "q_yingli_gao": "恪金疮稍可，欲催兵攻城。营吏告曰：“人人皆病，安能战乎？”",
    "q_renren_jie_bing": "人人皆病，安能战乎？",
    "q_bingzhe_zhan": "再说病者斩之！",
    "q_taozhe_wushu": "众军闻知，逃者无数。",
    "q_cailin_touwei": "忽报都督蔡林引本部军投魏去了。",
    "q_ke_bianshi": "恪大惊，自乘马遍视各营，果见军士面色黄肿，各带病容。",
    "q_ke_huanwu": "遂勒兵还吴。",
    "q_xizuo_bao": "早有细作报知毋丘俭。",
    "q_jian_yansha": "俭尽起大兵，随后掩杀。",
    "q_wubing_dabai": "吴兵大败而归，恪甚羞惭，托病不朝。",

    # ── 诸葛恪失势与孙峻谋诛 ────────────────────────────────────────────────
    "q_liang_wenAn": "吴主孙亮自幸其宅问安，文武官僚皆来拜见。",
    "q_ke_souqiu": "恪恐人议论，先搜求众官将过失，轻则发遣边方，重则斩首示众。",
    "q_neiwai_songju": "于是内外官僚，无不悚惧。",
    "q_zhangyue_zhuen": "又令心腹将张约、朱恩管御林军。以为牙爪。",
    "q_zhangyue_zhuen2": "又令心腹将张约、朱恩管御林军。",
    "q_sunjun_shenshi": "却说孙峻字子远，乃孙坚弟孙静曾孙，孙恭之子也；孙权存日，甚爱之，命掌御林军马。",
    "q_sunjun_zhang": "孙权存日，甚爱之，命掌御林军马。",
    "q_duo_quan": "今闻诸葛恪令张约、朱恩二人掌御林军，夺其权，心中大怒。",
    "q_tengyin_youxi": "太常卿滕胤，素与诸葛恪有隙，乃乘间说峻曰：",
    "q_tengyin_shuo": "诸葛恪专权恣虐，杀害公卿，将有不臣之心。公系宗室，何不早图之？",
    "q_jun_qingzhi": "我有是心久矣；今当即奏天子，请旨诛之。",
    "q_mizou": "于是孙峻、滕胤入见吴主孙亮，密奏其事。",
    "q_liang_kongbu": "朕见此人，亦甚恐怖；常欲除之，未得其便。今卿等果有忠义，可密图之。",
    "q_liang_midu": "今卿等果有忠义，可密图之。",
    "q_yin_xianji": "陛下可设席召恪，暗伏武士于壁衣中，掷杯为号，就席间杀之，以绝后患。",
    "q_bishi_weihao": "掷杯为号",
    "q_anfu_wushi": "暗伏武士于壁衣中",
    "q_liang_congzhi": "亮从之。",

    # ── 恪宅妖异与赴宴 ──────────────────────────────────────────────────────
    "q_ke_tuobing": "却说诸葛恪自兵败回朝，托病居家，心神恍惚。",
    "q_chuanna_xiaoxiao": "一日，偶出中堂，忽见一人穿麻挂孝而入。",
    "q_ke_kawen": "恪令拿下拷问，其人告曰：",
    "q_qiren_gao": "某因新丧父亲，入城请僧追荐；初见是寺院而入，却不想是太傅之府。却怎生来到此处也？",
    "q_junshi_gao": "某等数十人，皆荷戈把门，未尝暂离，并不见一人入来。",
    "q_jinshu_zhan": "恪大怒，尽数斩之。",
    "q_zhongliang_zhe": "恪自出视之，见中梁折为两段。",
    "q_yinfeng_suoming": "恪惊归寝室，忽然一阵阴风起处，见所杀披麻人与守门军士数十人，各提头索命。",
    "q_ke_jingdao": "恪惊倒在地，良久方苏。",
    "q_xueshui_chou": "次早洗面，闻水甚血臭。",
    "q_huanshui": "恪叱侍婢，连换数十盆，皆臭无异。",
    "q_tianzi_shi": "恪正惊疑间，忽报天子有使至，宣太傅赴宴。",
    "q_ke_chezhang": "恪令安排车仗。",
    "q_huangquan": "方欲出府，有黄犬衔住衣服，嘤嘤作声，如哭之状。",
    "q_qian_baihong": "行不数步，见车前一道白虹，自地而起，如白练冲天而去。",
    "q_zhangyue_migao": "恪甚惊怪，心腹将张约进车前密告曰；“今日宫中设宴，未知好歹，主公不可轻入。”",
    "q_zhangyue_gao": "今日宫中设宴，未知好歹，主公不可轻入。",
    "q_ke_huiche": "恪听罢，便令回车。",
    "q_jun_yin_zhi": "行不到十余步，孙峻、滕胤乘马至车前曰：“太傅何故便回？”",
    "q_ke_futong": "吾忽然腹痛，不可见天子。",
    "q_yin_quanxing": "朝廷为太傅军回，不曾面叙，故特设宴相召，兼议大事。太傅虽感贵恙，还当勉强一行。",
    "q_ke_rugong": "恪从其言，遂同孙峻、滕胤入宫，张约亦随入。",

    # ── 席间杀恪 ────────────────────────────────────────────────────────────
    "q_jiuxi": "恪见吴主孙亮，施礼毕，就席而坐。",
    "q_ke_yijiu": "亮命进酒，恪心疑，辞曰：“病躯不胜杯酌。”",
    "q_bingqu": "病躯不胜杯酌。",
    "q_yaojiu_wen": "孙峻曰：“太傅府中常服药酒，可取饮乎？”",
    "q_ke_yaojiu": "遂令从人回府取自制药酒到，恪方才放心饮之。",
    "q_liang_qishen": "酒至数巡，吴主孙亮托事先起。",
    "q_jun_xiaDian": "孙峻下殿，脱了长服，着短衣，内披环甲，手提利刃，上殿大呼曰：“天子有诏诛逆贼！”",
    "q_tianzi_zhao": "天子有诏诛逆贼！",
    "q_ke_touLuo": "诸葛恪大惊，掷杯于地，欲拔剑迎之，头已落地。",
    "q_zhangyue_ying": "张约见峻斩恪，挥刀来迎。",
    "q_jun_shoushang": "峻急闪过，刀尖伤其左指。",
    "q_kan_zhangyue": "峻转身一刀，砍中张约右臂。",
    "q_wushi_yongchu": "武士一齐拥出，砍倒张约，剁为肉泥。",
    "q_shou_jiajuan": "孙峻一面令武士收恪家眷，一面令人将张约并诸葛恪尸首，用芦席包裹，以小车载出，弃于城南门外石子岗乱冢坑内。",
    "q_luXi_baoguo": "用芦席包裹",
    "q_qi_shizigang": "以小车载出，弃于城南门外石子岗乱冢坑内。",

    # ── 恪家被诛 / 评语应验 / 孙峻掌权 ──────────────────────────────────────
    "q_ke_qi": "却说诸葛恪之妻正在房中心神恍惚，动止不宁，忽一婢女入房。",
    "q_ke_qi_wen": "恪妻问曰：“汝遍身如何血臭？”",
    "q_binu_dajiao": "其婢忽然反目切齿，飞身跳跃，头撞屋梁，口中大叫：“吾乃诸葛恪也！被奸贼孙峻谋杀！”",
    "q_binu_zhiyan": "吾乃诸葛恪也！被奸贼孙峻谋杀！",
    "q_hejia_haoku": "恪合家老幼，惊惶号哭。",
    "q_junma_wei": "不一时，军马至，围住府第，将恪全家老幼，俱缚至市曹斩首。",
    "q_quanjia_zhan": "将恪全家老幼，俱缚至市曹斩首。",
    "q_jianxing_erNian": "时吴建兴二年冬十月也。",
    "q_jin_yi": "昔诸葛瑾存日，见恪聪明尽显于外，叹曰：“此子非保家之主也！”",
    "q_jin_yiyu": "此子非保家之主也！",
    "q_zhangji_yu": "又魏光禄大夫张缉，曾对司马师曰：“诸葛恪不久死矣。”",
    "q_zhangji_bujiu": "诸葛恪不久死矣。",
    "q_ji_guQi": "师问其故，缉曰：“威震其主，何能久乎？”",
    "q_wei_zhen_qizhu": "威震其主，何能久乎？",
    "q_guo_zhong_qiyan": "至此果中其言。",
    "q_feng_jun": "却说孙峻杀了诸葛恪，吴主孙亮封峻为丞相、大将军、富春侯，总督中外诸军事。",
    "q_zongdu": "总督中外诸军事。",
    "q_quanbing_gui": "自此权柄尽归孙峻矣。",

    # ── 回末：姜维再举 ──────────────────────────────────────────────────────
    "q_jw_chengdu": "且说姜维在成都，接得诸葛恪书，欲求相助伐魏",
    "q_jw_ruChao": "遂入朝，奏准后主，复起大兵，北伐中原。",
    "q_weizhi_shengsu": "未知胜负如何，且看下文请看下文分解。",
    "q_weizhi_shengsu2": "未知胜负如何，且看下文分解。",
    "q_duiju": "正是：一度兴师未奏绩，两番讨贼欲成功。",
    "q_shishi": "一度兴师未奏绩，两番讨贼欲成功。",
}


# --------------------------------------------------------------------------- 解析
class Fail(Exception):
    pass


_CACHE = {}


def ref(key):
    """引文 key → quoteRef（偏移由精确子串搜索算出）。"""
    if key in _CACHE:
        return dict(_CACHE[key])
    if key not in Q:
        raise Fail("引文 key 未在 Q 表定义：%s" % key)
    s = Q[key]
    n_global = TEXT.count(s)
    if n_global != 1:
        raise Fail("引文全文命中数 %d（要求 1）：%r" % (n_global, s[:40]))
    i = TEXT.find(s)
    n_range = SEG.count(s)
    if n_range != 1:
        raise Fail("引文区间内命中数 %d（要求 1）：%r" % (n_range, s[:40]))
    assert TEXT[i:i + len(s)] == s, "往返失败"
    r = {
        "quote": s,
        "start": i,
        "end": i + len(s),
        "sourceHash": PROMPT_SOURCE_HASH,
    }
    _CACHE[key] = r
    return dict(r)


def refs(keys):
    return [ref(k) for k in keys]
