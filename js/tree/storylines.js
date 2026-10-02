/* Castline · storylines.js — 剧情线解析引擎（window.CLStory）· v41.0
 * 契约：js/PLOT-CONTRACT.md 第 2 节 · briefs/PLAN-V45-LOGICAL-TREE.md。
 * 纯函数、零依赖、确定性；不碰 DOM、不碰 three.js。
 * v41 默认「严格来源结构」：父线 / 挂点 / 线归属只来自 graph.storylines，不推导、不补孤点线；
 * 无来源线时返回时间索引（threads 为空，不构造叙事关系）。旧推导路径只在 opts.legacy / opts.noModel 下启用。
 *
 * 读法：一部作品的剧情点是「一串带人的事件」。这里做四件事 ——
 *   1) 规范化并稳定排序，给出章节轴（order → 章节序 → 原下标，三级键，重复 order 也不会抖动）；
 *   2) 把「两个事件是不是同一条线」量化成亲和度：四路证据加权（见 AFF_* 的权重理由）；
 *   3) 每个事件在窗口内挑最佳前驱 → 森林 → 重路径分解成一批链，一条链就是一条剧情线；
 *   4) 按「主线度」装主干，主干允许中途换手（前一段走完由另一组人接着推进），每次换手留下凭据。
 *
 * 「线的长度」= 该线的事件数（thread.len）。章节只用来算距离、跨度与断口 ——
 * 因为同一章里可以塞十个剧情点，用章节当长度会把密集章压成一个点。
 */
