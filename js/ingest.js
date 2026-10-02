/* Castline · ingest.js
 * 文件夹 → docs[{path,name,text}]，按自然章节序排序。
 * 支持 .md .txt .markdown .json(取字符串字段) .docx(mammoth)
 */
(function () {
  'use strict';
  var OK_EXT = /\.(md|markdown|txt|text|json|docx)$/i;
  var SKIP_DIR = /(^|\/)(\.|node_modules|__MACOSX|legacy|backups|outputs)/;

  // 读文本：先按 UTF-8，若出现大量替换符（GBK/GB18030 存的 txt）则改用 gb18030 重解
  function readText(file) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onerror = function () { rej(new Error('读取失败: ' + file.name)); };
      r.onload = function () {
        var buf = r.result;
        var txt = '';
        try { txt = new TextDecoder('utf-8', { fatal: false }).decode(buf); } catch (e) { txt = ''; }
        var bad = (txt.match(/\uFFFD/g) || []).length;
        if (bad > 0 && bad / Math.max(1, txt.length) > 0.002) {
          try { var alt = new TextDecoder('gb18030').decode(buf); if ((alt.match(/\uFFFD/g) || []).length < bad) txt = alt; } catch (e) {}
        }
        if (txt.charCodeAt(0) === 0xFEFF) txt = txt.slice(1);
        res(txt);
      };
      r.readAsArrayBuffer(file);
    });
  }
  function readDocx(file) {
    return new Promise(function (res, rej) {
      if (typeof mammoth === 'undefined') return rej(new Error('缺少 docx 解析库'));
      var r = new FileReader();
      r.onerror = function () { rej(new Error('读取失败: ' + file.name)); };
      r.onload = function () {
        mammoth.extractRawText({ arrayBuffer: r.result })
          .then(function (o) { res(o.value || ''); })
          .catch(rej);
      };
      r.readAsArrayBuffer(file);
    });
  }
  function jsonToText(s) {
    try {
      var o = JSON.parse(s), out = [];
      (function walk(v, key) {
        if (typeof v === 'string') { if (v.length > 1) out.push(key ? key + '：' + v : v); }
        else if (Array.isArray(v)) v.forEach(function (x) { walk(x, ''); });
        else if (v && typeof v === 'object') Object.keys(v).forEach(function (k) { walk(v[k], k); });
      })(o, '');
      return out.join('\n');
    } catch (e) { return s; }
  }

  // ---- 自然排序：优先章节号，其次数字，其次字典序 --------------------------
  var CN = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10, 百: 100, 千: 1000 };
  function cnNum(s) {
    if (/^\d+$/.test(s)) return parseInt(s, 10);
    var total = 0, sec = 0, num = 0;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i], v = CN[ch];
      if (v === undefined) return NaN;
      if (v >= 10) { if (num === 0) num = 1; sec += num * v; num = 0; }
      else num = v;
    }
    return total + sec + num;
  }
  function sortKey(path) {
    var base = path.split('/').pop();
    var vol = /第([零〇一二两三四五六七八九十百千\d]+)[卷部集]/.exec(path);
    var ch = /第([零〇一二两三四五六七八九十百千\d]+)[章节回幕]/.exec(base) || /^(\d+)[\s._\-、]/.exec(base);
    var v = vol ? cnNum(vol[1]) : 0;
    var c = ch ? cnNum(ch[1]) : NaN;
    // 设定类文件优先（角色/人物/设定/世界观/大纲）
    var pri = /角色|人物|设定|世界观|背景/.test(base) ? 0 : (/大纲|梗概|简介/.test(base) ? 1 : (/细纲/.test(base) ? 2 : 3));
    return { pri: pri, v: isNaN(v) ? 0 : v, c: isNaN(c) ? 1e9 : c, base: base };
  }
  function cmp(a, b) {
    var ka = a._k, kb = b._k;
    if (ka.pri !== kb.pri) return ka.pri - kb.pri;
    if (ka.v !== kb.v) return ka.v - kb.v;
    if (ka.c !== kb.c) return ka.c - kb.c;
    return ka.base.localeCompare(kb.base, 'zh');
  }

  // ---- 遍历 ------------------------------------------------------------------
  function fromFileList(files) {
    var list = [];
    for (var i = 0; i < files.length; i++) {
      var f = files[i], p = f.webkitRelativePath || f.name;
      if (!OK_EXT.test(f.name) || SKIP_DIR.test(p) || /^\./.test(f.name)) continue;
      list.push({ file: f, path: p });
    }
    return Promise.resolve(list);
  }
  function fromDataTransferItems(items) {
    var entries = [];
    for (var i = 0; i < items.length; i++) {
      var en = items[i].webkitGetAsEntry && items[i].webkitGetAsEntry();
      if (en) entries.push(en);
    }
    var out = [];
    function walk(entry, prefix) {
      return new Promise(function (res) {
        var p = prefix + entry.name;
        if (entry.isFile) {
          if (OK_EXT.test(entry.name) && !SKIP_DIR.test(p) && !/^\./.test(entry.name)) {
            entry.file(function (f) { out.push({ file: f, path: p }); res(); }, function () { res(); });
          } else res();
        } else if (entry.isDirectory) {
          if (SKIP_DIR.test(p + '/')) return res();
          var reader = entry.createReader(), all = [];
          (function batch() {
            reader.readEntries(function (ents) {
              if (!ents.length) {
                Promise.all(all.map(function (e) { return walk(e, p + '/'); })).then(res);
              } else { all = all.concat(Array.prototype.slice.call(ents)); batch(); }
            }, function () { res(); });
          })();
        } else res();
      });
    }
    return Promise.all(entries.map(function (e) { return walk(e, ''); })).then(function () { return out; });
  }

  // 读取：6 路并发（原先逐个串行）。上百个章节文件 + docx 解析时读取时间可缩短到原来的 1/4 左右；
  // 结果顺序不依赖完成顺序，最后统一按路径 / 卷章号排序。
  var READ_POOL = 6;
  function load(list, onProgress) {
    var docs = [], n = list.length, done = 0, next = 0;
    function one(it) {
      var f = it.file, rd = /\.docx$/i.test(f.name) ? readDocx(f) : readText(f);
      return rd.then(function (txt) {
        if (/\.json$/i.test(f.name)) txt = jsonToText(txt);
        txt = txt.replace(/\r\n?/g, '\n').replace(/[ \t]+\n/g, '\n').trim();
        if (txt) docs.push({ path: it.path, name: f.name.replace(/\.[^.]+$/, ''), text: txt, bytes: f.size, ext: (f.name.split('.').pop() || '').toLowerCase(), _k: sortKey(it.path) });
      }).catch(function (e) { console.warn(e); }).then(function () {
        done++; if (onProgress) onProgress(done, n, f.name);
      });
    }
    function worker() {
      if (next >= n) return Promise.resolve();
      var it = list[next++];
      return one(it).then(worker);
    }
    var workers = [];
    for (var w = 0; w < Math.min(READ_POOL, n); w++) workers.push(worker());
    return Promise.all(workers).then(function () {
      docs.sort(cmp);
      docs.forEach(function (d) { delete d._k; });
      return docs;
    });
  }

  window.CLIngest = {
    fromFileList: fromFileList,
    fromDataTransferItems: fromDataTransferItems,
    load: load,
    folderName: function (list) {
      var p = list[0] && list[0].path || '';
      return p.indexOf('/') > 0 ? p.split('/')[0] : '';
    }
  };
})();
