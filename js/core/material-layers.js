(function (g) {
  'use strict';

  var LAYERS = {
    /* ============================ 晶体 · 暗玻璃基底（CROWN_BASE_FS） ============================ */
    volume: {
      id: 'volume', label: '体积（volume/thickness）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrVolume', on: 1, off: 0, structure: false,
      anchor: 'float depthMetric = clamp((opticalDepth + vH * 0.40) * uLyrVolume, 0.0, 2.0);',
      baseline: 'float depthMetric = clamp(opticalDepth + vH * 0.40, 0.0, 2.0);',
      effect: '椭球弦长 × 高度的光学深度。关闭后 depthMetric 归零 => 宽面回到常数厚度读法，'
            + '透射/星海/晶纹/体色散射同时失去深度依据（这正是「均匀透明几何」的成因）。',
      metric: 'facetStats.localVariance 中位数下降、flatShare 上升',
      note: '体积层是 P07 的首要隔离对象：审核原话「晶体仍像均匀透明几何」直接指向它。'
    },
    surface: {
      id: 'surface', label: '表面（surface/roughness 逐面明暗）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrSurface', on: 1, off: 0, structure: false,
      anchor: 'float fv = mix(1.0, 1.0 + (0.34 * dot(N, L1) + 0.24 * dot(surfaceR, L2)) * uLyrSurface, viewWeight);',
      baseline: 'float fv = mix(1.0, 1.0 + 0.34 * dot(N, L1) + 0.24 * dot(surfaceR, L2), viewWeight);',
      effect: '逐面明暗（facet shading）—— 法线主导的晶面层次。关闭后 fv 恒为 1，'
            + '所有切面读数相同 => 宽面失去方向性明暗，只剩轮廓。',
      metric: 'facetStats.gradientLog1p 中位数下降、orientEntropy 下降',
      note: '与 uFacet 不同：uFacet 是 0..1 插值权重，会连带改变体积项；'
          + 'uLyrSurface 只缩放**偏差量**，几何与数据完全不动。'
    },
    rough: {
      id: 'rough', label: '表面粗糙（磨砂腰棱 frosting）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrRough', on: 1, off: 0, structure: false,
      anchor: 'float grit = 0.70 + 0.30 * h3(floor(vL * 3.4)) * uLyrRough;',
      baseline: 'float grit = 0.70 + 0.30 * h3(floor(vL * 3.4));',
      effect: '腰棱（aFace 3）的磨砂颗粒对比。关闭后颗粒变常数 0.70 —— 腰棱仍在、仍可读，'
            + '但失去微观粗糙度。审核提到「腰环偏暗褐」，此层是分离"腰环几何"与"腰环材质"的开关。',
      metric: '腰棱带的局部方差下降，全图平均亮度变化应 < 0.3%',
      note: 'review 证据「腰环偏暗褐」需要把腰环**几何**与**材质**分开评；本开关只动材质。'
    },
    transmission: {
      id: 'transmission', label: '透射（transmission/absorption 深度项）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrTrans', on: 1, off: 0, structure: false,
      anchor: 'vec3 transmission = exp(-spectralAbs * (0.12 + 3.20 * depthMetric * uLyrTrans) * uAbs * (0.92 + 0.18 * veil));',
      baseline: 'vec3 transmission = exp(-spectralAbs * (0.12 + 3.20 * depthMetric) * uAbs * (0.92 + 0.18 * veil));',
      effect: 'Beer-Lambert 光谱波长选择性吸收的**深度项**。关闭后只剩 0.12 的常数吸收，'
            + '透射不再随厚度变色 —— 这正是审核说的「大面积均匀透色」。'
            + '保留 0.12 常数项是刻意的：结构（晶面/棱线）不会因此消失。',
      metric: '青/紫宽面的色度随高度变化的相关系数下降（色相相似度上升）',
      note: '审核原话「青色上体和紫色下体拥有大面积均匀透色」= 该项的深度依赖被压平。'
    },
    innerlight: {
      id: 'innerlight', label: '内部光学（needle/晶纹内发光）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrInner', on: 1, off: 0, structure: false,
      anchor: 'inner += uRim * needleV * 0.46 * uLyrInner;',
      baseline: 'inner += uRim * needleV * 0.46;',
      effect: '体积射线步进累积的晶纹 / 星海 / 微米晶管贡献。关闭后晶体内腔变空，'
            + '只剩下表面反射与底吸收 —— 用来量「内部光学层次」单独占多少。',
      metric: '宽面局部方差显著下降；p90 亮度下降但均值变化应 < 2%',
      note: '该层依赖 volume（depthMetric 归零时 needleV 也归零）：'
          + 'A/B 顺序必须先测 volume 再测 innerlight，否则两者混淆。'
    },
    reflection: {
      id: 'reflection', label: '反射（specular/fresnel）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrRefl', on: 1, off: 0, structure: false,
      anchor: 'vec3 surface = (spec * fr * 1.45 * uLyrRefl + uRim * (s1 + s2) * 0.52 * uLyrRefl) * surfacePath;',
      baseline: 'vec3 surface = (spec * fr * 1.45 + uRim * (s1 + s2) * 0.52) * surfacePath;',
      effect: 'Fresnel 加权的环境反射 + 两枚椭圆光叶。关闭后晶体只剩体色与透射，'
            + '轮廓刃光（ed 项，在 col 之后单独相加）**保留** —— 结构可读性不丢。',
      metric: '掠射角像素亮度下降；facetMask.share 变化应 < 2%（结构未丢）',
      note: '刻意不动 `col += ... * ed * uEdge ...` 刃光项：那是结构线索，不是反射。'
    },
    additive: {
      id: 'additive', label: '加性（additive/emissive 火彩层）', shader: 'CROWN_FS',
      uniform: 'uLyrAdd', on: 1, off: 0, structure: false,
      anchor: 'col += (uCb * fire + mix(uRim, fireDisp * 1.25, 0.38) * sparkle * 1.22 + uRim * edgeLight * uEdge * 0.22 + uRim * flash * 0.92 + uRim * hlPulse * 0.40) * uLyrAdd;',
      baseline: 'col += uCb * fire + mix(uRim, fireDisp * 1.25, 0.38) * sparkle * 1.22 + uRim * edgeLight * uEdge * 0.22 + uRim * flash * 0.92 + uRim * hlPulse * 0.40;',
      effect: '火彩（scintillation）+ 镀膜干涉闪点 + 棱刃 + 晶面闪光 + 轴向脉动。'
            + '这一层用的是 AdditiveBlending，是**唯一**会整体抬高画面亮度的层；'
            + '单独关闭它是验证「不得用全局提高亮度掩盖结构问题」的对照面。',
      metric: '全图平均亮度下降（这正是要防的伪完成方向）；facetStats 结构读数应基本不变',
      note: 'P07 禁止用提亮冒充层次：本开关的存在使「亮度」与「层次」可分离测量。'
    },
    backAtten: {
      id: 'backAtten', label: '背面光程衰减（back-face path length）', shader: 'CROWN_BASE_FS',
      uniform: 'uLyrBackAtt', on: 1, off: 0, structure: false,
      anchor: '  if (!gl_FrontFacing) { a *= 1.0 + (clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.35, 1.0) - 1.0) * uLyrBackAtt; }',
      baseline: '  if (!gl_FrontFacing) { a *= 1.0 + (clamp(dot(transmission, vec3(0.2126, 0.7152, 0.0722)), 0.35, 1.0) - 1.0); }',
      effect: '背面片元的光已经穿过晶体一次，其 alpha 应乘透射亮度（Rec.709 亮度加权，下限 0.35）'
            + '而不是与正面同权再叠一层。关闭后背面以与正面相同的 alpha 叠加，'
            + '把正面建立的晶面层次冲淡 —— 这正是「背面像均匀透明几何」的成因。',
      metric: 'sd（局部层次）与 lap（相邻梯度）上升、暗部抬起而亮部几乎不动（分桶非均匀）；'
            + 'hi（>200 亮像素%）不下降',
      note: '实测（条带 768×1024，显式渲染，噪声 floor=0，**同一次运行内**取 Δ）：'
          + 'sd 24.0657→25.9320（Δ+1.87）、lap 2.1416→2.8956（Δ+0.75）；'
          + '用生产代码的 uniform 开关复测（另一口径）：sd 24.4271→26.2387（Δ+1.81）、'
          + 'lap 2.1817→2.8680（Δ+0.69）、hi 0.2537→0.2537（零损失）。'
          + '代价：mean +2.10~2.17，但分桶证明非均匀调亮（暗部 +3.18 / 中暗部 −1.60 / 亮部 +0.005），'
          + '不是整体提亮。'
          + '⚠ 两套口径的 Δ 略有差异（补丁走 shader 重编译、开关走 uniform），'
          + '**不可跨运行相减**取 Δ —— 先前本行曾误用「本次 candidate − 上次 baseline」得到 +1.62，已更正。'
    }
  };

  var RING_LAYERS = {
    domesection: {
      id: 'domesection', label: '光环截面 · 穹顶剖面（rim/dome cross-section）', shader: 'RF',
      uniform: 'uLyrDome', on: 1, off: 0, structure: false,
      anchor: 'float coreK=(1.0-smoothstep(hw-0.8,hw+0.8,d))*uLyrDome;',
      baseline: 'float coreK=1.0-smoothstep(hw-0.8,hw+0.8,d);',
      effect: '光环横截面的芯部（coreK）与穹顶轮廓（dome）。关闭后弧带的"实体感"消失，'
            + '只剩外发光；用来量「宽亮边」里有多少来自截面芯而非刻度。',
      metric: '弧带横截面峰值亮度下降；弧带中心线位置不变（结构定位不漂移）'
    },
    concentric: {
      id: 'concentric', label: '光环截面 · 同心干涉纹（concentric interference）', shader: 'RF',
      uniform: 'uLyrConc', on: 1, off: 0, structure: false,
      anchor: 'float concentric=1.0+(0.76+0.16*radInterf+0.08*radHarm-1.0)*uLyrConc;',
      baseline: 'float concentric=0.76+0.16*radInterf+0.08*radHarm;',
      effect: '双谐波法布里-珀罗光栅在天球上的同心干涉纹。关闭后 sheen 恒为 1，'
            + '弧带内出现均匀带 —— 与晶体「均匀透色」是同一类问题，必须能单独量。',
      metric: '弧带内亮度方差下降；弧带总亮度不变（off 值是向 1.0 收敛，不是衰减）'
    },
    astrolabe: {
      id: 'astrolabe', label: '光环截面 · 仪轨刻度（astrolabe ticks）', shader: 'RF',
      uniform: 'uLyrAstro', on: 1, off: 0, structure: true,
      anchor: 'float astrolabeTicks=(tickCoarse*0.45+tickFine*0.35)*shoulder*uLyrAstro;',
      baseline: 'float astrolabeTicks=(tickCoarse*0.45+tickFine*0.35)*shoulder;',
      effect: '天文仪轨经度辅助刻度（粗弧分 + 游标微刻度）。**这是刻度读数，属于结构信息**：'
            + 'structure=true，低画质/减弱动态/WebGL fallback 通路禁止关闭它。',
      metric: '刻度位置的高频能量下降；刻度所在的方位角不移动',
      note: '把它标成 structure=true 是刻意的：审核说「刻度、亮芯和引线相互竞争」，'
          + '正确解法是调**权重**，不是删刻度 —— 删了就是拿结构换画质。'
    },
    sparsefloor: {
      id: 'sparsefloor', label: '光环截面 · 稀疏扇区视差底（sparse-sector parallax floor）', shader: 'RF',
      uniform: 'uLyrFloor', on: 1, off: 0, structure: false,
      anchor: 'float sparseFloor=(coreK*(0.038+0.052*concentric+0.035*astrolabeTicks)+glow*0.02)*(0.25+0.75*uAMain)*uLyrFloor;',
      baseline: 'float sparseFloor=(coreK*(0.038+0.052*concentric+0.035*astrolabeTicks)+glow*0.02)*(0.25+0.75*uAMain);',
      effect: '事件稀疏扇区的暗金/冷灰视差底，注释自述目的是「杜绝大片死黑」。'
            + '关闭它会**降低**平均亮度 —— 因此这个开关必须与晶体 additive 层配对使用，'
            + '否则会误判成"去掉底噪"的改善。',
      metric: '稀疏扇区亮度下降；该扇区并非结构信息位（结构在弧带上），故 structure=false'
    }
  };

  var ORDER = ['volume', 'backAtten', 'surface', 'rough', 'transmission', 'innerlight', 'reflection', 'additive'];
  var RING_ORDER = ['domesection', 'concentric', 'astrolabe', 'sparsefloor'];

  function uniVal(u, name) {
    var v = u && u[name];
    if (v && typeof v === 'object' && 'value' in v) return v.value;
    return v;
  }
  function setUni(u, name, value) {
    if (!u) return false;
    var v = u[name];
    if (v && typeof v === 'object' && 'value' in v) { v.value = value; return true; }
    u[name] = value; return true;
  }

  function forShader(shaderText) {
    var name = shaderName(shaderText);
    if (name === 'RF') {
      var rl = layersFor(shaderText, true);
      return { shader: name, ring: true, layers: rl, count: rl.length };
    }
    var cl = layersFor(shaderText, false);
    return { shader: name, ring: false, layers: cl, count: cl.length };
  }
  function shaderName(text) {
    var s = String(text || '');
    if (s.indexOf(RING_LAYERS.domesection.anchor) >= 0) return 'RF';
    if (s.indexOf(LAYERS.additive.anchor) >= 0) return 'CROWN_FS';
    if (s.indexOf(LAYERS.volume.anchor) >= 0) return 'CROWN_BASE_FS';
    return 'unknown';
  }

  function layersFor(shaderText, ring) {
    var pool = ring ? RING_LAYERS : LAYERS, order = ring ? RING_ORDER : ORDER;
    var src = String(shaderText == null ? '' : shaderText), out = [];
    var want = ring ? 'RF' : shaderName(src);
    for (var i = 0; i < order.length; i++) {
      var L = pool[order[i]];
      if (L && L.shader === want && src.indexOf(L.anchor) >= 0) out.push(L);
    }
    return out;
  }

  function rollbackText(shaderText) {
    var s = String(shaderText == null ? '' : shaderText), all = inventory(), i, n = 0;
    for (i = 0; i < all.length; i++) {
      if (all[i].anchor !== all[i].baseline && s.indexOf(all[i].anchor) >= 0) {
        s = s.split(all[i].anchor).join(all[i].baseline); n++;
      }
    }
    return { text: s, reverted: n };
  }
  function forwardText(shaderText) {
    var s = String(shaderText == null ? '' : shaderText), all = inventory(), i, n = 0;
    for (i = 0; i < all.length; i++) {
      if (all[i].anchor !== all[i].baseline && s.indexOf(all[i].baseline) >= 0 && s.indexOf(all[i].anchor) < 0) {
        s = s.split(all[i].baseline).join(all[i].anchor); n++;
      }
    }
    return { text: s, applied: n };
  }

  function install(uniforms, layerList) {
    var list = layerList || [], i, L;
    for (i = 0; i < list.length; i++) {
      L = list[i];
      setUni(uniforms, L.uniform, L.on);
    }
    return uniforms;
  }

  function apply(uniforms, layerId, enabled, ring) {
    var pool = ring ? RING_LAYERS : LAYERS, L = pool[layerId];
    if (!L) throw new Error('unknown material layer: ' + layerId);
    var before = {}, order = ring ? RING_ORDER : ORDER, i, k;
    for (i = 0; i < order.length; i++) { k = pool[order[i]].uniform; before[k] = uniVal(uniforms, k); }
    setUni(uniforms, L.uniform, enabled ? L.on : L.off);
    var after = {}, changed = [];
    for (i = 0; i < order.length; i++) {
      k = pool[order[i]].uniform; after[k] = uniVal(uniforms, k);
      if (after[k] !== before[k]) changed.push(k);
    }
    return { layer: layerId, from: before[L.uniform], to: after[L.uniform],
             changedUniforms: changed, isolated: changed.length === 1 };
  }

  function snapshot(uniforms, ring) {
    var pool = ring ? RING_LAYERS : LAYERS, order = ring ? RING_ORDER : ORDER;
    var out = { ring: !!ring, values: {} };
    for (var i = 0; i < order.length; i++) {
      var k = pool[order[i]].uniform;
      out.values[k] = uniVal(uniforms, k);
    }
    return out;
  }
  function restore(uniforms, snap) {
    if (!snap || !snap.values) return false;
    for (var k in snap.values) if (Object.prototype.hasOwnProperty.call(snap.values, k)) setUni(uniforms, k, snap.values[k]);
    return true;
  }
  function canonical(ring) {
    var pool = ring ? RING_LAYERS : LAYERS, order = ring ? RING_ORDER : ORDER, out = {};
    for (var i = 0; i < order.length; i++) out[pool[order[i]].uniform] = pool[order[i]].on;
    return out;
  }
  function allOff(ring) {
    var pool = ring ? RING_LAYERS : LAYERS, order = ring ? RING_ORDER : ORDER, out = {};
    for (var i = 0; i < order.length; i++) {
      var L = pool[order[i]];
      out[L.uniform] = L.structure ? L.on : L.off;
    }
    return out;
  }
  function structureLayers(ring) {
    var pool = ring ? RING_LAYERS : LAYERS, order = ring ? RING_ORDER : ORDER, out = [];
    for (var i = 0; i < order.length; i++) if (pool[order[i]].structure) out.push(order[i]);
    return out;
  }
  function inventory() {
    var out = [], i, k;
    for (i = 0; i < ORDER.length; i++) out.push(LAYERS[ORDER[i]]);
    for (k = 0; k < RING_ORDER.length; k++) out.push(RING_LAYERS[RING_ORDER[k]]);
    return out;
  }

  g.CLLayerRegistry = {
    name: 'material-layers',
    version: 'p07',
    LAYERS: LAYERS,
    RING_LAYERS: RING_LAYERS,
    ORDER: ORDER,
    RING_ORDER: RING_ORDER,
    forShader: forShader,
    layersFor: layersFor,
    shaderName: shaderName,
    rollbackText: rollbackText,
    forwardText: forwardText,
    install: install,
    apply: apply,
    snapshot: snapshot,
    restore: restore,
    canonical: canonical,
    allOff: allOff,
    structureLayers: structureLayers,
    inventory: inventory,
    uniVal: uniVal,
    setUni: setUni
  };
})(typeof window !== 'undefined' ? window : this);