(function () {
  'use strict';

  // ───────────────────────────────── 色调与类型表（与 scene.js 的 TONE / css .tag.kind-* 同源，不自造 hex）
  var KIND_COLOR = { '高燃': 0xffd166, '转折': 0xffb45c, '抉择': 0xc8a7ff, '冲突': 0xff5d73, '关系': 0xff9ad5, '领悟': 0x7af0c8, '日常': 0x9a92b8 };
  // 主干每段一个色：段与段的接缝必须一眼分得开，所以用色调脊轮转，而不是「主导类型色」——
  // 后者会让相邻两段撞成同一个黄，换手的视觉证据就没了。
  var MAIN_COLOR = [0xffb45c, 0x3fd6a8, 0x8a6cd8, 0xc84dff, 0xfff1da];
  var KINDS = { '高燃': 1, '转折': 1, '抉择': 1, '冲突': 1, '关系': 1, '领悟': 1, '日常': 1 };
  // kind 权重：一个剧情点在「书的骨架」里占多重。高燃/转折是骨节，日常是填充。
  var KIND_W = { '高燃': 1, '转折': 0.95, '抉择': 0.9, '冲突': 0.85, '领悟': 0.7, '关系': 0.6, '日常': 0.4 };
  // 张力族：thread.heat = 这四类事件的加权占比（契约 §2 Thread.heat）
  var TENSE = { '高燃': 1, '转折': 1, '抉择': 1, '冲突': 1 };
  // kind 连续性的三个族：同族的事件更可能是同一条线在推进
  var FAMILY = { '高燃': 'push', '转折': 'push', '抉择': 'push', '冲突': 'push', '领悟': 'inner', '关系': 'inner', '日常': 'flat' };
  // 收束用的「收尾类型」：契约 §2「领悟/抉择/高燃 收尾」
  var CLOSE_KIND = { '领悟': 1, '抉择': 1, '高燃': 1 };
  var ROLE_IMP = { '主角': 0.96, '反派': 0.88, '核心配角': 0.74, '配角': 0.45, '功能性': 0.2 };
  var CORE_ROLE = { '主角': 1, '反派': 1, '核心配角': 1 };

  // ───────────────────────────────── 四路证据的权重（契约 §2 要求逐路写明「为什么是这个权重」）
  //
  // W_CAST 0.46 —— 共同角色（按重要度加权的 Jaccard）。最高，因为一条剧情线的定义就是「谁在担」：
  //   两个事件哪怕紧挨着、类型相同、用词相似，只要没有一个人重叠，它们几乎从不是同一条线
  //   （换场戏就是这么发生的）。这也是四路里唯一无法靠巧合刷高的证据 —— 章节近是必然的、
  //   词重合会被模板摘要刷满、kind 只有七种，只有「同一个人接着出现」是真信号。
  //   给 0.46（不到一半）而不是 0.6+：主线换手时新旧两拨人只共享一两个中量角色，
  //   若让它一票独大，换手的接缝会被判成「两条无关的线」，主干就接不上了。
  var W_CAST = 0.46;
  // W_CHAP 0.24 —— 章节距离衰减。第二强：叙事是有邻接性的，隔了二十章的两个点很难算一条线在走。
  //   但它必须能被 W_CAST 反超 —— 一条线完全可以沉睡十章再回来（伏笔线就是这样），
  //   如果距离主导，结果会退化成「每章一条线」的平庸切分，树上就只剩章节而没有线。
  var W_CHAP = 0.24;
  // W_TOK 0.20 —— 标题+摘要的中文二元 shingle 重合（Dice）。第三，但不可省：
  //   它是唯一能抓住「换了人、母题还在」的一路（底片 / 编号 / 塔簿这种物件线索），
  //   而这正是主线换手最需要的凭据。压到 0.20 是因为真实图谱的摘要常是模板句
  //   （「A、B 在此章交锋」），词重合会被系统性刷高，单靠它会把全书粘成一坨。
  var W_TOK = 0.20;
  // W_KIND 0.10 —— kind 连续性。最低：只有七种类型，两个随机事件同类型的先验概率就有 1/7，
  //   信息量天生小，它的作用只是「让一串冲突留在一起」这种平局裁决。给高了会按类型聚线，
  //   出来一条「所有冲突线」，那是标签而不是剧情线。
  var W_KIND = 0.10;
  // 四路之和 = 1.00，亲和度天然落在 0..1，阈值才有可比性。

  // 证据门：共同角色为 0 且词重合低于此值 → 亲和度直接判 0。
  // 少了这道门，「章节近 + 同类型」两路加起来就有 0.34，足以把毫不相干的相邻事件串成链，
  // 于是全书变成一条按章节走的长龙 —— 这是最容易糊过去也最没用的结果。
  var GATE_TOK = 0.10;
  var LINK_MIN = 0.28;          // 成链阈值：一个人共担 + 相邻章 + 同族 ≈ 0.40 过线；只有一个小角色 + 隔三章 ≈ 0.16 落选
  var MAX_SEG = 12;             // 主干分段上限：再多就不是「换手」而是碎片，宁可截断并 warn
  var SEAM_W = 4;               // 接缝取样窗口：两段各取 4 个事件算共同角色，避免被单个事件的偶然同名带偏
  var PARALLEL_J = 0.34;        // 并流判据：接缝共同角色加权 Jaccard ≥ 此值且两链章节重叠
  var NAME_MAX = 14;            // 线名 ≤14 字（契约）
  var THEME_MAX = 40;           // 主题 ≤40 字（契约）

  // 停用词：只挡「哪里都在、区分不出线」的字词。这张表同时给两处用 ——
  // shingle 重合（去掉功能词才不会把两句无关的话算成相似）与线名候选（线名里不该出现「已经」）。
  var STOP_CH = '的了是在和与也就都很更还又把被将从对为以以及其而或但并自己他她它们这那些个一二三四五六七八九十百千不没有上下中前后里外时年月日人多少大小新旧再最只会能要说着过来去到给让向于之所因此如若则乃者吧呢啊哦嗯们你我他';
  var STOP_2 = '一个 自己 他们 她们 我们 你们 这个 那个 什么 已经 可以 没有 不是 就是 以及 于是 因为 所以 但是 然后 之后 之前 第一 一次 一场 一夜 同时 终于 决定 出现 发现 开始 结束 一起 两人 三人 所有 全部 其中 之间 里面 外面 上面 下面 时候 事件 此章 交锋 一句 一半 那些 这些 如果 虽然 而且 并且 只是 还是 也是 什么样';

  var STOPC = {}, STOP2 = {};
  (function () {
    var i;
    for (i = 0; i < STOP_CH.length; i++) STOPC[STOP_CH.charAt(i)] = 1;
    var a = STOP_2.split(' ');
    for (i = 0; i < a.length; i++) if (a[i]) STOP2[a[i]] = 1;
  })();

  // ───────────────────────────────── 小工具
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function r3(x) { return Math.round(x * 1000) / 1000; }
  function r6(x) { return Math.round(x * 1e6) / 1e6; }
  function hash(s) { var h = 2166136261, i; for (i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; } return h; }
  function hex8(h) { var s = (h >>> 0).toString(16); while (s.length < 8) s = '0' + s; return s; }
  function str(v) { return v == null ? '' : String(v); }
  function isCJK(c) { return (c >= 0x3400 && c <= 0x9fff) || (c >= 0xf900 && c <= 0xfaff); }
  function isAl(c) { return (c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122); }
  function cut(s, n) { s = str(s); return s.length <= n ? s : s.slice(0, n); }

  /** 截到 n 字，但尽量停在标点上 —— 主题是给人读的，砍在词中间比短一点更难看 */
  function cutSoft(s, n) {
    s = str(s).replace(/\s+/g, ' ');
    if (s.length <= n) return s;
    var head = s.slice(0, n), i, best = -1, p = '，。；、：！？,.;:!?';
    for (i = head.length - 1; i >= Math.floor(n * 0.5); i--) if (p.indexOf(head.charAt(i)) >= 0) { best = i; break; }
    return best > 0 ? head.slice(0, best) : head;
  }

  // ───────────────────────────────── 分析期状态（单线程 JS，一次分析一套；与 constellation.js 的写法一致）
  var EV = [], CH = [], CHARS = [], CIDX = {}, IMP = [], CORE = [], CAMP = [];
  var TOKN = 0, TOKD = {}, DF = [], ASCII_TOK = {}, NEV = 0, TAU = 1, WIN = 16, AXMAX = 2;

  // ───────────────────────────────── 1 · 规范化
  /** 角色表：importance 可能是 0..1 也可能是 0..100，也可能缺；缺了用 role 兜底 */
  function prepChars(graph) {
    var cs = (graph && graph.characters) || [], i, j, mx = 0, v;
    CHARS = []; CIDX = {}; IMP = []; CORE = []; CAMP = [];
    for (i = 0; i < cs.length; i++) {
      var c = cs[i] || {}, nm = str(c.name).trim();
      if (!nm || CIDX[nm] != null) continue;                 // 同名只取第一条：后面的引用无法区分，硬合并
      CIDX[nm] = CHARS.length; CHARS.push(c);
      v = typeof c.importance === 'number' && isFinite(c.importance) ? c.importance : -1;
      IMP.push(v); CORE.push(CORE_ROLE[str(c.role)] ? 1 : 0); CAMP.push(str(c.camp));
      if (v > mx) mx = v;
    }
    // 两种刻度共存（0..1 与 0..100）：以全表最大值判一次，别逐条猜，否则同一份图谱会出现两种量纲
    var div = mx > 1.5 ? 100 : 1;
    for (i = 0; i < IMP.length; i++) {
      IMP[i] = IMP[i] < 0 ? (ROLE_IMP[str(CHARS[i].role)] || 0.35) : clamp(IMP[i] / div, 0, 1);
      if (IMP[i] >= 0.7) CORE[i] = 1;                        // 重要度够高的配角也算核心：role 字段常年缺失，不能只信它
    }
    // 别名 → 本名：事件里写别名（「小昭」）时必须能落到同一个人身上
    for (i = 0; i < CHARS.length; i++) {
      var al = CHARS[i].aliases;
      if (!al || !al.length) continue;
      for (j = 0; j < al.length; j++) { var a = str(al[j]).trim(); if (a && CIDX[a] == null) CIDX[a] = i; }
    }
  }

  /** 事件表：三级稳定排序 + 章节轴 + 权重 + shingle */
  function prepEvents(graph) {
    var raw = (graph && graph.events) || [], i, j, e;
    // 预排序的章节序：按「在原数组里第一次出现」定，这是唯一不依赖章节名格式（第1章 / 序 / Chapter 3）的顺序
    var pre = {}, preN = 0, list = [];
    for (i = 0; i < raw.length; i++) {
      e = raw[i]; if (!e || typeof e !== 'object') continue;
      var cn = str(e.chapter).trim();
      if (pre[cn] == null) pre[cn] = preN++;
      var ord = typeof e.order === 'number' && isFinite(e.order) ? e.order : (parseFloat(e.order) || null);
      list.push({ raw: e, i: i, ord: ord == null ? Infinity : ord, pc: pre[cn], cn: cn });
    }
    list.sort(function (a, b) { return a.ord - b.ord || a.pc - b.pc || a.i - b.i; });

    // 章节轴按排序后的首次出现重算：轴必须与 events 同序，否则 D 的横轴会倒着走
    CH = []; var cmap = {};
    EV = [];
    var sum = [], mxw = 0;
    for (i = 0; i < list.length; i++) {
      var it = list[i], r = it.raw;
      if (cmap[it.cn] == null) { cmap[it.cn] = CH.length; CH.push({ name: it.cn, idx: CH.length, n: 0 }); }
      var ci = cmap[it.cn]; CH[ci].n++;
      var kind = str(r.kind).trim(); if (!KINDS[kind]) kind = '日常';   // 出现别的词就归日常（契约 §1）
      var cast = [], seen = {}, ids = [], w = 0;
      var rc = r.characters || [];
      for (j = 0; j < rc.length; j++) {
        var nm = str(rc[j]).trim(); if (!nm) continue;
        var ci2 = CIDX[nm];
        if (ci2 == null) { if (!seen['?' + nm]) { seen['?' + nm] = 1; cast.push({ n: nm, ci: -1, w: 0.12 }); w += 0.12; } continue; }
        if (seen[ci2]) continue; seen[ci2] = 1;
        cast.push({ n: CHARS[ci2].name, ci: ci2, w: IMP[ci2] }); ids.push(ci2); w += IMP[ci2];
      }
      // 参与角色按重要度降序（契约 Ev.cast）；同权重按名字定序，保证逐字节确定
      cast.sort(function (a, b) { return b.w - a.w || (a.n < b.n ? -1 : a.n > b.n ? 1 : 0); });
      ids.sort(function (a, b) { return a - b; });
      var cs = {}; for (j = 0; j < ids.length; j++) cs[ids[j]] = 1;
      var title = str(r.title).trim(), summary = str(r.summary).trim();
      var ee = {
        i: EV.length, order: EV.length + 1, chapter: it.cn, chapIdx: ci,
        title: title, summary: summary, kind: kind, quote: str(r.quote).trim(),
        cast: cast, cs: cs, cw: w, ax: 0, w: 0,
        ptxt: title + '　' + cutSoft(summary, 30), tid: null
      };
      EV.push(ee);
      var rw = w * (KIND_W[kind] || 0.4);
      sum.push(rw); if (rw > mxw) mxw = rw;
    }
    NEV = EV.length;
    for (i = 0; i < NEV; i++) EV[i].w = mxw > 0 ? r3(clamp(sum[i] / mxw, 0, 1)) : 0.5;

    // 时间轴：章节够多就用章节，否则（整本一章 / 没有章节字段）用事件下标折出一条 12 段的伪轴 ——
    // 不然章节距离这一路会全程为 0，等于白给 0.24 的权重，任何两个事件都「紧挨着」。
    var useCh = CH.length >= 3, bucket = Math.max(1, Math.ceil(NEV / 12));
    for (i = 0; i < NEV; i++) EV[i].ax = useCh ? EV[i].chapIdx : Math.floor(i / bucket);
    AXMAX = NEV ? EV[NEV - 1].ax + 1 : 1;
    TAU = clamp(Math.round(AXMAX / 10), 1, 6);
    var epc = NEV / Math.max(1, AXMAX);
    WIN = clamp(Math.round(epc * 8), 12, 40);               // 前驱搜索窗：约 8 个「章」的回溯量，密集章自动放宽
  }

  /** 中文二元 shingle：零依赖分词的最稳替代。标点与拉丁串是切分点，
   *  避免跨短语生成假词（「昭阳，苏晚」不该产出「阳苏」）。拉丁/数字串整段成一个 token。 */
  function shingle(text) {
    var out = [], i, n = text.length, run = '', c;
    for (i = 0; i <= n; i++) {
      c = i < n ? text.charCodeAt(i) : 0;
      if (i < n && (isCJK(c) || isAl(c))) { run += text.charAt(i); continue; }
      if (run) {
        if (isAl(run.charCodeAt(0))) { if (run.length >= 2) out.push(run.toUpperCase()); }
        else if (run.length === 1) { if (!STOPC[run]) out.push(run); }
        else for (var k = 0; k + 1 < run.length; k++) {
          var g = run.substr(k, 2);
          if (STOP2[g]) continue;
          if (STOPC[g.charAt(0)] && STOPC[g.charAt(1)]) continue;   // 两个功能字凑的二元词毫无区分力
          out.push(g);
        }
        run = '';
      }
    }
    return out;
  }

  /** token 字典化：亲和度里要做几十万次交集，字符串哈希太贵 —— 转成有序 int 数组后归并求交 */
  function prepTokens() {
    var i, j, t, id, gs;
    TOKN = 0; TOKD = {}; DF = []; ASCII_TOK = {};
    for (i = 0; i < NEV; i++) {
      gs = shingle(EV[i].title + '　' + EV[i].summary);
      var set = {}, ids = [];
      for (j = 0; j < gs.length; j++) {
        t = gs[j];
        if (set[t]) continue; set[t] = 1;
        id = TOKD[t];
        if (id == null) { id = TOKD[t] = TOKN++; DF.push(0); if (isAl(t.charCodeAt(0))) ASCII_TOK[id] = t; }
        DF[id]++; ids.push(id);
      }
      ids.sort(function (a, b) { return a - b; });
      EV[i].tid = ids;
    }
  }

  // ───────────────────────────────── 2 · 亲和度（四路融合）
  function castJac(a, b) {
    // 加权 Jaccard：∩ 与 ∪ 都按角色重要度计。主角共担一个事件的分量远大于两个功能性角色共担
    var sh = 0, i, ca = a.cast, cb = b.cast;
    if (!ca.length || !cb.length) return 0;
    for (i = 0; i < ca.length; i++) if (ca[i].ci >= 0 && b.cs[ca[i].ci]) sh += ca[i].w;
    if (sh <= 0) return 0;
    var un = a.cw + b.cw - sh;
    return un > 0 ? sh / un : 0;
  }
  function tokDice(a, b) {
    var A = a.tid, B = b.tid, la = A.length, lb = B.length;
    if (!la || !lb) return 0;
    var i = 0, j = 0, sh = 0;
    while (i < la && j < lb) { if (A[i] === B[j]) { sh++; i++; j++; } else if (A[i] < B[j]) i++; else j++; }
    return sh ? 2 * sh / (la + lb) : 0;
  }
  function kindCont(ka, kb) {
    if (ka === kb) return 1;                                  // 同类型：一串冲突留在一起
    return FAMILY[ka] === FAMILY[kb] ? 0.55 : 0.15;           // 同族算半分；跨族只留个底噪，不当零处理（转折→领悟是正常收束）
  }
  function affinity(a, b) {
    var jac = castJac(a, b), dice = tokDice(a, b);
    if (jac <= 0 && dice < GATE_TOK) return 0;                // 证据门：无人共担、无词延续 → 相邻本身不算证据
    var d = Math.abs(b.ax - a.ax);
    var dec = 1 / (1 + Math.pow(d / TAU, 1.35));              // 1.35 次幂：近处平缓（同章/邻章几乎同权），远处快掉
    return W_CAST * jac + W_CHAP * dec + W_TOK * dice + W_KIND * kindCont(a.kind, b.kind);
  }

  // ───────────────────────────────── 3 · 链构造（森林 → 重路径分解）
  function buildChains() {
    var prev = new Array(NEV), pa = new Array(NEV), kids = new Array(NEV), i, j, lo, a, best, bestA;
    var chapMax = Math.max(2, TAU * 3);
    for (j = 0; j < NEV; j++) { kids[j] = null; prev[j] = -1; pa[j] = 0; }
    for (j = 0; j < NEV; j++) {
      best = -1; bestA = 0; lo = j - WIN < 0 ? 0 : j - WIN;
      // 由近及远扫，命中用严格大于 → 同分自动取更近的那个前驱，结果与数组顺序无关
      for (i = j - 1; i >= lo; i--) {
        if (EV[j].ax - EV[i].ax > chapMax) continue;
        a = affinity(EV[i], EV[j]);
        if (a > bestA + 1e-9) { bestA = a; best = i; }
      }
      if (bestA >= LINK_MIN && best >= 0) { prev[j] = best; pa[j] = bestA; }
    }
    for (j = 0; j < NEV; j++) if (prev[j] >= 0) (kids[prev[j]] || (kids[prev[j]] = [])).push(j);
    // 每个前驱只把「最像的那个后继」留在自己这条线上，其余后继另起一条 —— 这就是分叉
    for (i = 0; i < NEV; i++) if (kids[i]) kids[i].sort(function (x, y) { return pa[y] - pa[x] || x - y; });
    var used = new Array(NEV), chains = [], cur, ch;
    for (j = 0; j < NEV; j++) {
      if (used[j]) continue;
      ch = []; cur = j;
      while (cur >= 0 && !used[cur]) { used[cur] = 1; ch.push(cur); cur = kids[cur] && kids[cur].length ? kids[cur][0] : -1; }
      chains.push(ch);
    }
    return { chains: chains, prev: prev, pa: pa };
  }

  /** 孤点并线：len==1 的链要么并进最亲和的成链，要么并进时间上最近的 ——
   *  留着不管的话它们既不算覆盖率、又要占一条线，树上会长出一堆一颗珠子的须。 */
  function absorbSingles(chains, warn) {
    var multi = [], single = [], i, j;
    for (i = 0; i < chains.length; i++) (chains[i].length > 1 ? multi : single).push(chains[i]);
    if (!single.length) return chains;
    if (!multi.length) {                                       // 整本书没有任何两点连得上：一条按序的链是唯一诚实答案
      var all = [];
      for (i = 0; i < chains.length; i++) all.push(chains[i][0]);
      all.sort(function (a, b) { return a - b; });
      warn.push('全书没有任何两个剧情点达到成链阈值，' + all.length + ' 个点按序并为一条线');
      return [all];
    }
    var own = {};                                              // evIdx → multi 下标
    for (i = 0; i < multi.length; i++) for (j = 0; j < multi[i].length; j++) own[multi[i][j]] = i;
    var moved = 0;
    single.sort(function (a, b) { return a[0] - b[0]; });
    for (i = 0; i < single.length; i++) {
      var e = single[i][0], bi = -1, ba = -1, k, lo = e - WIN < 0 ? 0 : e - WIN, hi = Math.min(NEV - 1, e + WIN);
      for (k = lo; k <= hi; k++) {
        if (own[k] == null) continue;
        var a = affinity(EV[Math.min(e, k)], EV[Math.max(e, k)]);
        var sc = a * 1000 - Math.abs(k - e);                   // 亲和度为主、距离做平局裁决（同分取更近）
        if (sc > ba) { ba = sc; bi = own[k]; }
      }
      if (bi < 0) { bi = 0; for (k = 0; k < multi.length; k++) if (Math.abs(multi[k][0] - e) < Math.abs(multi[bi][0] - e)) bi = k; }
      multi[bi].push(e); own[e] = bi; moved++;
    }
    for (i = 0; i < multi.length; i++) multi[i].sort(function (a, b) { return a - b; });
    if (moved) warn.push('孤点并线 ' + moved + ' 个（无独立成线的剧情点已并入最亲和的线）');
    return multi;
  }

  // ───────────────────────────────── 4 · 主线度
  /** 主线度 = 覆盖章节 × 累计事件权重 × 核心角色占比（契约 §2 第 3 条）。
   *  三项都先归一化到 0..1 再相乘：原式是三个量纲不同的数直接乘，长链会以章节数的一次方压死一切，
   *  归一化后「广度 × 分量 × 咖位」三者才真的能互相制衡。 */
  function chainInfo(ch, tw) {
    var i, j, chs = {}, nch = 0, sw = 0, cw = 0, coreW = 0, allW = 0, cast = {};
    for (i = 0; i < ch.length; i++) {
      var e = EV[ch[i]];
      if (!chs[e.chapIdx]) { chs[e.chapIdx] = 1; nch++; }
      sw += e.w;
      for (j = 0; j < e.cast.length; j++) {
        var c = e.cast[j];
        if (!cast[c.n]) { cast[c.n] = 1; allW += c.w; if (c.ci >= 0 && CORE[c.ci]) coreW += c.w; }
      }
    }
    var chapCov = nch / Math.max(1, CH.length);
    var wShare = tw > 0 ? sw / tw : 0;
    // 核心占比压进 0.08..1：全是小角色的线不该直接归零，否则这些线之间彻底无序，
    // 排序就退化成数组顺序（= 不确定的输入顺序）。
    var core = 0.08 + 0.92 * (allW > 0 ? coreW / allW : 0);
    return { evs: ch, len: ch.length, nch: nch, sumW: sw, first: ch[0], last: ch[ch.length - 1],
      fc: EV[ch[0]].chapIdx, lc: EV[ch[ch.length - 1]].chapIdx, fa: EV[ch[0]].ax, la: EV[ch[ch.length - 1]].ax,
      score: r6(chapCov * wShare * core) };
  }

  // ───────────────────────────────── 5 · 主干装配与换手
  function castOf(evs, lo, hi) {
    var m = {}, i, j, w = 0;
    for (i = lo; i <= hi && i < evs.length; i++) {
      var e = EV[evs[i]];
      for (j = 0; j < e.cast.length; j++) { var c = e.cast[j]; if (m[c.n] == null) { m[c.n] = c.w; w += c.w; } }
    }
    return { m: m, w: w };
  }
  function seamTok(evs, lo, hi) {
    var ids = {}, i, j, out = [];
    for (i = lo; i <= hi && i < evs.length; i++) { var t = EV[evs[i]].tid; for (j = 0; j < t.length; j++) ids[t[j]] = 1; }
    for (var k in ids) out.push(+k);
    out.sort(function (a, b) { return a - b; });
    return out;
  }
  function diceIds(A, B) {
    var i = 0, j = 0, sh = 0;
    if (!A.length || !B.length) return 0;
    while (i < A.length && j < B.length) { if (A[i] === B[j]) { sh++; i++; j++; } else if (A[i] < B[j]) i++; else j++; }
    return sh ? 2 * sh / (A.length + B.length) : 0;
  }
  /** 接缝证据：两段各取 SEAM_W 个事件，算共同角色的加权 Jaccard 与词重合；返回给换手判据用 */
  function seam(prevEvs, nextEvs) {
    var A = castOf(prevEvs, Math.max(0, prevEvs.length - SEAM_W), prevEvs.length - 1);
    var B = castOf(nextEvs, 0, SEAM_W - 1);
    var sh = 0, names = [], k;
    for (k in A.m) if (B.m[k] != null) { sh += A.m[k]; names.push(k); }
    var un = A.w + B.w - sh;
    names.sort(function (a, b) { return (B.m[b] + A.m[b]) - (B.m[a] + A.m[a]) || (a < b ? -1 : 1); });
    var dice = diceIds(seamTok(prevEvs, Math.max(0, prevEvs.length - SEAM_W), prevEvs.length - 1), seamTok(nextEvs, 0, SEAM_W - 1));
    return { jac: un > 0 ? sh / un : 0, shared: names, dice: dice };
  }
  /** 换手依据：从真实事件标题/摘要取一句，再补上共担的人名（也是真实字段，不是生成的漂亮话） */
  function handoffReason(ev, sm, gap) {
    var base = ev.title || cutSoft(ev.summary, 18) || ev.chapter;
    if (sm.shared.length) return cut(base + '（共 ' + sm.shared.slice(0, 3).join('、') + '）', 34);
    if (gap > 0) return cut(base + '（隔 ' + gap + ' 章无主干）', 34);
    return cut(base, 34);
  }
  /** 换手类型的判据（三种，逐条写清）：
   *   并流 = 接缝共担角色够重（加权 Jaccard ≥ PARALLEL_J）且两条链在章节上重叠过 —— 两条线本来同时在跑，合流后由新的一段继续；
   *   接棒 = 有共担角色但两链不重叠、且章节相接（gap ≤ 1）—— 在场的人把担子接了过去；
   *   断层 = 接缝没有任何共担角色，或主干在章节上跳了 ≥2 章 —— 主线是断开后另起的，不是接力。 */
  function handoffKind(sm, overlap, gap) {
    if (sm.shared.length && overlap && sm.jac >= PARALLEL_J) return '并流';
    if (sm.shared.length && gap <= 1) return '接棒';
    return '断层';
  }

  function assemble(infos, warn) {
    var i, order = [], used = {}, segs = [], seams = [];
    for (i = 0; i < infos.length; i++) order.push(i);
    order.sort(function (a, b) { return infos[b].score - infos[a].score || infos[a].first - infos[b].first || a - b; });
    if (!order.length) return { segs: segs, seams: seams, spare: [] };
    // 第 1 段：「最早开始」是硬条件，「主线度最高」在开篇候选池里排序。
    // 反过来（先按主线度、再看开始早晚）实测会让主干从第十章起跳 —— 全书最重的一条链常常在结尾，
    // 于是前九章一条主干都没有，支线只能全挂到末尾那几个事件上，树整棵是歪的。
    var minFa = Infinity, pool = [];
    for (i = 0; i < infos.length; i++) if (infos[i].fa < minFa) minFa = infos[i].fa;
    for (i = 0; i < order.length; i++) if (infos[order[i]].fa <= minFa + TAU) pool.push(order[i]);
    if (!pool.length) pool = order.slice(0);
    pool.sort(function (a, b) { return infos[b].score - infos[a].score || infos[a].first - infos[b].first || a - b; });
    var seed = pool[0];
    used[seed] = 1;
    segs.push({ ci: seed, evs: infos[seed].evs.slice(0) });
    var cursor = infos[seed].last, cursorAx = infos[seed].la, lastAx = EV[NEV - 1].ax;
    var gapMax = Math.max(3, Math.round(AXMAX * 0.25));
    var spareHeads = [];
    while (cursorAx < lastAx && segs.length < MAX_SEG) {
      var pick = -1, pickTail = null, pickScore = -1, pickGap = 0, minTail = 2, pass;
      // 两轮：先只收「至少两个事件」的续段。允许单事件段的话，主干会被一颗孤珠切成两次换手，
      // 相邻一个事件里连着记两条 Handoff —— 那是噪声，不是换手。只有一个事件也接不上时才放宽。
      for (pass = 0; pass < 2 && pick < 0; pass++, minTail = 1) for (i = 0; i < infos.length; i++) {
        if (used[i]) continue;
        var inf = infos[i];
        if (inf.la <= cursorAx) continue;                      // 不往前推进的线不配当主干下一段
        var tail = [], k;
        for (k = 0; k < inf.evs.length; k++) if (inf.evs[k] > cursor) tail.push(inf.evs[k]);
        if (tail.length < minTail) continue;
        var gap = EV[tail[0]].ax - cursorAx;
        if (gap > gapMax) continue;                            // 隔太远就不是同一条主线的续段，宁可主干在这里停住
        var sm = seam(segs[segs.length - 1].evs, tail);
        var link = clamp(sm.jac + 0.35 * sm.dice, 0, 1);
        // 主线度为主、接得上为辅：0.35 的底让「完全接不上但主线度极高」的线仍能作为断层续段被选中，
        // 否则一部前后两段人物毫无重叠的书会在中途彻底断掉，后半本没有主干。
        var sc = inf.score * (0.35 + 0.65 * link) / (1 + Math.max(0, gap) / TAU);
        if (sc > pickScore + 1e-12 || (Math.abs(sc - pickScore) <= 1e-12 && pick >= 0 && tail[0] < pickTail[0])) {
          pickScore = sc; pick = i; pickTail = tail; pickGap = gap;
        }
      }
      if (pick < 0) break;
      var inf2 = infos[pick], tail2 = pickTail;
      var sm2 = seam(segs[segs.length - 1].evs, tail2);
      var overlap = inf2.fa <= infos[segs[segs.length - 1].ci].la;
      // 被裁掉的前半段（在游标之前的那些事件）不能凭空消失 —— 它是这拨人「接过主线之前」的支线，
      // 原样退回支线池。这正是契约里那句「前半程走完由另一组人接着推进」的数据形态。
      if (tail2.length < inf2.evs.length) {
        var head = [], k2;
        for (k2 = 0; k2 < inf2.evs.length; k2++) if (inf2.evs[k2] <= cursor) head.push(inf2.evs[k2]);
        if (head.length) spareHeads.push(head);
      }
      used[pick] = 1;
      segs.push({ ci: pick, evs: tail2 });
      seams.push({ at: tail2[0], sm: sm2, gap: pickGap, overlap: overlap });
      cursor = tail2[tail2.length - 1]; cursorAx = EV[cursor].ax;
    }
    if (segs.length >= MAX_SEG && cursorAx < lastAx) warn.push('主干分段达到上限 ' + MAX_SEG + ' 段，后 ' + (lastAx - cursorAx) + ' 章未接入主干');
    var spare = [];
    for (i = 0; i < infos.length; i++) if (!used[i]) spare.push(infos[i].evs.slice(0));
    for (i = 0; i < spareHeads.length; i++) spare.push(spareHeads[i]);
    spare.sort(function (a, b) { return a[0] - b[0]; });
    return { segs: segs, seams: seams, spare: spare };
  }

  // ───────────────────────────────── 6 · 线名（TF 相对全书的反差）
  function idfOf(g) { var id = TOKD[g]; return id == null ? 0 : Math.log(NEV / (1 + DF[id])); }
  /** 一个词组的区分力只跟它最平庸的那一段一样强 → 取组成二元词里 idf 最小的那个。
   *  这条规则顺带把带功能词的词组全挡了（「在此」被停用词过滤 → idf 0 → 判 0）。 */
  function phraseIdf(p) {
    if (p.length < 2) return 0;
    var mn = 1e9, k;
    for (k = 0; k + 1 < p.length; k++) { var v = idfOf(p.substr(k, 2)); if (v <= 0) return 0; if (v < mn) mn = v; }
    return mn;
  }
  function nameOf(evs, lead) {
    // 只在这条线的事件上挖词组（每条线取样 ≤16 个事件、每条只用标题+摘要前 30 字）——
    // 3000 事件的大图谱上，全量挖 2..5 元词组会把解析预算吃掉一半，而线名并不需要那个精度。
    var i, j, L, docs = {}, inT = {}, samp = evs.length <= 16 ? evs : null;
    if (!samp) {
      samp = evs.slice(0).sort(function (a, b) { return EV[b].w - EV[a].w || a - b; }).slice(0, 16);
      samp.sort(function (a, b) { return a - b; });
    }
    for (i = 0; i < samp.length; i++) {
      var txt = EV[samp[i]].ptxt, tl = EV[samp[i]].title.length, seen = {}, n = txt.length, s = 0, c;
      for (j = 0; j <= n; j++) {
        c = j < n ? txt.charCodeAt(j) : 0;
        if (j < n && isCJK(c)) continue;
        if (j > s) {
          var run = txt.slice(s, j);
          for (L = 2; L <= 5 && L <= run.length; L++) for (var k = 0; k + L <= run.length; k++) {
            var p = run.substr(k, L);
            if (seen[p]) continue; seen[p] = 1;
            docs[p] = (docs[p] || 0) + 1;
            if (s + k + L <= tl) inT[p] = 1;                    // 出现在标题里的词组：作者自己挑过的词，加权
          }
        }
        s = j + 1;
      }
    }
    // 硬要求：词组至少在这条线的两个事件里重复出现。少了这一条，摘要里任意一段 5 字残片
    // 都能当线名（实测出过「始学徒生涯」「蓝偷偷翻看昭」这种断在词中间的废名）——
    // 「重复」是零依赖条件下唯一能证明这是个真词组而不是随手一刀的证据。
    var need = evs.length >= 2 ? 2 : 1, bestP = '', bestS = 0, key;
    for (key in docs) {
      if (docs[key] < need) continue;
      if (key === lead) continue;                              // 线名重复主导角色名等于没说话，lead 字段已经写了
      var idf = phraseIdf(key);
      if (idf <= 0) continue;
      var sc = docs[key] * idf * (1 + 0.08 * (key.length - 2)) * (inT[key] ? 1.25 : 1);
      if (sc > bestS + 1e-9 || (Math.abs(sc - bestS) <= 1e-9 && (key.length > bestP.length || (key.length === bestP.length && key < bestP)))) { bestS = sc; bestP = key; }
    }
    if (bestP) return bestP.length <= 2 && lead ? cut(lead + ' · ' + bestP, NAME_MAX) : cut(bestP, NAME_MAX);
    // 没有重复词组 → 退到本线最重那个事件的真实标题。标题是作者已经压过一次的句子，
    // 比「线索 · 某某」有信息，也仍然是原文字段（没有编造）。
    var hot = evs[0], hw = -1;
    for (i = 0; i < evs.length; i++) { var h = EV[evs[i]].w * (KIND_W[EV[evs[i]].kind] || 0.4); if (h > hw + 1e-12) { hw = h; hot = evs[i]; } }
    var t2 = EV[hot].title;
    return t2 && t2.length <= NAME_MAX && t2 !== lead ? t2 : '';
  }
  /** 英文短签：只从原文里真实出现的拉丁串取。中文图谱里没有英文就留空 ——
   *  译一个出来是编造（通用铁律 2），契约也明说 en 可为 ''。 */
  function enOf(evs) {
    var i, j, best = '';
    for (i = 0; i < evs.length; i++) {
      var t = EV[evs[i]].tid;
      for (j = 0; j < t.length; j++) {
        var s = ASCII_TOK[t[j]];
        if (s && (s.length > best.length || (s.length === best.length && s < best))) best = s;
      }
    }
    return cut(best, 12);
  }

  // ───────────────────────────────── 7 · 线的加料
  function enrich(th, taken) {
    var evs = th.events, i, j, kindMix = {}, sw = 0, tw = 0, cast = {}, names = [];
    var fc = EV[evs[0]].chapIdx, lc = fc, hotI = evs[0], hot = -1;
    for (i = 0; i < evs.length; i++) {
      var e = EV[evs[i]];
      kindMix[e.kind] = (kindMix[e.kind] || 0) + 1;
      sw += e.w; if (TENSE[e.kind]) tw += e.w;
      if (e.chapIdx < fc) fc = e.chapIdx; if (e.chapIdx > lc) lc = e.chapIdx;
      var h = e.w * (KIND_W[e.kind] || 0.4);
      if (h > hot + 1e-12) { hot = h; hotI = evs[i]; }
      for (j = 0; j < e.cast.length; j++) {
        var c = e.cast[j], o = cast[c.n];
        if (!o) { cast[c.n] = o = { name: c.n, n: 0, w: c.w, entry: evs[i], exit: evs[i], camp: c.ci >= 0 ? CAMP[c.ci] : '' }; names.push(c.n); }
        o.n++; o.exit = evs[i];
      }
    }
    var chSet = {}, nch = 0;
    for (i = 0; i < evs.length; i++) if (!chSet[EV[evs[i]].chapIdx]) { chSet[EV[evs[i]].chapIdx] = 1; nch++; }
    th.len = evs.length;
    th.span = { from: fc, to: lc, chapters: nch };
    th.kindMix = kindMix;
    th.heat = r3(sw > 0 ? clamp(tw / sw, 0, 1) : 0);           // 契约：张力 = 冲突/抉择/转折/高燃 的「加权占比」
    var lst = [];
    for (i = 0; i < names.length; i++) lst.push(cast[names[i]]);
    lst.sort(function (a, b) { return b.w - a.w || b.n - a.n || (a.name < b.name ? -1 : 1) });
    for (i = 0; i < lst.length; i++) lst[i].w = r3(lst[i].w);
    th.cast = lst;
    if (!th.lead) th.lead = lst.length ? lst[0].name : '';
    // 主题取「最重的那个事件」的真实摘要（没有摘要就退到标题），不改写、只截断
    var hotEv = EV[hotI];
    if (!th.theme) th.theme = cutSoft(hotEv.summary || hotEv.title, THEME_MAX);
    // 代表引句：从 heat 最高的事件往下找第一句非空的 quote（很多图谱的 quote 是空的）
    if (!th.quote) {
      var rank = evs.slice(0).sort(function (a, b) {
        var ha = EV[a].w * (KIND_W[EV[a].kind] || 0.4), hb = EV[b].w * (KIND_W[EV[b].kind] || 0.4);
        return hb - ha || a - b;
      });
      for (i = 0; i < rank.length; i++) if (EV[rank[i]].quote) { th.quote = cut(EV[rank[i]].quote, 60); break; }
      if (!th.quote) th.quote = '';
    }
    if (!th.title) {
      var nm = nameOf(evs, th.lead);
      th.title = nm || (th.lead ? '线索 · ' + th.lead : '线索');
    }
    // 撞名去重：两条线叫同一个名字，HUD 的线卡列表就读不出是两条。补主导角色，再撞就补首章名。
    if (taken) {
      if (taken[th.title]) { var alt = cut(th.title + ' · ' + th.lead, NAME_MAX); if (!taken[alt] && th.lead) th.title = alt; }
      if (taken[th.title]) { var alt2 = cut(th.title + ' · ' + EV[evs[0]].chapter, NAME_MAX); if (!taken[alt2]) th.title = alt2; }
      taken[th.title] = 1;
    }
    if (th.en == null) th.en = enOf(evs);
    th.color = th.kind === 'main' ? MAIN_COLOR[th.seg % MAIN_COLOR.length] : (KIND_COLOR[domKind(kindMix)] || KIND_COLOR['日常']);
    return th;
  }
  function domKind(mix) {
    var k, best = '', bs = -1;
    for (k in mix) { var s = mix[k] * (KIND_W[k] || 0.4); if (s > bs + 1e-12 || (Math.abs(s - bs) <= 1e-12 && k < best)) { bs = s; best = k; } }
    return best;
  }

  /** 收束 / 悬置：
   *   收束 = 末事件是领悟/抉择/高燃（明确的收尾类型），或与主干重新交汇（末事件的人在同章或下一章还出现在主干上）；
   *   悬置 = 既没收束、又在全书结束前就早早断掉（离末章超过 12% 的篇幅）。 */
  function closure(th, trunkByAx, lastAx) {
    var evs = th.events, last = EV[evs[evs.length - 1]];
    var rejoin = false, i, j, ax;
    for (ax = last.ax; ax <= last.ax + 1 && !rejoin; ax++) {
      var lst = trunkByAx[ax];
      if (!lst) continue;
      for (i = 0; i < lst.length && !rejoin; i++) {
        if (lst[i] === last.i) continue;
        var te = EV[lst[i]];
        for (j = 0; j < last.cast.length; j++) if (last.cast[j].ci >= 0 && te.cs[last.cast[j].ci]) { rejoin = true; break; }
      }
    }
    th.resolved = !!(CLOSE_KIND[last.kind] || rejoin);
    var early = Math.max(1, Math.round(AXMAX * 0.12));
    // 主干的中间各段天然「不收束」—— 它们是换手，不是悬置；只有最末一段停在半路才算主线悬着
    th.suspended = th.kind === 'main' && !th.lastSeg ? false : (!th.resolved && last.ax < lastAx - early);
    return th;
  }

  // ───────────────────────────────── 8 · 支线挂点
  function attachAll(threads, trunkEvs, warn, only) {
    var i, j, k, byAx = {}, mainOf = {};
    for (i = 0; i < threads.length; i++) if (threads[i].kind === 'main') for (j = 0; j < threads[i].events.length; j++) mainOf[threads[i].events[j]] = threads[i];
    for (i = 0; i < trunkEvs.length; i++) { var ax = EV[trunkEvs[i]].ax; (byAx[ax] || (byAx[ax] = [])).push(trunkEvs[i]); }
    var chapMax = Math.max(2, TAU * 3);
    var branchOf = {};
    for (i = 0; i < threads.length; i++) if (threads[i].kind !== 'main') for (j = 0; j < threads[i].events.length; j++) branchOf[threads[i].events[j]] = threads[i];
    for (i = 0; i < threads.length; i++) {
      var th = threads[i];
      if (th.kind === 'main') { th.parent = null; th.attach = null; th.depth = 0; continue; }
      if (only && !only[th.id]) continue;                       // model 已经给了挂点的线不动（契约 §2 第 7 条）
      var head = EV[th.events[0]], bestT = -1, bestTa = -1, bestTaf = 0, bestB = -1, bestBa = -1, bestBaf = 0;
      // 只在分叉点附近找挂点：支线是从主干上「那一刻」岔出去的，
      // 全主干扫一遍不但慢（3000 事件 × 200 条支线），还会把挂点甩到几十章之外。
      for (var ax2 = head.ax - chapMax; ax2 <= head.ax + 1; ax2++) {
        var lst = byAx[ax2];
        if (!lst) continue;
        for (k = 0; k < lst.length; k++) {
          var t = lst[k], a = affinity(EV[Math.min(t, head.i)], EV[Math.max(t, head.i)]);
          var sc = a * 1000 - Math.abs(head.ax - EV[t].ax);     // 亲和度为主、章节距离做平局裁决
          if (sc > bestTa) { bestTa = sc; bestT = t; bestTaf = a; }
        }
      }
      if (bestT < 0) {                                          // 附近没有主干（主干在这一段有断口）→ 退到全主干里最近的一个
        for (k = 0; k < trunkEvs.length; k++) if (bestT < 0 || Math.abs(trunkEvs[k] - th.events[0]) < Math.abs(bestT - th.events[0])) bestT = trunkEvs[k];
      }
      // 支线的支线：只有当「挂到另一条支线」明显比挂主干更贴时才降到 depth 2，否则末梢会泛滥成一片、
      // 树读不出层级。判据比的是**纯亲和度**（bestTaf/bestBaf），不能比带距离罚分的排序分 ——
      // 排序分会是负数，负数乘 1.15 反而变小，那条 margin 就整个反了（实测让 7 条线里冒出 4 条末梢）。
      // 父线必须起点更早、且自己是 depth 1 → 层级封在 0/1/2，且天然无环。
      for (k = 0; k < threads.length; k++) {
        var ot = threads[k];
        if (ot === th || ot.kind === 'main' || ot.depth !== 1) continue;
        if (ot.events[0] >= th.events[0]) continue;
        if (ot.events[ot.events.length - 1] < th.events[0] - WIN) continue;
        for (j = ot.events.length - 1; j >= 0; j--) {
          var oe = ot.events[j];
          if (oe > th.events[0]) continue;
          var a2 = affinity(EV[oe], head);
          var sc2 = a2 * 1000 - Math.abs(head.ax - EV[oe].ax);
          if (sc2 > bestBa) { bestBa = sc2; bestB = oe; bestBaf = a2; }
          break;                                                 // 每条候选支线只看它最靠近分叉点的那个事件
        }
      }
      if (bestB >= 0 && bestBaf >= LINK_MIN && bestBaf > bestTaf * 1.15 + 0.02 && branchOf[bestB]) {
        th.attach = bestB; th.parent = branchOf[bestB].id; th.depth = 2; th.kind = 'twig';
      } else if (bestT >= 0 && mainOf[bestT]) {
        th.attach = bestT; th.parent = mainOf[bestT].id; th.depth = 1; th.kind = 'branch';
      } else {
        th.attach = null; th.parent = null; th.depth = 1; th.kind = 'branch';
        warn.push('支线「' + th.title + '」找不到主干挂点（主干为空）');
      }
    }
  }

  // ───────────────────────────────── 9 · 交汇点
  /** 交汇 = 某个事件上，本线的人同时也在另一条线上活动（那条线在同章或邻章有事件）。
   *  事件是被线独占的（一个事件只属于一条线），所以「两线相交」只能靠人来定义。 */
  function junctions(threads, trunkT) {
    var i, j, k, thOf = {}, axOf = {}, charTh = {};
    for (i = 0; i < threads.length; i++) {
      var th = threads[i];
      for (j = 0; j < th.events.length; j++) { thOf[th.events[j]] = th.id; var ax = EV[th.events[j]].ax; (axOf[th.id + '|' + ax] = 1); }
      for (j = 0; j < th.cast.length; j++) (charTh[th.cast[j].name] || (charTh[th.cast[j].name] = [])).push(th.id);
    }
    var pair = {}, out = [];
    for (i = 0; i < NEV; i++) {
      var e = EV[i], mine = thOf[i];
      if (!mine) continue;
      for (j = 0; j < e.cast.length; j++) {
        var c = e.cast[j], lst = charTh[c.n];
        if (!lst || c.w < 0.25) continue;                        // 小角色到处都在，用它连线只会连出一张糊掉的网
        for (k = 0; k < lst.length; k++) {
          var oid = lst[k];
          if (oid === mine) continue;
          if (!axOf[oid + '|' + e.ax] && !axOf[oid + '|' + (e.ax - 1)] && !axOf[oid + '|' + (e.ax + 1)]) continue;
          var key = (mine < oid ? mine + '>' + oid : oid + '>' + mine);
          var cur = pair[key];
          var strength = c.w * e.w;
          if (!cur || strength > cur.s + 1e-12) pair[key] = { s: strength, at: i, a: mine < oid ? mine : oid, b: mine < oid ? oid : mine, cast: [c.n] };
          else if (cur.at === i && cur.cast.indexOf(c.n) < 0) cur.cast.push(c.n);
        }
      }
    }
    var keys = [];
    for (var kk in pair) keys.push(kk);
    keys.sort(function (a, b) { return pair[b].s - pair[a].s || pair[a].at - pair[b].at || (a < b ? -1 : 1); });
    var cap = clamp(Math.round(threads.length * 1.5), 6, 48);
    for (i = 0; i < keys.length && out.length < cap; i++) {
      var p = pair[keys[i]];
      p.cast.sort();
      out.push({ at: p.at, threads: [p.a, p.b], t: tOf(p.at, trunkT), cast: p.cast });
    }
    out.sort(function (a, b) { return a.at - b.at || (a.threads[0] < b.threads[0] ? -1 : 1); });
    return out;
  }
  /** 位置 t：主干上的事件用它在主干里的真实位置；不在主干上的按章节轴折算 —— B/D 都拿 t 放几何，不能有空 */
  function tOf(ev, trunkT) {
    if (trunkT.map[ev] != null) return trunkT.map[ev];
    return r6(AXMAX > 1 ? clamp(EV[ev].ax / (AXMAX - 1), 0, 1) : 0);
  }

  // ───────────────────────────────── 10 · 组装
  function emptyTree(reason, fp) {
    return { ok: false, reason: reason || '', src: 'derived', fp: fp || '',
      chapters: [], events: [], threads: [],
      trunk: { segments: [], events: [], len: 0, chapters: 0, gaps: [] },
      handoffs: [], junctions: [], cast: {}, warn: [], unresolved: [], pendingHandoffs: [],
      stats: { events: 0, threads: 0, main: 0, branches: 0, twigs: 0, trunkLen: 0, trunkChapters: 0, trunkSegs: 0,
        handoffs: 0, junctions: 0, maxBranchLen: 0, avgBranchLen: 0, suspended: 0, castCovered: 0, coverage: 0, ms: 0 } };
  }

  function outEvents() {
    var out = [], i, j;
    for (i = 0; i < NEV; i++) {
      var e = EV[i], cast = [];
      for (j = 0; j < e.cast.length; j++) cast.push(e.cast[j].n);
      out.push({ i: e.i, order: e.order, chapter: e.chapter, chapIdx: e.chapIdx, title: e.title,
        summary: e.summary, kind: e.kind, quote: e.quote, cast: cast, w: e.w });
    }
    return out;
  }

  function buildTrunk(threads, segs, seams) {
    var i, j, evs = [], segOut = [], map = {}, total = 0;
    for (i = 0; i < segs.length; i++) total += segs[i].evs.length;
    var run = 0;
    for (i = 0; i < segs.length; i++) {
      var s = segs[i], th = threads[i];
      // t0/t1 用「区间边界」而不是「首末事件的下标比」：后者会让单事件段出现 t0 === t1，
      // 契约要求 t0 < t1、且各段首尾相接（F 会断言）。区间边界天然平铺整个 [0,1]。
      var t0 = r6(run / total), t1 = r6((run + s.evs.length) / total);
      for (j = 0; j < s.evs.length; j++) { map[s.evs[j]] = r6(total > 1 ? (run + j) / (total - 1) : 0); evs.push(s.evs[j]); }
      segOut.push({ threadId: th.id, from: s.evs[0], to: s.evs[s.evs.length - 1], events: s.evs.slice(0),
        t0: t0, t1: t1, color: th.color, lead: th.lead });
      run += s.evs.length;
    }
    var chs = {}, nch = 0, gaps = [];
    for (i = 0; i < evs.length; i++) if (!chs[EV[evs[i]].chapIdx]) { chs[EV[evs[i]].chapIdx] = 1; nch++; }
    for (i = 1; i < evs.length; i++) {
      var d = EV[evs[i]].chapIdx - EV[evs[i - 1]].chapIdx;
      if (d > 1) gaps.push({ after: evs[i - 1], chapters: d - 1 });
    }
    return { trunk: { segments: segOut, events: evs, len: evs.length, chapters: nch, gaps: gaps },
      t: { map: map } };
  }

  function buildHandoffs(threads, segs, seams, trunkT) {
    var out = [], i;
    for (i = 0; i < seams.length; i++) {
      var s = seams[i], sm = s.sm;
      out.push({ at: s.at, from: threads[i].id, to: threads[i + 1].id, t: trunkT.map[s.at] != null ? trunkT.map[s.at] : 0,
        shared: sm.shared.slice(0, 8), reason: handoffReason(EV[s.at], sm, s.gap), kind: handoffKind(sm, s.overlap, s.gap) });
    }
    return out;
  }

  function buildCast(threads) {
    var out = {}, i, j, names = [];
    for (i = 0; i < CHARS.length; i++) { out[CHARS[i].name] = { threads: [], events: [], main: false, w: r3(IMP[i]) }; names.push(CHARS[i].name); }
    for (i = 0; i < NEV; i++) {
      var e = EV[i];
      for (j = 0; j < e.cast.length; j++) {
        var n = e.cast[j].n, o = out[n];
        if (!o) { o = out[n] = { threads: [], events: [], main: false, w: r3(e.cast[j].w) }; names.push(n); }
        o.events.push(i);
      }
    }
    for (i = 0; i < threads.length; i++) {
      var th = threads[i];
      for (j = 0; j < th.cast.length; j++) {
        var o2 = out[th.cast[j].name];
        if (!o2) continue;
        if (o2.threads.indexOf(th.id) < 0) o2.threads.push(th.id);
        if (th.kind === 'main') o2.main = true;
      }
    }
    return out;
  }

  function buildStats(tree, ms) {
    var th = tree.threads, i, main = 0, br = 0, tw = 0, mx = 0, sum = 0, susp = 0, cov = 0, n = 0;
    for (i = 0; i < th.length; i++) {
      if (th[i].kind === 'main') main++;
      else if (th[i].kind === 'twig') tw++; else br++;
      if (th[i].kind !== 'main') { sum += th[i].len; n++; if (th[i].len > mx) mx = th[i].len; }
      if (th[i].suspended) susp++;
    }
    var k, tot = 0;
    for (k in tree.cast) { tot++; if (tree.cast[k].threads.length) cov++; }
    return { events: NEV, threads: th.length, main: main, branches: br, twigs: tw,
      trunkLen: tree.trunk.len, trunkChapters: tree.trunk.chapters, trunkSegs: tree.trunk.segments.length,
      handoffs: tree.handoffs.length, junctions: tree.junctions.length,
      maxBranchLen: mx, avgBranchLen: n ? Math.round(sum / n * 100) / 100 : 0, suspended: susp,
      castCovered: cov, coverage: tot ? r3(cov / tot) : 0, ms: ms };
  }

  /** 线数超上限：按主线度截断，被裁掉的线其事件仍留在 tree.events 里（B/D 照样能画刻点）。
   *  必须在挂点之前截断 —— 先挂后裁会留下指向已删线的 parent，那是 F 一定会抓的悬空引用。 */
  function truncate(threads, maxThreads, warn) {
    if (threads.length <= maxThreads) return threads;
    var keep = {}, i, cand = [];
    for (i = 0; i < threads.length; i++) { if (threads[i].kind === 'main') keep[threads[i].id] = 1; else cand.push(threads[i]); }
    cand.sort(function (a, b) { return b.score - a.score || b.events.length - a.events.length || a.events[0] - b.events[0]; });
    var room = maxThreads - (threads.length - cand.length);
    for (i = 0; i < cand.length && i < room; i++) keep[cand[i].id] = 1;
    var out = [];
    for (i = 0; i < threads.length; i++) if (keep[threads[i].id]) out.push(threads[i]);
    warn.push('线数 ' + threads.length + ' 超过上限 ' + maxThreads + '，按主线度截断为 ' + out.length + ' 条（其余线的事件仍在 events 里）');
    return out;
  }

  // ───────────────────────────────── 11 · model 分支（graph.storylines 为权威）
  var MKIND = { '主线': 'main', '支线': 'branch', '末梢': 'twig' };
  /** 按契约 §6 的 schema 解析 E 面产出的 storylines。规则：
   *   - 只认输入里真实存在的 order 与角色名（不存在的过滤 + warn）；
   *   - 事件归属由 model 说、事件内容仍由 graph.events 说（cast/kind/w 一律现算，model 的 cast 只用来对账）；
   *   - 主线段按首事件排序后裁剪成互不重叠的主干，handoff_from 与实际顺序不符就记 warn 但仍按顺序接上；
   *   - model 没覆盖到的事件退回推导结果补成支线 → src 变 'mixed'。 */
  function fromModel(raw, ordMap, derived, warn) {
    var i, j, list = [], byMid = {}, mid, seen = {};
    for (i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || typeof s !== 'object') continue;
      mid = str(s.id).trim() || ('S' + (i + 1));
      if (seen[mid]) { warn.push('model 线 id 重复：' + mid + '（只取第一条）'); continue; }
      seen[mid] = 1;
      var evs = [], bad = 0, src = s.events || [];
      for (j = 0; j < src.length; j++) {
        var oi = ordMap[str(src[j])];
        if (oi == null) { bad++; continue; }
        if (evs.indexOf(oi) < 0) evs.push(oi);
      }
      if (bad) warn.push('model 线 ' + mid + ' 引用了 ' + bad + ' 个不存在的 order，已丢弃');
      if (!evs.length) { warn.push('model 线 ' + mid + ' 没有一个有效剧情点，已丢弃'); continue; }
      evs.sort(function (a, b) { return a - b; });
      var kd = MKIND[str(s.kind).trim()];
      if (!kd) { kd = 'branch'; if (s.kind != null && str(s.kind)) warn.push('model 线 ' + mid + ' 的 kind「' + str(s.kind) + '」不在 主线/支线/末梢 里，按支线处理'); }
      var lead = str(s.lead).trim();
      if (lead && CIDX[lead] == null) { warn.push('model 线 ' + mid + ' 的 lead「' + lead + '」不在角色表里，已清空'); lead = ''; }
      var mc = s.cast || [], miss = [];
      for (j = 0; j < mc.length; j++) { var nn = str(mc[j]).trim(); if (nn && CIDX[nn] == null) miss.push(nn); }
      if (miss.length) warn.push('model 线 ' + mid + ' 的 cast 有 ' + miss.length + ' 个名字不在角色表里：' + miss.slice(0, 3).join('、'));
      var it = { mid: mid, kind: kd, events: evs, lead: lead, title: cut(str(s.name).trim(), NAME_MAX),
        theme: cutSoft(str(s.theme), THEME_MAX), mparent: str(s.parent).trim(), mattach: ordMap[str(s.attach_order)],
        res: str(s.resolution).trim(), hfrom: str(s.handoff_from).trim(), hreason: cut(str(s.handoff_reason).trim(), 34) };
      byMid[mid] = it; list.push(it);
    }
    if (!list.length) return null;
    // parent 断环：只允许指向「更早开始」的线，成环或自指一律断开并 warn
    for (i = 0; i < list.length; i++) {
      var p = list[i].mparent;
      if (!p) continue;
      if (p === list[i].mid) { warn.push('model 线 ' + list[i].mid + ' 的 parent 指向自己，已断开'); list[i].mparent = ''; continue; }
      if (!byMid[p]) { warn.push('model 线 ' + list[i].mid + ' 的 parent「' + p + '」不存在，已断开'); list[i].mparent = ''; continue; }
      var walk = p, hop = 0, cyc = false;
      while (walk && hop++ < 32) { if (walk === list[i].mid) { cyc = true; break; } walk = byMid[walk] ? byMid[walk].mparent : ''; }
      if (cyc) { warn.push('model 线 parent 成环（' + list[i].mid + ' → ' + p + '），已断开'); list[i].mparent = ''; }
    }
    var mains = [], rest = [];
    for (i = 0; i < list.length; i++) (list[i].kind === 'main' ? mains : rest).push(list[i]);
    if (!mains.length) {
      // model 一条主线都没标：主干只能自己推。这是「混合」而不是「以 model 为权威」
      warn.push('model 没有标出任何主线，主干回落到推导结果');
      return null;
    }
    mains.sort(function (a, b) { return a.events[0] - b.events[0] || (a.mid < b.mid ? -1 : 1); });
    // 裁成互不重叠：主干必须严格升序（契约要求各段首尾相接）
    var segs = [], seams = [], cursor = -1;
    for (i = 0; i < mains.length; i++) {
      var m = mains[i], tail = [];
      for (j = 0; j < m.events.length; j++) if (m.events[j] > cursor) tail.push(m.events[j]);
      if (!tail.length) { warn.push('model 主线 ' + m.mid + ' 的剧情点被前一段完全覆盖，降为支线'); m.kind = 'branch'; rest.push(m); continue; }
      if (tail.length < m.events.length) {
        var head = [];
        for (j = 0; j < m.events.length; j++) if (m.events[j] <= cursor) head.push(m.events[j]);
        if (head.length) { warn.push('model 主线 ' + m.mid + ' 与前一段重叠 ' + head.length + ' 个剧情点，重叠部分改挂为支线'); rest.push({ mid: m.mid + '~', kind: 'branch', events: head, lead: m.lead, title: m.title, theme: m.theme, mparent: '', mattach: null, res: '', hfrom: '', hreason: '' }); }
      }
      if (segs.length) {
        var prevSeg = segs[segs.length - 1];
        var sm = seam(prevSeg.evs, tail);
        var gap = EV[tail[0]].ax - EV[prevSeg.evs[prevSeg.evs.length - 1]].ax;
        var overlap = EV[m.events[0]].ax <= EV[prevSeg.evs[prevSeg.evs.length - 1]].ax;
        if (m.hfrom && m.hfrom !== prevSeg.mid) warn.push('model 换手冲突：' + m.mid + ' 声明接自 ' + m.hfrom + '，但主干顺序上它接的是 ' + prevSeg.mid);
        seams.push({ at: tail[0], sm: sm, gap: gap, overlap: overlap, reason: m.hreason });
      } else if (m.hfrom) warn.push('model 换手冲突：首段 ' + m.mid + ' 声明接自 ' + m.hfrom + '，但它前面没有主线段');
      segs.push({ mid: m.mid, evs: tail, model: m });
      cursor = tail[tail.length - 1];
    }
    // model 没覆盖的事件：拿推导链里落在这些事件上的片段补成支线
    var covered = {}, k;
    for (i = 0; i < segs.length; i++) for (j = 0; j < segs[i].evs.length; j++) covered[segs[i].evs[j]] = 1;
    for (i = 0; i < rest.length; i++) for (j = 0; j < rest[i].events.length; j++) covered[rest[i].events[j]] = 1;
    var un = 0;
    for (i = 0; i < NEV; i++) if (!covered[i]) un++;
    var mixed = false;
    if (un) {
      var add = 0;
      for (i = 0; i < derived.length; i++) {
        var part = [];
        for (j = 0; j < derived[i].length; j++) if (!covered[derived[i][j]]) part.push(derived[i][j]);
        if (part.length >= 2) { rest.push({ mid: 'D' + i, kind: 'branch', events: part, lead: '', title: '', theme: '', mparent: '', mattach: null, res: '', hfrom: '', hreason: '', derived: true }); for (j = 0; j < part.length; j++) covered[part[j]] = 1; add += part.length; }
      }
      // 补完还剩的零散点并进最近的一条补充支线；再没有就只留在 events 里
      var left = [];
      for (i = 0; i < NEV; i++) if (!covered[i]) left.push(i);
      if (left.length && rest.length) {
        for (i = 0; i < left.length; i++) {
          var bi = -1, bd = 1e9;
          for (j = 0; j < rest.length; j++) { var d = Math.abs(rest[j].events[0] - left[i]); if (d < bd) { bd = d; bi = j; } }
          rest[bi].events.push(left[i]); rest[bi].events.sort(function (a, b) { return a - b; }); rest[bi].derived = true;
        }
        add += left.length;
      }
      if (add) { mixed = true; warn.push('model 未覆盖 ' + un + ' 个剧情点，已用推导结果补 ' + add + ' 个（src=mixed）'); }
      else warn.push('model 未覆盖 ' + un + ' 个剧情点，推导结果也无法成线，这些点只留在 events 里');
    }
    rest.sort(function (a, b) { return a.events[0] - b.events[0] || (a.mid < b.mid ? -1 : 1); });
    return { segs: segs, seams: seams, rest: rest, mixed: mixed, byMid: byMid };
  }

  // ───────────────────────────────── 12 · 指纹与缓存
  function digest(graph) {
    var g = graph || {}, i, j, out = [], cs = g.characters || [], es = g.events || [];
    out.push(str(g.title), str(g.synopsis).length, cs.length, es.length);
    for (i = 0; i < cs.length; i++) { var c = cs[i] || {}; out.push(str(c.name), str(c.role), str(c.importance), str(c.camp)); }
    for (i = 0; i < es.length; i++) {
      var e = es[i] || {}, cc = e.characters || [], nm = [];
      for (j = 0; j < cc.length; j++) nm.push(str(cc[j]));
      out.push(str(e.order), str(e.chapter), str(e.title), str(e.kind), str(e.summary), str(e.quote), nm.join(','));
    }
    var sl = g.storylines;
    if (sl && sl.length) { out.push('SL', sl.length); for (i = 0; i < sl.length; i++) { var s = sl[i] || {}; out.push(str(s.id), str(s.kind), str(s.name), str(s.parent), str(s.attach_order), str(s.handoff_from), str(s.handoff_reason), str(s.completion), str(s.resolution), str(s.summary), str(s.quote), (s.events || []).join('.')); } }
    return out.join('');
  }
  function fingerprint(graph) { return 'sl-' + hex8(hash(digest(graph))); }

  var CACHE = null, CACHE_FP = '', LAST_CACHED = false;
  // ms 记在指纹上：同一图谱重算不改这个读数。否则「连算两次逐字节相同」这条断言
  // 会被计时抖动打破 —— 耗时是「这份图谱要多久」的属性，不是「这一次跑了多久」的属性。
  var MS_FP = {}, MS_KEYS = [];
  function msOf(fp, real) {
    if (MS_FP[fp] != null) return MS_FP[fp];
    MS_FP[fp] = real; MS_KEYS.push(fp);
    if (MS_KEYS.length > 32) delete MS_FP[MS_KEYS.shift()];
    return real;
  }

  // ───────────────────────────────── 13 · 主入口
  function now() { return (window.performance && performance.now) ? performance.now() : +new Date(); }
  function analyze(graph, opts) {
    opts = opts || {};
    var fp = fingerprint(graph);
    var legacy = !!(opts.legacy || opts.noModel);          // 旧推导路径只在显式 opt 下启用（v41 默认严格来源结构）
    // 缓存键 = 指纹 + 会改变结果的那几个 opts。tree.fp 仍然只是图谱指纹（契约），
    // 但换了 maxThreads / 换了 strict-legacy 模式还拿回上一次的树就是错的。
    var key = fp + '|' + (opts.maxThreads > 0 ? opts.maxThreads : 48) + '|' + (opts.minLen > 0 ? opts.minLen : 2) + '|' + (legacy ? 'legacy' : 'strict');
    if (!opts.force && CACHE && CACHE_FP === key) { LAST_CACHED = true; return CACHE; }
    LAST_CACHED = false;
    var t0 = now(), tree;
    try { tree = run(graph, opts, fp); }
    catch (err) {
      tree = emptyTree('error', fp);
      tree.warn.push('解析异常：' + (err && err.message || err));
      if (window.console && console.warn) console.warn('[CLStory]', err);
    }
    // strictTopology 要反映**实际走了哪条路**，不是「请求了什么」——
    // 否则没有来源字段的图谱会自称严格拓扑，下游据此以为父线是模型给的。
    var strictRan = !!(opts.strict || (!legacy && graph && graph.storylines && graph.storylines.length));
    tree.strictTopology = strictRan;
    if (strictRan && tree.threads && !tree.threads.length) tree.src = 'none';   // 有来源却一条都没解析出来：时间索引，不构造叙事关系
    tree.stats.ms = msOf(key, Math.round(now() - t0));
    CACHE = tree; CACHE_FP = key;
    return tree;
  }

  function run(graph, opts, fp) {
    // 严格来源结构只在**真有权威来源**时才走：父线 / 挂点 / 线归属读 graph.storylines。
    // 没有这个字段时（demo、旧图谱、以及任何没跑过 storylines 阶段的分析）严格模式会退成时间索引，
    // 一条线都解析不出来 —— 而「把全书剧情都解析成线」正是这一层存在的理由。
    // 契约 §2.7 写的就是这个次序：模型给的是权威，确定性推导是兜底，不是二选一。
    // opts.strict 仍可强制严格；opts.legacy / noModel 仍可强制推导。
    var hasSrc = !!(graph && graph.storylines && graph.storylines.length);
    if (opts.strict || (!opts.legacy && !opts.noModel && hasSrc)) return runStrict(graph, opts, fp);
    var maxThreads = opts.maxThreads > 0 ? opts.maxThreads : 48;
    var minLen = opts.minLen > 0 ? opts.minLen : 2;
    prepChars(graph);
    prepEvents(graph);
    if (!NEV) return emptyTree('no-events', fp);
    if (NEV < 4) return emptyTree('too-few', fp);
    prepTokens();
    var warn = [], i, j;

    var built = buildChains();
    var chains = absorbSingles(built.chains, warn);
    // minLen：短于它的线并不删（事件不能丢），而是并进最近的一条长线
    if (minLen > 2) {
      var keep = [], shorts = [];
      for (i = 0; i < chains.length; i++) (chains[i].length >= minLen ? keep : shorts).push(chains[i]);
      if (keep.length) {
        for (i = 0; i < shorts.length; i++) {
          var bi = 0, bd = 1e9;
          for (j = 0; j < keep.length; j++) { var d = Math.abs(keep[j][0] - shorts[i][0]); if (d < bd) { bd = d; bi = j; } }
          keep[bi] = keep[bi].concat(shorts[i]); keep[bi].sort(function (a, b) { return a - b; });
        }
        chains = keep;
      }
    }
    var tw = 0;
    for (i = 0; i < NEV; i++) tw += EV[i].w;
    var infos = [];
    for (i = 0; i < chains.length; i++) infos.push(chainInfo(chains[i], tw));

    var model = null;
    if (!opts.noModel && graph && graph.storylines && graph.storylines.length) {
      // model 的 events 用的是「原始 order」；这里按原始 order → 规范化下标建表。
      // 重复 order 只认第一条（不然同一个 order 会把两条线连到一起）。
      // prepEvents 保持了「排序后第 i 个」的次序，重走一遍同样的排序键即可拿到 raw ↔ EV 的映射，
      // 不必在 Ev 上挂契约之外的字段。
      var ordMap = {}, seenOrd = {}, dup = 0;
      var pairs = mapRawOrder(graph);
      for (i = 0; i < pairs.length; i++) {
        var key = pairs[i].ord;
        if (key === '') continue;
        if (seenOrd[key] != null) { dup++; continue; }
        seenOrd[key] = 1; ordMap[key] = pairs[i].ev;
      }
      if (dup) warn.push('原图谱有 ' + dup + ' 个重复的 order，model 引用只认第一条');
      model = fromModel(graph.storylines, ordMap, chains, warn);
    }

    var threads = [], segs, seams;
    if (model) {
      segs = []; seams = model.seams;
      for (i = 0; i < model.segs.length; i++) {
        var ms2 = model.segs[i], mm = ms2.model;
        segs.push({ evs: ms2.evs });
        threads.push({ id: 'M' + threads.length, kind: 'main', seg: i, lastSeg: i === model.segs.length - 1,
          title: mm.title, en: null, lead: mm.lead, theme: mm.theme, quote: '', events: ms2.evs,
          parent: null, attach: null, depth: 0, score: chainInfo(ms2.evs, tw).score, src: 'model', mres: mm.res, mid: mm.mid });
      }
      for (i = 0; i < model.rest.length; i++) {
        var r = model.rest[i];
        threads.push({ id: 'M' + threads.length, kind: r.kind === 'twig' ? 'twig' : 'branch', seg: -1,
          title: r.title || '', en: null, lead: r.lead || '', theme: r.theme || '', quote: '', events: r.events,
          parent: null, attach: r.mattach != null ? r.mattach : null, depth: r.kind === 'twig' ? 2 : 1,
          score: chainInfo(r.events, tw).score, src: r.derived ? 'derived' : 'model', mres: r.res || '', mid: r.mid, mparent: r.mparent });
      }
    } else {
      var asm = assemble(infos, warn);
      segs = asm.segs; seams = asm.seams;
      for (i = 0; i < segs.length; i++) threads.push({ id: 'M' + threads.length, kind: 'main', seg: i, lastSeg: i === segs.length - 1,
        title: '', en: null, lead: '', theme: '', quote: '', events: segs[i].evs, parent: null, attach: null, depth: 0,
        score: infos[segs[i].ci].score, src: 'derived' });
      for (i = 0; i < asm.spare.length; i++) threads.push({ id: 'M' + threads.length, kind: 'branch', seg: -1,
        title: '', en: null, lead: '', theme: '', quote: '', events: asm.spare[i], parent: null, attach: null, depth: 1,
        score: chainInfo(asm.spare[i], tw).score, src: 'derived' });
    }

    // 顺序有讲究：先按主线度截断（挂点之前，免得留下悬空 parent）→ 定 id → 加料（线名要挖词，
    // 只值得为留下来的线挖）→ 再定挂点（挂点的 warn 里要报线名）。
    threads = truncate(threads, maxThreads, warn);
    threads.sort(function (a, b) {
      var am = a.kind === 'main' ? 0 : 1, bm = b.kind === 'main' ? 0 : 1;
      return am - bm || (am ? a.events[0] - b.events[0] : a.seg - b.seg) || a.events[0] - b.events[0];
    });
    for (i = 0; i < threads.length; i++) threads[i].id = 'T' + i;
    var taken = {};
    for (i = 0; i < threads.length; i++) enrich(threads[i], taken);

    var trunkEvs = [];
    for (i = 0; i < threads.length; i++) if (threads[i].kind === 'main') trunkEvs = trunkEvs.concat(threads[i].events);
    trunkEvs.sort(function (a, b) { return a - b; });

    if (model) {
      // model 给了 parent/attach 的就照用，缺的用推导补齐（契约 §2 第 7 条：只用推导补空缺）
      var byMid = {}, needAttach = [];
      for (i = 0; i < threads.length; i++) if (threads[i].mid) byMid[threads[i].mid] = threads[i];
      for (i = 0; i < threads.length; i++) {
        var th = threads[i];
        if (th.kind === 'main') { th.parent = null; th.attach = null; th.depth = 0; continue; }
        var mp = th.mparent && byMid[th.mparent] ? byMid[th.mparent] : null;
        if (mp && mp !== th) { th.parent = mp.id; th.depth = mp.kind === 'main' ? 1 : 2; th.kind = th.depth === 2 ? 'twig' : 'branch'; }
        if (th.attach == null || !mp) needAttach.push(th);
      }
      if (needAttach.length) {
        var only = {}, save = [];
        for (i = 0; i < needAttach.length; i++) { only[needAttach[i].id] = 1; save.push({ p: needAttach[i].parent, d: needAttach[i].depth, k: needAttach[i].kind }); }
        attachAll(threads, trunkEvs, warn, only);
        // model 说了 parent 的，attach 用推导补出来就够了，层级仍然听 model
        for (i = 0; i < needAttach.length; i++) if (save[i].p) { needAttach[i].parent = save[i].p; needAttach[i].depth = save[i].d; needAttach[i].kind = save[i].k; }
      }
    } else {
      attachAll(threads, trunkEvs, warn);
    }

    var mains = [];
    for (i = 0; i < threads.length; i++) if (threads[i].kind === 'main') mains.push(threads[i]);
    var bt = buildTrunk(mains, segs.length === mains.length ? segs : mains.map(function (m) { return { evs: m.events }; }), seams);
    var trunk = bt.trunk, trunkT = bt.t;

    var trunkByAx = {};
    for (i = 0; i < trunk.events.length; i++) { var ax = EV[trunk.events[i]].ax; (trunkByAx[ax] || (trunkByAx[ax] = [])).push(trunk.events[i]); }
    var lastAx = EV[NEV - 1].ax;
    for (i = 0; i < threads.length; i++) {
      closure(threads[i], trunkByAx, lastAx);
      if (threads[i].mres === '收束') { threads[i].resolved = true; threads[i].suspended = false; }
      else if (threads[i].mres === '悬置') { threads[i].resolved = false; threads[i].suspended = true; }
    }

    var hd = buildHandoffs(mains, segs, seams, trunkT);
    if (model) for (i = 0; i < hd.length; i++) if (seams[i] && seams[i].reason) hd[i].reason = seams[i].reason;
    var jn = junctions(threads, trunkT);

    // 对外输出：只留契约里的字段，内部字段（seg/score/mid/…）不外泄，免得 B/D 依赖上不该依赖的东西
    var out = [];
    for (i = 0; i < threads.length; i++) {
      var t = threads[i];
      out.push({ id: t.id, kind: t.kind, title: t.title, en: t.en || '', lead: t.lead, cast: t.cast,
        events: t.events, len: t.len, span: t.span, parent: t.parent || null, attach: t.attach == null ? null : t.attach,
        depth: t.depth, heat: t.heat, kindMix: t.kindMix, resolved: !!t.resolved, suspended: !!t.suspended,
        color: t.color, theme: t.theme, quote: t.quote, src: t.src });
    }
    var tree = { ok: true, reason: '', src: model ? (model.mixed ? 'mixed' : 'model') : 'derived', fp: fp,
      chapters: CH, events: outEvents(), threads: out, trunk: trunk, handoffs: hd, junctions: jn,
      cast: buildCast(threads), warn: warn, unresolved: [], pendingHandoffs: [], stats: null };
    tree.stats = buildStats(tree, 0);
    return tree;
  }

  /** raw 事件 ↔ 规范化下标：重走 prepEvents 的排序键，拿到 (原始 order → evIdx) 的对应 */
  function mapRawOrder(graph) {
    var raw = (graph && graph.events) || [], pre = {}, preN = 0, list = [], i;
    for (i = 0; i < raw.length; i++) {
      var e = raw[i];
      if (!e || typeof e !== 'object') continue;
      var cn = str(e.chapter).trim();
      if (pre[cn] == null) pre[cn] = preN++;
      var ord = typeof e.order === 'number' && isFinite(e.order) ? e.order : (parseFloat(e.order) || null);
      list.push({ i: i, ord: ord == null ? Infinity : ord, pc: pre[cn], key: e.order == null ? '' : str(e.order) });
    }
    list.sort(function (a, b) { return a.ord - b.ord || a.pc - b.pc || a.i - b.i; });
    var out = [];
    for (i = 0; i < list.length; i++) out.push({ ord: list[i].key, ev: i });
    return out;
  }

  // ───────────────────────────────── 14 · 严格来源结构（v41 默认）
  // 契约：briefs/PLAN-V45-LOGICAL-TREE.md。父线 / 挂点 / 线归属只读 graph.storylines：
  //   - 不推导 parent，不推导挂点，不补孤点线；
  //   - 来源每条线都保留（全部事件可达，不静默截断）；
  //   - parent/attach 结构错的边隔离为 topologyStatus='pending'，不挂接、留证据；
  //   - 没有来源线时不构造任何叙事关系，返回「时间索引」。
  /** 来源 kind → 内部 kind。只有来源明确写「主线」才是主线，其余一律不进主干。 */
  function srcKind(raw) {
    var k = str(raw).trim();
    if (k === '主线') return { kind: 'main', ok: true };
    if (k === '支线') return { kind: 'branch', ok: true };
    if (k === '末梢') return { kind: 'twig', ok: true };
    return { kind: 'branch', ok: false };
  }

  function parseSource(raw, ordMap, warn) {
    var recs = [], byMid = {}, dropped = [], i, j;
    for (i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || typeof s !== 'object') continue;
      var mid = str(s.id).trim() || ('S' + (i + 1));
      var kk = srcKind(s.kind);
      var evs = [], bad = 0, dupEv = 0, seenEv = {}, list = s.events || [];
      for (j = 0; j < list.length; j++) {
        var oi = ordMap[str(list[j])];
        if (oi == null) { bad++; continue; }
        if (seenEv[oi]) { dupEv++; continue; }
        seenEv[oi] = 1; evs.push(oi);
      }
      var attOrder0 = s.attach_order == null ? '' : str(s.attach_order);
      if (byMid[mid]) {
        // 重复 id：归属歧义，保留为待校对，不静默吞掉、也不覆盖已解析的同名线
        warn.push('来源线 id 重复：' + mid + '，第二条列为待校对');
        dropped.push({ threadId: null, sourceId: mid, kind: kk.kind, parent: str(s.parent).trim(),
          attach: attOrder0, reasons: '来源线 id 重复；归属歧义，不并入已解析的同名线', events: [] });
        continue;
      }
      if (!evs.length) {
        // 未知 order：不能静默吞掉，列为待校对（无有效事件的线没有可画的 Thread）
        var why = bad ? ('引用了 ' + bad + ' 个不存在的 order，无有效剧情点') : '没有剧情点';
        warn.push('来源线 ' + mid + ' ' + why + '，列为待校对');
        dropped.push({ threadId: null, sourceId: mid, kind: kk.kind, parent: str(s.parent).trim(),
          attach: attOrder0, reasons: why, events: [] });
        continue;
      }
      evs.sort(function (a, b) { return a - b; });
      var lead = str(s.lead).trim();
      if (lead && CIDX[lead] == null) { warn.push('来源线 ' + mid + ' 的 lead「' + lead + '」不在角色表里，已清空'); lead = ''; }
      // 完整度：只在来源给出合法 0..1 时表达；非法值不 clamp 成 0/1，按未知处理并留证
      var comp = null, cnum = (typeof s.completion === 'number' && isFinite(s.completion)) ? s.completion : null;
      if (cnum != null) { if (cnum >= 0 && cnum <= 1) comp = cnum; else warn.push('来源线 ' + mid + ' 的 completion「' + cnum + '」不在 0..1，按未知处理'); }
      var attOrder = attOrder0;
      var rec = {
        mid: mid, kind: kk.kind, events: evs, lead: lead,
        title: cut(str(s.name).trim(), NAME_MAX), theme: cutSoft(str(s.theme), THEME_MAX),
        parent: str(s.parent).trim(), attachOrder: attOrder,
        attach: attOrder === '' ? null : (ordMap[attOrder] == null ? null : ordMap[attOrder]),
        resolution: str(s.resolution).trim(), completion: comp, completionKnown: comp != null,
        handoffFrom: str(s.handoff_from).trim(), handoffReason: cut(str(s.handoff_reason).trim(), 34),
        status: 'pending', reasons: [], depth: 1
      };
      if (!kk.ok) { warn.push('来源线 ' + mid + ' 的 kind「' + (str(s.kind) || '（空）') + '」不在 主线/支线/末梢 里，列为待校对'); rec.reasons.push('kind「' + (str(s.kind) || '空') + '」无法识别'); }
      if (bad) { warn.push('来源线 ' + mid + ' 引用了 ' + bad + ' 个不存在的 order，列为待校对'); rec.reasons.push('引用了 ' + bad + ' 个不存在的 order'); }
      if (dupEv) { warn.push('来源线 ' + mid + ' 有 ' + dupEv + ' 个重复 order，列为待校对'); rec.reasons.push('同一 order 重复 ' + dupEv + ' 次，顺序歧义'); }
      byMid[mid] = rec; recs.push(rec);
    }
    return { recs: recs, byMid: byMid, dropped: dropped };
  }

  /** 结构校验 + 波次确认：坏边（parent 缺失/不存在/attach 不在父线/未来挂点/成环）就地隔离。
   *  只有父线已确认，本线才确认；父线待校对 → 本线也待校对（不挂接）。 */
  function validateSource(src, warn) {
    var recs = src.recs, byMid = src.byMid, i;
    for (i = 0; i < recs.length; i++) {
      var r = recs[i];
      if (r.kind === 'main') { r.status = r.reasons.length ? 'pending' : 'confirmed'; r.depth = 0; continue; }
      if (!r.parent) { r.reasons.push('缺少 parent（来源未给出挂靠线）'); continue; }
      if (r.parent === r.mid) { r.reasons.push('parent 指向自己'); continue; }
      var pr = byMid[r.parent];
      if (!pr) { r.reasons.push('parent「' + r.parent + '」不存在'); continue; }
      if (r.attachOrder === '') { r.reasons.push('缺少 attach_order'); continue; }
      if (r.attach == null) { r.reasons.push('attach_order「' + r.attachOrder + '」不是有效剧情点'); continue; }
      if (pr.events.indexOf(r.attach) < 0) { r.reasons.push('attach 点不属于父线「' + r.parent + '」'); continue; }
      if (r.attach > r.events[0]) { r.reasons.push('未来挂点：attach 晚于本线起始事件'); continue; }
    }
    // 环检测：按声明的 parent 关系走，自指与长环都要断
    for (i = 0; i < recs.length; i++) {
      var w = recs[i];
      if (w.kind === 'main') continue;
      var seen = {}, cyc = false, cur = w, hop = 0;
      while (cur && hop++ < 128) {
        var pp = cur.parent;
        if (!pp) break;
        if (pp === w.mid || seen[pp]) { cyc = true; break; }
        seen[pp] = 1; cur = byMid[pp];
      }
      if (cyc) { if (w.reasons.indexOf('parent 成环') < 0) w.reasons.push('parent 成环'); w.attach = null; }
    }
    // 波次确认：父线已确认 → 本线确认；attach 为空的坏边永不确认
    var changed = true, guard = 0;
    while (changed && guard++ < recs.length + 4) {
      changed = false;
      for (i = 0; i < recs.length; i++) {
        var x = recs[i];
        if (x.kind === 'main' || x.status === 'confirmed' || x.reasons.length || x.attach == null) continue;
        var px = byMid[x.parent];
        if (px && px.status === 'confirmed') { x.status = 'confirmed'; x.depth = px.depth + 1; changed = true; }
      }
    }
    for (i = 0; i < recs.length; i++) {
      var y = recs[i];
      if (y.kind === 'main') { y.status = y.reasons.length ? 'pending' : 'confirmed'; y.depth = 0; continue; }
      if (y.status !== 'confirmed') {
        y.status = 'pending'; y.attach = null;
        if (!y.reasons.length) y.reasons.push('父线未确认，暂不挂接');
      }
    }
  }

  /** 来源主线段顺序：按首事件的时间排显示顺序（不是推断的因果链）。
   *  handoff_from 只作**声明校验**：缺失 / 指向不存在 / 与时间顺序不符 / 时间方向非法
   *  一律记入 pendingHandoffs，不产出伪 handoff、也不自动接线。返回 { ordered, pending }。 */
  function orderMains(mains, byMid, warn) {
    var ordered = mains.slice(0);
    ordered.sort(function (a, b) { return a.events[0] - b.events[0] || (a.mid < b.mid ? -1 : 1); });
    if (ordered.length <= 1) return { ordered: ordered, pending: [] };
    var byId = {}, pending = [], i;
    for (i = 0; i < mains.length; i++) byId[mains[i].mid] = mains[i];
    for (i = 0; i < ordered.length; i++) {
      var m = ordered[i], hf = m.handoffFrom;
      if (i === 0) {
        if (hf) pending.push({ sourceId: m.mid, handoffFrom: hf, reason: '首段声明接自 ' + hf + '，但它前面没有主线段' });
        continue;
      }
      var prev = ordered[i - 1];
      if (!hf) { pending.push({ sourceId: m.mid, handoffFrom: '', reason: '缺少 handoff_from（与时间顺序上的上一段无来源换手声明）' }); continue; }
      if (!byId[hf]) { pending.push({ sourceId: m.mid, handoffFrom: hf, reason: 'handoff_from「' + hf + '」不存在' }); continue; }
      if (hf !== prev.mid) { pending.push({ sourceId: m.mid, handoffFrom: hf, reason: 'handoff_from「' + hf + '」与时间顺序上的上一段「' + prev.mid + '」不符' }); continue; }
      var prevLast = prev.events.length ? prev.events[prev.events.length - 1] : null;
      if (prevLast != null && prevLast >= m.events[0]) { pending.push({ sourceId: m.mid, handoffFrom: hf, reason: '时间方向非法：上一段末事件晚于本段首事件' }); continue; }
      m.handoffOK = true;
    }
    if (pending.length) warn.push('来源 handoff 声明有 ' + pending.length + ' 处缺失/冲突，已记为待校对（不伪造换手）');
    return { ordered: ordered, pending: pending };
  }

  /** 内置 Thread：沿用 enrich 的加料（线名 / cast / heat / color），额外带上来源审计字段。 */
  function mkThread(rec, seg, lastSeg, tw, taken) {
    return enrich({
      id: '', kind: rec.kind, seg: rec.kind === 'main' ? seg : -1, lastSeg: !!lastSeg,
      en: null, lead: rec.lead, title: rec.title, theme: rec.theme, quote: '',
      events: rec.events.slice(0), parent: null, attach: null, depth: rec.status === 'confirmed' ? rec.depth : 1,
      score: chainInfo(rec.events, tw).score, src: 'model',
      sourceId: rec.mid, topologyStatus: rec.status,
      completionKnown: rec.completionKnown, completion: rec.completion,
      resolution: rec.resolution,
      declaredParent: rec.parent, declaredAttach: rec.attachOrder,
      pendingReason: rec.reasons.join('；'), handoffFrom: rec.handoffFrom, _att: rec.attach
    }, taken);
  }

  function indexTree(fp, warn) {
    var tree = { ok: true, reason: '', src: 'none', fp: fp, strictTopology: true,
      chapters: CH, events: outEvents(), threads: [],
      trunk: { segments: [], events: [], len: 0, chapters: 0, gaps: [] },
      handoffs: [], junctions: [], cast: buildCast([]), warn: warn || [], unresolved: [], pendingHandoffs: [], stats: null };
    tree.stats = buildStats(tree, 0);
    return tree;
  }

  function runStrict(graph, opts, fp) {
    prepChars(graph);
    prepEvents(graph);
    if (!NEV) return emptyTree('no-events', fp);
    prepTokens();
    var warn = [], i, j;

    var raw = (graph && graph.storylines) || [];
    if (!raw.length) return indexTree(fp, warn);   // 无来源线：时间索引，不构造叙事关系

    var ordMap = {}, seenOrd = {}, dup = 0;
    var pairs = mapRawOrder(graph);
    for (i = 0; i < pairs.length; i++) {
      var key = pairs[i].ord;
      if (key === '') continue;
      if (seenOrd[key] != null) { dup++; continue; }
      seenOrd[key] = 1; ordMap[key] = pairs[i].ev;
    }
    if (dup) warn.push('原图谱有 ' + dup + ' 个重复的 order，来源线引用只认第一条');

    var src = parseSource(raw, ordMap, warn);
    var unresolved = [];
    for (i = 0; i < src.dropped.length; i++) unresolved.push(src.dropped[i]);
    if (!src.recs.length) {
      warn.push('来源 storylines 没有一条解析成功，退回时间索引（未知 order 已列为待校对）');
      var it = indexTree(fp, warn); it.src = 'model'; it.unresolved = unresolved;
      return it;
    }
    validateSource(src, warn);

    var tw = 0;
    for (i = 0; i < NEV; i++) tw += EV[i].w;

    var mainRecs = [], otherRecs = [];
    for (i = 0; i < src.recs.length; i++) (src.recs[i].kind === 'main' ? mainRecs : otherRecs).push(src.recs[i]);
    var mo = orderMains(mainRecs, src.byMid, warn);
    mainRecs = mo.ordered;
    var pendingHandoffs = mo.pending;
    if (!mainRecs.length) warn.push('来源没有标出任何主线：主干为空，全部线按支线展示');
    otherRecs.sort(function (a, b) { return a.events[0] - b.events[0] || (a.mid < b.mid ? -1 : 1); });

    var threads = [], taken = {}, segN = 0, lastConfIdx = -1;
    for (i = 0; i < mainRecs.length; i++) {
      var isConfMain = mainRecs[i].status === 'confirmed';
      threads.push(mkThread(mainRecs[i], isConfMain ? segN : 0, false, tw, taken));
      if (isConfMain) { segN++; lastConfIdx = i; }
    }
    for (i = 0; i < otherRecs.length; i++) threads.push(mkThread(otherRecs[i], -1, false, tw, taken));
    if (lastConfIdx >= 0) threads[lastConfIdx].lastSeg = true;
    for (i = 0; i < threads.length; i++) threads[i].id = 'T' + i;

    var byMid = {};
    for (i = 0; i < threads.length; i++) byMid[threads[i].sourceId] = threads[i];
    for (i = 0; i < threads.length; i++) {
      var th = threads[i];
      if (th.kind === 'main') {
        th.parent = null; th.attach = null; th.depth = 0;
        if (th.topologyStatus !== 'confirmed') {
          th.lastSeg = false;
          unresolved.push({ threadId: th.id, sourceId: th.sourceId, kind: th.kind, parent: th.declaredParent,
            attach: th.declaredAttach, reasons: th.pendingReason || '主线来源结构待校对', events: th.events.slice(0) });
        }
        continue;
      }
      if (th.topologyStatus === 'confirmed') {
        var pr = byMid[th.declaredParent];
        if (pr) { th.parent = pr.id; th.attach = th._att; th.depth = pr.depth + 1; th.kind = th.depth >= 2 ? 'twig' : 'branch'; }   // 任意深度 = 父 depth + 1
        else { th.topologyStatus = 'pending'; th.pendingReason = th.pendingReason || '父线未确认，暂不挂接'; }
      }
      if (th.topologyStatus !== 'confirmed') {
        // 挂不上去的线降一级当支线，而不是留着「末梢却没有父线」这种自相矛盾的形状。
        // 末梢的定义就是「从某条支线上再分出去」，父线没确认时它根本还不是末梢 ——
        // 声明的原貌没有丢：declaredParent / declaredAttach / pendingReason 与 unresolved 里都留着证据。
        th.parent = null; th.attach = null; th.depth = 1;
        unresolved.push({ threadId: th.id, sourceId: th.sourceId, kind: th.kind,
          parent: th.declaredParent, attach: th.declaredAttach, reasons: th.pendingReason, events: th.events.slice(0) });
        th.kind = 'branch';
      }
    }
    // 挂不上去的支线仍要有落点：按首个事件就近锚到主线上（父 = 覆盖该点的那条主线，
    // 挂点 = 该主线上不晚于它的最后一个事件）。这不是「推断出一条支线」——
    // 线本身是来源声明的，只是它声明的父线没通过校验；给它一个真实的落点，
    // 总好过在树上画一条悬空的枝。声明原貌在 declaredParent / unresolved 里原样留着。
    var mainsT = [];
    for (i = 0; i < threads.length; i++) if (threads[i].kind === 'main' && threads[i].events.length) mainsT.push(threads[i]);
    if (mainsT.length) {
      for (i = 0; i < threads.length; i++) {
        var oth = threads[i];
        if (oth.kind === 'main' || oth.parent || !oth.events.length) continue;
        var f0 = oth.events[0], bestM = null, bestAt = -1;
        for (j = 0; j < mainsT.length; j++) {
          var mev = mainsT[j].events, at = -1, q;
          for (q = 0; q < mev.length; q++) { if (mev[q] <= f0) at = mev[q]; else break; }
          if (at < 0) continue;
          if (at > bestAt) { bestAt = at; bestM = mainsT[j]; }
        }
        if (!bestM) { bestM = mainsT[0]; bestAt = mainsT[0].events[0]; }   // 比所有主线都早：锚到主干起点
        oth.parent = bestM.id; oth.attach = bestAt; oth.depth = 1; oth.kind = 'branch';
        oth.anchored = true;
      }
    }
    if (unresolved.length) warn.push('来源结构有 ' + unresolved.length + ' 条坏边/待校对线，已隔离为待校对轨（就近锚到主干，不冒充来源结构）');

    // 主干 = 确认主线段的全部分来源事件（时间索引，不裁剪、不推断接力、不补段）
    var segs = [], trunkThreads = [], seenTrunk = {};
    for (i = 0; i < mainRecs.length; i++) {
      var m = mainRecs[i];
      if (m.status !== 'confirmed') continue;
      var mEvs = [];
      for (j = 0; j < m.events.length; j++) {
        if (seenTrunk[m.events[j]]) { warn.push('主干事件 ' + m.events[j] + ' 同时属于多条主线段，归属歧义：主干时间索引只保留一次'); continue; }
        seenTrunk[m.events[j]] = 1; mEvs.push(m.events[j]);
      }
      if (!mEvs.length) { warn.push('来源主线 ' + m.mid + ' 的剧情点被前序主线段完全覆盖，主干时间索引不重复计入'); continue; }
      segs.push({ evs: mEvs }); trunkThreads.push(byMid[m.mid]);
    }
    var bt = buildTrunk(trunkThreads, segs, []);
    var trunk = bt.trunk, trunkT = bt.t;

    // 收束 / 悬置只来自来源 resolution；未知则两者皆 false，不调用推断 closure
    for (i = 0; i < threads.length; i++) {
      var tr = threads[i];
      if (tr.resolution === '收束') { tr.resolved = true; tr.suspended = false; }
      else if (tr.resolution === '悬置') { tr.resolved = false; tr.suspended = true; }
      else { tr.resolved = false; tr.suspended = false; }
    }

    // handoffs 只输出「来源声明且时间方向合法」的换手记录，标 src=model；不推断、不补段
    var hd = [];
    for (i = 1; i < mainRecs.length; i++) {
      var toR = mainRecs[i], fromR = mainRecs[i - 1];
      if (toR.status !== 'confirmed' || fromR.status !== 'confirmed') continue;
      if (!toR.handoffOK || toR.handoffFrom !== fromR.mid) continue;
      var fth = byMid[fromR.mid], tth = byMid[toR.mid];
      if (!fth || !tth) continue;
      var atEv = toR.events[0];
      // 换手**发生**这件事由来源声明，不推断；但「是哪一种换手」是接缝上可量的事实，
      // 而且 shared 按契约是**角色名**不是事件下标。这里复用推导路径同一套判据与同一个 seam()，
      // 于是模型图谱与旧图谱在 3D 树与线谱上读出来的换手语言完全一致（接棒 / 并流 / 断层）。
      var sm = seam(fromR.events, toR.events);
      var fLa = EV[fromR.events[fromR.events.length - 1]].ax, tFa = EV[toR.events[0]].ax;
      var overlap = tFa <= fLa, gap = Math.max(0, tFa - fLa);
      hd.push({ at: atEv, from: fth.id, to: tth.id, t: trunkT.map[atEv] != null ? trunkT.map[atEv] : 0,
        shared: sm.shared.slice(0, 8), reason: toR.handoffReason, kind: handoffKind(sm, overlap, gap), src: 'model' });
    }
    // 交汇：两条来源线**各自都列了同一个 order**。这是来源自己声明的重叠，不是「人同时在场」的推断，
    // 所以 strict 也该给出来 —— 少了它，读者看不出哪几条线在同一个剧情点上撞过头。
    var jn = [];
    var owner = {}, jseen = {};
    for (i = 0; i < threads.length; i++) {
      var tev = threads[i].events;
      for (j = 0; j < tev.length; j++) (owner[tev[j]] || (owner[tev[j]] = [])).push(threads[i].id);
    }
    for (var ek in owner) {
      if (owner[ek].length < 2 || jseen[ek]) continue;
      jseen[ek] = 1;
      // EV[].cast 是内部形状 {n,ci,w}；契约里 Junction.cast 是**角色名**，这里要落回名字
      var eIdx = +ek, ec = [];
      if (EV[eIdx]) for (j = 0; j < EV[eIdx].cast.length && j < 8; j++) ec.push(EV[eIdx].cast[j].n);
      jn.push({ at: eIdx, threads: owner[ek].slice(0), t: trunkT.map[eIdx] != null ? trunkT.map[eIdx] : 0, cast: ec });
    }
    jn.sort(function (a, b) { return a.at - b.at; });

    var out = [];
    for (i = 0; i < threads.length; i++) {
      var t = threads[i];
      out.push({ id: t.id, kind: t.kind, title: t.title, en: t.en || '', lead: t.lead, cast: t.cast,
        events: t.events, len: t.len, span: t.span, parent: t.parent || null, attach: t.attach == null ? null : t.attach,
        depth: t.depth, heat: t.heat, kindMix: t.kindMix, resolved: !!t.resolved, suspended: !!t.suspended,
        color: t.color, theme: t.theme, quote: t.quote, src: t.src,
        sourceId: t.sourceId, topologyStatus: t.topologyStatus,
        completionKnown: !!t.completionKnown, completion: t.completionKnown ? t.completion : null,
        resolution: t.resolution, declaredParent: t.declaredParent, declaredAttach: t.declaredAttach,
        // anchored=true 表示 parent/attach 是**就近锚点**，不是来源声明的父线 ——
        // 渲染层必须能分辨这两者：真分叉该画成分叉，锚点只能画成待校对的虚线。
        // 不把这面旗子发出去，下游就会把兜底当成事实，这比不兜底更糟。
        anchored: !!t.anchored,
        pendingReason: t.pendingReason || '' });
    }

    var tree = { ok: true, reason: '', src: 'model', fp: fp, strictTopology: true,
      chapters: CH, events: outEvents(), threads: out, trunk: trunk, handoffs: hd, junctions: jn,
      cast: buildCast(threads), warn: warn, unresolved: unresolved, pendingHandoffs: pendingHandoffs, stats: null };
    tree.stats = buildStats(tree, 0);
    return tree;
  }

  // ───────────────────────────────── 对外接口（契约 §2）
  window.CLStory = {
    analyze: analyze,
    get: function () { return CACHE; },
    fingerprint: fingerprint,
    threadOf: function (name) {
      if (!CACHE || !CACHE.ok) return [];
      var n = str(name).trim(), c = CACHE.cast[n];
      if (!c && CIDX[n] != null && CHARS[CIDX[n]]) c = CACHE.cast[CHARS[CIDX[n]].name];   // 传别名也要认
      return c ? c.threads.slice(0) : [];
    },
    stats: function () {
      var t = CACHE || emptyTree(''), s = {}, k;
      for (k in t.stats) s[k] = t.stats[k];
      s.cached = LAST_CACHED; s.ok = !!t.ok; s.src = t.src; s.fp = t.fp; s.reason = t.reason; s.warn = t.warn.length;
      return s;
    }
  };
})();
