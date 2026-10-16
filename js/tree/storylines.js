(function () {
  'use strict';

  var KIND_COLOR = { '高燃': 0xffd166, '转折': 0xffb45c, '抉择': 0xc8a7ff, '冲突': 0xff5d73, '关系': 0xff9ad5, '领悟': 0x7af0c8, '日常': 0x9a92b8 };
  var MAIN_COLOR = [0xffb45c, 0x3fd6a8, 0x8a6cd8, 0xc84dff, 0xfff1da];
  var KINDS = { '高燃': 1, '转折': 1, '抉择': 1, '冲突': 1, '关系': 1, '领悟': 1, '日常': 1 };
  var KIND_W = { '高燃': 1, '转折': 0.95, '抉择': 0.9, '冲突': 0.85, '领悟': 0.7, '关系': 0.6, '日常': 0.4 };
  var TENSE = { '高燃': 1, '转折': 1, '抉择': 1, '冲突': 1 };
  var FAMILY = { '高燃': 'push', '转折': 'push', '抉择': 'push', '冲突': 'push', '领悟': 'inner', '关系': 'inner', '日常': 'flat' };
  var CLOSE_KIND = { '领悟': 1, '抉择': 1, '高燃': 1 };
  var ROLE_IMP = { '主角': 0.96, '反派': 0.88, '核心配角': 0.74, '配角': 0.45, '功能性': 0.2 };
  var CORE_ROLE = { '主角': 1, '反派': 1, '核心配角': 1 };

  var W_CAST = 0.46;
  var W_CHAP = 0.24;
  var W_TOK = 0.20;
  var W_KIND = 0.10;

  var GATE_TOK = 0.10;
  var LINK_MIN = 0.28;
  var MAX_SEG = 12;
  var SEAM_W = 4;
  var PARALLEL_J = 0.34;
  var NAME_MAX = 14;
  var THEME_MAX = 40;

  var STOP_CH = '的了是在和与也就都很更还又把被将从对为以以及其而或但并自己他她它们这那些个一二三四五六七八九十百千不没有上下中前后里外时年月日人多少大小新旧再最只会能要说着过来去到给让向于之所因此如若则乃者吧呢啊哦嗯们你我他';
  var STOP_2 = '一个 自己 他们 她们 我们 你们 这个 那个 什么 已经 可以 没有 不是 就是 以及 于是 因为 所以 但是 然后 之后 之前 第一 一次 一场 一夜 同时 终于 决定 出现 发现 开始 结束 一起 两人 三人 所有 全部 其中 之间 里面 外面 上面 下面 时候 事件 此章 交锋 一句 一半 那些 这些 如果 虽然 而且 并且 只是 还是 也是 什么样';

  var STOPC = {}, STOP2 = {};
  (function () {
    var i;
    for (i = 0; i < STOP_CH.length; i++) STOPC[STOP_CH.charAt(i)] = 1;
    var a = STOP_2.split(' ');
    for (i = 0; i < a.length; i++) if (a[i]) STOP2[a[i]] = 1;
  })();

  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function r3(x) { return Math.round(x * 1000) / 1000; }
  function r6(x) { return Math.round(x * 1e6) / 1e6; }
  function hash(s) { var h = 2166136261, i; for (i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; } return h; }
  function hex8(h) { var s = (h >>> 0).toString(16); while (s.length < 8) s = '0' + s; return s; }
  function str(v) { return v == null ? '' : String(v); }
  function isCJK(c) { return (c >= 0x3400 && c <= 0x9fff) || (c >= 0xf900 && c <= 0xfaff); }
  function isAl(c) { return (c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122); }
  function cut(s, n) { s = str(s); return s.length <= n ? s : s.slice(0, n); }

  function cutSoft(s, n) {
    s = str(s).replace(/\s+/g, ' ');
    if (s.length <= n) return s;
    var head = s.slice(0, n), i, best = -1, p = '，。；、：！？,.;:!?';
    for (i = head.length - 1; i >= Math.floor(n * 0.5); i--) if (p.indexOf(head.charAt(i)) >= 0) { best = i; break; }
    return best > 0 ? head.slice(0, best) : head;
  }

  var EV = [], CH = [], CHARS = [], CIDX = {}, IMP = [], CORE = [], CAMP = [];
  var TOKN = 0, TOKD = {}, DF = [], ASCII_TOK = {}, NEV = 0, TAU = 1, WIN = 16, AXMAX = 2;

  function prepChars(graph) {
    var cs = (graph && graph.characters) || [], i, j, mx = 0, v;
    CHARS = []; CIDX = {}; IMP = []; CORE = []; CAMP = [];
    for (i = 0; i < cs.length; i++) {
      var c = cs[i] || {}, nm = str(c.name).trim();
      if (!nm || CIDX[nm] != null) continue;
      CIDX[nm] = CHARS.length; CHARS.push(c);
      v = typeof c.importance === 'number' && isFinite(c.importance) ? c.importance : -1;
      IMP.push(v); CORE.push(CORE_ROLE[str(c.role)] ? 1 : 0); CAMP.push(str(c.camp));
      if (v > mx) mx = v;
    }
    var div = mx > 1.5 ? 100 : 1;
    for (i = 0; i < IMP.length; i++) {
      IMP[i] = IMP[i] < 0 ? (ROLE_IMP[str(CHARS[i].role)] || 0.35) : clamp(IMP[i] / div, 0, 1);
      if (IMP[i] >= 0.7) CORE[i] = 1;
    }
    for (i = 0; i < CHARS.length; i++) {
      var al = CHARS[i].aliases;
      if (!al || !al.length) continue;
      for (j = 0; j < al.length; j++) { var a = str(al[j]).trim(); if (a && CIDX[a] == null) CIDX[a] = i; }
    }
  }

  function prepEvents(graph) {
    var raw = (graph && graph.events) || [], i, j, e;
    var pre = {}, preN = 0, list = [];
    for (i = 0; i < raw.length; i++) {
      e = raw[i]; if (!e || typeof e !== 'object') continue;
      var cn = str(e.chapter).trim();
      if (pre[cn] == null) pre[cn] = preN++;
      var ord = typeof e.order === 'number' && isFinite(e.order) ? e.order : (parseFloat(e.order) || null);
      list.push({ raw: e, i: i, ord: ord == null ? Infinity : ord, pc: pre[cn], cn: cn });
    }
    list.sort(function (a, b) { return a.ord - b.ord || a.pc - b.pc || a.i - b.i; });

    CH = []; var cmap = {};
    EV = [];
    var sum = [], mxw = 0;
    for (i = 0; i < list.length; i++) {
      var it = list[i], r = it.raw;
      if (cmap[it.cn] == null) { cmap[it.cn] = CH.length; CH.push({ name: it.cn, idx: CH.length, n: 0 }); }
      var ci = cmap[it.cn]; CH[ci].n++;
      var kind = str(r.kind).trim(); if (!KINDS[kind]) kind = '日常';
      var cast = [], seen = {}, ids = [], w = 0;
      var rc = r.characters || [];
      for (j = 0; j < rc.length; j++) {
        var nm = str(rc[j]).trim(); if (!nm) continue;
        var ci2 = CIDX[nm];
        if (ci2 == null) { if (!seen['?' + nm]) { seen['?' + nm] = 1; cast.push({ n: nm, ci: -1, w: 0.12 }); w += 0.12; } continue; }
        if (seen[ci2]) continue; seen[ci2] = 1;
        cast.push({ n: CHARS[ci2].name, ci: ci2, w: IMP[ci2] }); ids.push(ci2); w += IMP[ci2];
      }
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

    var useCh = CH.length >= 3, bucket = Math.max(1, Math.ceil(NEV / 12));
    for (i = 0; i < NEV; i++) EV[i].ax = useCh ? EV[i].chapIdx : Math.floor(i / bucket);
    AXMAX = NEV ? EV[NEV - 1].ax + 1 : 1;
    TAU = clamp(Math.round(AXMAX / 10), 1, 6);
    var epc = NEV / Math.max(1, AXMAX);
    WIN = clamp(Math.round(epc * 8), 12, 40);
  }

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
          if (STOPC[g.charAt(0)] && STOPC[g.charAt(1)]) continue;
          out.push(g);
        }
        run = '';
      }
    }
    return out;
  }

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

  function castJac(a, b) {
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
    if (ka === kb) return 1;
    return FAMILY[ka] === FAMILY[kb] ? 0.55 : 0.15;
  }
  function affinity(a, b) {
    var jac = castJac(a, b), dice = tokDice(a, b);
    if (jac <= 0 && dice < GATE_TOK) return 0;
    var d = Math.abs(b.ax - a.ax);
    var dec = 1 / (1 + Math.pow(d / TAU, 1.35));
    return W_CAST * jac + W_CHAP * dec + W_TOK * dice + W_KIND * kindCont(a.kind, b.kind);
  }

  function buildChains() {
    var prev = new Array(NEV), pa = new Array(NEV), kids = new Array(NEV), i, j, lo, a, best, bestA;
    var chapMax = Math.max(2, TAU * 3);
    for (j = 0; j < NEV; j++) { kids[j] = null; prev[j] = -1; pa[j] = 0; }
    for (j = 0; j < NEV; j++) {
      best = -1; bestA = 0; lo = j - WIN < 0 ? 0 : j - WIN;
      for (i = j - 1; i >= lo; i--) {
        if (EV[j].ax - EV[i].ax > chapMax) continue;
        a = affinity(EV[i], EV[j]);
        if (a > bestA + 1e-9) { bestA = a; best = i; }
      }
      if (bestA >= LINK_MIN && best >= 0) { prev[j] = best; pa[j] = bestA; }
    }
    for (j = 0; j < NEV; j++) if (prev[j] >= 0) (kids[prev[j]] || (kids[prev[j]] = [])).push(j);
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

  function absorbSingles(chains, warn) {
    var multi = [], single = [], i, j;
    for (i = 0; i < chains.length; i++) (chains[i].length > 1 ? multi : single).push(chains[i]);
    if (!single.length) return chains;
    if (!multi.length) {
      var all = [];
      for (i = 0; i < chains.length; i++) all.push(chains[i][0]);
      all.sort(function (a, b) { return a - b; });
      warn.push('全书没有任何两个剧情点达到成链阈值，' + all.length + ' 个点按序并为一条线');
      return [all];
    }
    var own = {};
    for (i = 0; i < multi.length; i++) for (j = 0; j < multi[i].length; j++) own[multi[i][j]] = i;
    var moved = 0;
    single.sort(function (a, b) { return a[0] - b[0]; });
    for (i = 0; i < single.length; i++) {
      var e = single[i][0], bi = -1, ba = -1, k, lo = e - WIN < 0 ? 0 : e - WIN, hi = Math.min(NEV - 1, e + WIN);
      for (k = lo; k <= hi; k++) {
        if (own[k] == null) continue;
        var a = affinity(EV[Math.min(e, k)], EV[Math.max(e, k)]);
        var sc = a * 1000 - Math.abs(k - e);
        if (sc > ba) { ba = sc; bi = own[k]; }
      }
      if (bi < 0) { bi = 0; for (k = 0; k < multi.length; k++) if (Math.abs(multi[k][0] - e) < Math.abs(multi[bi][0] - e)) bi = k; }
      multi[bi].push(e); own[e] = bi; moved++;
    }
    for (i = 0; i < multi.length; i++) multi[i].sort(function (a, b) { return a - b; });
    if (moved) warn.push('孤点并线 ' + moved + ' 个（无独立成线的剧情点已并入最亲和的线）');
    return multi;
  }

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
    var core = 0.08 + 0.92 * (allW > 0 ? coreW / allW : 0);
    return { evs: ch, len: ch.length, nch: nch, sumW: sw, first: ch[0], last: ch[ch.length - 1],
      fc: EV[ch[0]].chapIdx, lc: EV[ch[ch.length - 1]].chapIdx, fa: EV[ch[0]].ax, la: EV[ch[ch.length - 1]].ax,
      score: r6(chapCov * wShare * core) };
  }

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
  function handoffReason(ev, sm, gap) {
    var base = ev.title || cutSoft(ev.summary, 18) || ev.chapter;
    if (sm.shared.length) return cut(base + '（共 ' + sm.shared.slice(0, 3).join('、') + '）', 34);
    if (gap > 0) return cut(base + '（隔 ' + gap + ' 章无主干）', 34);
    return cut(base, 34);
  }
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
      for (pass = 0; pass < 2 && pick < 0; pass++, minTail = 1) for (i = 0; i < infos.length; i++) {
        if (used[i]) continue;
        var inf = infos[i];
        if (inf.la <= cursorAx) continue;
        var tail = [], k;
        for (k = 0; k < inf.evs.length; k++) if (inf.evs[k] > cursor) tail.push(inf.evs[k]);
        if (tail.length < minTail) continue;
        var gap = EV[tail[0]].ax - cursorAx;
        if (gap > gapMax) continue;
        var sm = seam(segs[segs.length - 1].evs, tail);
        var link = clamp(sm.jac + 0.35 * sm.dice, 0, 1);
        var sc = inf.score * (0.35 + 0.65 * link) / (1 + Math.max(0, gap) / TAU);
        if (sc > pickScore + 1e-12 || (Math.abs(sc - pickScore) <= 1e-12 && pick >= 0 && tail[0] < pickTail[0])) {
          pickScore = sc; pick = i; pickTail = tail; pickGap = gap;
        }
      }
      if (pick < 0) break;
      var inf2 = infos[pick], tail2 = pickTail;
      var sm2 = seam(segs[segs.length - 1].evs, tail2);
      var overlap = inf2.fa <= infos[segs[segs.length - 1].ci].la;
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

  function idfOf(g) { var id = TOKD[g]; return id == null ? 0 : Math.log(NEV / (1 + DF[id])); }
  function phraseIdf(p) {
    if (p.length < 2) return 0;
    var mn = 1e9, k;
    for (k = 0; k + 1 < p.length; k++) { var v = idfOf(p.substr(k, 2)); if (v <= 0) return 0; if (v < mn) mn = v; }
    return mn;
  }
  function nameOf(evs, lead) {
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
            if (s + k + L <= tl) inT[p] = 1;
          }
        }
        s = j + 1;
      }
    }
    var need = evs.length >= 2 ? 2 : 1, bestP = '', bestS = 0, key;
    for (key in docs) {
      if (docs[key] < need) continue;
      if (key === lead) continue;
      var idf = phraseIdf(key);
      if (idf <= 0) continue;
      var sc = docs[key] * idf * (1 + 0.08 * (key.length - 2)) * (inT[key] ? 1.25 : 1);
      if (sc > bestS + 1e-9 || (Math.abs(sc - bestS) <= 1e-9 && (key.length > bestP.length || (key.length === bestP.length && key < bestP)))) { bestS = sc; bestP = key; }
    }
    if (bestP) return bestP.length <= 2 && lead ? cut(lead + ' · ' + bestP, NAME_MAX) : cut(bestP, NAME_MAX);
    var hot = evs[0], hw = -1;
    for (i = 0; i < evs.length; i++) { var h = EV[evs[i]].w * (KIND_W[EV[evs[i]].kind] || 0.4); if (h > hw + 1e-12) { hw = h; hot = evs[i]; } }
    var t2 = EV[hot].title;
    return t2 && t2.length <= NAME_MAX && t2 !== lead ? t2 : '';
  }
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
    th.heat = r3(sw > 0 ? clamp(tw / sw, 0, 1) : 0);
    var lst = [];
    for (i = 0; i < names.length; i++) lst.push(cast[names[i]]);
    lst.sort(function (a, b) { return b.w - a.w || b.n - a.n || (a.name < b.name ? -1 : 1) });
    for (i = 0; i < lst.length; i++) lst[i].w = r3(lst[i].w);
    th.cast = lst;
    if (!th.lead) th.lead = lst.length ? lst[0].name : '';
    var hotEv = EV[hotI];
    if (!th.theme) th.theme = cutSoft(hotEv.summary || hotEv.title, THEME_MAX);
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
    th.suspended = th.kind === 'main' && !th.lastSeg ? false : (!th.resolved && last.ax < lastAx - early);
    return th;
  }

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
      if (only && !only[th.id]) continue;
      var head = EV[th.events[0]], bestT = -1, bestTa = -1, bestTaf = 0, bestB = -1, bestBa = -1, bestBaf = 0;
      for (var ax2 = head.ax - chapMax; ax2 <= head.ax + 1; ax2++) {
        var lst = byAx[ax2];
        if (!lst) continue;
        for (k = 0; k < lst.length; k++) {
          var t = lst[k], a = affinity(EV[Math.min(t, head.i)], EV[Math.max(t, head.i)]);
          var sc = a * 1000 - Math.abs(head.ax - EV[t].ax);
          if (sc > bestTa) { bestTa = sc; bestT = t; bestTaf = a; }
        }
      }
      if (bestT < 0) {
        for (k = 0; k < trunkEvs.length; k++) if (bestT < 0 || Math.abs(trunkEvs[k] - th.events[0]) < Math.abs(bestT - th.events[0])) bestT = trunkEvs[k];
      }
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
          break;
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
        if (!lst || c.w < 0.25) continue;
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
  function tOf(ev, trunkT) {
    if (trunkT.map[ev] != null) return trunkT.map[ev];
    return r6(AXMAX > 1 ? clamp(EV[ev].ax / (AXMAX - 1), 0, 1) : 0);
  }

  function emptyTree(reason, fp) {
    return { ok: false, reason: reason || '', src: 'derived', fp: fp || '',
      chapters: [], events: [], threads: [],
      trunk: { segments: [], events: [], len: 0, chapters: 0, gaps: [] },
      handoffs: [], junctions: [], cast: {}, warn: [], unresolved: [], pendingHandoffs: [], lineHonesty: null,
      stats: { events: 0, threads: 0, main: 0, branches: 0, twigs: 0, trunkLen: 0, trunkChapters: 0, trunkSegs: 0,
        handoffs: 0, junctions: 0, maxBranchLen: 0, avgBranchLen: 0, suspended: 0, castCovered: 0, coverage: 0,
        declaredLines: 0, mechLines: 0, ms: 0 } };
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
    var covEvents = 0, seenEv = {};
    for (var ei = 0; ei < th.length; ei++) {
      var le = th[ei].events || [];
      for (var ej = 0; ej < le.length; ej++) {
        var key2 = String(le[ej]);
        if (!seenEv[key2]) { seenEv[key2] = 1; covEvents++; }
      }
    }
    return { events: NEV, threads: th.length, main: main, branches: br, twigs: tw,
      trunkLen: tree.trunk.len, trunkChapters: tree.trunk.chapters, trunkSegs: tree.trunk.segments.length,
      handoffs: tree.handoffs.length, junctions: tree.junctions.length,
      maxBranchLen: mx, avgBranchLen: n ? Math.round(sum / n * 100) / 100 : 0, suspended: susp,
      castCovered: cov, coverage: tot ? r3(cov / tot) : 0, ms: ms,
      eventCovered: covEvents, eventCoverage: NEV ? r3(covEvents / NEV) : 0,
      unassignedEvents: Math.max(0, NEV - covEvents),
      castTotal: tot,
      chapters: tree.trunk.chapters };
  }

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

  var MKIND = { '主线': 'main', '支线': 'branch', '末梢': 'twig' };
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
      warn.push('model 没有标出任何主线，主干回落到推导结果');
      return null;
    }
    mains.sort(function (a, b) { return a.events[0] - b.events[0] || (a.mid < b.mid ? -1 : 1); });
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
    if (sl && sl.length) { out.push('SL', sl.length); for (i = 0; i < sl.length; i++) { var s = sl[i] || {}; out.push(str(s.id), str(s.kind), str(s.name), str(s.parent), str(s.parentBasis), str(s.parentRelation), str(s.attach_order), str(s.handoff_from), str(s.handoff_reason), str(s.completion), str(s.resolution), str(s.summary), str(s.quote), str(s.goal), (s.events || []).join('.')); } }
    return out.join('');
  }
  function fingerprint(graph) { return 'sl-' + hex8(hash(digest(graph))); }

  var CACHE = null, CACHE_FP = '', LAST_CACHED = false;
  var MS_FP = {}, MS_KEYS = [];
  function msOf(fp, real) {
    if (MS_FP[fp] != null) return MS_FP[fp];
    MS_FP[fp] = real; MS_KEYS.push(fp);
    if (MS_KEYS.length > 32) delete MS_FP[MS_KEYS.shift()];
    return real;
  }

  function now() { return (window.performance && performance.now) ? performance.now() : +new Date(); }
  function analyze(graph, opts) {
    opts = opts || {};
    var fp = fingerprint(graph);
    var legacy = !!(opts.legacy || opts.noModel);
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
    var strictRan = !!(opts.strict || (!legacy && graph && graph.storylines && graph.storylines.length));
    tree.strictTopology = strictRan;
    if (strictRan && tree.threads && !tree.threads.length) tree.src = 'none';
    tree.stats.ms = msOf(key, Math.round(now() - t0));
    applyHonesty(tree, graph);
    CACHE = tree; CACHE_FP = key;
    return tree;
  }

  function run(graph, opts, fp) {
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
        warn.push('来源线 id 重复：' + mid + '，第二条列为待校对');
        dropped.push({ threadId: null, sourceId: mid, kind: kk.kind, parent: str(s.parent).trim(),
          attach: attOrder0, reasons: '来源线 id 重复；归属歧义，不并入已解析的同名线', events: [] });
        continue;
      }
      if (!evs.length) {
        var why = bad ? ('引用了 ' + bad + ' 个不存在的 order，无有效剧情点') : '没有剧情点';
        warn.push('来源线 ' + mid + ' ' + why + '，列为待校对');
        dropped.push({ threadId: null, sourceId: mid, kind: kk.kind, parent: str(s.parent).trim(),
          attach: attOrder0, reasons: why, events: [] });
        continue;
      }
      evs.sort(function (a, b) { return a - b; });
      var lead = str(s.lead).trim();
      if (lead && CIDX[lead] == null) { warn.push('来源线 ' + mid + ' 的 lead「' + lead + '」不在角色表里，已清空'); lead = ''; }
      var comp = null, cnum = (typeof s.completion === 'number' && isFinite(s.completion)) ? s.completion : null;
      if (cnum != null) { if (cnum >= 0 && cnum <= 1) comp = cnum; else warn.push('来源线 ' + mid + ' 的 completion「' + cnum + '」不在 0..1，按未知处理'); }
      var attOrder = attOrder0;
      var rec = {
        mid: mid, kind: kk.kind, events: evs, lead: lead,
        title: cut(str(s.name).trim(), NAME_MAX), theme: cutSoft(str(s.theme), THEME_MAX),
        parent: str(s.parent).trim(), parentBasis: str(s.parentBasis).trim(), parentRelation: str(s.parentRelation).trim(), attachOrder: attOrder,
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

  function validateSource(src, warn) {
    var recs = src.recs, byMid = src.byMid, i;
    for (i = 0; i < recs.length; i++) {
      var r = recs[i];
      if (r.kind === 'main') { r.status = r.reasons.length ? 'pending' : 'confirmed'; r.depth = 0; continue; }
      if (r.parentBasis === 'layout') r.reasons.push('parent 仅为布局挂点，剧情父线尚未确认');
      if (!r.parent) { r.reasons.push('缺少 parent（来源未给出挂靠线）'); continue; }
      if (r.parent === r.mid) { r.reasons.push('parent 指向自己'); continue; }
      var pr = byMid[r.parent];
      if (!pr) { r.reasons.push('parent「' + r.parent + '」不存在'); continue; }
      if (r.attachOrder === '') { r.reasons.push('缺少 attach_order'); continue; }
      if (r.attach == null) { r.reasons.push('attach_order「' + r.attachOrder + '」不是有效剧情点'); continue; }
      if (pr.events.indexOf(r.attach) < 0) { r.reasons.push('attach 点不属于父线「' + r.parent + '」'); continue; }
      if (r.attach > r.events[0]) { r.reasons.push('未来挂点：attach 晚于本线起始事件'); continue; }
    }
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

  function mkThread(rec, seg, lastSeg, tw, taken) {
    return enrich({
      id: '', kind: rec.kind, seg: rec.kind === 'main' ? seg : -1, lastSeg: !!lastSeg,
      en: null, lead: rec.lead, title: rec.title, theme: rec.theme, quote: '',
      events: rec.events.slice(0), parent: null, attach: null, depth: rec.status === 'confirmed' ? rec.depth : 1,
      score: chainInfo(rec.events, tw).score, src: 'model',
      sourceId: rec.mid, topologyStatus: rec.status,
      completionKnown: rec.completionKnown, completion: rec.completion,
      resolution: rec.resolution,
      declaredParent: rec.parent, declaredAttach: rec.attachOrder, parentBasis: rec.parentBasis, parentRelation: rec.parentRelation,
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
    if (!raw.length) return indexTree(fp, warn);

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
        if (pr) { th.parent = pr.id; th.attach = th._att; th.depth = pr.depth + 1; th.kind = th.depth >= 2 ? 'twig' : 'branch'; }
        else { th.topologyStatus = 'pending'; th.pendingReason = th.pendingReason || '父线未确认，暂不挂接'; }
      }
      if (th.topologyStatus !== 'confirmed') {
        th.parent = null; th.attach = null; th.depth = 1;
        unresolved.push({ threadId: th.id, sourceId: th.sourceId, kind: th.kind,
          parent: th.declaredParent, attach: th.declaredAttach, reasons: th.pendingReason, events: th.events.slice(0) });
        th.kind = 'branch';
      }
    }
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
        if (!bestM) { bestM = mainsT[0]; bestAt = mainsT[0].events[0]; }
        oth.parent = bestM.id; oth.attach = bestAt; oth.depth = 1; oth.kind = 'branch';
        oth.anchored = true;
      }
    }
    if (unresolved.length) warn.push('来源结构有 ' + unresolved.length + ' 条坏边/待校对线，已隔离为待校对轨（就近锚到主干，不冒充来源结构）');

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

    for (i = 0; i < threads.length; i++) {
      var tr = threads[i];
      if (tr.resolution === '收束') { tr.resolved = true; tr.suspended = false; }
      else if (tr.resolution === '悬置') { tr.resolved = false; tr.suspended = true; }
      else { tr.resolved = false; tr.suspended = false; }
    }

    var hd = [];
    for (i = 1; i < mainRecs.length; i++) {
      var toR = mainRecs[i], fromR = mainRecs[i - 1];
      if (toR.status !== 'confirmed' || fromR.status !== 'confirmed') continue;
      if (!toR.handoffOK || toR.handoffFrom !== fromR.mid) continue;
      var fth = byMid[fromR.mid], tth = byMid[toR.mid];
      if (!fth || !tth) continue;
      var atEv = toR.events[0];
      var sm = seam(fromR.events, toR.events);
      var fLa = EV[fromR.events[fromR.events.length - 1]].ax, tFa = EV[toR.events[0]].ax;
      var overlap = tFa <= fLa, gap = Math.max(0, tFa - fLa);
      hd.push({ at: atEv, from: fth.id, to: tth.id, t: trunkT.map[atEv] != null ? trunkT.map[atEv] : 0,
        shared: sm.shared.slice(0, 8), reason: toR.handoffReason, kind: handoffKind(sm, overlap, gap), src: 'model' });
    }
    var jn = [];
    var owner = {}, jseen = {};
    for (i = 0; i < threads.length; i++) {
      var tev = threads[i].events;
      for (j = 0; j < tev.length; j++) (owner[tev[j]] || (owner[tev[j]] = [])).push(threads[i].id);
    }
    for (var ek in owner) {
      if (owner[ek].length < 2 || jseen[ek]) continue;
      jseen[ek] = 1;
      var eIdx = +ek, ec = [];
      if (EV[eIdx]) for (j = 0; j < EV[eIdx].cast.length && j < 8; j++) ec.push(EV[eIdx].cast[j].n);
      jn.push({ at: eIdx, threads: owner[ek].slice(0), t: trunkT.map[eIdx] != null ? trunkT.map[eIdx] : 0, cast: ec });
    }
    jn.sort(function (a, b) { return a.at - b.at; });

    var coveredEv = {};
    for (i = 0; i < threads.length; i++) {
      var cev = threads[i].events || [];
      for (var ci = 0; ci < cev.length; ci++) coveredEv[cev[ci]] = 1;
    }
    var uncoveredN = 0;
    for (i = 0; i < NEV; i++) if (!coveredEv[i]) uncoveredN++;
    if (uncoveredN) {
      warn.push('来源 storylines 只覆盖 ' + (NEV - uncoveredN) + '/' + NEV +
        ' 个剧情点：**' + uncoveredN + ' 个事件不在任何故事线里**（只作为事件保留，不臆造归属）');
    }

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
        parentBasis: t.parentBasis, parentRelation: t.parentRelation,
        anchored: !!t.anchored,
        pendingReason: t.pendingReason || '' });
    }

    var tree = { ok: true, reason: '', src: 'model', fp: fp, strictTopology: true,
      chapters: CH, events: outEvents(), threads: out, trunk: trunk, handoffs: hd, junctions: jn,
      cast: buildCast(threads), warn: warn, unresolved: unresolved, pendingHandoffs: pendingHandoffs, stats: null };
    tree.stats = buildStats(tree, 0);
    return tree;
  }

  var GOAL_MIN = 6;
  var MECH_LEN_TOL = 0.03;

  function objectiveOf(line) {
    var g = line && line.goal;
    if (typeof g === 'string' && g.trim().length >= GOAL_MIN) return { state: 'declared', reason: 'goal 文本 ' + g.trim().length + ' 字', text: cut(g.trim(), 48) };
    if (g == null) return { state: 'none', reason: 'goal 字段缺席' };
    if (typeof g === 'string') return { state: 'none', reason: g.trim() ? ('goal 仅 ' + g.trim().length + ' 字，不足 ' + GOAL_MIN) : 'goal 为空串' };
    return { state: 'none', reason: 'goal 类型异常（' + (Array.isArray(g) ? '数组' : typeof g) + '，非文本目标）' };
  }

  function mechRun(cands, keyOf) {
    cands.sort(function (a, b) { return a.first - b.first || (a.last - b.last) || keyOf(a).localeCompare(keyOf(b)); });
    var best = [], i, run = [cands[0]];
    for (i = 1; i < cands.length; i++) {
      var prev = run[run.length - 1], cur = cands[i];
      var contiguous = prev.last + 1 === cur.first;
      var even = cur.len <= prev.len ? (cur.len >= prev.len * (1 - MECH_LEN_TOL)) : (prev.len >= cur.len * (1 - MECH_LEN_TOL));
      if (contiguous && even) { run.push(cur); continue; }
      if (run.length >= 2 && run.length > best.length) best = run;
      run = [cur];
    }
    if (run.length >= 2 && run.length > best.length) best = run;
    return best;
  }

  function honestyOf(graph) {
    var g = graph || {}, raw = g.storylines || [], meta = g.meta || {}, cur = meta.storylines || {};
    var provenanceDerived = !!(cur.derived === true || cur.src === 'local-completion' || cur.src === 'derived' ||
      (meta.completion && meta.completion.method === 'existing-graph-local-completion'));
    var rows = [], cands = [], i, j, s, orders;
    for (i = 0; i < raw.length; i++) {
      s = raw[i];
      if (!s || typeof s !== 'object') continue;
      var id = str(s.id).trim() || ('S' + (i + 1));
      var ob = objectiveOf(s), first = Infinity, last = -Infinity;
      orders = s.events || [];
      for (j = 0; j < orders.length; j++) {
        var o = +orders[j];
        if (!isFinite(o)) continue;
        if (o < first) first = o;
        if (o > last) last = o;
      }
      var row = { id: id, objective: ob.state, reason: ob.reason, text: ob.text || '', mechanical: false, first: isFinite(first) ? first : null, len: orders.length };
      rows.push(row);
      if (ob.state === 'none' && isFinite(first)) cands.push({ id: id, first: first, last: last, len: orders.length });
    }
    var structural = false, mechIds = {};
    if (cands.length >= 2) {
      var run = mechRun(cands.slice(0), function (x) { return x.id; });
      if (run.length >= 2) { structural = true; for (i = 0; i < run.length; i++) mechIds[run[i].id] = 1; }
    }
    var declared = 0, mechanical = 0, unknown = 0;
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      r.mechanical = r.objective === 'none' && (provenanceDerived || !!mechIds[r.id]);
      if (r.objective === 'declared') declared++;
      else if (r.mechanical) mechanical++;
      else unknown++;
    }
    var verdict = !rows.length ? 'none' :
      (declared + mechanical + unknown === declared ? 'all-declared' :
       (mechanical === rows.length ? 'all-mechanical' : 'mixed'));
    return { version: 'honesty/1', lines: rows, total: rows.length, declared: declared, mechanical: mechanical,
      unknown: unknown, structural: structural, provenanceDerived: provenanceDerived, verdict: verdict };
  }

  function applyHonesty(tree, graph) {
    var h = honestyOf(graph), byId = {}, mech = 0, decl = 0, unk = 0, i;
    for (i = 0; i < h.lines.length; i++) byId[h.lines[i].id] = h.lines[i];
    var taskIdx = {};
    var tasks = (graph && graph.tasks) || [];
    for (i = 0; i < tasks.length; i++) {
      var tk = tasks[i]; if (!tk || tk.id == null) continue;
      var eids = tk.eventIds || [];
      for (var k = 0; k < eids.length; k++) {
        var key = String(eids[k]);
        (taskIdx[key] = taskIdx[key] || []).push(String(tk.id));
      }
    }
    var taskById = {};
    for (i = 0; i < tasks.length; i++) if (tasks[i] && tasks[i].id != null) taskById[String(tasks[i].id)] = tasks[i];
    var th = (tree && tree.threads) || [];
    for (i = 0; i < th.length; i++) {
      var t = th[i], row = t.sourceId != null ? byId[t.sourceId] : null;
      var seen = {}, tids = [], evs = t.events || [];
      var gevents = (graph && graph.events) || [];
      var idFrom = function (v) {
        if (v && typeof v === 'object') return v.id != null ? String(v.id) : null;
        var n = Number(v);
        if (isFinite(n) && n >= 1 && n <= gevents.length && gevents[n - 1] && gevents[n - 1].id != null) return String(gevents[n - 1].id);
        return v == null ? null : String(v);
      };
      for (var q = 0; q < evs.length; q++) {
        var eid2 = idFrom(evs[q]);
        if (eid2 == null) continue;
        var hit = taskIdx[eid2];
        if (!hit) continue;
        for (var z = 0; z < hit.length; z++) if (!seen[hit[z]]) { seen[hit[z]] = 1; tids.push(hit[z]); }
      }
      tids.sort();
      var withGoal = 0;
      for (var g2 = 0; g2 < tids.length; g2++) {
        var tt = taskById[tids[g2]];
        if (tt && typeof tt.goal === 'string' && tt.goal.trim()) withGoal++;
      }
      t.taskIds = tids;
      t.taskGoalCount = withGoal;
      if (row) {
        t.objective = row.objective; t.autoSegment = !!row.mechanical;
        t.objectiveText = row.objective === 'declared' ? row.text : ''; t.objectiveReason = row.reason;
      } else {
        t.objective = 'unknown'; t.autoSegment = false; t.objectiveText = ''; t.objectiveReason = '无对应来源线（推导产物）';
      }
      if (t.objective === 'declared') decl++; else if (t.autoSegment) mech++; else unk++;
    }
    if (tree) {
      tree.lineHonesty = { version: h.version, total: h.total, declared: h.declared, mechanical: h.mechanical, unknown: h.unknown,
        structural: h.structural, provenanceDerived: h.provenanceDerived, verdict: h.verdict };
      if (tree.stats) { tree.stats.declaredLines = decl; tree.stats.mechLines = mech; }
      if (h.mechanical) tree.warn = [].concat(tree.warn || [], ['诚实分层：' + h.mechanical + '/' + h.total + ' 条来源线为无目标自动分段（非作者结构），已降权展示，不作为任务深度证据']);
    }
    return tree;
  }

  window.CLStory = {
    analyze: analyze,
    get: function () { return CACHE; },
    fingerprint: fingerprint,
    objectiveOf: objectiveOf,
    honestyOf: honestyOf,
    GOAL_MIN: GOAL_MIN,
    threadOf: function (name) {
      if (!CACHE || !CACHE.ok) return [];
      var n = str(name).trim(), c = CACHE.cast[n];
      if (!c && CIDX[n] != null && CHARS[CIDX[n]]) c = CACHE.cast[CHARS[CIDX[n]].name];
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
