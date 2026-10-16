(function (g) {
  'use strict';

  var THREE = g.THREE;
  var T = g.CLSkyTokens;
  var LAYER = T.LAYER_DISC;
  var RT_PX_CAP = 1400000;
  var RT_SCALE = { high: 1, mid: 0.5, low: 0.5 };
  var UQ = { high: 1, mid: 0.6, low: 0.2 };
  var inst = null;

  var VS =
    'varying vec2 vUv;\n' +
    'void main() {\n' +
    '  vUv = uv;\n' +
    '  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );\n' +
    '}';

  var FS_BLUR =
    'uniform sampler2D tDiffuse;\n' +
    'uniform vec2 uDir;\n' +
    'varying vec2 vUv;\n' +
    'void main() {\n' +
    '  vec4 s = texture2D( tDiffuse, vUv ) * 0.2270270270;\n' +
    '  s += ( texture2D( tDiffuse, vUv + uDir ) + texture2D( tDiffuse, vUv - uDir ) ) * 0.1945945946;\n' +
    '  s += ( texture2D( tDiffuse, vUv + uDir * 2.0 ) + texture2D( tDiffuse, vUv - uDir * 2.0 ) ) * 0.1216216216;\n' +
    '  s += ( texture2D( tDiffuse, vUv + uDir * 3.0 ) + texture2D( tDiffuse, vUv - uDir * 3.0 ) ) * 0.0540540541;\n' +
    '  s += ( texture2D( tDiffuse, vUv + uDir * 4.0 ) + texture2D( tDiffuse, vUv - uDir * 4.0 ) ) * 0.0162162162;\n' +
    '  gl_FragColor = s;\n' +
    '}';

  var FS_COMP =
    'uniform sampler2D tBase;\n' +
    'uniform sampler2D tDisc;\n' +
    'uniform float uAlpha;\n' +
    'uniform float uLens;\n' +
    'uniform float uTime;\n' +
    'uniform float uAspect;\n' +
    'varying vec2 vUv;\n' +
    'void main() {\n' +
    '  vec2 c = vUv - 0.5;\n' +
    '  float asp = max( uAspect, 0.2 );\n' +
    '  vec2 cAsp = vec2( c.x * asp, c.y );\n' +
    '  float r2 = dot( cAsp, cAsp );\n' +
    '  vec3 base = texture2D( tBase, vUv ).rgb;\n' +
    '  vec3 disc = texture2D( tDisc, vUv ).rgb;\n' +
    '  /* 4K 宽荧幕微色散（Prism Split）：在物理屏幕空间保持各向同性径向分离 */\n' +
    '  vec2 abDir = c * ( r2 * 0.0038 * uLens );\n' +
    '  vec3 prism;\n' +
    '  prism.r = texture2D( tDisc, vUv + abDir ).r;\n' +
    '  prism.g = disc.g;\n' +
    '  prism.b = texture2D( tDisc, vUv - abDir ).b;\n' +
    '  /* 4K 宽荧幕横向变形镜头光斑（Anamorphic Streak）：沿横轴微步进采样高光 */\n' +
    '  float hStep = ( 0.0036 * uLens ) / asp;\n' +
    '  vec3 sL1 = texture2D( tDisc, vUv + vec2( hStep, 0.0 ) ).rgb;\n' +
    '  vec3 sR1 = texture2D( tDisc, vUv - vec2( hStep, 0.0 ) ).rgb;\n' +
    '  vec3 sL2 = texture2D( tDisc, vUv + vec2( hStep * 2.4, 0.0 ) ).rgb;\n' +
    '  vec3 sR2 = texture2D( tDisc, vUv - vec2( hStep * 2.4, 0.0 ) ).rgb;\n' +
    '  vec3 streakColor = prism * 0.38 + ( sL1 + sR1 ) * 0.22 + ( sL2 + sR2 ) * 0.09;\n' +
    '  float streakLum = dot( streakColor, vec3( 0.2126, 0.7152, 0.0722 ) );\n' +
    '  float streak = max( streakLum - 0.36, 0.0 );\n' +
    '  vec3 tint = mix( vec3( 0.72, 0.84, 1.0 ), vec3( 1.0, 0.78, 0.50 ), smoothstep( 0.0, 1.0, 0.5 + 0.5 * sin( uTime * 0.018 ) ) );\n' +
    '  float vigLens = 0.92 + 0.08 * smoothstep( 0.0, 1.0, length( cAsp ) );\n' +
    '  vec3 outCol = base + prism * uAlpha * vigLens + tint * streak * ( 0.042 * uLens );\n' +
    '  outCol = max( outCol, vec3( 0.0 ) );\n' +
    '  /* 线性直通，不级调（见文件头「级调立法」）：高光肩部、高光去饱和与 ACES 都由链末端\n' +
    '     cine pass 统一施加一次；这里再压一遍会让软路径吃双重级调。下游缓冲是 8-bit\n' +
    '     目标（合成器与 MSAA 场景目标同为 UnsignedByteType），>1 分量的截断语义与星盘 /\n' +
    '     罗盘把星盘层 inline 画进场景目标时完全一致；泛光阈值（scene-core 默认 0.85）\n' +
    '     比较的输入因此与直绘路径同语义——越过阈值的依旧是星核级高光。 */\n' +
    '  gl_FragColor = vec4( outCol, 1.0 );\n' +
    '}';

  var clamp = g.CLSkyUtil.clamp;
  function num( v, dflt ) { v = +v; return isFinite( v ) ? v : dflt; }

  function makeRT( renderer, w, h ) {
    var webgl2 = !!( renderer && renderer.capabilities && renderer.capabilities.isWebGL2 );
    return new THREE.WebGLRenderTarget( w, h, {
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat,
      type: webgl2 ? THREE.HalfFloatType : THREE.UnsignedByteType,
      depthBuffer: false,
      stencilBuffer: false
    } );
  }

  function makeEmpty( S ) {
    var e = {
      installed: false,
      tier: 'high',
      blurPx: 0,
      alpha: 1,
      frames: 0
    };
    e.setBlur = function ( px ) { e.blurPx = clamp( num( px, 0 ), 0, 14 ); };
    e.blur = function () { return e.blurPx; };
    e.setDiscAlpha = function ( a ) { e.alpha = clamp( num( a, 1 ), 0, 1 ); };
    e.discAlpha = function () { return e.alpha; };
    e.setTier = function ( t ) { e.tier = ( t === 'low' || t === 'mid' ) ? t : 'high'; };
    e.update = function () { e.frames++; };
    e.stats = function () {
      return {
        installed: false,
        mode: e.blurPx >= 0.35 ? 'soft' : 'sharp',
        blur: e.blurPx,
        alpha: e.alpha,
        passIndex: -1,
        rt: [ 0, 0 ],
        layerOnCamera: !!( S && S.camera && ( S.camera.layers.mask & ( 1 << LAYER ) ) !== 0 ),
        frames: e.frames
      };
    };
    e.dispose = function () { if ( inst === e ) inst = null; };
    return e;
  }

  function makeFull( S, core, composer ) {
    var self = {
      installed: true,
      tier: 'high',
      blurPx: 0,
      alpha: 1,
      frames: 0,
      time: 0,
      sizeW: 2,
      sizeH: 2,
      rtW: 0,
      rtH: 0,
      rtScaleEff: 1,
      rtA: null,
      rtB: null,
      renderer: S.renderer || null,
      v2: new THREE.Vector2(),
      tmpColor: new THREE.Color(),
      tmpV4: new THREE.Vector4()
    };

    var blurMat = new THREE.ShaderMaterial( {
      uniforms: { tDiffuse: { value: null }, uDir: { value: new THREE.Vector2() } },
      vertexShader: VS,
      fragmentShader: FS_BLUR,
      depthTest: false,
      depthWrite: false
    } );

    var compMat = new THREE.ShaderMaterial( {
      uniforms: {
        tBase: { value: null },
        tDisc: { value: null },
        uAlpha: { value: 1 },
        uLens: { value: 0 },
        uTime: { value: 0 },
        uAspect: { value: 1.7778 }
      },
      vertexShader: VS,
      fragmentShader: FS_COMP,
      depthTest: false,
      depthWrite: false
    } );

    var quadBlur = new THREE.FullScreenQuad( blurMat );
    var quadComp = new THREE.FullScreenQuad( compMat );

    function ensureRT() {
      var k = RT_SCALE[ self.tier ] || 1;
      var w = Math.max( 2, Math.round( self.sizeW * k ) );
      var h = Math.max( 2, Math.round( self.sizeH * k ) );
      if ( w * h > RT_PX_CAP ) {
        var s = Math.sqrt( RT_PX_CAP / ( w * h ) );
        w = Math.max( 2, Math.floor( w * s * 0.5 ) * 2 );
        h = Math.max( 2, Math.floor( h * s * 0.5 ) * 2 );
      }
      if ( !self.rtA ) {
        self.rtA = makeRT( self.renderer, w, h );
        self.rtB = makeRT( self.renderer, w, h );
      } else {
        self.rtA.setSize( w, h );
        self.rtB.setSize( w, h );
      }
      self.rtW = w;
      self.rtH = h;
      self.rtScaleEff = w / self.sizeW;
      if ( self.sizeH > 0 ) {
        compMat.uniforms.uAspect.value = self.sizeW / self.sizeH;
      }
    }

    function draw( renderer, mat, target ) {
      renderer.setRenderTarget( target );
      quadBlur._mesh.material = mat;
      quadBlur.render( renderer );
    }

    var discPass = {
      enabled: false,
      needsSwap: true,
      clear: false,
      renderToScreen: false,
      setSize: function ( w, h ) {
        self.sizeW = Math.max( 2, w | 0 );
        self.sizeH = Math.max( 2, h | 0 );
        ensureRT();
      },
      render: function ( renderer, writeBuffer, readBuffer ) {
        if ( !self.rtA || !S.scene ) return;
        self.renderer = renderer;
        var prevTarget = renderer.getRenderTarget();
        var prevAutoClear = renderer.autoClear;
        renderer.getClearColor( self.tmpColor );
        var prevAlpha = renderer.getClearAlpha();
        renderer.getViewport( self.tmpV4 );
        var mask = S.camera.layers.mask;

        S.camera.layers.set( LAYER );
        renderer.autoClear = false;
        renderer.setRenderTarget( self.rtA );
        renderer.setClearColor( 0x000000, 0 );
        renderer.clear( true, true, false );
        renderer.render( S.scene, S.camera );
        S.camera.layers.mask = mask;

        var dpr = renderer.getPixelRatio ? renderer.getPixelRatio() : 1;
        var step = self.blurPx * dpr * 0.25 * self.rtScaleEff;

        blurMat.uniforms.tDiffuse.value = self.rtA.texture;
        blurMat.uniforms.uDir.value.set( step / self.rtW, 0 );
        draw( renderer, blurMat, self.rtB );

        blurMat.uniforms.tDiffuse.value = self.rtB.texture;
        blurMat.uniforms.uDir.value.set( 0, step / self.rtH );
        draw( renderer, blurMat, self.rtA );

        compMat.uniforms.tBase.value = readBuffer.texture;
        compMat.uniforms.tDisc.value = self.rtA.texture;
        compMat.uniforms.uAlpha.value = self.alpha;
        compMat.uniforms.uLens.value = self.blurPx >= 0.35 ? Math.min(1, self.blurPx / 8) : 0;
        compMat.uniforms.uTime.value = self.time;
        if ( self.sizeH > 0 ) {
          compMat.uniforms.uAspect.value = self.sizeW / self.sizeH;
        }
        renderer.setRenderTarget( this.renderToScreen ? null : writeBuffer );
        quadComp.render( renderer );

        renderer.setRenderTarget( prevTarget );
        renderer.setClearColor( self.tmpColor, prevAlpha );
        renderer.setViewport( self.tmpV4 );
        renderer.autoClear = prevAutoClear;
      }
    };

    function setBlur( px ) { self.blurPx = clamp( num( px, 0 ), 0, 14 ); }
    function setDiscAlpha( a ) { self.alpha = clamp( num( a, 1 ), 0, 1 ); }

    function setTier( t ) {
      self.tier = ( t === 'low' || t === 'mid' ) ? t : 'high';
      ensureRT();
    }

    function update( dt, tAnim ) {
      self.frames++;
      var reducedMotion = T.reduced();
      if ( !reducedMotion ) {
        self.time = ( typeof tAnim === 'number' && isFinite( tAnim ) ) ? tAnim : self.time + num( dt, 0 );
      }

      if ( self.blurPx >= 0.35 ) {
        S.camera.layers.disable( LAYER );
        discPass.enabled = true;
      } else {
        S.camera.layers.enable( LAYER );
        discPass.enabled = false;
      }

      var u = ( core && core.bgMat && core.bgMat.uniforms ) || null;
      if ( u ) {
        if ( u.uTime ) u.uTime.value = self.time;
        if ( u.uQ ) u.uQ.value = ( UQ[ self.tier ] !== undefined ) ? UQ[ self.tier ] : 1;
        var r = self.renderer;
        if ( r && r.getDrawingBufferSize ) {
          r.getDrawingBufferSize( self.v2 );
          if ( self.v2.x > 0 && self.v2.y > 0 && u.uRes && u.uRes.value && u.uRes.value.set ) {
            var dpr = r.getPixelRatio ? r.getPixelRatio() : 1;
            u.uRes.value.set( self.v2.x / dpr, self.v2.y / dpr );
          }
        }
        if ( u.uDrift && u.uDrift.value && u.uDrift.value.set ) {
          u.uDrift.value.set(
            Math.sin( self.time * 0.0021 ) * 0.012,
            Math.cos( self.time * 0.0017 ) * 0.009
          );
        }
      }

      var passes = composer.passes || [];
      for ( var i = 0; i < passes.length; i++ ) {
        var pu = passes[ i ] && passes[ i ].uniforms;
        if ( pu && pu.uDof && pu.uTime ) pu.uTime.value = self.time;
      }
    }

    function stats() {
      var idx = -1;
      var passes = composer.passes || [];
      for ( var i = 0; i < passes.length; i++ ) {
        if ( passes[ i ] === discPass ) { idx = i; break; }
      }
      return {
        installed: true,
        mode: self.blurPx >= 0.35 ? 'soft' : 'sharp',
        blur: self.blurPx,
        alpha: self.alpha,
        passIndex: idx,
        rt: [ self.rtW, self.rtH ],
        layerOnCamera: ( S.camera.layers.mask & ( 1 << LAYER ) ) !== 0,
        frames: self.frames
      };
    }

    var api = {
      setBlur: setBlur,
      blur: function () { return self.blurPx; },
      setDiscAlpha: setDiscAlpha,
      discAlpha: function () { return self.alpha; },
      setTier: setTier,
      update: update,
      stats: stats,
      dispose: function () {
        var passes = composer.passes || [];
        var i = passes.indexOf( discPass );
        if ( i >= 0 ) passes.splice( i, 1 );
        discPass.enabled = false;
        S.camera.layers.enable( LAYER );
        if ( self.rtA ) { self.rtA.dispose(); self.rtA = null; }
        if ( self.rtB ) { self.rtB.dispose(); self.rtB = null; }
        blurMat.uniforms.tDiffuse.value = null;
        compMat.uniforms.tBase.value = null;
        compMat.uniforms.tDisc.value = null;
        blurMat.dispose();
        compMat.dispose();
        if ( quadBlur && typeof quadBlur.dispose === 'function' ) quadBlur.dispose();
        if ( quadComp && typeof quadComp.dispose === 'function' ) quadComp.dispose();
        if ( inst === api ) inst = null;
      }
    };

    composer.insertPass( discPass, 1 );
    if ( S.renderer && S.renderer.getDrawingBufferSize ) {
      S.renderer.getDrawingBufferSize( self.v2 );
      discPass.setSize( self.v2.x, self.v2.y );
    } else {
      ensureRT();
    }
    return api;
  }

  g.CLSkyPost = {
    install: function ( S ) {
      if ( inst ) return inst;
      var core = S.core && S.core();
      var composer = core && core.getComposer && core.getComposer();
      if ( !composer || !composer.passes || !S.camera ) {
        inst = makeEmpty( S );
        return inst;
      }
      try {
        inst = makeFull( S, core, composer );
      } catch ( err ) {
        if ( g.console && g.console.warn ) g.console.warn( '[sky-post] install failed', err );
        inst = makeEmpty( S );
      }
      return inst;
    }
  };
})( window );
