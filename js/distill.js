/* Castline · distill.js — 文风蒸馏客户端
 *
 * 契约：**只有用户点「开始蒸馏」才会发起模型调用。** 打开面板只走 probe（服务端只读、零调用），
 * 载入图谱、切作品、刷新页面都不会触发蒸馏。
 *
 *   CLDistill.probe(docs)            → {key, cached, running_job, cjk, samples_planned, ...}
 *   CLDistill.load(docs)             → {distill}（取已有结果，仍然零调用）
 *   CLDistill.run(docs, opt)         → Promise<distill>；opt = {names, title, force, onEvent, control}
 *   CLDistill.cancel(job)            → Promise
 */
(function () {
  'use strict';

  function post(body) {
    return fetch('/api/distill', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || ('服务返回 ' + r.status)); return d; }); });
  }

  function slim(docs) {
    return docs.map(function (d) { return { path: d.path, name: d.name, text: d.text, kind: d.kind }; });
  }

  function probe(docs) { return post({ docs: slim(docs), probe: true }); }
  /** 后台是否还在跑旧代码。蒸馏的硬性度量是不可协商的结论，
   *  旧进程的算法版本不同就会给出不同的句长 / 对白占比 —— 必须当面拦住，
   *  而不是让用户拿着一份数字错了的提示词去写作。 */
  function staleServer() {
    return fetch('/api/health').then(function (r) { return r.json(); }).then(function (h) {
      if (!h || !h.build) return '后台是更早启动的旧进程（/api/health 没有 build 字段）';
      if (h.build_disk && h.build !== h.build_disk) return '源码已更新，后台仍在跑旧进程';
      return '';
    }).catch(function () { return ''; });
  }
  function load(docs) { return post({ docs: slim(docs), load: true }); }
  function cancel(job) {
    return fetch('/api/cancel', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ job: job || '' }) })
      .then(function (r) { return r.json(); }).catch(function () { return { ok: false }; });
  }

  function cancelErr(msg) { var e = new Error(msg || '已取消蒸馏'); e.cancelled = true; return e; }

  function run(docs, opt) {
    opt = opt || {};
    var emit = opt.onEvent || function () {};
    var ctl = opt.control || {};
    var ac = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    ctl.abort = function () { ctl.aborted = true; if (ac) try { ac.abort(); } catch (e) {} };
    var payload = { docs: slim(docs), names: opt.names || [], title: opt.title || '', force: !!opt.force };
    return fetch('/api/distill', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload), signal: ac ? ac.signal : undefined
    }).catch(function (e) {
      if (ctl.aborted) throw cancelErr();
      throw new Error('无法连接本地服务（' + (e && e.message) + '）。请确认 python3 -s serve.py 8000 正在运行。');
    }).then(function (resp) {
      if (!resp.ok) throw new Error('服务返回 ' + resp.status + '。蒸馏接口需要新版 serve.py —— 请重启本地服务。');
      if (!resp.body) throw new Error('浏览器不支持流式响应');
      var reader = resp.body.getReader(), dec = new TextDecoder('utf-8'), buf = '';
      return new Promise(function (res, rej) {
        var result = null, ended = false;
        function fin(fn, arg) { if (ended) return; ended = true; fn(arg); }
        function pump() {
          reader.read().then(function (r) {
            if (r.done) {
              if (result) return fin(res, result);
              if (ctl.aborted) return fin(rej, cancelErr());
              return fin(rej, new Error('与服务端的连接中断。蒸馏没有块级缓存，需要重新开始。'));
            }
            buf += dec.decode(r.value, { stream: true });
            var idx;
            while ((idx = buf.indexOf('\n\n')) >= 0) {
              var block = buf.slice(0, idx); buf = buf.slice(idx + 2);
              var ev = 'message', data = '';
              block.split('\n').forEach(function (ln) {
                if (ln.indexOf('event:') === 0) ev = ln.slice(6).trim();
                else if (ln.indexOf('data:') === 0) data += ln.slice(5).trim();
              });
              var obj = null;
              try { obj = data ? JSON.parse(data) : {}; } catch (e2) { obj = { raw: data }; }
              if (ev === 'hello') { ctl.job = obj.job; ctl.cancel = function () { ctl.cancelling = true; return cancel(obj.job); }; }
              if (ev === 'error') { emit(ev, obj); return fin(rej, new Error(obj.message || '蒸馏失败')); }
              if (ev === 'cancelled') { emit(ev, obj); return fin(rej, cancelErr(obj.message)); }
              if (ev === 'done') result = obj.distill;
              emit(ev, obj);
            }
            pump();
          }).catch(function (e) {
            if (ctl.aborted) return fin(rej, cancelErr());
            fin(rej, new Error('读取蒸馏流失败：' + (e && e.message)));
          });
        }
        pump();
      });
    });
  }

  window.CLDistill = { probe: probe, load: load, run: run, cancel: cancel };

  // =========================================================================
  // 面板：方案 → 进度 → 结果。整个状态机放在这里，app.js 只提供读取接口，
  // 这样图谱侧的改动和蒸馏侧的改动不会互相牵动。
  // =========================================================================
  var $ = function (id) { return document.getElementById(id); };
  var showEl = function (idOrEl, on, displayVal) {
    var el = typeof idOrEl === 'string' ? $(idOrEl) : idOrEl;
    if (!el) return;
    el.classList.toggle('is-hidden', !on);
    el.style.display = on ? (displayVal || '') : 'none';
  };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fmt(n) { n = +n || 0; return n >= 1e8 ? (n / 1e8).toFixed(2) + ' 亿' : n >= 1e4 ? (n / 1e4).toFixed(1) + ' 万' : String(n); }
  function dur(s) { s = Math.max(0, Math.round(s)); var m = Math.floor(s / 60); return m ? m + 'm ' + (s % 60) + 's' : s + 's'; }

  var PHASES = ['measure', 'sample', 'soak', 'codex', 'mind', 'arch', 'voice', 'guard', 'assemble', 'fidelity'];
  var PH_NAME = { cache: '命中缓存', measure: '硬性度量', sample: '场景取样', soak: '样本浸泡', codex: '文风法典',
    mind: '作者思维', arch: '构思引擎', voice: '声纹提取', guard: 'AI 病灶对照', assemble: '拼装文档',
    fidelity: '保真回测' };
  // 各阶段占进度条的权重：浸泡是唯一按批走的阶段，权重最大；回测是两次试写，比分析阶段快
  var PH_W = { measure: 2, sample: 3, soak: 34, codex: 13, mind: 11, arch: 12, voice: 10, guard: 6,
    assemble: 2, fidelity: 7 };

  var panel, RES = null, PROBE = null, CTL = null, running = false, ticker = null, t0 = 0, tab = 'prompt', lastDocs = null;

  function open() {
    if (!panel) return;
    if ($('library')) $('library').classList.remove('on');
    if ($('apiPanel')) $('apiPanel').classList.remove('on', 'must');
    panel.classList.add('on');
    show('plan');
    refreshPlan();
  }
  function close() {
    if (running) {
      panel.classList.remove('on');
      if (window.CLApp) CLApp.toast('文风蒸馏在后台继续 · 右下角运行环可查看进度并随时点回');
      return;
    }
    panel.classList.remove('on');
  }
  function show(which) {
    showEl('dsPlanView', which === 'plan');
    showEl('dsRunView', which === 'run');
    showEl('dsResultView', which === 'result');
  }

  /** 取材料：托盘优先，其次从作品库回填当前图谱的材料 */
  function docsFor() {
    var ds = window.CLApp ? CLApp.docs() : [];
    if (ds.length) return Promise.resolve(ds);
    if (!window.CLApp) return Promise.reject(new Error('页面还没准备好'));
    return CLApp.loadDocs().then(function () { return CLApp.docs(); });
  }

  function refreshPlan() {
    var box = $('dsPlan');
    box.innerHTML = '<div class="ds-loading">读取材料…</div>';
    showEl('dsWarn', false);
    $('dsStart').disabled = true;
    showEl('dsForce', false);
    showEl('dsOpenCached', false);
    Promise.all([docsFor(), staleServer()]).then(function (pair) {
      var ds = pair[0], stale = pair[1];
      lastDocs = ds;
      return probe(ds).then(function (p) {
        PROBE = p;
        if (stale) {
          showEl('dsWarn', true);
          $('dsWarn').innerHTML = '<b>请先重启本地服务</b>：' + esc(stale) +
            '。蒸馏的硬性度量（句长 / 对白占比 / 四字短句率）由服务端算法算出，' +
            '旧进程会给出不同的数字，据此写出来的东西是照着错的口径写的。<br>' +
            '在终端里执行：<code>pkill -f \'serve.py 8000\' &amp;&amp; python3 -s serve.py 8000</code>' +
            '（如果正有分析在跑，等它跑完再重启）。';
        }
        $('dsCur').textContent = p.model ? 'MODEL · ' + p.model : '';
        var rows = [
          ['材料', p.files + ' 文件 · ' + fmt(p.chars) + ' 字（正文 ' + fmt(p.cjk) + ' 汉字）'],
          ['计划取样', p.samples_planned + ' 段真实原文 · 按场景类型分带覆盖全书'],
          // 实际是 浸泡 N 批 + 法典/思维/构思/声纹/病灶 5 次 + 保真回测 2 次。
          // 旧文案写 +4，少算了构思与回测三次 —— 这是给用户的花费预估，不能少报。
          ['模型调用', '约 ' + (Math.ceil(p.samples_planned / 3) + 7) + ' 次深度调用（浸泡 ' +
            Math.ceil(p.samples_planned / 3) + ' 批并行 + 法典 / 思维 / 构思 / 声纹 / 病灶 + 保真回测 2 次）'],
          ['引擎版本', p.version]
        ];
        rows.push(['构思证据', p.has_graph ? '已分析过这部作品 —— 构思一节读得到剧情点序列'
          : '这部作品还没分析过图谱 —— 构思一节会降级（先跑一次分析可显著提升）']);
        if (p.resume) {
          rows.push(['可续跑', '上次中断时有 ' + p.resume + ' 段已存盘 —— 这次只补没跑完的部分']);
        }
        if (p.cached && p.counts) {
          rows.push(['已有结果', '提示词 ' + fmt(p.counts.prompt_chars) + ' 字 · 浸泡文档 ' + fmt(p.counts.soak_chars) +
            ' 字 · ' + p.counts.samples + ' 段样本 · ' + p.counts.roles + ' 位角色声纹' +
            (p.meta && p.meta.at ? ' · ' + esc(p.meta.at) : '')]);
          if (p.meta && p.meta.degraded && p.meta.degraded.length) {
            rows.push(['⚠ 该结果不完整', '缺 ' + p.meta.degraded.join('、') + ' —— 点「重新蒸馏」可补齐']);
          }
        }
        box.innerHTML = rows.map(function (r) {
          return '<div class="ds-row"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>';
        }).join('');

        if (!p.enough) {
          showEl('dsWarn', true);
          $('dsWarn').innerHTML = '<b>材料太少</b>：正文只有 ' + fmt(p.cjk) + ' 汉字，不足 800，蒸馏文风需要足够的原文样本。' +
            '请先「更换材料」拖入正文（大纲和设定表蒸馏不出文风）。';
          return;
        }
        $('dsStart').disabled = false;
        if (p.running_job) {
          $('dsNote').textContent = '这批材料已有蒸馏在运行，点「开始蒸馏」会附着到它，不会重复计费。';
          $('dsStart').textContent = '附着查看进度';
        } else if (p.cached) {
          $('dsStart').textContent = '打开已有结果';
          showEl('dsForce', true);
          $('dsNote').textContent = '这批材料已经蒸馏过（引擎 ' + p.version + '）。打开已有结果不花钱；换了模型或改了材料才需要重新蒸馏。';
        } else if (p.resume) {
          $('dsStart').textContent = '继续蒸馏（已完成 ' + p.resume + ' 段）';
          showEl('dsForce', true);
          $('dsNote').textContent = '上次没跑完，但已完成的 ' + p.resume + ' 段存在盘上。' +
            '点「继续蒸馏」只补剩下的部分，不会为已完成的段重复付费；要彻底重来就点「重新蒸馏」。';
        } else {
          $('dsStart').textContent = '开始蒸馏';
          $('dsNote').textContent = '点开这个面板不会调用模型。只有按下「开始蒸馏」才开始。';
        }
      });
    }).catch(function (e) {
      box.innerHTML = '<div class="ds-row bad"><span>无法准备</span><b>' + esc(e.message || String(e)) + '</b></div>';
      $('dsNote').textContent = '蒸馏需要原文。请先从「更换材料」拖入，或在作品库里点「载入材料」。';
    });
  }

  // ---- 进度
  function resetRun() {
    PHASES.forEach(function (p) {
      var li = $('dsSteps').querySelector('[data-p="' + p + '"]');
      if (li) { li.className = ''; li.querySelector('.d').textContent = ''; }
    });
    $('dsLog').innerHTML = ''; $('dsErr').textContent = ''; $('dsMeter').innerHTML = '';
    var back = $('dsBack'); if (back) back.textContent = '← 方案';
    arc(0); $('dsStage').textContent = '准备…'; $('dsStageM').textContent = '';
  }
  function arc(f) {
    var c = $('dsArc'); if (!c) return;
    var len = 2 * Math.PI * 18;
    c.style.strokeDasharray = len; c.style.strokeDashoffset = len * (1 - Math.max(0, Math.min(1, f)));
  }
  function stepMark(p, state, detail) {
    var li = $('dsSteps').querySelector('[data-p="' + p + '"]');
    if (!li) return;
    li.className = state;
    if (detail != null) li.querySelector('.d').textContent = detail;
  }
  function log(t) {
    var d = document.createElement('div'); d.textContent = t;
    $('dsLog').appendChild(d); $('dsLog').scrollTop = $('dsLog').scrollHeight;
  }

  var cur = { phase: '', i: 0, n: 0, base: 0, span: 0 };
  function phaseFrac() {
    var total = 0; PHASES.forEach(function (p) { total += PH_W[p]; });
    var acc = 0, base = 0, span = 0;
    for (var k = 0; k < PHASES.length; k++) {
      var w = PH_W[PHASES[k]] / total;
      if (PHASES[k] === cur.phase) { base = acc; span = w; break; }
      acc += w;
    }
    var inner = cur.n > 0 ? Math.min(1, cur.i / cur.n) : 0.45;
    return base + span * inner;
  }
  function meter(rows) {
    $('dsMeter').innerHTML = rows.map(function (r) {
      return '<div class="dm"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>';
    }).join('');
  }

  function cancelDistill() {
    if (CTL && CTL.cancel) CTL.cancel();
    else if (CTL && CTL.abort) CTL.abort();
    $('dsStage').textContent = '正在取消…';
    if (window.CLRunbar) {
      CLRunbar.set({
        type: 'distill',
        stage: '蒸馏 · 正在取消',
        percent: phaseFrac(),
        meta: '正在中断…',
        open: function () { open(); show('run'); },
        cancel: cancelDistill
      });
    }
  }

  function updateDistillRunbar(stageText, metaText) {
    if (!window.CLRunbar || !running) return;
    var frac = phaseFrac();
    var pName = PH_NAME[cur.phase] || cur.phase || '准备中';
    var st = stageText || ('蒸馏 · ' + pName);
    var mt = metaText || ('已用 ' + dur((Date.now() - t0) / 1000) + (cur.n ? ' · ' + cur.i + '/' + cur.n : ''));
    CLRunbar.set({
      type: 'distill',
      stage: st,
      percent: frac,
      meta: mt,
      open: function () { open(); show('run'); },
      cancel: cancelDistill
    });
  }

  function onEvent(ev, d) {
    if (ev === 'stage') {
      var p = d.phase;
      if (p === 'cache') { log('命中蒸馏缓存'); return; }
      if (p && PHASES.indexOf(p) >= 0) {
        if (p !== cur.phase) {
          var prev = PHASES.indexOf(cur.phase);
          if (prev >= 0) stepMark(cur.phase, 'done');
          cur.phase = p; cur.i = 0; cur.n = 0;
          stepMark(p, 'run');
        }
        if (d.i != null) cur.i = d.i;
        if (d.n != null) cur.n = d.n;
        if (cur.n) stepMark(p, 'run', cur.i + '/' + cur.n);
        $('dsStage').textContent = PH_NAME[p] || p;
        arc(phaseFrac());
      }
      if (d.text) { $('dsStageM').textContent = d.text; log(d.text); }
      updateDistillRunbar('蒸馏 · ' + (PH_NAME[cur.phase] || cur.phase || '分析中'),
        (d.text ? d.text + ' · ' : '') + '已用 ' + dur((Date.now() - t0) / 1000) + (cur.n ? ' · ' + cur.i + '/' + cur.n : ''));
    } else if (ev === 'progress') {
      var rows = [];
      var pInfo = '';
      if (d.waiting != null) { rows.push(['等待模型', dur(d.waiting)]); pInfo = '等待 ' + dur(d.waiting); }
      if (d.streamed != null) { rows.push(['模型吐字', fmt(d.streamed)]); pInfo = '吐字 ' + fmt(d.streamed); }
      if (d.thinking) { rows.push(['状态', '模型思考中']); pInfo = '思考中'; }
      if (rows.length) meter(rows.concat([['已用', dur((Date.now() - t0) / 1000)]]));
      updateDistillRunbar(null, '已用 ' + dur((Date.now() - t0) / 1000) + (pInfo ? ' · ' + pInfo : '') + (cur.n ? ' · ' + cur.i + '/' + cur.n : ''));
    } else if (ev === 'reconnect') {
      log('连接中断，重新附着…');
      updateDistillRunbar('蒸馏 · 重连中', '连接中断 · 正在重新附着');
    }
  }

  function startTicker() {
    t0 = Date.now();
    stopTicker();
    ticker = setInterval(function () {
      var el = (Date.now() - t0) / 1000;
      $('dsStageM').dataset.el = dur(el);
      var m = $('dsMeter');
      if (!m.children.length) meter([['已用', dur(el)], ['阶段', PH_NAME[cur.phase] || '—']]);
      else {
        var last = m.querySelector('.dm:last-child b');
        if (last && /^\d/.test(last.textContent)) last.textContent = dur(el);
      }
      updateDistillRunbar();
    }, 1000);
  }
  function stopTicker() { if (ticker) { clearInterval(ticker); ticker = null; } }

  function start(force) {
    if (running) return;
    if (!lastDocs || !lastDocs.length) { refreshPlan(); return; }
    if (PROBE && PROBE.cached && !force && !PROBE.running_job) { openCached(); return; }
    running = true; CTL = {};
    show('run'); resetRun(); startTicker();
    cur = { phase: '', i: 0, n: 0 };
    updateDistillRunbar('文风蒸馏 · 准备中', '已用 0s');
    var names = window.CLApp ? CLApp.names() : [];
    var title = window.CLApp ? CLApp.title() : '';
    run(lastDocs, { names: names, title: title, force: !!force, onEvent: onEvent, control: CTL })
      .then(function (out) {
        running = false; stopTicker();
        if (window.CLRunbar) CLRunbar.close('distill');
        PHASES.forEach(function (p) { stepMark(p, 'done'); });
        arc(1);
        RES = out; PROBE = PROBE || {}; PROBE.cached = true; PROBE.counts = out.counts; PROBE.meta = out.meta;
        renderResult();
        if (window.CLApp) CLApp.toast('文风蒸馏完成 · 提示词 ' + fmt(out.counts.prompt_chars) + ' 字');
      })
      .catch(function (e) {
        running = false; stopTicker();
        if (window.CLRunbar) CLRunbar.close('distill');
        if (e.cancelled) { $('dsErr').textContent = e.message || '已取消蒸馏'; log(e.message || '已取消'); show('plan'); refreshPlan(); return; }
        // 失败不再是「白跑二十分钟」：已完成的阶段在盘上，说清楚下一步怎么捡回来
        $('dsErr').innerHTML = esc(e.message || String(e)) +
          '<br><b>已完成的阶段已存盘。</b>回到上一页点「继续蒸馏」会从中断处接着跑，' +
          '不会为已完成的段重复调用模型。';
        if (cur.phase) stepMark(cur.phase, 'fail');
        var back = $('dsBack'); if (back) back.textContent = '返回（可继续蒸馏）';
      });
  }

  function openCached() {
    $('dsStart').disabled = true;
    $('dsNote').textContent = '读取已有结果…';
    load(lastDocs).then(function (d) {
      RES = d.distill; renderResult();
    }).catch(function (e) {
      $('dsStart').disabled = false;
      $('dsNote').textContent = '读取失败：' + (e.message || e) + '。可以点「重新蒸馏」。';
    });
  }

  // ---- 结果
  function renderResult() {
    if (!RES) return;
    show('result');
    var c = RES.counts || {}, mt = RES.meta || {};
    $('dsStats').innerHTML = [
      ['提示词', fmt(c.prompt_chars || 0) + ' 字'],
      ['精简版', fmt(c.core_chars || 0) + ' 字'],
      ['浸泡文档', fmt(c.soak_chars || 0) + ' 字'],
      ['样本', (c.samples || 0) + ' 段'],
      ['声纹', (c.roles || 0) + ' 位'],
      ['法典条目', (c.rules || 0) + ' 条'],
      ['构思条目', (c.arch_rules || 0) + ' 条'],
      ['施工单', (c.build_steps || 0) + ' 步'],
      ['禁忌', (c.taboos || 0) + ' 条'],
      ['病灶', (c.pitfalls || 0) + ' 条'],
      ['引证核验', (mt.quotes_checked || 0) + ' 查 / 剔除 ' + (mt.quotes_dropped || 0)],
      ['结构核验', (mt.facts_checked || 0) + ' 查 / 剔除 ' + (mt.facts_dropped || 0)],
      ['保真回测', c.fid_with == null ? '未出分' : (c.fid_with + ' 分 / 对照 ' + (c.fid_ctrl == null ? '—' : c.fid_ctrl))],
      ['耗时', dur(mt.secs || 0)]
    ].map(function (r) { return '<span class="dst"><i>' + esc(r[0]) + '</i>' + esc(r[1]) + '</span>'; }).join('');
    $('dsResNote').textContent = ((mt.degraded && mt.degraded.length)
      ? '⚠ 本次有 ' + mt.degraded.length + ' 节未能生成（' + mt.degraded.join('、') +
        '），文档里这几节是空的；重跑一次即可补齐，已完成的阶段会直接从存盘取回不重复花钱；'
      : '') +
      (mt.quotes_dropped ? '已剔除 ' + mt.quotes_dropped + ' 条模型改写过的「原文」引证；' : '') +
      (mt.facts_dropped ? '已剔除 ' + mt.facts_dropped + ' 条指认不到真实章节的结构依据；' : '') +
      (mt.vague ? '检出 ' + mt.vague + ' 处不可执行的形容词结论（文档内可见）；' : '') +
      (mt.has_graph === false ? '这部作品还没跑过图谱分析，构思一节证据受限 —— 先分析再蒸馏会结实得多；' : '') +
      '三份文档都是纯 Markdown，可直接贴进任意模型的系统提示词。';
    renderTab();
  }
  function renderTab() {
    var v = $('dsView');
    if (!RES) { v.textContent = ''; return; }
    if (tab === 'prompt' || tab === 'core' || tab === 'soak') {
      var md = mdOf(tab);
      v.innerHTML = '<pre class="ds-md">' + esc(md) + '</pre>';
      v.scrollTop = 0;
      return;
    }
    if (tab === 'metrics') { v.innerHTML = metricsHTML(RES.metrics || {}); return; }
    if (tab === 'arch') { v.innerHTML = archHTML(RES.arch || {}, RES.arch_metrics || {}, RES.hooks || {}, RES.meta || {}); v.scrollTop = 0; return; }
    if (tab === 'fid') { v.innerHTML = fidHTML(RES.fidelity); v.scrollTop = 0; return; }
    v.innerHTML = voiceHTML(RES.voice || {});
  }

  /** 构思引擎：左边是程序算出的结构硬指标，右边是模型据此蒸出的可执行条目。
   *  刻意把两者并排 —— 结论若与数字不符，用户当场就能看出来。 */
  function archHTML(a, am, hs, mt) {
    if (!a || !Object.keys(a).length) return '<div class="ds-empty">这次蒸馏没有构思结果（旧版结果不含此节，重跑一次即可）</div>';
    var out = '';
    if (mt.has_graph === false) {
      out += '<div class="ds-warn">这部作品还没有剧情图谱，所以没有剧情点序列可用。本节只依据章节收尾 / 开篇分型推得，' +
        '伏笔间隔、升级阶梯、副线这类长跨度结论证据不足。先在主界面跑一次分析，再重跑蒸馏。</div>';
    }
    if (am && am.events) {
      var pc = am.per_chapter || {}, ce = am.cast_per_event || {}, ca = am.cast || {}, rl = am.relations || {};
      out += '<div class="ds-mgrid">' +
        card('剧情点密度', [['总数', fmt(am.events)], ['覆盖章', fmt(am.chapters_with_events)], ['每章均', pc.mean], ['中位', pc.median], ['最密一章', pc.max]]) +
        card('一场戏的人数', [['均', ce.mean + ' 人'], ['独角戏', ce.solo_ratio + '%'], ['三人以上群戏', ce.crowd_ratio + '%']]) +
        card('角色调度', [['全书', fmt(ca.total) + ' 人'], ['主要角色', (ca.majors || 0) + ' 人'], ['主角', ca.lead || '—'], ['主角在场率', ca.lead_on_stage + '%']].concat(
          (ca.intro || []).map(function (x) { return ['前 ' + x.by + ' 已引入', x.pct + '%']; }))) +
        card('关系网', [['总数', fmt(rl.total)], ['暗线', (rl.hidden || 0) + ' 条'], ['暗线占比', rl.hidden_ratio + '%']]) +
        '</div>';
      var kd = {}; (am.kind_dist || []).forEach(function (kv) { kd[kv[0]] = kv[1]; });
      out += '<div class="ds-msec"><div class="eyebrow">剧情点类型分布</div>' + barsOf(kd, ' 个') + '</div>';
      if ((am.kind_bigrams || []).length) {
        out += '<div class="ds-msec"><div class="eyebrow">推进语法 · 一个剧情点之后最常接什么</div><div class="ds-words">' +
          am.kind_bigrams.slice(0, 12).map(function (b) {
            return '<span class="dw">' + esc(b.from) + '→' + esc(b.to) + '<i>' + b.pct + '%</i></span>';
          }).join('') + '</div></div>';
      }
      if ((am.curve || []).length) {
        out += '<div class="ds-msec"><div class="eyebrow">分带节奏曲线 · 全书十等分</div><table class="ds-tab"><tbody>' +
          am.curve.map(function (b) {
            return '<tr><td class="mono">' + esc(b.band) + '</td><td>' +
              (b.top || []).map(function (kv) { return esc(kv[0]) + ' <i class="mono">' + kv[1] + '</i>'; }).join(' · ') + '</td></tr>';
          }).join('') + '</tbody></table></div>';
      }
    }
    if (hs && (hs.tail || []).length) {
      var th = {}; hs.tail.forEach(function (x) { th[x.kind] = x.pct; });
      var hh = {}; (hs.head || []).forEach(function (x) { hh[x.kind] = x.pct; });
      out += '<div class="ds-msec"><div class="eyebrow">章节收尾配比 · 抽样 ' + hs.sampled + ' 章（已剔除章末的作者行外话）</div>' +
        barsOf(th, '%') + '</div>' +
        '<div class="ds-msec"><div class="eyebrow">章节开篇配比</div>' + barsOf(hh, '%') + '</div>';
    }
    function sec(label, key, note) {
      var it = a[key] || []; if (!it.length) return;
      out += '<div class="ds-msec"><div class="eyebrow">' + esc(label) + '</div>' +
        (note ? '<div class="ds-note mono" style="margin:0 0 8px">' + esc(note) + '</div>' : '') +
        it.map(function (r, i) {
          return '<div class="ds-rule"><b>' + (i + 1) + '. ' + esc(r.rule || r.step || '') + '</b>' +
            (r.why ? '<span class="rw">' + esc(r.why) + '</span>' : '') +
            (r.fact ? '<span class="rq">结构依据：' + esc(r.fact) + '</span>'
              : '<span class="rq bad">未指认到真实章节 / 剧情点（已核验剔除）</span>') + '</div>';
        }).join('') + '</div>';
    }
    sec('情节生成引擎 · 新麻烦从哪来', 'engine', '写不出下一章时，从这里挑一台引擎起手。');
    sec('升级阶梯 · 小事怎么做大', 'escalation');
    sec('伏笔与兑现', 'setups');
    sec('章节钩子谱', 'hooks', '先按上面的收尾配比定这一章用哪种收尾，再倒推最后一段怎么写。');
    sec('反转机制', 'reversal');
    sec('信息差管理', 'suspense');
    sec('副线编织', 'subplot');
    sec('角色调度', 'cast_use');
    sec('章节施工单 · 从一个点子到一章成稿', 'chapter_build', '照着做，不是读一遍。');
    sec('长线施工单 · 一个单元十来章怎么搭', 'arc_build');
    var oe = a.open_end || {};
    if (oe.opening || oe.ending) {
      out += '<div class="ds-msec"><div class="eyebrow">开头法与收束法</div>' +
        (oe.opening ? '<div class="ds-kv"><span>开头</span><b>' + esc(oe.opening) + '</b></div>' : '') +
        (oe.ending ? '<div class="ds-kv"><span>收束</span><b>' + esc(oe.ending) + '</b></div>' : '') + '</div>';
    }
    if (a.pace_curve) out += '<div class="ds-msec"><div class="eyebrow">全书节奏纲</div><div class="ds-lead">' + esc(a.pace_curve) + '</div></div>';
    return out;
  }

  /** 保真回测：这一页是本面板唯一「不夸自己」的地方，只报测出来的数。 */
  function fidHTML(f) {
    if (!f) {
      return '<div class="ds-empty">这次没有保真回测结果。<br><br>' +
        '回测会让同一个模型分别在「拿到这份提示词」和「什么都不给」两种条件下试写同样的场景，' +
        '再用统计原著的同一套算法逐维比对。它失败不影响提示词交付 —— 常见原因是网关抽风或试写样本太短。</div>';
    }
    var better = f.rows.filter(function (r) { return r.better; }).length;
    var out = '<div class="ds-fid"><div class="fh"><b>' + f.score_with + '</b><span>有提示词</span></div>' +
      '<div class="fv">vs</div>' +
      '<div class="fh ctrl"><b>' + (f.score_ctrl == null ? '—' : f.score_ctrl) + '</b><span>无提示词（对照组）</span></div>' +
      '<div class="fw">' + better + ' / ' + f.rows.length + ' 维更贴近原著</div></div>' +
      '<div class="ds-lead">' + esc(f.verdict) + '</div>' +
      '<div class="ds-msec"><div class="eyebrow">逐维比对</div><table class="ds-tab fid"><thead><tr>' +
      '<th>维度</th><th>原著</th><th>有提示词</th><th>无提示词</th><th>贴合度</th></tr></thead><tbody>' +
      f.rows.map(function (r) {
        return '<tr' + (r.better ? ' class="win"' : '') + '><td>' + esc(r.dim) + '</td>' +
          '<td class="mono">' + r.author + '</td><td class="mono">' + r["with"] + '</td>' +
          '<td class="mono">' + (r.ctrl == null ? '—' : r.ctrl) + '</td>' +
          '<td class="mono">' + r.hit_with + '% → ' + (r.hit_ctrl == null ? '—' : r.hit_ctrl + '%') +
          (r.better ? ' ✓' : '') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    if (f.tag) {
      out += '<div class="ds-msec"><div class="eyebrow">对话标签首选</div>' +
        '<div class="ds-kv"><span>原著</span><b>' + esc(f.tag.author || '—') + '</b></div>' +
        '<div class="ds-kv"><span>有提示词</span><b>' + esc(f.tag["with"] || '—') + '</b></div>' +
        '<div class="ds-kv"><span>无提示词</span><b>' + esc(f.tag.ctrl || '—') + '</b></div></div>';
    }
    var sp = f.sample || {};
    if (sp.with_text) {
      out += '<div class="ds-msec"><div class="eyebrow">回测试写 · 有提示词（' + fmt(sp.with_cjk || 0) + ' 字）</div>' +
        '<pre class="ds-md sm">' + esc(sp.with_text) + '</pre></div>' +
        '<div class="ds-msec"><div class="eyebrow">回测试写 · 无提示词对照（' + fmt(sp.ctrl_cjk || 0) + ' 字）</div>' +
        '<pre class="ds-md sm">' + esc(sp.ctrl_text || '') + '</pre></div>';
    }
    out += '<div class="ds-warn" style="margin-top:12px">这份分数测的是可量化的笔法特征：句长分布、段落形态、' +
      '对白比重与标签偏好、四字短句率、感官与动作密度。<b>测不了</b>立意、人物魅力、长跨度结构与情感重量 —— ' +
      '那些没有客观标尺，本引擎不假装能打分。另外回测样本只有几百字，密度类指标本身有波动，看趋势不看小数。</div>';
    return out;
  }
  function barsOf(obj, unit) {
    var ks = Object.keys(obj || {}); if (!ks.length) return '';
    var mx = Math.max.apply(null, ks.map(function (k) { return +obj[k] || 0; })) || 1;
    return '<div class="ds-bars">' + ks.map(function (k) {
      return '<div class="db"><span>' + esc(k) + '</span><i style="width:' + Math.round(100 * (obj[k] / mx)) + '%"></i><b>' + obj[k] + (unit || '') + '</b></div>';
    }).join('') + '</div>';
  }
  function metricsHTML(m) {
    if (!m.sent_len) return '<div class="ds-empty">没有度量数据</div>';
    var s = m.sent_len, d = m.dialogue || {}, p = m.para_len || {}, c = m.clause || {};
    var bars = barsOf;
    var tags = {}; (d.tags || []).forEach(function (kv) { tags[kv[0]] = kv[1]; });
    return '<div class="ds-mgrid">' +
      card('规模', [['汉字', fmt(m.cjk)], ['句', fmt(m.sentences)], ['段', fmt(m.paras)], ['章', m.chapters]]) +
      card('句长', [['均值', s.mean + ' 字'], ['中位', s.median], ['十分位', s.p10], ['九十分位', s.p90], ['最长', s.max], ['≤8 字短句', s.short_ratio + '%'], ['≥40 字长句', s.long_ratio + '%']]) +
      card('段落', [['均值', p.mean + ' 字'], ['每段句数', p.sent_per_para], ['单句成段', p.one_sent_ratio + '%']]) +
      card('对白', [['占正文', d.ratio + '%'], ['处数', fmt(d.count)], ['每句均', d.mean_len + ' 字'], ['九十分位', d.p90_len], ['裸引号', d.bare_ratio + '%']]) +
      card('分句节奏', [['逗号间均', c.mean + ' 字'], ['四字短句', c.four_ratio + '%']]) +
      card('章节体量', [['均', fmt(Math.round((m.chapter_len || {}).mean || 0)) + ' 字'], ['最短', fmt((m.chapter_len || {}).min || 0)], ['最长', fmt((m.chapter_len || {}).max || 0)]]) +
      '</div>' +
      '<div class="ds-msec"><div class="eyebrow">对话标签偏好</div>' + bars(tags, ' 次') + '</div>' +
      '<div class="ds-msec"><div class="eyebrow">感官配比 · 每万字</div>' + bars(m.sense) + '</div>' +
      '<div class="ds-msec"><div class="eyebrow">人称 · 每万字</div>' + bars(m.pronoun) + '</div>' +
      '<div class="ds-msec"><div class="eyebrow">标点 · 每万字</div>' + bars(m.punct_per10k) + '</div>' +
      '<div class="ds-msec"><div class="eyebrow">高频词</div><div class="ds-words">' +
      (m.ngrams || []).map(function (x) { return '<span class="dw">' + esc(x.w) + '<i>' + x.n + '</i></span>'; }).join('') + '</div></div>' +
      '<div class="ds-msec"><div class="eyebrow">高频句首</div><div class="ds-words">' +
      (m.sent_openers || []).map(function (x) { return '<span class="dw">' + esc(x.w) + '<i>' + x.n + '</i></span>'; }).join('') + '</div></div>' +
      ((m.warnings || []).length ? '<div class="ds-warn" style="margin-top:12px">' + m.warnings.map(esc).join('<br>') + '</div>' : '');
  }
  function card(t, rows) {
    return '<div class="ds-card"><div class="eyebrow">' + esc(t) + '</div>' + rows.map(function (r) {
      return '<div class="ds-kv"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>';
    }).join('') + '</div>';
  }
  function voiceHTML(v) {
    var out = '';
    var n = v.narrator;
    if (n) {
      out += '<div class="ds-vp"><div class="vh"><b>叙述者</b><span class="mono">NARRATOR</span></div>' +
        '<div class="ds-kv"><span>站位</span><b>' + esc(n.stance || '—') + '</b></div>' +
        '<div class="ds-kv"><span>用词层级</span><b>' + esc(n.lexicon || '—') + '</b></div>' +
        (n.tells || []).map(function (x) { return '<div class="vt">' + esc(x) + '</div>'; }).join('') +
        (n.quote ? '<div class="vq">' + esc(n.quote) + '</div>' : '') + '</div>';
    }
    (v.characters || []).forEach(function (c) {
      out += '<div class="ds-vp"><div class="vh"><b>' + esc(c.name || '—') + '</b></div>' +
        '<div class="ds-kv"><span>语域</span><b>' + esc(c.register || '—') + '</b></div>' +
        '<div class="ds-kv"><span>句式</span><b>' + esc(c.sentence || '—') + '</b></div>' +
        '<div class="ds-kv"><span>称呼</span><b>' + esc(c.address || '—') + '</b></div>' +
        '<div class="ds-kv bad"><span>不会说</span><b>' + esc(c.taboo || '—') + '</b></div>' +
        (c.tells || []).map(function (x) { return '<div class="vt">' + esc(x) + '</div>'; }).join('') +
        (c.quotes || []).map(function (x) { return '<div class="vq">「' + esc(x) + '」</div>'; }).join('') + '</div>';
    });
    // 「没取到」和「跑失败了」是两回事：后者说成前者，用户会去改材料而不是重跑
    if (out) return out;
    var dg = ((RES && RES.meta && RES.meta.degraded) || []).indexOf('声纹') >= 0;
    return '<div class="ds-empty">' + (dg
      ? '声纹这一段两次调用都失败了，本节留空 —— 重跑一次蒸馏即可补齐（其余已完成的段会从存盘直接取回）。'
      : '这次蒸馏没有取到声纹（材料里没有可归属的对白）') + '</div>';
  }

  /** 当前页对应的 Markdown；可视化页返回 null。core_md 是旧版结果里没有的字段，兜底回完整版。 */
  function mdOf(t) {
    if (!RES) return null;
    if (t === 'prompt') return RES.prompt_md;
    if (t === 'core') return RES.core_md || RES.prompt_md;
    if (t === 'soak') return RES.soak_md;
    return null;
  }

  function download() {
    if (!RES) return;
    var t = (RES.title || '未命名').replace(/[\\/:*?"<>|]/g, '_');
    [[t + ' · 文风蒸馏提示词.md', RES.prompt_md],
     [t + ' · 文风蒸馏提示词 · 精简版.md', RES.core_md || RES.prompt_md],
     [t + ' · 样本浸泡文档.md', RES.soak_md]].forEach(function (pair, i) {
      setTimeout(function () {
        var b = new Blob([pair[1]], { type: 'text/markdown;charset=utf-8' });
        var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = pair[0];
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      }, i * 350);
    });
    $('dsResNote').textContent = '已下载三份文档。完整版提示词整段贴进系统提示词即可用；上下文吃紧改用精简版；浸泡文档给人读，读完再写。';
  }
  function copyCur() {
    if (!RES) return;
    var md = mdOf(tab);
    if (md == null) { $('dsResNote').textContent = '这一页是可视化视图，切到「蒸馏提示词」或「样本浸泡文档」再复制。'; return; }
    var ok = function () { $('dsResNote').textContent = '已复制 ' + fmt(md.length) + ' 字到剪贴板。'; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(md).then(ok).catch(function () { fallbackCopy(md, ok); });
    } else fallbackCopy(md, ok);
  }
  function fallbackCopy(md, ok) {
    var ta = document.createElement('textarea'); ta.value = md; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); ok(); } catch (e) { $('dsResNote').textContent = '复制失败，请用「下载三份 .md」。'; }
    ta.remove();
  }

  // ---- 接线
  function wire() {
    panel = $('dsPanel');
    if (!panel || !$('btnDistill')) return;
    $('btnDistill').addEventListener('click', function () {
      if (window.CLApp && CLApp.busy()) { CLApp.toast('图谱分析正在运行，等它跑完再蒸馏'); return; }
      open();
    });
    $('dsClose').addEventListener('click', close);
    panel.addEventListener('click', function (e) { if (e.target === panel) close(); });
    $('dsStart').addEventListener('click', function () { start(false); });
    $('dsForce').addEventListener('click', function () { start(true); });
    $('dsOpenCached').addEventListener('click', openCached);
    $('dsCancel').addEventListener('click', cancelDistill);
    $('dsBack').addEventListener('click', function () { show('plan'); refreshPlan(); });
    $('dsCopy').addEventListener('click', copyCur);
    $('dsDown').addEventListener('click', download);
    $('dsTabs').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-t]'); if (!b) return;
      tab = b.dataset.t;
      Array.prototype.forEach.call(this.children, function (c) { c.classList.toggle('on', c === b); });
      renderTab();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('on')) { e.stopPropagation(); close(); }
    }, true);
    // 探针钩子：无头自测用，不触发任何模型调用
    window.__cldistill = { open: open, close: close, panel: function () { return panel; },
      probe: function () { return PROBE; }, result: function () { return RES; },
      running: function () { return running; }, start: start, tab: function (t) { tab = t; renderTab(); },
      render: function (d) { RES = d; renderResult(); } };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
