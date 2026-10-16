(function (g) {
  'use strict';
  var LAYERS = { storylines: '故事线', tasks: '人物任务', causeEdges: '事件因果', clues: '伏笔回收', characterStates: '人物变化', relations: '人物关系' }, KEY = /^[0-9a-f]{8,40}$/, ui = null;
  function str(v) { return String(v == null ? '' : v); }
  function failure(message, status) { var e = new Error(message); e.status = status || 0; e.auth = /\b40[13]\b|forbidden|没有可用模型|没有.*档案|密钥|认证/i.test(message) || status === 401 || status === 403; return e; }
  function validKey(v) { return typeof v === 'string' && KEY.test(v); }
  function semanticReady(plan, sourceOnly) { return !!sourceOnly || !!(plan && plan.sourceContext && Array.isArray(plan.sourceContext.batches) && plan.sourceContext.batches.length && plan.sourceContext.batches.every(function (batch) { return batch.contextComplete === true; })); }
  function inputCoverageText(coverage) {
    if (!coverage || !/^(scheduled|accepted_batches)$/.test(coverage.state)) return '';
    var total = coverage.originalChars, included = coverage.includedChars, missing = coverage.notIncludedChars;
    if (!Number.isSafeInteger(total) || total <= 0 || !Number.isSafeInteger(included) || included < 0 || included > total || missing !== total - included) return '本次原文输入覆盖尚未确认；全文语义完整度未验证。';
    var percent = (Math.floor(included / total * 10000) / 100).toFixed(2);
    return (coverage.state === 'scheduled' ? '本次计划输入原文 ' : '已接受批次输入原文 ') + percent + '%（' + included + ' / ' + total + ' 字符），' + missing + ' 字符未进入本次窗口。输入覆盖不等于已精读，全文语义完整度未验证。';
  }
  function createClient(fetcher, sleep) {
    fetcher = fetcher || function (url, opts) { return g.fetch(url, opts); };
    sleep = sleep || function (ms) { return new Promise(function (resolve) { g.setTimeout(resolve, ms); }); };
    async function post(url, payload) {
      var response = await fetcher(url, { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) {
        var data; try { data = await response.json(); } catch (ignore) { data = {}; }
        throw failure(data.error || data.message || (g.CLLlmErrors ? g.CLLlmErrors.why({ status: response.status, src: url }) : '服务暂不可用（' + response.status + '）'), response.status);
      }
      return response;
    }
    async function plan(payload) {
      var response = await post('/api/enrich/plan', payload);
      try { return await response.json(); } catch (ignore) {
        var e = failure(g.CLLlmErrors ? g.CLLlmErrors.why({ kind: 'corrupt', status: response.status, src: '/api/enrich/plan' }) : '服务返回内容不是预期的数据格式，本次没有启动补析。'); e.corrupt = true; throw e;
      }
    }
    async function cancel(ctl) {
      ctl.cancelRequested = true;
      if (!ctl.job) return { queued: true };
      var answer = await (await post('/api/cancel', { job: ctl.job })).json();
      if (!answer.ok) throw failure('作业未确认取消；可能已结束，请保留连接查看结果。');
      ctl.cancelSent = true; return answer;
    }
    async function connect(payload, emit, ctl) {
      var response;
      try { response = await post('/api/enrich', payload); } catch (e) { if (!e.status) e.stream = true; throw e; }
      if (!response.body || typeof response.body.getReader !== 'function') throw failure('当前浏览器无法读取补析进度。');
      var reader = response.body.getReader(), decoder = new TextDecoder('utf-8'), buffer = '';
      try {
        while (true) {
          var part;
          try { part = await reader.read(); } catch (e) { var lost = failure('进度连接中断'); lost.stream = true; throw lost; }
          if (part.done) { var end = failure('进度连接已结束，但没有确认完成结果。'); end.stream = true; throw end; }
          buffer += decoder.decode(part.value, { stream: true });
          if (buffer.length > 64 * 1024 * 1024) throw failure('进度响应过大；本次没有确认新版本。');
          var boundary;
          while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
            var block = buffer.slice(0, boundary.index); buffer = buffer.slice(boundary.index + boundary[0].length);
            var event = 'message', lines = [];
            block.split(/\r?\n/).forEach(function (line) { if (line.indexOf('event:') === 0) event = line.slice(6).trim(); else if (line.indexOf('data:') === 0) lines.push(line.slice(5).trim()); });
            if (!lines.length) continue;
            var data; try { data = JSON.parse(lines.join('\n')); } catch (e) { throw failure('补析进度格式无效；没有确认新版本。'); }
            if (event === 'hello') {
              if (typeof data.job !== 'string' || !data.job || data.kind !== 'enrich' || ctl.job && ctl.job !== data.job) throw failure('作业续接信息不一致；已停止接收，未重开补析。');
              ctl.job = data.job;
              emit(event, data);
              if (ctl.cancelRequested && !ctl.cancelSent) cancel(ctl).catch(function (e) { emit('cancel-error', { message: e.message }); });
              continue;
            }
            if (event === 'error') { emit(event, data); throw failure(data.message || '补析失败；原图保留。'); }
            if (event === 'cancelled') { emit(event, data); var stopped = failure(data.message || '已取消补析'); stopped.cancelled = true; throw stopped; }
            if (event === 'done') {
              var revision = data.graph && data.graph.meta && data.graph.meta.revision;
              if (!ctl.job || !validKey(data.key) || data.key === payload.key || data.parentKey !== payload.key || data.originalPreserved !== true || !data.graph || !Array.isArray(data.graph.characters) || !Array.isArray(data.graph.events) || !revision || revision.key !== data.key || revision.parentKey !== payload.key || revision.originalPreserved !== true) throw failure('返回版本没有通过完整性检查；当前原图保持原状。');
              emit(event, data); return data;
            }
            emit(event, data);
          }
        }
      } finally { try { await reader.cancel(); } catch (ignore) {} }
    }
    async function run(payload, emit, ctl) {
      ctl = ctl || {}; emit = emit || function () {}; var retries = 0, request = Object.assign({}, payload);
      if (request.job) ctl.job = request.job;
      while (true) {
        try { return await connect(request, emit, ctl); } catch (e) {
          if (!e.stream || ctl.cancelRequested || !ctl.job || retries >= 2) { if (e.stream) e.interrupted = true; throw e; }
          retries++; request.job = ctl.job;
          emit('reconnect', { message: '连接中断，正在恢复同一作业的进度', attempt: retries });
          await sleep(retries * 600);
        }
      }
    }
    return { plan: plan, run: run, cancel: cancel };
  }
  function currentKey() {
    var app = g.CLApp;
    if (app && typeof app.storedGraphKey === 'function') { var stored = app.storedGraphKey(); return validKey(stored) ? stored : null; }
    if (app && typeof app.key === 'function') { var key = app.key(); return validKey(key) ? key : null; }
    try { var data = new URLSearchParams(g.location.search).get('data'), match = /^\/?data\/cache\/([0-9a-f]{8,40})\.json$/.exec(data || ''); return match ? match[1] : null; } catch (ignore) { return null; }
  }
  function ensure() {
    if (ui) return ui;
    var doc = g.document, root = doc.createElement('aside'); root.id = 'skyEnrichPanel'; root.className = 'sky-enrich-panel'; root.hidden = true;
    root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'false'); root.setAttribute('aria-labelledby', 'skyEnrichTitle');
    function mk(tag, cls, parent, text) { var e = doc.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
    function button(parent, text, id, fn) { var b = mk('button', '', parent, text); b.type = 'button'; b.dataset.action = id; b.addEventListener('click', fn); return b; }
    var state = { key: null, parentKey: null, title: '', plan: null, manifest: [], payload: null, ctl: null, busy: false, result: null, phase: 'idle', authBlock: null, configTag: '', planToken: 0 }, client = createClient(), head = mk('header', 'ske-head', root);
    mk('h2', '', head, '结构补析').id = 'skyEnrichTitle'; button(head, '关闭', 'close', close);
    var body = mk('div', 'ske-body', root), target = mk('p', 'ske-versions', body), intro = mk('p', '', body, '在当前版本上核对引文或补充结构，完成后保存为新版本。原图仍可从作品库打开。');
    var controls = mk('div', 'ske-controls', body), modeLabel = mk('label', '', controls, '处理方式 '), mode = mk('select', '', modeLabel);
    mode.setAttribute('aria-label', '补析方式'); [['sources', '核对引文来源 · 0 次模型调用'], ['semantic', '补充叙事结构 · 调用模型']].forEach(function (x) { var o = mk('option', '', mode, x[1]); o.value = x[0]; });
    var layerBox = mk('fieldset', 'ske-layers', body); mk('legend', '', layerBox, '补充内容'); var checks = {};
    Object.keys(LAYERS).forEach(function (key) { var label = mk('label', '', layerBox), check = mk('input', '', label); check.type = 'checkbox'; check.checked = true; check.dataset.layer = key; label.appendChild(doc.createTextNode(LAYERS[key])); checks[key] = check; });
    var scopeBox = mk('div', 'ske-scope', body), scopeLabel = mk('label', '', scopeBox, '事件范围 '), scope = mk('select', '', scopeLabel);
    scope.setAttribute('aria-label', '补析事件范围'); [['all', '当前版本的全部已识别事件'], ['range', '指定事件段']].forEach(function (x) { var o = mk('option', '', scope, x[1]); o.value = x[0]; });
    var range = mk('div', '', scopeBox), firstLabel = mk('label', '', range, '从第 '), first = mk('input', '', firstLabel), lastLabel = mk('label', '', range, ' 到第 '), last = mk('input', '', lastLabel);
    [first, last].forEach(function (e) { e.type = 'number'; e.min = '1'; e.step = '1'; }); first.value = '1'; first.setAttribute('aria-label', '起始事件序号'); last.setAttribute('aria-label', '结束事件序号');
    mk('p', '', scopeBox, '“全部”指这个版本已经识别出的事件记录，不能代表整部原文已完整解析。');
    var actions = mk('div', 'ske-actions', body), preview = button(actions, '查看方案', 'plan', function () { prepare().catch(showError); }), start = button(actions, '开始核对', 'start', startRun), cancel = button(actions, '取消补析', 'cancel', cancelRun), resume = button(actions, '恢复作业进度', 'resume', resumeRun);
    var feedback = mk('div', 'ske-feedback', body), status = mk('p', 'ske-status', feedback); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    var progress = mk('progress', 'ske-progress', feedback); progress.max = 1; progress.value = 0; progress.setAttribute('aria-label', '补析已完成批次');
    var error = mk('p', 'ske-error', feedback); error.setAttribute('role', 'alert');
    var help = mk('div', 'ske-actions', feedback), local = button(help, '改为核对引文 · 无需 API', 'local', function () { mode.value = 'sources'; invalidate(); state.phase = 'idle'; state.ctl = null; state.payload = null; status.textContent = '已切换为本地引文核对，先查看方案再开始。'; save(); render(); preview.focus(); }), api = button(help, '更新 API 配置', 'api', function () { close(); var b = doc.getElementById('btnApi'); if (b) b.click(); }), library = button(help, '打开作品库', 'library', function () { close(); var b = doc.getElementById('btnLib'); if (b) b.click(); });
    var versions = mk('div', 'ske-versions', feedback), versionLabel = mk('p', '', versions), openNew = button(versions, '进入补析新版本', 'new-version', openRevision), openOld = button(versions, '返回原图', 'original-version', function () { var original = state.result ? state.key : state.parentKey; if (original && g.CLApp && CLApp.openVersion) { close(); CLApp.openVersion(original).catch(function (e) { open(); showError(e); }); } });
    var info = mk('div', 'ske-plan', body);
    doc.body.appendChild(root);
    function sessionKey() { return 'castline.enrich.' + state.key; }
    function save() { if (!state.key) return; try { g.sessionStorage.setItem(sessionKey(), JSON.stringify({ payload: state.payload, job: state.ctl && state.ctl.job, phase: state.phase, title: state.title, plan: state.plan, authBlock: state.authBlock, range: [first.value, last.value] })); } catch (ignore) {} }
    function restore() { try { var saved = JSON.parse(g.sessionStorage.getItem(sessionKey()) || 'null'); if (saved && saved.payload && saved.payload.key === state.key) { state.authBlock = saved.authBlock || null; if (/^(running|reconnecting|interrupted)$/.test(saved.phase)) {
      state.payload = saved.payload; state.plan = saved.plan; state.ctl = { job: saved.job || null }; state.phase = 'interrupted'; mode.value = saved.payload.sourceOnly ? 'sources' : 'semantic'; scope.value = saved.payload.eventIds ? 'range' : 'all';
      Object.keys(checks).forEach(function (key) { checks[key].checked = (saved.payload.layers || []).indexOf(key) >= 0; });
      if (saved.range && saved.range.length === 2) { first.value = saved.range[0]; last.value = saved.range[1]; }
      if (state.plan) showPlan(state.plan); status.textContent = '发现上次作业，可恢复原来的范围和进度；不会自动重新开始。';
    } } } catch (ignore) {} }
    function render() {
      target.textContent = state.key ? state.title + ' · 原图版本 ' + state.key.slice(0, 12) : '当前图谱没有可用的作品库版本，请先从作品库打开作品。';
      var sourceOnly = mode.value === 'sources'; layerBox.hidden = scopeBox.hidden = sourceOnly; layerBox.disabled = sourceOnly || state.busy; range.hidden = sourceOnly || scope.value !== 'range';
      [mode, scope, first, last].forEach(function (e) { e.disabled = state.busy; }); preview.disabled = !state.key || state.busy;
      scope.disabled = state.busy || sourceOnly;
      start.textContent = sourceOnly ? '开始核对 · 0 次模型调用' : '开始补析'; start.disabled = !state.key || !state.plan || state.busy || !!(state.authBlock && state.authBlock === state.configTag && !sourceOnly);
      if (!semanticReady(state.plan, sourceOnly)) start.disabled = true;
      cancel.hidden = !state.busy; resume.hidden = state.phase !== 'interrupted' || state.busy || !state.ctl || !state.ctl.job; progress.hidden = !state.busy;
      openNew.hidden = !state.result; openOld.hidden = !state.result && !state.parentKey; versions.hidden = !state.result && !state.parentKey; api.hidden = !state.authBlock; error.hidden = !error.textContent;
      local.hidden = !state.authBlock || sourceOnly || state.busy;
    }
    function revealFeedback() {
      g.requestAnimationFrame(function () {
        if (!root.hidden && feedback.scrollIntoView) feedback.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      });
    }
    async function configTag() {
      try { var r = await g.fetch('/api/llm-config'), d = await r.json(); return JSON.stringify([d.current, (d.profiles || []).map(function (p) { return [p.id, p.last_used, p.model, p.base_url]; }), (d.history || []).slice(0, 3)]); } catch (ignore) { return state.configTag || 'unavailable'; }
    }
    function choice() { var sourceOnly = mode.value === 'sources', layers = Object.keys(checks).filter(function (key) { return sourceOnly || checks[key].checked; }); if (!layers.length) throw failure('请至少选择一类结构。'); return { key: state.key, layers: layers, sourceOnly: sourceOnly }; }
    function showInputCoverage(context) {
      var coverage = context && context.coverage, label = inputCoverageText(coverage);
      if (!label) return;
      mk('p', '', info, label);
      var sources = coverage.sources;
      if (!Array.isArray(sources) || !sources.length) return;
      var detail = mk('details', '', info); mk('summary', '', detail, '查看各材料的输入范围');
      sources.forEach(function (source) {
        if (!source || !Number.isSafeInteger(source.originalChars) || !Number.isSafeInteger(source.notIncludedChars)) return;
        mk('p', '', detail, str(source.name || source.sourceId) + '：共 ' + source.originalChars + ' 字符，' + source.notIncludedChars + ' 字符未进入本次窗口。' + (source.identityConflict ? '来源身份冲突，需先核对材料。' : ''));
      });
    }
    function showPlan(p) {
      info.textContent = ''; mk('p', '', info, mode.value === 'sources' ? '核对整个版本的引文位置，不生成新的结构判断。这个版本包含 ' + p.events + ' 条已识别事件。' : '本次处理 ' + p.events + ' 条已识别事件 · ' + (p.layers || []).map(function (l) { return LAYERS[l] || l; }).join('、'));
      mk('p', '', info, p.estimatedCalls === 0 ? '0 次模型调用，仅核对引文位置；不验证内容判断。' : '预计 ' + p.estimatedCalls + ' 次模型调用。已保存的结果将尽量复用，实际调用与费用以接入服务为准。');
      if (mode.value !== 'sources') mk('p', '', info, '依据这些事件和可定位的局部原文补充结构，不等于重新通读整部小说。');
      if (mode.value !== 'sources') showInputCoverage(p.sourceContext);
      if (mode.value !== 'sources') { var contexts = p.sourceContext && p.sourceContext.batches;
        if (!Array.isArray(contexts) || !contexts.length) mk('p', '', info, '当前方案没有确认可用的原文范围，本次不能开始模型补析。');
        else { var incomplete = contexts.filter(function (b) { return b.contextComplete !== true; }).length; mk('p', '', info, incomplete ? '还有 ' + incomplete + ' 段事件的原文范围不足，请先补齐材料；当前不能启动模型补析。' : '所选事件的原文范围已准备；内容判断仍需核对。'); } }
      mk('p', '', info, '保存为新版本，原图保留。结构判断和未定位的引文仍需核对。');
      if (scope.value === 'range') mk('p', '', info, '范围：第 ' + first.value + '–' + last.value + ' 条事件。');
    }
    async function prepare() {
      if (!state.key || state.busy) throw failure('请先选择可用作品，或等待当前补析结束。');
      if (currentKey() !== state.key) throw failure('当前作品已切换，请重新打开结构补析查看对应版本。');
      var token = ++state.planToken, targetKey = state.key, payload = choice(); status.textContent = '正在查看方案 · 不调用模型'; error.textContent = ''; start.disabled = true;
      var slowTimer = g.setTimeout(function () {
        if (token !== state.planToken) return;
        state.planToken++;
        showError(failure(g.CLLlmErrors ? g.CLLlmErrors.why({ kind: 'slow', src: '/api/enrich/plan' }) : '查看方案超过 15 秒没有返回：本地服务可能已停止。可以稍后重试；本次没有开始任何处理。'));
        status.textContent = '查看方案没有返回，本次没有开始任何处理；可以再次「查看方案」。';
        render();
      }, (g.CLLlmErrors && CLLlmErrors.SLOW_MS) || 15000);
      try {
      var full = await client.plan(payload);
      if (token !== state.planToken || state.key !== targetKey) throw failure('作品或选项已改变，请重新查看方案。');
      function completePlan(p) { return p && validKey(p.key) && p.sourceKey === state.key && /^[0-9a-f]{64}$/.test(str(p.originalHash)) && p.writePolicy === 'new_version_original_unchanged' && p.identity && Array.isArray(p.identity.eventIds) && p.identity.eventIds.every(function (id) { return typeof id === 'string' && !!id; }) && p.events === p.identity.eventIds.length && Number.isInteger(p.estimatedCalls) && p.estimatedCalls >= 0; }
      if (!completePlan(full)) throw failure('方案信息不完整，本次不能启动。');
      state.manifest = full.identity.eventIds.slice(); last.max = first.max = String(state.manifest.length); if (!last.value) last.value = String(state.manifest.length);
      if (scope.value === 'range') {
        var a = Number(first.value), b = Number(last.value);
        if (!Number.isInteger(a) || !Number.isInteger(b) || a < 1 || b < a || b > state.manifest.length) throw failure('请选择有效的起止事件序号。');
        payload.eventIds = state.manifest.slice(a - 1, b); full = await client.plan(payload);
        if (!completePlan(full)) throw failure('范围方案信息不完整，本次不能启动。');
        if (token !== state.planToken || state.key !== targetKey) throw failure('作品或选项已改变，请重新查看方案。');
      }
      var nextConfig = payload.sourceOnly ? state.configTag : await configTag();
      if (token !== state.planToken || state.key !== targetKey) throw failure('作品或选项已改变，请重新查看方案。');
      state.configTag = nextConfig; state.plan = full; state.payload = payload; state.result = null; status.textContent = '方案已就绪，点击开始才执行。'; showPlan(full);
      if (!payload.sourceOnly && state.authBlock && state.authBlock === state.configTag) showError(failure('当前接入仍未更新；本次没有再次调用模型。', 403));
      else { render(); revealFeedback(); }
      g.clearTimeout(slowTimer);
      return full;
      } catch (e) { g.clearTimeout(slowTimer); if (token !== state.planToken || state.key !== targetKey) e.stale = true; throw e; }
    }
    function showError(e) {
      if (e.stale) return;
      state.busy = false; state.phase = e.cancelled ? 'cancelled' : e.interrupted ? 'interrupted' : 'failed';
      error.textContent = e.cancelled ? '' : e.auth ? (mode.value === 'sources'
        ? '本地服务拒绝了这次查看方案的请求（' + (e.status ? 'HTTP ' + e.status : '401/403') + '）。核对引文不调用模型，但请求仍被拒绝；重试多半重复同样的拒绝，请确认是从本机打开的页面，或重启本地服务后再试。'
        : '当前模型接入不可用，本次未完成结构补析。可以继续浏览，或改为核对引文来源，无需 API。') : e.message;
      status.textContent = e.cancelled ? '补析已取消，原图保留；已完成的内容可在后续相同补析中续用。' : e.interrupted ? state.ctl && state.ctl.job ? '连接未能恢复，可恢复已确认作业的进度；不会自动重开。' : '连接中断，没有确认可恢复的作业。未自动开始新调用，请先查看方案。' : '本次未确认完成，原图保留。';
      if (e.auth) { state.authBlock = state.configTag || 'unavailable'; error.title = e.message; }
      save(); render(); revealFeedback();
    }
    function event(ev, d) {
      if (ev === 'hello') { state.phase = 'running'; status.textContent = (d.attached ? '已恢复原作业进度' : '补析已开始') + (state.payload && !state.payload.sourceOnly && d.model ? ' · ' + d.model : ''); }
      else if (ev === 'stage') status.textContent = d.stage === 'narrative-sources' ? '正在核对原文引文位置' : '正在补充叙事结构' + (d.i && d.n ? ' · ' + d.i + ' / ' + d.n : '');
      else if (ev === 'progress' && d.done != null) { progress.max = Math.max(1, d.n || 1); progress.value = d.done; status.textContent = '已完成 ' + d.done + ' / ' + (d.n || '未知') + ' 段 · 本次调用 ' + (d.calls || 0) + ' 次 · 已复用 ' + (d.resumed || 0) + ' 段'; }
      else if (ev === 'reconnect') { state.phase = 'reconnecting'; status.textContent = d.message; }
      else if (ev === 'cancel-error') error.textContent = d.message;
      save(); render();
    }
    async function execute(payload, job) {
      state.busy = true; state.phase = 'running'; state.ctl = { job: job || null }; state.result = null; error.textContent = ''; save(); render(); revealFeedback();
      try { var d = await client.run(Object.assign({}, payload, job ? { job: job } : {}), event, state.ctl); state.result = d; state.busy = false; state.phase = 'done';
        var e = d.enrichment || {}; status.textContent = d.sourceOnly ? '引文位置核对已生成新版本 · 0 次模型调用' : '补析已生成新版本 · ' + (e.status === 'partial' ? '有待补充内容' : '已处理所选事件') + ' · 判断仍需核对';
        versionLabel.textContent = '新版本 ' + d.key.slice(0, 12) + ' · 原图 ' + d.parentKey.slice(0, 12) + ' 保留';
        mk('p', '', info, '本次模型调用 ' + (Number.isInteger(e.calls) ? e.calls : '未知') + ' 次 · 已复用 ' + (e.resumedBatches || 0) + ' 段。');
        if (!d.sourceOnly) showInputCoverage(e.sourceContext);
        if (Array.isArray(e.warnings) && e.warnings.length) { var notes = mk('details', '', info); mk('summary', '', notes, '待核对说明 · ' + e.warnings.length + ' 条'); e.warnings.forEach(function (w) { mk('p', '', notes, str(w)); }); }
        versions.setAttribute('aria-label', '新版本 ' + d.key.slice(0, 12) + ' · 原图 ' + d.parentKey.slice(0, 12)); save(); render(); revealFeedback();
      } catch (e) { showError(e); }
    }
    async function startRun() {
      if (state.busy || !state.plan || !state.key) return;
      if (g.CLApp && CLApp.busy && CLApp.busy()) { showError(failure('另一个材料分析正在运行，请先等待或取消。')); return; }
      var reviewed = state.plan.key;
      try { var fresh = await prepare(); if (fresh.key !== reviewed) { status.textContent = '方案已更新，请检查新的范围和调用量后再开始。'; return; }
        if (currentKey() !== state.key) throw failure('作品已切换，本次没有开始补析。');
        if (!semanticReady(fresh, state.payload.sourceOnly)) throw failure('原文范围尚未准备完整，本次没有调用模型。');
        if (!state.payload.sourceOnly && state.authBlock && state.authBlock === state.configTag) throw failure('当前接入仍未更新；本次没有再次调用模型。', 403);
        await execute(state.payload);
      } catch (e) { showError(e); }
    }
    async function cancelRun() { if (!state.busy || !state.ctl) return; status.textContent = '正在请求取消，等待作业确认'; try { await client.cancel(state.ctl); } catch (e) { error.textContent = e.message; } render(); }
    async function resumeRun() { if (state.busy || !state.payload || !state.ctl || !state.ctl.job) return; await execute(state.payload, state.ctl.job); }
    async function openRevision() { if (!state.result || !g.CLApp || !CLApp.mountRevision) return; var d = state.result; try { await CLApp.mountRevision(d.graph, d.key, d.parentKey); close(); } catch (e) { error.textContent = '新版本已保存，但显示未成功：' + e.message; status.textContent = '结果已保留，可从作品库打开；当前作品未替换。'; render(); revealFeedback(); } }
    function invalidate() { if (state.busy) return; if (mode.value === 'sources') scope.value = 'all'; state.planToken++; state.plan = null; state.result = null; info.textContent = ''; error.textContent = ''; render(); }
    [mode, scope, first, last].concat(Object.keys(checks).map(function (key) { return checks[key]; })).forEach(function (e) { e.addEventListener('change', invalidate); });
    root.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); } }, true);
    var manager = g.CLPanelManager; if (manager) manager.register('skyEnrich', { el: root, tier: 'dock', modal: false, title: '结构补析', onClose: function () { root.hidden = true; } });
    function open() {
      if (!state.busy && currentKey() !== state.key) { state.key = currentKey(); state.title = g.CLApp && CLApp.title ? CLApp.title() : '未命名作品'; state.plan = state.payload = state.result = state.ctl = null; state.phase = 'idle'; state.authBlock = null; info.textContent = ''; status.textContent = ''; error.textContent = ''; last.value = ''; mode.value = 'sources'; scope.value = 'all';
        var graph = g.CLApp && CLApp.graph ? CLApp.graph() : null, revision = graph && graph.meta && graph.meta.revision;
        state.parentKey = revision && revision.originalPreserved === true && validKey(revision.parentKey) && revision.parentKey !== state.key ? revision.parentKey : null;
        versionLabel.textContent = state.parentKey ? '上个版本 ' + state.parentKey.slice(0, 12) + ' 仍保留' : ''; restore(); }
      if (manager) manager.open('skyEnrich'); else root.hidden = false;
      render();
      if (!state.busy) discover().catch(function () {});
    }
    async function discover() {
      var key = state.key, plan = state.plan, payload = state.payload;
      if (!key || !plan || !payload || state.ctl && state.ctl.job || state.phase === 'done' || state.phase === 'failed' || state.phase === 'cancelled') return;
      var r = await g.fetch('/api/jobs'), data = await r.json();
      if (state.busy || state.key !== key || state.plan !== plan) return;
      var matches = (data.jobs || []).filter(function (j) { return j.kind === 'enrich' && j.key === key && j.enrichmentPlanKey === plan.key && !j.cancelled; });
      if (matches.length !== 1) return;
      state.ctl = { job: matches[0].job }; state.phase = 'interrupted'; status.textContent = '找到同一方案的作业，可恢复其进度；不会重新开始模型调用。'; save(); render();
    }
    function close() { if (manager) manager.close('skyEnrich'); else root.hidden = true; var trigger = doc.getElementById('skyTools'); if (trigger) trigger.focus({ preventScroll: true }); }
    ui = { open: open, close: close, state: function () { return { key: state.key, phase: state.phase, busy: state.busy, job: state.ctl && state.ctl.job, plan: state.plan, resultKey: state.result && state.result.key, sourceOnly: mode.value === 'sources' }; } }; render(); return ui;
  }
  g.CLSkyEnrich = { createClient: createClient, currentKey: currentKey, validKey: validKey, semanticReady: semanticReady, inputCoverageText: inputCoverageText, layers: LAYERS, open: function () { ensure().open(); }, close: function () { if (ui) ui.close(); }, state: function () { return ui && ui.state(); } };
})(window);
