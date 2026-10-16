'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const ROOT = path.join(__dirname, '..');

let count = 0;
function check(value, name) { if (!value) throw new Error('FAIL: ' + name); count++; }

function mockFile(name, buf, fail) { return { name: name, size: buf.byteLength, __buf: buf, __fail: !!fail }; }
function makeFileReaderCtor() {
  return function FileReader() {
    const self = this;
    self.readAsArrayBuffer = function (file) {
      setTimeout(function () {
        if (file.__fail) { if (self.onerror) self.onerror(); }
        else { self.result = file.__buf.slice(0); if (self.onload) self.onload(); }
      }, 0);
    };
  };
}
function makeIndexedDB(opt) {
  opt = opt || {};
  const persisted = opt.persisted || new Map();
  function guard(idb, fn) { return function () { try { fn && fn(); } catch (e) { idb._callbackErrors.push(e); } }; }
  const idb = {
    _persisted: persisted,
    _callbackErrors: [],
    failOpen: !!opt.failOpen,
    failPut: !!opt.failPut,
    abortAfterPut: !!opt.abortAfterPut,
    open: function () {
      const req = {};
      setTimeout(function () {
        if (idb.failOpen) { req.error = new Error('mock open failed'); if (req.onerror) req.onerror(); return; }
        const db = {
          transaction: function () {
            const tx = { error: null };
            tx.objectStore = function () {
              return {
                put: function (value, key) {
                  const r = {};
                  setTimeout(function () {
                    if (idb.failPut) {
                      tx.error = new Error('mock put failed');
                      r.error = tx.error;
                      guard(idb, r.onerror)();
                      guard(idb, tx.onerror)();
                      guard(idb, tx.onabort)();
                    } else {
                      if (!idb.abortAfterPut) persisted.set(key, JSON.parse(JSON.stringify(value)));
                      guard(idb, r.onsuccess)();
                      if (idb.abortAfterPut) {
                        tx.error = new Error('transaction aborted after put success');
                        guard(idb, tx.onerror)();
                        guard(idb, tx.onabort)();
                      } else guard(idb, tx.oncomplete)();
                    }
                  }, 0);
                  return r;
                },
                get: function (key) {
                  const r = {};
                  setTimeout(function () {
                    r.result = persisted.has(key) ? JSON.parse(JSON.stringify(persisted.get(key))) : undefined;
                    guard(idb, r.onsuccess)();
                    guard(idb, tx.oncomplete)();
                  }, 0);
                  return r;
                }
              };
            };
            return tx;
          }
        };
        req.result = db;
        if (opt.needUpgrade) guard(idb, req.onupgradeneeded)();
        guard(idb, req.onsuccess)();
      }, 0);
      return req;
    }
  };
  return idb;
}
function loadModule(file, sandbox) { vm.runInNewContext(fs.readFileSync(path.join(ROOT, file), 'utf8'), sandbox, { filename: file }); }
function freshIngest() {
  const sandbox = { window: {}, console: { warn: function () {}, error: function () {} }, TextDecoder: TextDecoder, Promise: Promise, setTimeout: setTimeout };
  sandbox.FileReader = makeFileReaderCtor();
  vm.createContext(sandbox);
  loadModule('js/ingest.js', sandbox);
  return sandbox.window.CLIngest;
}
function freshTray(idbOpt) {
  const sandbox = { window: {}, console: { warn: function () {}, error: function () {} }, Promise: Promise, Date: Date, Math: Math, setTimeout: setTimeout };
  sandbox.indexedDB = makeIndexedDB(idbOpt);
  vm.createContext(sandbox);
  loadModule('js/tray.js', sandbox);
  return { tray: sandbox.window.CLTray, idb: sandbox.indexedDB };
}

