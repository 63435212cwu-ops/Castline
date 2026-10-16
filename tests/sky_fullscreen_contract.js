var api = require('../js/sky/sky-fullscreen.js');
var count = 0;
function ok(value, label) { if (!value) throw new Error('FAIL ' + label); count++; }

function stubBtn() {
  var b = { disabled: false, title: '', textContent: '全屏', attrs: {}, listeners: {} };
  b.classList = {
    _set: {},
    toggle: function (c, on) { if (on === undefined) on = !this._set[c]; this._set[c] = !!on; },
    add: function (c) { this._set[c] = true; },
    remove: function (c) { delete this._set[c]; },
    contains: function (c) { return !!this._set[c]; }
  };
  b.setAttribute = function (k, v) { this.attrs[k] = String(v); };
  b.removeAttribute = function (k) { delete this.attrs[k]; };
  b.addEventListener = function (t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); };
  b.fire = function (t) { (this.listeners[t] || []).forEach(function (f) { f(); }); };
  return b;
}
function stubDoc(mode) {
  var doc = { fullscreenElement: null, listeners: {} };
  doc.documentElement = { __doc: doc };
  doc.addEventListener = function (t, f) { (doc.listeners[t] = doc.listeners[t] || []).push(f); };
  doc.fire = function (t) { (doc.listeners[t] || []).forEach(function (f) { f(); }); };
  if (mode === 'modern') {
    doc.documentElement.requestFullscreen = function () { doc.calls.push('request'); doc.fullscreenElement = doc.documentElement; return Promise.resolve(); };
    doc.exitFullscreen = function () { doc.calls.push('exit'); doc.fullscreenElement = null; return Promise.resolve(); };
  } else if (mode === 'legacy') {
    doc.documentElement.webkitRequestFullscreen = function () { doc.calls.push('webkit-request'); doc.webkitFullscreenElement = doc.documentElement; };
    doc.webkitExitFullscreen = function () { doc.calls.push('webkit-exit'); doc.webkitFullscreenElement = null; };
  } else if (mode === 'reject') {
    doc.documentElement.requestFullscreen = function () { doc.calls.push('request'); return Promise.reject(new DOMException('Permissions check failed')); };
    doc.exitFullscreen = function () { return Promise.resolve(); };
  } else if (mode === 'throw') {
    doc.documentElement.requestFullscreen = function () { throw new Error('sync boom'); };
  }
  doc.calls = [];
  return doc;
}

var none = stubDoc('none');
ok(api.supported(none) === false, 'no Fullscreen API → unsupported');
ok(!!none.documentElement && api.supported({}) === false, 'missing documentElement → unsupported');
ok(api.supported(null) === false, 'null doc → unsupported');
var bN = stubBtn();
ok(api.syncButton(bN, none).supported === false, 'unsupported doc reports supported=false');
ok(bN.disabled === true && bN.attrs['aria-disabled'] === 'true', 'unsupported → explicit disable, not a dead-looking live button');
ok(!('aria-pressed' in bN.attrs), 'unsupported button carries no pressed state to fake');
ok(bN.title.indexOf('部分移动端浏览器不支持') >= 0, 'unsupported title honestly names partial mobile browsers (iOS Safari class)');
ok(api.toggle(none).kind === 'unsupported', 'toggle on unsupported doc refuses as unsupported, never fakes entry');

