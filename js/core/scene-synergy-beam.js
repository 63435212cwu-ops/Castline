
(function (root, factory) {
  if (typeof exports === 'object' && typeof module !== 'undefined') {
    module.exports = factory();
  } else if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else {
    var mod = factory();
    root.CLSceneSynergyBeam = mod;
    if (typeof window !== 'undefined') {
      window.CLSceneSynergyBeam = mod;
      window.CLRadarSynergyBeam = mod;
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];

  var EN = {
    智谋: 'MIND',
    实力: 'FORCE',
    意志: 'WILL',
    魅力: 'CHARM',
    情感: 'HEART',
    野心: 'DRIVE',
    权势: 'REACH',
    道义: 'CODE'
  };

  var THEME_COLORS = {
    mint: '#7af0c8',
    signal: '#ffb45c',
    violet: '#a688ff',
    hot: '#ff5c7c',
    crimson: '#ff5c7c',
    legend: '#fff1c4',
    obsidian: '#07060d',
    muted: '#7d7696'
  };

  var THEME_TOKENS = {
    mint: 'var(--abyss-mint, #7af0c8)',
    signal: 'var(--abyss-signal, #ffb45c)',
    violet: 'var(--abyss-violet, #a688ff)',
    hot: 'var(--abyss-crimson, #ff5d73)',
    crimson: 'var(--abyss-crimson, #ff5d73)',
    legend: 'var(--abyss-tier-legend, #fff1c4)',
    obsidian: 'var(--abyss-obsidian, #05050b)',
    muted: 'var(--abyss-ink-3, #88819d)',
    inkBright: 'var(--abyss-ink-bright, #ffffff)'
  };

  var TOP_PAIRS = {
    '智谋_实力': {
      name: '文武经纬',
      tagline: '文能提笔安天下，武能策马定乾坤；算计与锋刃并重。',
      synergy: '布局深远兼具强悍执行力，计出必行，行之必克。',
      theme: 'signal'
    },
    '智谋_意志': {
      name: '潜行策魂',
      tagline: '耐得极寒，算尽枯荣；经年隐忍只待一击必杀。',
      synergy: '如冰山下之暗流，以万古不移之韧性守护终极谋篇。',
      theme: 'violet'
    },
    '智谋_魅力': {
      name: '经世辩杰',
      tagline: '辩才无碍，智光灼然；以如簧之舌与超卓眼界折服四方。',
      synergy: '洞察人心幽微，言语兼具逻辑机锋与煽动威能。',
      theme: 'signal'
    },
    '智谋_情感': {
      name: '深情哲思',
      tagline: '情丝深重，慧眼穿石；在炽烈共情中洞悉人间终局。',
      synergy: '以敏锐情感感知苍生苦乐，以冷静智算推演解题之道。',
      theme: 'mint'
    },
    '智谋_野心': {
      name: '纵横枭谋',
      tagline: '胸罗万象，志吞山海；以无双算度构筑通天之梯。',
      synergy: '智计与欲望交织，长线落子步步为营，凡所谋求势必达成。',
      theme: 'violet'
    },
    '智谋_权势': {
      name: '深谋策士',
      tagline: '帷幄定局，运筹乾坤；落子无声，翻覆间风云皆入彀中。',
      synergy: '智计通神，手握重器；谋定后动，权倾一方。',
      theme: 'mint'
    },
    '智谋_道义': {
      name: '明德哲人',
      tagline: '格物明理，怀德致远；融博大智慧于清澈道义之中。',
      synergy: '智慧用于守护本心与公理，思虑通达而不堕深渊。',
      theme: 'mint'
    },

    '实力_意志': {
      name: '霸绝战将',
      tagline: '横刀断水，气吞山河；千军辟易处，唯以硬实力破万法。',
      synergy: '百炼成钢，横推八极；武道硬实力与不可摧折之韧性相融贯通。',
      theme: 'hot'
    },
    '实力_魅力': {
      name: '盖世英豪',
      tagline: '力拔山兮气盖世，豪情动地万夫从；天生武宗领袖风范。',
      synergy: '绝对武勇引发追随狂潮，威名赫赫令敌胆寒、令友信服。',
      theme: 'signal'
    },
    '实力_情感': {
      name: '护道战狂',
      tagline: '拳握山河，心系一人；唯有挚爱牵绊能点燃焚天狂怒。',
      synergy: '炽烈情感化为无可遏止的力量源泉，因守护而所向披靡。',
      theme: 'hot'
    },
    '实力_野心': {
      name: '破阵狂澜',
      tagline: '狂澜既起，破阵摧坚；烈意奔涌处，万钧难当。',
      synergy: '锋芒裂阵，图谋浩瀚；以绝顶战力开疆拓土，欲壑所向无坚不摧。',
      theme: 'hot'
    },
    '实力_权势': {
      name: '铁腕霸主',
      tagline: '重兵在握，威加海内；实权与强横战力合二为一。',
      synergy: '以实战硬实力奠定政治根基，以铁血军权慑服四海。',
      theme: 'hot'
    },
    '实力_道义': {
      name: '仗剑侠尊',
      tagline: '侠之大者，以武卫道；仗剑斩尽天下不平事。',
      synergy: '绝顶战力恪守道义底线，行侠仗义，虽千万人吾往矣。',
      theme: 'mint'
    },

    '意志_魅力': {
      name: '风骨行者',
      tagline: '傲骨铮铮，虽折不挠；以高洁气节感召天下同道。',
      synergy: '不可征服的坚韧心性凝聚为崇高人格魅力，四方景附。',
      theme: 'signal'
    },
    '意志_情感': {
      name: '执念守护',
      tagline: '情深不悔，志逾金石；为心中挚念甘受万劫千难。',
      synergy: '情感是唯一灯塔，意志是破浪长桨，任风暴摧残绝不回头。',
      theme: 'violet'
    },
    '意志_野心': {
      name: '宿命狂徒',
      tagline: '身负逆鳞，狂蹈死生；纵是万劫不复，亦要撞碎宿命桎梏。',
      synergy: '执念入骨，逆命狂歌；以不屈铁石意志托举滔天野心。',
      theme: 'violet'
    },
    '意志_权势': {
      name: '定鼎重臣',
      tagline: '砥柱中流，权柄在握；狂风骤雨中稳固社稷江山。',
      synergy: '身居高位而心性坚忍，临危受命力挽狂澜。',
      theme: 'signal'
    },
    '意志_道义': {
      name: '孤忠铁壁',
      tagline: '千磨万击，守死不移；狂澜既倒之际独撑天地脊梁。',
      synergy: '至高原则与铁石意志融为一体，舍生取义，誓不退让。',
      theme: 'mint'
    },

    '魅力_情感': {
      name: '倾世明珠',
      tagline: '情动四方，绝代风华；令万千生灵为之共鸣与驻足。',
      synergy: '真挚浓烈的情感赋魅于一颦一笑，具颠倒众生之感召力。',
      theme: 'signal'
    },
    '魅力_野心': {
      name: '煽惑枭杰',
      tagline: '欲壑吞天，言动天下；以天生魅力编织狂热幻梦引万人奔赴。',
      synergy: '野心隐于耀眼光环之下，极富鼓动性与号召力。',
      theme: 'violet'
    },
    '魅力_权势': {
      name: '天命领袖',
      tagline: '人望归心，坐断东南；超凡声望与实权统治无缝融合。',
      synergy: '权势放大个人威仪，魅力巩固统御根基，天生位居人上。',
      theme: 'signal'
    },
    '魅力_道义': {
      name: '德望贤者',
      tagline: '大德载物，四方景从；以温润仁德感化人间戾气。',
      synergy: '高尚道德情操凝聚无上人望，不怒而自威，不言而自化。',
      theme: 'mint'
    },

    '情感_野心': {
      name: '狂焰殉欲',
      tagline: '情欲如炽，灼烧命运；以偏执烈火撕扯一切阻碍。',
      synergy: '私欲与深情剧烈纠缠，形成吞噬一切也毁灭自我的狂暴动力。',
      theme: 'violet'
    },
    '情感_权势': {
      name: '仁恩魁首',
      tagline: '情系袍泽，恩抚部曲；以深情牵绊织就牢固权力网络。',
      synergy: '权柄化为羽翼庇护所爱之人，部众感念恩义誓死效忠。',
      theme: 'signal'
    },
    '情感_道义': {
      name: '悲悯行者',
      tagline: '心怀万灵之痛，孤身涉渡长夜；以至柔之慈悲抵御凛冽宿命。',
      synergy: '慈悲济世，守正不移；至深共情化为坚不可摧的人间底线。',
      theme: 'mint'
    },

    '野心_权势': {
      name: '登极枭雄',
      tagline: '九五之尊，野心勃勃；调动一切权柄资源只为登顶称王。',
      synergy: '欲望与地位互相催化，步步为营，凡所目及皆欲掌控。',
      theme: 'violet'
    },
    '野心_道义': {
      name: '改序仁雄',
      tagline: '胸怀宏图，正道直行；以不世雄心重塑世间公理秩序。',
      synergy: '既有颠覆旧秩序之雄图大略，又恪守仁义公理之赤子初心。',
      theme: 'mint'
    },

    '权势_道义': {
      name: '清平宪首',
      tagline: '手握重柄，秉公持正；身居显赫而两袖清风、断恶抚弱。',
      synergy: '权位用于匡扶正义，以铁面无私之原则捍卫世间公道。',
      theme: 'mint'
    }
  };


  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function isValidPoint(p) {
    if (!p || typeof p !== 'object') return false;
    var x = p.x != null ? p.x : p.x0;
    var y = p.y != null ? p.y : p.y0;
    if (typeof x !== 'number' || isNaN(x) || !isFinite(x)) return false;
    if (typeof y !== 'number' || isNaN(y) || !isFinite(y)) return false;
    if (p.z != null && (typeof p.z !== 'number' || isNaN(p.z) || !isFinite(p.z))) return false;
    return true;
  }

  function extractPoint(p) {
    return {
      x: p.x != null ? p.x : p.x0,
      y: p.y != null ? p.y : p.y0,
      z: p.z != null ? p.z : 0
    };
  }

  function dist3D(a, b) {
    var dx = b.x - a.x, dy = b.y - a.y, dz = (b.z || 0) - (a.z || 0);
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  function makeDuckVector3(x, y, z) {
    return {
      x: x,
      y: y,
      z: z,
      isVector3: true,
      set: function (nx, ny, nz) { this.x = nx; this.y = ny; this.z = nz; return this; },
      copy: function (v) { this.x = v.x; this.y = v.y; this.z = v.z || 0; return this; },
      clone: function () { return makeDuckVector3(this.x, this.y, this.z); },
      add: function (v) { this.x += v.x; this.y += v.y; this.z += v.z || 0; return this; },
      sub: function (v) { this.x -= v.x; this.y -= v.y; this.z -= v.z || 0; return this; },
      multiplyScalar: function (s) { this.x *= s; this.y *= s; this.z *= s; return this; },
      distanceTo: function (v) { return dist3D(this, v); }
    };
  }


  function resolveSynergyPair(attrs) {
    if (!attrs || typeof attrs !== 'object') return null;

    var raw = attrs;
    if (attrs.attrs && typeof attrs.attrs === 'object') {
      raw = attrs.attrs;
    }

    var scored = [];

    for (var i = 0; i < KEYS.length; i++) {
      var k = KEYS[i];
      var item = raw[k];
      if (item === undefined || item === null) continue;

      var sc = NaN;
      if (typeof item === 'number') {
        sc = item;
      } else if (typeof item === 'object') {
        if (item.pending === true) continue;
        if (item.score !== undefined && item.score !== null) {
          sc = Number(item.score);
        }
      }

      if (typeof sc === 'number' && !isNaN(sc) && isFinite(sc) && sc >= 0) {
        scored.push({
          key: k,
          en: EN[k] || 'DIM',
          score: clamp(Math.round(sc), 0, 100),
          origIndex: i
        });
      }
    }

    if (scored.length < 2) return null;

    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.origIndex - b.origIndex;
    });

    var first = scored[0];
    var second = scored[1];

    if (first.score <= 0 && second.score <= 0) return null;

    var pairKey1 = first.key + '_' + second.key;
    var pairKey2 = second.key + '_' + first.key;
    var pairDef = TOP_PAIRS[pairKey1] || TOP_PAIRS[pairKey2] || {
      name: first.key + second.key + '先驱',
      tagline: first.key + '与' + second.key + '双核驱动，独树一帜。',
      synergy: first.key + '与' + second.key + '高频共鸣，构筑核心优势。',
      theme: 'mint'
    };

    var theme = pairDef.theme || 'mint';
    var color = THEME_COLORS[theme] || THEME_COLORS.mint;
    var token = THEME_TOKENS[theme] || THEME_TOKENS.mint;

    var delta = Math.abs(first.score - second.score);
    var meanScore = (first.score + second.score) / 2;
    var tension = Number(((first.score * 0.55 + second.score * 0.45) / 100).toFixed(3));
    var power = Number(((first.score * second.score) / 10000).toFixed(3));
    var closeness = Number((1 - delta / Math.max(1, first.score)).toFixed(3));
    var harmonicFreq = Number((1.2 + (first.score + second.score) / 160).toFixed(2));

    return {
      primary: {
        key: first.key,
        en: first.en,
        score: first.score,
        index: first.origIndex,
        rank: 1
      },
      secondary: {
        key: second.key,
        en: second.en,
        score: second.score,
        index: second.origIndex,
        rank: 2
      },
      keys: [first.key, second.key],
      pairKey: pairKey1,
      label: first.key + ' × ' + second.key,
      archetype: pairDef.name,
      tagline: pairDef.tagline,
      synergy: pairDef.synergy,
      theme: theme,
      color: color,
      token: token,
      delta: delta,
      mean: Number(meanScore.toFixed(1)),
      ratio: Number((second.score / Math.max(1, first.score)).toFixed(3)),
      tension: tension,
      power: power,
      closeness: closeness,
      harmonicFreq: harmonicFreq
    };
  }


  function createSynergyCurve(ptA, ptB, time, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var L = dist3D(pA, pB);
    if (L < 0.001) return null;

    var t = (typeof time === 'number' && !isNaN(time) && isFinite(time)) ? time : 0;
    var options = (opt && typeof opt === 'object') ? opt : {};

    var samples = clamp(options.samples || 32, 8, 128);
    var curvature = (typeof options.curvature === 'number' && !isNaN(options.curvature)) ? options.curvature : 0.28;
    var sagitta = (typeof options.sagitta === 'number' && !isNaN(options.sagitta)) ? options.sagitta : L * curvature;
    var is3D = options.is3D !== undefined ? Boolean(options.is3D) : (ptA.z != null || ptB.z != null);
    var particleCount = clamp(options.particleCount || 5, 1, 16);
    var pulseSpeed = (typeof options.pulseSpeed === 'number') ? options.pulseSpeed : 0.85;
    var resonance = (typeof options.resonance === 'number') ? clamp(options.resonance, 0, 2) : 0.75;
    var harmonicFreq = (typeof options.harmonicFreq === 'number') ? options.harmonicFreq : 2.0;
    var elevation = (typeof options.elevation === 'number') ? options.elevation : (is3D ? L * 0.12 : 0);

    var gravityCenter = isValidPoint(options.gravityCenter) ? extractPoint(options.gravityCenter) : { x: 0, y: 0, z: 0 };

    var Mx = (pA.x + pB.x) * 0.5;
    var My = (pA.y + pB.y) * 0.5;
    var Mz = (pA.z + pB.z) * 0.5;

    var Dx = pB.x - pA.x;
    var Dy = pB.y - pA.y;
    var Dz = pB.z - pA.z;

    var uDx = Dx / L;
    var uDy = Dy / L;
    var uDz = Dz / L;

    var Rx = Mx - gravityCenter.x;
    var Ry = My - gravityCenter.y;
    var Rz = Mz - gravityCenter.z;

    var Nx = 0, Ny = 0, Nz = 0;

    if (!is3D) {
      Nx = -uDy;
      Ny = uDx;
      Nz = 0;
      var dot2D = Nx * Rx + Ny * Ry;
      if (dot2D < 0) {
        Nx = -Nx;
        Ny = -Ny;
      }
    } else {
      var dotR = Rx * uDx + Ry * uDy + Rz * uDz;
      var rawNx = Rx - dotR * uDx;
      var rawNy = Ry - dotR * uDy;
      var rawNz = Rz - dotR * uDz;
      var lenN = Math.sqrt(rawNx * rawNx + rawNy * rawNy + rawNz * rawNz);

      if (lenN > 0.001) {
        Nx = rawNx / lenN;
        Ny = rawNy / lenN;
        Nz = rawNz / lenN;
      } else {
        Nx = -uDz;
        Ny = 0;
        Nz = uDx;
        var lenAlt = Math.sqrt(Nx * Nx + Nz * Nz);
        if (lenAlt > 0.001) {
          Nx /= lenAlt;
          Nz /= lenAlt;
        } else {
          Nx = 0; Ny = 1; Nz = 0;
        }
      }
    }

    var Cx = Mx + Nx * sagitta;
    var Cy = My + Ny * sagitta + elevation;
    var Cz = Mz + Nz * sagitta;

    var C1x = pA.x + Dx * 0.333 + Nx * sagitta * 0.85;
    var C1y = pA.y + Dy * 0.333 + Ny * sagitta * 0.85 + elevation * 0.7;
    var C1z = pA.z + Dz * 0.333 + Nz * sagitta * 0.85;

    var C2x = pA.x + Dx * 0.667 + Nx * sagitta * 0.85;
    var C2y = pA.y + Dy * 0.667 + Ny * sagitta * 0.85 + elevation * 0.7;
    var C2z = pA.z + Dz * 0.667 + Nz * sagitta * 0.85;

    var tickFrac = (typeof options.tickFrac === 'number') ? clamp(options.tickFrac, 0, 1) : (t % 1);
    var tickPulse = Math.exp(-tickFrac * 4.5);
    var waveAmp = (L * 0.024) * resonance * (1.0 + 0.45 * tickPulse);
    var phase = t * harmonicFreq * Math.PI * 2;

    var Bx = uDy * Nz - uDz * Ny;
    var By = uDz * Nx - uDx * Nz;
    var Bz = uDx * Ny - uDy * Nx;
    var lenB = Math.sqrt(Bx * Bx + By * By + Bz * Bz);
    if (lenB > 0.001) { Bx /= lenB; By /= lenB; Bz /= lenB; }
    else { Bx = 0; By = 0; Bz = 1; }

    var spiralA = [];
    var spiralB = [];
    var spiralRadius = L * 0.038;

    var points = [];
    var positions = new Float32Array((samples + 1) * 3);

    for (var s = 0; s <= samples; s++) {
      var u = s / samples;
      var omt = 1 - u;

      var b0 = omt * omt;
      var b1 = 2 * omt * u;
      var b2 = u * u;

      var bx = b0 * pA.x + b1 * Cx + b2 * pB.x;
      var by = b0 * pA.y + b1 * Cy + b2 * pB.y;
      var bz = b0 * pA.z + b1 * Cz + b2 * pB.z;

      var sinEnvelope = Math.sin(Math.PI * u);
      var standingWave = Math.sin(Math.PI * 4.0 * u - phase) * sinEnvelope * waveAmp;

      var px = bx + Nx * standingWave;
      var py = by + Ny * standingWave;
      var pz = bz + Nz * standingWave;

      var ptVec = makeDuckVector3(
        Number(px.toFixed(2)),
        Number(py.toFixed(2)),
        Number(pz.toFixed(2))
      );

      points.push(ptVec);
      positions[s * 3] = px;
      positions[s * 3 + 1] = py;
      positions[s * 3 + 2] = pz;

      var spEnv = sinEnvelope;
      var spR = spiralRadius * spEnv;
      var thetaA = u * Math.PI * 6.0 + phase;
      var thetaB = thetaA + Math.PI;

      var cosA = Math.cos(thetaA), sinA = Math.sin(thetaA);
      var cosB = Math.cos(thetaB), sinB = Math.sin(thetaB);

      var spAx = px + (Nx * cosA + Bx * sinA) * spR;
      var spAy = py + (Ny * cosA + By * sinA) * spR;
      var spAz = pz + (Nz * cosA + Bz * sinA) * spR;

      var spBx = px + (Nx * cosB + Bx * sinB) * spR;
      var spBy = py + (Ny * cosB + By * sinB) * spR;
      var spBz = pz + (Nz * cosB + Bz * sinB) * spR;

      spiralA.push(makeDuckVector3(Number(spAx.toFixed(2)), Number(spAy.toFixed(2)), Number(spAz.toFixed(2))));
      spiralB.push(makeDuckVector3(Number(spBx.toFixed(2)), Number(spBy.toFixed(2)), Number(spBz.toFixed(2))));
    }

    var svgPath = 'M ' + pA.x.toFixed(1) + ' ' + pA.y.toFixed(1) +
                  ' Q ' + Cx.toFixed(1) + ' ' + Cy.toFixed(1) +
                  ' ' + pB.x.toFixed(1) + ' ' + pB.y.toFixed(1);

    var svgPathCubic = 'M ' + pA.x.toFixed(1) + ' ' + pA.y.toFixed(1) +
                       ' C ' + C1x.toFixed(1) + ' ' + C1y.toFixed(1) +
                       ' ' + C2x.toFixed(1) + ' ' + C2y.toFixed(1) +
                       ' ' + pB.x.toFixed(1) + ' ' + pB.y.toFixed(1);

    var waveParts = ['M ' + points[0].x.toFixed(1) + ' ' + points[0].y.toFixed(1)];
    for (var w = 1; w < points.length; w++) {
      waveParts.push('L ' + points[w].x.toFixed(1) + ' ' + points[w].y.toFixed(1));
    }
    var svgPathWave = waveParts.join(' ');

    var particles = [];
    for (var k = 0; k < particleCount; k++) {
      var progress = ((t * pulseSpeed + (k / particleCount)) % 1 + 1) % 1;
      var pomt = 1 - progress;

      var partBx = pomt * pomt * pA.x + 2 * pomt * progress * Cx + progress * progress * pB.x;
      var partBy = pomt * pomt * pA.y + 2 * pomt * progress * Cy + progress * progress * pB.y;
      var partBz = pomt * pomt * pA.z + 2 * pomt * progress * Cz + progress * progress * pB.z;

      var partWave = Math.sin(Math.PI * 4.0 * progress - phase) * Math.sin(Math.PI * progress) * waveAmp;
      var ppx = partBx + Nx * partWave;
      var ppy = partBy + Ny * partWave;
      var ppz = partBz + Nz * partWave;

      var env = Math.sin(Math.PI * progress);
      var alpha = Math.max(0, Math.min(1, Math.pow(env, 0.65) * (0.65 + 0.35 * Math.sin(t * 4.0 + k))));
      var size = Number((2.2 + 2.0 * env * (1.0 + 0.3 * tickPulse)).toFixed(2));
      var glow = Number((size * 2.8).toFixed(2));

      particles.push({
        index: k,
        progress: Number(progress.toFixed(4)),
        x: Number(ppx.toFixed(2)),
        y: Number(ppy.toFixed(2)),
        z: Number(ppz.toFixed(2)),
        size: size,
        alpha: Number(alpha.toFixed(3)),
        glow: glow
      });
    }

    var midIdx = Math.floor(samples / 2);
    var midPt = points[midIdx] || points[0];
    var nodeSize = Number((4.2 + 3.2 * tickPulse * resonance).toFixed(2));
    var resonanceNode = {
      x: midPt.x,
      y: midPt.y,
      z: midPt.z,
      size: nodeSize,
      pulse: Number(tickPulse.toFixed(3)),
      phase: Number(phase.toFixed(3)),
      intensity: Number((0.65 + 0.35 * tickPulse).toFixed(3))
    };

    return {
      points: points,
      positions: positions,
      pointCount: points.length,
      distance: Number(L.toFixed(2)),
      midpoint: makeDuckVector3(Number(Mx.toFixed(2)), Number(My.toFixed(2)), Number(Mz.toFixed(2))),
      controlPoint: makeDuckVector3(Number(Cx.toFixed(2)), Number(Cy.toFixed(2)), Number(Cz.toFixed(2))),
      controlPoint1: makeDuckVector3(Number(C1x.toFixed(2)), Number(C1y.toFixed(2)), Number(C1z.toFixed(2))),
      controlPoint2: makeDuckVector3(Number(C2x.toFixed(2)), Number(C2y.toFixed(2)), Number(C2z.toFixed(2))),
      sagitta: Number(sagitta.toFixed(2)),
      svgPath: svgPath,
      svgPathCubic: svgPathCubic,
      svgPathWave: svgPathWave,
      particles: particles,
      hasLightBridge: true,
      spiralA: spiralA,
      spiralB: spiralB,
      resonanceNode: resonanceNode,
      resonance: {
        phase: Number(phase.toFixed(3)),
        intensity: Number((0.65 + 0.35 * tickPulse).toFixed(3)),
        tickPulse: Number(tickPulse.toFixed(3)),
        coreWidth: Number((1.6 + 0.6 * tickPulse).toFixed(2)),
        haloWidth: Number((5.5 + 2.5 * tickPulse).toFixed(2)),
        breath: Number((1.0 + 0.08 * Math.sin(t * 2.62)).toFixed(3)),
        coherence: Number((0.92 + 0.08 * tickPulse).toFixed(3))
      }
    };
  }


  function createGravityField(ptA, ptB, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);
    var L = dist3D(pA, pB);
    if (L < 0.001) return null;

    var options = (opt && typeof opt === 'object') ? opt : {};
    var scoreA = (typeof options.scoreA === 'number' && !isNaN(options.scoreA)) ? clamp(options.scoreA, 1, 100) : 80;
    var scoreB = (typeof options.scoreB === 'number' && !isNaN(options.scoreB)) ? clamp(options.scoreB, 1, 100) : 80;

    var massA = scoreA;
    var massB = scoreB;
    var totalMass = massA + massB;

    var bx = (massA * pA.x + massB * pB.x) / totalMass;
    var by = (massA * pA.y + massB * pB.y) / totalMass;
    var bz = (massA * pA.z + massB * pB.z) / totalMass;
    var barycenter = makeDuckVector3(Number(bx.toFixed(2)), Number(by.toFixed(2)), Number(bz.toFixed(2)));

    var sqrtA = Math.sqrt(massA);
    var sqrtB = Math.sqrt(massB);
    var fracA = sqrtA / (sqrtA + sqrtB);

    var l1x = pA.x + fracA * (pB.x - pA.x);
    var l1y = pA.y + fracA * (pB.y - pA.y);
    var l1z = pA.z + fracA * (pB.z - pA.z);
    var lagrangeL1 = makeDuckVector3(Number(l1x.toFixed(2)), Number(l1y.toFixed(2)), Number(l1z.toFixed(2)));

    var fieldRadius = Number((L * 1.25).toFixed(2));
    var dipolePower = Number(((massA - massB) / Math.max(1, totalMass)).toFixed(3));
    var potentialDepth = Number((- (massA + massB) / Math.max(10, L)).toFixed(3));

    function evaluateAt(targetPt) {
      if (!isValidPoint(targetPt)) {
        return {
          force: makeDuckVector3(0, 0, 0),
          potential: 0,
          fieldStrength: 0,
          direction: makeDuckVector3(0, 0, 0)
        };
      }

      var pt = extractPoint(targetPt);
      var softening = 8.0;

      var dxA = pt.x - pA.x, dyA = pt.y - pA.y, dzA = pt.z - pA.z;
      var distA = Math.sqrt(dxA * dxA + dyA * dyA + dzA * dzA + softening * softening);

      var dxB = pt.x - pB.x, dyB = pt.y - pB.y, dzB = pt.z - pB.z;
      var distB = Math.sqrt(dxB * dxB + dyB * dyB + dzB * dzB + softening * softening);

      var pot = - (massA / distA + massB / distB);

      var fA = massA / (distA * distA * distA);
      var fB = massB / (distB * distB * distB);

      var fx = - (fA * dxA + fB * dxB);
      var fy = - (fA * dyA + fB * dyB);
      var fz = - (fA * dzA + fB * dzB);

      var fMag = Math.sqrt(fx * fx + fy * fy + fz * fz);
      var dirX = fMag > 0.0001 ? fx / fMag : 0;
      var dirY = fMag > 0.0001 ? fy / fMag : 0;
      var dirZ = fMag > 0.0001 ? fz / fMag : 0;

      return {
        force: makeDuckVector3(Number(fx.toFixed(3)), Number(fy.toFixed(3)), Number(fz.toFixed(3))),
        potential: Number(pot.toFixed(3)),
        fieldStrength: Number(fMag.toFixed(3)),
        direction: makeDuckVector3(Number(dirX.toFixed(3)), Number(dirY.toFixed(3)), Number(dirZ.toFixed(3)))
      };
    }

    return {
      barycenter: barycenter,
      lagrangeL1: lagrangeL1,
      fieldRadius: fieldRadius,
      dipolePower: dipolePower,
      potentialDepth: potentialDepth,
      massA: massA,
      massB: massB,
      evaluateAt: evaluateAt
    };
  }


  function createResonanceField(ptA, ptB, time, opt) {
    if (!isValidPoint(ptA) || !isValidPoint(ptB)) return null;

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);
    var t = (typeof time === 'number' && !isNaN(time) && isFinite(time)) ? time : 0;
    var options = (opt && typeof opt === 'object') ? opt : {};

    var tickFrac = (typeof options.tickFrac === 'number') ? clamp(options.tickFrac, 0, 1) : (t % 1);
    var pulse = Math.exp(-tickFrac * 4.5);
    var coherence = (typeof options.coherence === 'number') ? clamp(options.coherence, 0.5, 1) : 0.95;

    var ringA = {
      scale: Number((1.0 + 0.35 * pulse).toFixed(3)),
      opacity: Number((0.65 + 0.35 * pulse).toFixed(3)),
      glow: Number((6.0 + 10.0 * pulse).toFixed(2)),
      reticleRadius: Number((7.0 + 2.5 * pulse).toFixed(2))
    };

    var ringB = {
      scale: Number((1.0 + 0.30 * pulse).toFixed(3)),
      opacity: Number((0.60 + 0.35 * pulse).toFixed(3)),
      glow: Number((5.5 + 9.5 * pulse).toFixed(2)),
      reticleRadius: Number((6.5 + 2.2 * pulse).toFixed(2))
    };

    var nodeMid = {
      x: Number(((pA.x + pB.x) * 0.5).toFixed(2)),
      y: Number(((pA.y + pB.y) * 0.5).toFixed(2)),
      z: Number(((pA.z + pB.z) * 0.5).toFixed(2))
    };

    return {
      ringA: ringA,
      ringB: ringB,
      nodeMid: nodeMid,
      tickPulse: Number(pulse.toFixed(3)),
      coherence: coherence,
      intensity: Number((0.70 + 0.30 * pulse).toFixed(3)),
      breath: Number((1.0 + 0.08 * Math.sin(t * 2.62)).toFixed(3))
    };
  }


  function renderSVGBeam(ptA, ptB, time, opt) {
    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) {
      return {
        svgHTML: '',
        curve: null,
        id: '',
        pathD: '',
        toString: function () { return ''; }
      };
    }

    var options = (opt && typeof opt === 'object') ? opt : {};
    var theme = options.theme || 'mint';
    var beamColor = THEME_TOKENS[theme] || THEME_TOKENS.mint;
    var beamId = options.id || ('cl-beam-' + Math.floor(Math.random() * 100000));
    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var partsHTML = [];
    for (var i = 0; i < curve.particles.length; i++) {
      var p = curve.particles[i];
      partsHTML.push(
        '<circle class="cl-synergy-particle" cx="' + p.x + '" cy="' + p.y + '" r="' + p.size + '" ' +
        'fill="var(--abyss-ink-bright, #ffffff)" opacity="' + p.alpha + '" ' +
        'style="filter:drop-shadow(0 0 4px ' + beamColor + ');vector-effect:non-scaling-stroke;" />'
      );
    }

    var lockRadiusA = (6.5 * curve.resonance.intensity).toFixed(1);
    var lockRadiusB = (6.5 * curve.resonance.intensity).toFixed(1);

    var svgHTML = [
      '<g class="cl-synergy-beam" id="' + beamId + '" data-theme="' + theme + '" style="opacity:0.96;">',
      '  <!-- 霓虹外层泛光导轨 (Halo) -->',
      '  <path class="cl-synergy-glow" d="' + curve.svgPath + '" fill="none" stroke="' + beamColor + '" ' +
         'stroke-width="var(--abyss-sp-sm, 6px)" stroke-linecap="round" opacity="' + (0.32 * curve.resonance.intensity).toFixed(3) + '" ' +
         'style="filter:drop-shadow(0 0 8px ' + beamColor + ');vector-effect:non-scaling-stroke;" />',
      '  <!-- 高能光核导轨 (Laser Core) -->',
      '  <path class="cl-synergy-core" d="' + curve.svgPath + '" fill="none" stroke="var(--abyss-ink-bright, #ffffff)" ' +
         'stroke-width="var(--abyss-sp-2xs, 2px)" stroke-linecap="round" opacity="0.94" ' +
         'style="filter:drop-shadow(0 0 3px var(--abyss-ink-bright, #ffffff));vector-effect:non-scaling-stroke;" />',
      '  <!-- 光子能量流动包 (Travelling Photons) -->',
      '  ' + partsHTML.join('\n  '),
      '  <!-- 晶冠顶点战术锁定环 A -->',
      '  <circle class="cl-synergy-lock cl-synergy-lock-a" cx="' + pA.x.toFixed(1) + '" cy="' + pA.y.toFixed(1) + '" r="' + lockRadiusA + '" ' +
         'fill="none" stroke="' + beamColor + '" stroke-width="1.2" style="filter:drop-shadow(0 0 5px ' + beamColor + ');" />',
      '  <!-- 晶冠顶点战术锁定环 B -->',
      '  <circle class="cl-synergy-lock cl-synergy-lock-b" cx="' + pB.x.toFixed(1) + '" cy="' + pB.y.toFixed(1) + '" r="' + lockRadiusB + '" ' +
         'fill="none" stroke="' + beamColor + '" stroke-width="1.2" style="filter:drop-shadow(0 0 5px ' + beamColor + ');" />',
      '</g>'
    ].join('\n');

    return {
      id: beamId,
      svgHTML: svgHTML,
      curve: curve,
      pathD: curve.svgPath,
      toString: function () { return svgHTML; }
    };
  }


  function updateSVGBeamElement(groupEl, ptA, ptB, time, opt) {
    if (!groupEl || typeof groupEl.setAttribute !== 'function') return null;

    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) {
      groupEl.style.display = 'none';
      return null;
    }

    groupEl.style.display = '';

    var glowPath = groupEl.querySelector('.cl-synergy-glow');
    if (glowPath) {
      glowPath.setAttribute('d', curve.svgPath);
      glowPath.setAttribute('opacity', (0.32 * curve.resonance.intensity).toFixed(3));
    }

    var corePath = groupEl.querySelector('.cl-synergy-core');
    if (corePath) {
      corePath.setAttribute('d', curve.svgPath);
    }

    var particleEls = groupEl.querySelectorAll('.cl-synergy-particle');
    for (var i = 0; i < particleEls.length; i++) {
      var pData = curve.particles[i];
      if (pData) {
        particleEls[i].setAttribute('cx', pData.x);
        particleEls[i].setAttribute('cy', pData.y);
        particleEls[i].setAttribute('r', pData.size);
        particleEls[i].setAttribute('opacity', pData.alpha);
      }
    }

    var pA = extractPoint(ptA);
    var pB = extractPoint(ptB);

    var lockA = groupEl.querySelector('.cl-synergy-lock-a');
    if (lockA) {
      lockA.setAttribute('cx', pA.x.toFixed(1));
      lockA.setAttribute('cy', pA.y.toFixed(1));
      lockA.setAttribute('r', (6.5 * curve.resonance.intensity).toFixed(1));
    }

    var lockB = groupEl.querySelector('.cl-synergy-lock-b');
    if (lockB) {
      lockB.setAttribute('cx', pB.x.toFixed(1));
      lockB.setAttribute('cy', pB.y.toFixed(1));
      lockB.setAttribute('r', (6.5 * curve.resonance.intensity).toFixed(1));
    }

    return curve;
  }


  function createSynergy3DGeometry(ptA, ptB, time, opt) {
    var curve = createSynergyCurve(ptA, ptB, time, opt);
    if (!curve) return null;

    var nPoints = curve.points.length;
    var colors = new Float32Array(nPoints * 3);

    var options = (opt && typeof opt === 'object') ? opt : {};
    var theme = options.theme || 'mint';
    var baseHex = THEME_COLORS[theme] || THEME_COLORS.mint;

    var r = parseInt(baseHex.slice(1, 3), 16) / 255;
    var g = parseInt(baseHex.slice(3, 5), 16) / 255;
    var b = parseInt(baseHex.slice(5, 7), 16) / 255;

    for (var i = 0; i < nPoints; i++) {
      var u = i / (nPoints - 1);
      var peak = Math.sin(Math.PI * u);

      colors[i * 3] = clamp(r + peak * (1.0 - r) * 0.75, 0, 1);
      colors[i * 3 + 1] = clamp(g + peak * (1.0 - g) * 0.75, 0, 1);
      colors[i * 3 + 2] = clamp(b + peak * (1.0 - b) * 0.75, 0, 1);
    }

    var geom = null;
    var T = (typeof window !== 'undefined' && window.THREE) ? window.THREE : (typeof root !== 'undefined' && root.THREE) ? root.THREE : null;

    if (T && typeof T.BufferGeometry === 'function') {
      try {
        geom = new T.BufferGeometry();
        geom.setAttribute('position', new T.BufferAttribute(curve.positions, 3));
        geom.setAttribute('color', new T.BufferAttribute(colors, 3));
      } catch (err) {
        geom = null;
      }
    }

    return {
      geometry: geom,
      positions: curve.positions,
      colors: colors,
      count: nPoints,
      curve: curve
    };
  }


  function getPairDefinition(keyA, keyB) {
    if (!keyA || !keyB) {
      return {
        name: '未知协同',
        tagline: '未定之弦，静候启明。',
        synergy: '属性矩阵尚待校准，双核特征暂未显化。',
        theme: 'mint'
      };
    }

    var p1 = keyA + '_' + keyB;
    var p2 = keyB + '_' + keyA;
    return TOP_PAIRS[p1] || TOP_PAIRS[p2] || {
      name: keyA + keyB + '先驱',
      tagline: keyA + '与' + keyB + '双核驱动，独树一帜。',
      synergy: keyA + '与' + keyB + '高频共鸣，构筑核心优势。',
      theme: 'mint'
    };
  }

  return {
    KEYS: KEYS,
    EN: EN,
    THEME_COLORS: THEME_COLORS,
    THEME_TOKENS: THEME_TOKENS,
    TOP_PAIRS: TOP_PAIRS,

    resolveSynergyPair: resolveSynergyPair,
    createSynergyCurve: createSynergyCurve,
    createGravityField: createGravityField,
    createResonanceField: createResonanceField,
    renderSVGBeam: renderSVGBeam,
    updateSVGBeamElement: updateSVGBeamElement,
    createSynergy3DGeometry: createSynergy3DGeometry,
    getPairDefinition: getPairDefinition
  };
});
