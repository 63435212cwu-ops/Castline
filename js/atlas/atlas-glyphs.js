(function () {
  'use strict';

  var STROKE_W = '1.25';

  var GLYPHS = {
    'start':
      '<path d="M6.4,3.2 C4.5,5 4.5,11 6.4,12.8"/>' +
      '<circle cx="11" cy="8" r="1.3" fill="currentColor" stroke="none"/>',

    'end-resolved':
      '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',

    'end-suspended':
      '<circle cx="8" cy="8" r="3"/>',

    'end-open':
      '<line x1="2.4" y1="8" x2="7.4" y2="8" stroke-dasharray="1.6,1.4"/>' +
      '<line x1="7.4" y1="8" x2="11.6" y2="8"/>' +
      '<path d="M9.4,5.6 L12.6,8 L9.4,10.4"/>',

    'end-unknown':
      '<rect x="4" y="4" width="8" height="8"/>' +
      '<path d="M6.6,6.6 C6.6,5.5 7.4,4.8 8.2,4.8 C9.1,4.8 9.8,5.5 9.8,6.35 C9.8,7.6 8.1,7.6 8.1,8.9" stroke-width="1.1"/>' +
      '<circle cx="8.1" cy="10.9" r="0.55" fill="currentColor" stroke="none"/>',

    'handoff':
      '<line x1="5" y1="3" x2="5" y2="8.4"/>' +
      '<line x1="11" y1="7.6" x2="11" y2="13"/>' +
      '<line x1="5" y1="8" x2="11" y2="8" stroke-dasharray="1,1.4"/>',

    'turn':
      '<path d="M8,3 L13,8 L8,13 L3,8 Z"/>',

    'fork':
      '<path d="M8,3 L8,7.2 M8,7.2 L3.6,13 M8,7.2 L12.4,13"/>',

    'aggregate':
      '<circle cx="6" cy="10.5" r="3"/>' +
      '<circle cx="8.4" cy="7.7" r="3"/>' +
      '<circle cx="10.8" cy="4.9" r="3"/>',

    'lead':
      '<circle cx="8" cy="8" r="2.6" fill="currentColor" stroke="none"/>',

    'core':
      '<circle cx="8" cy="8" r="2.6"/>' +
      '<path d="M8,5.4 A2.6,2.6 0 0 1 8,10.6 Z" fill="currentColor" stroke="none"/>',

    'minor':
      '<circle cx="8" cy="8" r="2.1"/>'
  };

  var KINDS = [
    'start', 'end-resolved', 'end-suspended', 'end-open', 'end-unknown',
    'handoff', 'turn', 'fork', 'aggregate', 'lead', 'core', 'minor'
  ];

  function buildSymbol(kind) {
    var body = GLYPHS[kind];
    if (body == null) { return ''; }
    return '<symbol id="cl-g-' + kind + '" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
      'stroke-width="' + STROKE_W + '" stroke-linecap="round" stroke-linejoin="round">' +
      body + '</symbol>';
  }

  function defs() {
    var out = [];
    for (var i = 0; i < KINDS.length; i++) {
      out.push(buildSymbol(KINDS[i]));
    }
    return '<svg class="cl-atlas-defs" aria-hidden="true" focusable="false">' + out.join('') + '</svg>';
  }

  function use(kind, cls) {
    var classAttr = 'cl-g cl-g-' + kind + (cls ? ' ' + cls : '');
    return '<svg class="' + classAttr + '" aria-hidden="true" focusable="false">' +
      '<use href="#cl-g-' + kind + '"></use></svg>';
  }

  window.CLAtlasGlyphs = {
    defs: defs,
    use: use,
    KINDS: KINDS.slice(),
    VERSION: '7.0'
  };
})();