var doc = stubDoc('modern'), btn = stubBtn(), toasts = [];
var w = api.wire({ doc: doc, btn: btn, toast: function (t) { toasts.push(t); } });
ok(w.wired === true && w.unsupported === false, 'wire succeeds on modern doc');
ok(w.listeners.indexOf('keydown') < 0 && w.listeners.length === 3, 'wire registers click + 2 fullscreenchange listeners and NEVER keydown (Esc stays native)');
ok(btn.disabled === false && btn.attrs['aria-pressed'] === 'false' && btn.textContent === '全屏', 'wired button starts enabled, unpressed, labeled enter');
var settled = null;
btn.fire('click');
ok(doc.calls[0] === 'request', 'click while windowed requests fullscreen on documentElement');
Promise.resolve().then(function () {
  doc.fire('fullscreenchange');
  ok(btn.attrs['aria-pressed'] === 'true' && btn.textContent === '退出全屏', 'fullscreenchange after enter flips pressed state and copy');
  doc.fire('webkitfullscreenchange');
  ok(btn.attrs['aria-pressed'] === 'true', 'webkit-prefixed event drives the same single state channel');
  ok(btn.classList.contains('on'), 'active state class follows the event');

  btn.fire('click');
  ok(doc.calls.join(',') === 'request,exit', 'click while fullscreen exits via document.exitFullscreen — request/exit correctly paired');
  ok(btn.textContent === '退出全屏', 'button does not flip off a bare click; it waits for the real event (no parallel state)');
  return Promise.resolve();
}).then(function () {
  doc.fire('fullscreenchange');
  ok(btn.attrs['aria-pressed'] === 'false' && btn.textContent === '全屏' && !btn.classList.contains('on'), 'fullscreenchange after exit restores enter state');
  ok(toasts.length === 0, 'no toast on the happy path');

  doc.fullscreenElement = doc.documentElement;
  doc.fire('fullscreenchange');
  ok(btn.attrs['aria-pressed'] === 'true' && btn.textContent === '退出全屏', 'system-level (F11) fullscreen syncs the button through the same event, no parallel flag');
  doc.fullscreenElement = null;
  doc.fire('fullscreenchange');
  ok(btn.attrs['aria-pressed'] === 'false', 'system exit (native Esc) syncs back');

  var L = stubDoc('legacy'); L.calls = []; var bL = stubBtn();
  api.wire({ doc: L, btn: bL });
  ok(api.supported(L) === true && api.active(L) === false, 'webkit-only doc is supported and windowed');
  var lr = null;
  api.toggle(L, function (r) { lr = r; });
  ok(L.calls[0] === 'webkit-request' && lr && lr.ok === true && lr.action === 'enter', 'legacy toggle issues webkit request and honestly reports the issued action');
  ok(api.active(L) === true, 'legacy stub state became fullscreen');
  api.toggle(L);
  ok(L.calls.join(',') === 'webkit-request,webkit-exit', 'legacy exit pairs webkit exit call');

  var R = stubDoc('reject'), bR = stubBtn(), rToasts = [];
  api.wire({ doc: R, btn: bR, toast: function (t) { rToasts.push(t); } });
  var rr = null;
  api.toggle(R, function (r) { rr = r; });
  ok(R.calls[0] === 'request' && rr === null, 'denied request does not settle synchronously');
  bR.fire('click');
  ok(R.calls.length === 2 && rToasts.length === 0, 'wired click issues another request and still no synchronous toast');
  return Promise.resolve().then(function () {
    ok(rr && rr.ok === false && rr.kind === 'denied', 'rejected promise lands as denied');
    ok(rToasts.length === 1 && rToasts[0].indexOf('拒绝') >= 0, 'denied path tells the user the browser refused, in plain words');
    R.fire('fullscreenchange');
    ok(bR.attrs['aria-pressed'] === 'false' && bR.textContent === '全屏', 'button stays unpressed after denial — state only follows real events');
    ok(api.why('denied').indexOf('拒绝') >= 0 && api.why('denied').indexOf('框架') >= 0, 'denied copy names gesture/iframe causes');

    var E = stubDoc('throw');
    var er = null;
    api.toggle(E, function (r) { er = r; });
    ok(er && er.kind === 'error' && er.ok === false, 'synchronous throw lands as error kind');
    ok([null, undefined].every(function (d) { var r = api.toggle(d); return r && r.kind === 'unsupported'; }), 'null doc toggles safely into unsupported');

    ok(api.wire({}).wired === false && api.wire({ doc: none, btn: null }).wired === false, 'wire without doc/button does not crash');
    ok(api.syncButton(null, none) === null, 'syncButton tolerates null button');

    ok(api.version === 'castline/sky-fullscreen/1', 'version string is published');
    process.stdout.write('sky_fullscreen_contract OK · ' + count + ' checks\n');
  });
}).catch(function (e) { process.stdout.write('FAIL ' + (e && e.message || e) + '\n'); process.exit(1); });