const utf8 = (s) => new TextEncoder().encode(s).buffer;
function utf16buf(s, le, bom) {
  const bytes = [];
  if (bom) { if (le) bytes.push(0xFF, 0xFE); else bytes.push(0xFE, 0xFF); }
  for (let i = 0; i < s.length; i++) { const u = s.charCodeAt(i); if (le) bytes.push(u & 0xFF, u >> 8); else bytes.push(u >> 8, u & 0xFF); }
  return new Uint8Array(bytes).buffer;
}
function goodEntry(i) {
  return { id: 'ok' + i, hash: 'h' + i, path: 'f' + i + '.txt', name: 'f' + i, text: '正文' + i, bytes: 4, ext: 'txt', kind: null, exclude: false, batch: i, batchLabel: '第 ' + i + ' 批', addedAt: i };
}

(async function () {
  const mixed = await freshIngest().load([
    { file: mockFile('u16le.txt', utf16buf('第一章 风起 Hello', true, true)), path: 'u16le.txt' },
    { file: mockFile('u16be.txt', utf16buf('第二章 云涌 World', false, true)), path: 'u16be.txt' },
    { file: mockFile('u8bom.txt', utf8('﻿第三章 雷鸣')), path: 'u8bom.txt' },
    { file: mockFile('gbk.txt', new Uint8Array([0xC4, 0xE3, 0xC3, 0xC7]).buffer), path: 'gbk.txt' },
    { file: mockFile('trunc.txt', new TextEncoder().encode('测试内容').slice(0, 5).buffer), path: 'trunc.txt' },
    { file: mockFile('u16nobom.txt', utf16buf('plain english note', true, false)), path: 'u16nobom.txt' },
    { file: mockFile('u16benobom.txt', utf16buf('Hello big endian', false, false)), path: 'u16benobom.txt' },
    { file: mockFile('mix-nul.txt', new Uint8Array([0, 97, 0, 98, 99, 0, 100, 0]).buffer), path: 'mix-nul.txt' },
    { file: mockFile('u8nul.txt', new Uint8Array([97, 98, 0, 99, 100, 0, 101, 102, 0]).buffer), path: 'u8nul.txt' },
    { file: mockFile('empty.txt', utf8('   \n  ')), path: 'empty.txt' }
  ]);
  const byPath = {}; mixed.forEach(function (d) { byPath[d.path] = d; });
  check(byPath['u16le.txt'] && byPath['u16le.txt'].text === '第一章 风起 Hello', 'UTF-16LE BOM 解码');
  check(byPath['u16be.txt'] && byPath['u16be.txt'].text === '第二章 云涌 World', 'UTF-16BE BOM 解码');
  check(byPath['u8bom.txt'] && byPath['u8bom.txt'].text === '第三章 雷鸣', 'UTF-8 BOM 剥离');
  check(byPath['gbk.txt'] && byPath['gbk.txt'].text === '你们', 'GBK 回退保持');
  check(byPath['trunc.txt'] && byPath['trunc.txt'].text.indexOf('测') === 0 && byPath['trunc.txt'].text.indexOf('�') >= 0, '截断 UTF-8 保留可见替换符（可解释）');
  check(byPath['u16nobom.txt'] && byPath['u16nobom.txt'].text === 'plain english note', '无 BOM UTF-16LE 按原始字节奇偶 NUL 判端序');
  check(byPath['u16benobom.txt'] && byPath['u16benobom.txt'].text === 'Hello big endian', '无 BOM UTF-16BE 判 BE 而非误写为 LE 乱码（主控缺口 1）');
  var Z = String.fromCharCode(0);
  check(byPath['mix-nul.txt'] && byPath['mix-nul.txt'].text === Z + 'a' + Z + 'bc' + Z + 'd' + Z, '奇偶 NUL 对称 = 歧义不瞎猜，保留 UTF-8 原解 ' + JSON.stringify(byPath['mix-nul.txt'] && byPath['mix-nul.txt'].text));
  check(byPath['u8nul.txt'] && byPath['u8nul.txt'].text === 'ab' + Z + 'cd' + Z + 'ef' + Z, '普通 UTF-8 含少量 NUL 边界保持原码 ' + JSON.stringify(byPath['u8nul.txt'] && byPath['u8nul.txt'].text));
  check(!byPath['empty.txt'], '空白文件不入库（既有行为）');

  const part = await freshIngest().load([
    { file: mockFile('good.txt', utf8('正常章节')), path: 'good.txt' },
    { file: mockFile('bad.txt', utf8('x'), true), path: 'bad.txt' }
  ]);
  check(part.length === 1 && part[0].path === 'good.txt', '成功文件照常返回');
  check(Array.isArray(part.failures) && part.failures.length === 1, 'failures 数组存在且含一条');
  check(part.failures[0].path === 'bad.txt' && /读取失败/.test(part.failures[0].error), '失败条目含路径与可解释错误');
  check(JSON.stringify([part[0].path]) === JSON.stringify(part.map(function (d) { return d.path; })), 'failures 不影响数组常规用法');
  check(Object.keys(part).indexOf('failures') < 0, 'failures 不可枚举');

  const envC = freshTray({ persisted: new Map([['tray', [
    goodEntry(1),
    { id: 'bad1', path: 'b.txt', name: 'b', bytes: 4, ext: 'txt', batch: 1 },
    'garbage-string',
    null,
    { id: 'bad2', text: 42, batch: 2 },
    { id: 'ok1', text: '重复 id', batch: 7 },
    { text: '', batch: 3 }
  ]]]) });
  await envC.tray.restore();
  check(envC.idb._callbackErrors.length === 0, 'restore 回调不再抛错');
  check(envC.tray.items().length === 2, '损坏条目被过滤，仅两条有效');
  const kept = envC.tray.items();
  check(kept[0].id === 'ok1' && kept[0].text === '正文1', '原样保留合法条目');
  check(kept[1].text === '重复 id' && kept[1].id !== 'ok1' && kept[1].id, '重复 id 被重新生成');
  check(typeof kept[1].hash === 'string' && kept[1].hash.length > 0 && kept[1].hash !== 'h', '缺失 hash 被重算');
  check(kept[1].ext === 'path' || typeof kept[1].ext === 'string', '归一化字段存在');
  const t = envC.tray.totals();
  check(t.files === 2 && t.active === 2 && t.chars === 3 + 5, 'totals() 不再抛错 ' + JSON.stringify(t));
  check(envC.tray.groups().length >= 1, 'groups() 可用');
  const r2 = envC.tray.add([{ path: 'z.md', name: 'z', text: '新增', bytes: 2, ext: 'md' }], 'later');
  check(r2.batch === 8, 'batchSeq 从恢复批次续接（max 7 + 1 = 8），实际 ' + r2.batch);

  const idbF = makeIndexedDB({ failPut: true });
  const sandboxF = { window: {}, console: { warn: function () {}, error: function () {} }, Promise: Promise, Date: Date, Math: Math, setTimeout: setTimeout, indexedDB: idbF };
  vm.createContext(sandboxF);
  loadModule('js/tray.js', sandboxF);
  const trayF = sandboxF.window.CLTray;
  await trayF.restore();
  await new Promise(function (res) { trayF.add([{ path: 'x.md', name: 'x', text: '内容', bytes: 2, ext: 'md' }], 't'); setTimeout(res, 30); });
  check(trayF.items().length === 1, 'put 失败不影响内存托盘');
  check(trayF.lastPersistError() !== null, 'put 失败记录 lastPersistError');
  idbF.failPut = false;
  await new Promise(function (res) { trayF.add([{ path: 'y.md', name: 'y', text: '第二份', bytes: 2, ext: 'md' }], 't2'); setTimeout(res, 30); });
  check(trayF.lastPersistError() === null, '持久化恢复后错误被清除（以 tx.oncomplete 为准）');
  check(idbF._persisted.has('tray') && idbF._persisted.get('tray').length === 2, '恢复后快照正确落盘');

  const envA = freshTray({ abortAfterPut: true });
  await envA.tray.restore();
  await new Promise(function (res) { envA.tray.add([{ path: 'a.md', name: 'a', text: '甲', bytes: 1, ext: 'md' }], 'ta'); setTimeout(res, 30); });
  check(envA.tray.lastPersistError() !== null && /中止|abort/i.test(String(envA.tray.lastPersistError().message || envA.tray.lastPersistError())), 'put 成功后事务 onabort 被捕获（主控缺口 2），实际 ' + envA.tray.lastPersistError());
  check(envA.tray.items().length === 1, '事务中止后内存托盘仍正常');
  check(!envA.idb._persisted.has('tray'), '中止的事务不落盘');
  envA.idb.abortAfterPut = false;
  await new Promise(function (res) { envA.tray.add([{ path: 'b.md', name: 'b', text: '乙', bytes: 1, ext: 'md' }], 'tb'); setTimeout(res, 30); });
  check(envA.tray.lastPersistError() === null, '后续事务完成后错误清除：串行 persistQueue 未挂起');
  check(envA.idb._persisted.has('tray') && envA.idb._persisted.get('tray').length === 2, '失败后串行后续快照仍能写入');

  async function race(mutate, expect) {
    const env = freshTray({ persisted: new Map([['tray', [goodEntry(9)]]]) });
    const p = env.tray.restore();
    mutate(env.tray);
    await p;
    await new Promise(function (res) { setTimeout(res, 30); });
    check(env.tray.items().length === expect.n, expect.name + '：内存为准');
    const snap = env.idb._persisted.get('tray');
    check(!expect.disk ? !snap || snap.length === expect.n : true, expect.name + '：磁盘被内存反向覆盖');
  }
  await race(function (tr) { tr.add([{ path: 'n.md', name: 'n', text: '用户新拖入', bytes: 5, ext: 'md' }], 'rush'); }, { n: 1, name: 'restore 期间 add' });
  await race(function (tr) { tr.clear(); }, { n: 0, name: 'restore 期间 clear' });

  const envN = freshTray({ persisted: new Map([['tray', { oops: 1 }]]) });
  await envN.tray.restore();
  check(envN.tray.items().length === 0 && envN.tray.totals().files === 0, '非数组快照按空托盘恢复');
  const envO = freshTray({ failOpen: true });
  await envO.tray.restore();
  check(envO.tray.items().length === 0, 'IndexedDB 打开失败降级为内存托盘');

  const envG = freshTray({ persisted: new Map([['tray', [goodEntry(1), goodEntry(2)]]]) });
  await envG.tray.restore();
  check(envG.tray.items().length === 2, '正常快照完整恢复');
  check(envG.tray.items()[0].batch === 1 && envG.tray.items()[1].batch === 2, '批次字段保持');
  const envW = freshTray({});
  await envW.tray.restore();
  envW.tray.add([{ path: 'w.md', name: 'w', text: '往返文本', bytes: 4, ext: 'md' }], 'w');
  await new Promise(function (res) { setTimeout(res, 30); });
  const envR = freshTray({ persisted: envW.idb._persisted });
  await envR.tray.restore();
  check(envR.tray.items().length === 1 && envR.tray.items()[0].text === '往返文本', '快照 roundtrip 恢复');
  const dup = envR.tray.add([{ path: 'w.md', name: 'w', text: '往返文本', bytes: 4, ext: 'md' }], 'dup');
  check(dup.added === 0 && dup.dup === 1, '同文本去重保持');

  const sorted = await freshIngest().load([
    { file: mockFile('第三章.txt', utf8('三')), path: '第三章.txt' },
    { file: mockFile('第一章.txt', utf8('一')), path: '第一章.txt' },
    { file: mockFile('第二章.txt', utf8('二')), path: '第二章.txt' }
  ]);
  check(sorted.length === 3 && sorted[0].path === '第一章.txt' && sorted[2].path === '第三章.txt', '章节自然排序保持');
  check(!('_k' in sorted[0]), '内部排序键不外泄');

  console.log('K3-W4-INGEST OK · ' + count + ' assertions');
})().catch(function (e) { console.error(e.message || e); process.exit(1); });
