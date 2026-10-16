(function (g) {
  'use strict';
  if (!g.THREE) { return; }

  var NCLOUD = 5;

  var VS = 'varying vec2 vUv;void main(){vUv = uv;gl_Position = vec4(position.xy, 0.0, 1.0);}';

  var FS =
    'varying vec2 vUv;uniform float uFace;uniform float uSeed;uniform float uGain;' +
    'uniform vec3 uPole;uniform vec3 uCoreDir;uniform vec3 uBase;uniform vec3 uBand;uniform vec3 uBandHot;uniform vec3 uCoreCol;' +
    'uniform vec3 uCDir[5];uniform vec3 uCCol[5];uniform float uCRad[5];uniform float uCOn[5];uniform float uBandT;uniform float uBandK;uniform float uLaneW;uniform float uBandT0;uniform float uBandK0;' +
    'float hs(vec3 p){p = floor(p);return fract(sin(dot(p, vec3(127.1, 311.7, 74.7)) + uSeed) * 43758.5453123);}' +
    'float vn(vec3 p){vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);' +
    'float n000 = hs(i), n100 = hs(i + vec3(1.0, 0.0, 0.0)), n010 = hs(i + vec3(0.0, 1.0, 0.0)), n110 = hs(i + vec3(1.0, 1.0, 0.0));' +
    'float n001 = hs(i + vec3(0.0, 0.0, 1.0)), n101 = hs(i + vec3(1.0, 0.0, 1.0)), n011 = hs(i + vec3(0.0, 1.0, 1.0)), n111 = hs(i + vec3(1.0, 1.0, 1.0));' +
    'return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y), mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);}' +
    'float fbm(vec3 p){float s = 0.0, a = 0.5; for(int i = 0; i < 5; i++){ s += a * vn(p); p = p * 2.03 + 1.7; a *= 0.5; } return s;}' +
    'void main(){float u = 2.0 * vUv.x - 1.0, v = 2.0 * vUv.y - 1.0; vec3 d;' +
    'if(uFace < 0.5) d = vec3(1.0, -v, -u); else if(uFace < 1.5) d = vec3(-1.0, -v, u); else if(uFace < 2.5) d = vec3(u, 1.0, v);' +
    'else if(uFace < 3.5) d = vec3(u, -1.0, -v); else if(uFace < 4.5) d = vec3(u, -v, 1.0); else d = vec3(-u, -v, -1.0); d = normalize(d);' +
    'vec3 q = d * 2.2 + 0.8 * vec3(fbm(d * 1.7), fbm(d * 1.7 + 5.2), fbm(d * 1.7 + 9.1));' +
    'float lat = asin(clamp(dot(d, uPole), -1.0, 1.0)), ka = acos(clamp(dot(d, uCoreDir), -1.0, 1.0));' +
    'float n1 = fbm(q * 1.4), n2 = fbm(q * 3.6 + 3.1), clump = smoothstep(0.32, 0.82, n1 * 0.7 + n2 * 0.45);' +
    'float thin = exp(-(lat / uBandT) * (lat / uBandT)), thick = exp(-(lat / uBandK) * (lat / uBandK)), lon = 0.4 + 0.6 * exp(-ka * ka / 0.8);' +
    'float rid = 1.0 - abs(2.0 * fbm(q * 2.4 + 11.0) - 1.0), lane = smoothstep(0.62, 0.94, rid) * exp(-(lat / uLaneW) * (lat / uLaneW));' +
    'float lum = (thin * (0.35 + 1.1 * clump) + thick * 0.22 * (0.5 + n1)) * lon * (1.0 - 0.82 * lane); lum = lum / (1.0 + 0.6 * lum);' +
    'vec3 bc = mix(uBand, uBandHot, smoothstep(0.35, 0.8, lum)); bc = mix(bc, vec3(dot(bc, vec3(0.3333))), 0.35);' +
    'vec3 c = uBase * (0.85 + 0.3 * n2) + bc * lum * 0.62;' +
    'c += uCoreCol * exp(-ka * ka / 0.1) * (0.45 + 0.55 * n1) * (1.0 - 0.75 * lane) * 0.16;' +
    'for(int i = 0; i < 5; i++){ if(uCOn[i] > 0.5){ float a = acos(clamp(dot(d, uCDir[i]), -1.0, 1.0)) / uCRad[i];' +
    'float fil = smoothstep(0.38, 0.92, fbm(q * 2.8 + float(i) * 7.3)), wisp = pow(1.0 - abs(2.0 * vn(q * 6.0 + float(i)) - 1.0), 3.0);' +
    'c += uCCol[i] * exp(-a * a) * fil * (0.8 + 0.35 * wisp) * 0.8; } }' +
    'c *= uGain; c += (hs(d * 913.7) - 0.5) / 255.0; gl_FragColor = vec4(clamp(c, 0.0, 0.18), 1.0);}';

  function unitVec(arr, fallback) {
    var v = new THREE.Vector3(fallback[0], fallback[1], fallback[2]);
    if (arr && arr.length >= 3) { v.set(arr[0], arr[1], arr[2]); }
    if (v.lengthSq() < 1e-8) { v.set(fallback[0], fallback[1], fallback[2]); }
    return v.normalize();
  }

  function numOr(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }

  function bake(renderer, opts) {
    opts = opts || {};
    var T = g.CLSkyTokens;
    if (!renderer || !T || !T.COSMOS) { return null; }
    var COS = T.COSMOS;

    var size = opts.size || 512;

    var rt = new THREE.WebGLCubeRenderTarget(size, {
      format: THREE.RGBAFormat,
      type: THREE.UnsignedByteType,
      generateMipmaps: false,
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter
    });
    rt.texture.name = 'sky-cosmos-bake';

    var pole = unitVec(opts.pole, [0, 1, 0]);
    var coreDir = unitVec(opts.core, [1, 0, 0]);
    var gain = (typeof opts.gain === 'number') ? opts.gain : 1;

    var cdir = [], ccol = [], crad = [], con = [], i;
    for (i = 0; i < NCLOUD; i++) {
      cdir.push(new THREE.Vector3(0, 1, 0));
      ccol.push(new THREE.Color(0x000000));
      crad.push(0.5);
      con.push(0);
    }
    var list = opts.clouds || [];
    for (i = 0; i < NCLOUD && i < list.length; i++) {
      var cd = list[i];
      if (!cd) { continue; }
      cdir[i] = unitVec(cd.dir, [0, 1, 0]);
      crad[i] = Math.max(0.01, cd.radius || 0.5);
      ccol[i] = new THREE.Color(typeof cd.hex === 'number' ? cd.hex : 0x000000);
      con[i] = 1;
    }

    var mat = new THREE.ShaderMaterial({
      vertexShader: VS,
      fragmentShader: FS,
      depthTest: false,
      depthWrite: false,
      side: THREE.DoubleSide,
      uniforms: {
        uFace: { value: 0 },
        uSeed: { value: (typeof opts.seed === 'number') ? opts.seed : 1 },
        uGain: { value: gain },
        uPole: { value: pole },
        uCoreDir: { value: coreDir },
        uBase: { value: new THREE.Color(COS.base) },
        uBand: { value: new THREE.Color(COS.band) },
        uBandHot: { value: new THREE.Color(COS.bandHot) },
        uCoreCol: { value: new THREE.Color(COS.core) },
        uCDir: { value: cdir },
        uCCol: { value: ccol },
        uCRad: { value: crad },
        uCOn: { value: con },
        uBandT: { value: numOr(opts.bandThin, 0.09) },
        uBandK: { value: numOr(opts.bandThick, 0.32) },
        uLaneW: { value: numOr(opts.laneWidth, 0.075) },
        uBandT0: { value: 0.09 },
        uBandK0: { value: 0.32 }
      }
    });

    var geo = new THREE.PlaneGeometry(2, 2);
    var quad = new THREE.Mesh(geo, mat);
    quad.frustumCulled = false;
    var sc = new THREE.Scene();
    sc.add(quad);
    var cam = new THREE.Camera();

    var prev = renderer.getRenderTarget();
    for (var f = 0; f < 6; f++) {
      mat.uniforms.uFace.value = f;
      renderer.setRenderTarget(rt, f);
      renderer.render(sc, cam);
    }
    renderer.setRenderTarget(prev);

    var freed = false;
    return {
      texture: rt.texture,
      size: size,
      dispose: function () {
        if (freed) { return; }
        freed = true;
        sc.remove(quad);
        rt.dispose();
        geo.dispose();
        mat.dispose();
      }
    };
  }

  g.CLSkyCosmosBake = { bake: bake };
})(window);
