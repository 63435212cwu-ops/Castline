(function (g) {
  'use strict';

  var VERSION = '1';
  var LABEL_MAX = 48;
  var CHAPTER_MAX = 16;
  var UNKNOWN = '未命名事件';


  function isUsable(v) {
    return typeof v === 'string' && v.trim().length > 0;
  }

  function str(v) { return typeof v === 'string' ? v : ''; }

  function clip(s, max) {
    var t = str(s).trim().replace(/\s+/g, ' ');
    return t.length > max ? t.slice(0, max) : t;
  }

  function stripTags(s) {
    return str(s).replace(/[<>]/g, '');
  }

  function hashOf(v) {
    var s = str(v), h = 2166136261, i;
    for (i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    return ('0000' + h.toString(36)).slice(-4);
  }

  function chapterShort(chapter) {
    var t = str(chapter).trim();
    if (!t) return '';
    var m = t.match(/^第\s*[0-9一二三四五六七八九十百千两]+\s*[章回节卷篇]/);
    if (m) return m[0].replace(/\s+/g, '');
    return clip(t, CHAPTER_MAX);
  }


  function eventLabel(e, opts) {
    var o = opts || {};
    var max = typeof o.max === 'number' && o.max > 0 ? o.max : LABEL_MAX;
    var ev = (e && typeof e === 'object') ? e : {};

    var title = stripTags(str(ev.title)).trim();
    if (title) return clip(title, max);

    var name = stripTags(str(ev.name)).trim();
    if (name) return clip(name, max);

    var ch = chapterShort(ev.chapter);
    var parts = [UNKNOWN];
    if (ch) parts.push(ch);
    if (isUsable(ev.id)) parts.push('#' + hashOf(ev.id));
    return clip(parts.join(' · '), Math.max(max, LABEL_MAX));
  }

  function labelParts(e) {
    var ev = (e && typeof e === 'object') ? e : {};
    var title = stripTags(str(ev.title)).trim();
    if (title) return { text: clip(title, LABEL_MAX), source: 'title', unknown: false };
    var name = stripTags(str(ev.name)).trim();
    if (name) return { text: clip(name, LABEL_MAX), source: 'name', unknown: false };
    return {
      text: eventLabel(ev),
      source: 'unknown',
      unknown: true,
      chapter: chapterShort(ev.chapter),
      detail: clip(ev.summary, 120),
      id: isUsable(ev.id) ? String(ev.id) : null,
      cast: Array.isArray(ev.characters) ? ev.characters.slice() : []
    };
  }

  var API = {
    VERSION: VERSION,
    LABEL_MAX: LABEL_MAX,
    UNKNOWN: UNKNOWN,
    eventLabel: eventLabel,
    labelParts: labelParts,
    isUsable: isUsable,
    chapterShort: chapterShort,
    hashOf: hashOf,
    pure: {
      eventLabel: eventLabel,
      labelParts: labelParts,
      isUsable: isUsable,
      chapterShort: chapterShort,
      hashOf: hashOf,
      clip: clip,
      stripTags: stripTags
    }
  };

  g.CLSkyEventLabel = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
