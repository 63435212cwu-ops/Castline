(function (global) {
  'use strict';

  var CLTreeShapeConfig = {
    version: '1.0.0',

    TRUNK_N: 72,
    FREE: 0.18,
    AT_TOP: 0.74,
    TIP_LO: 0.42,
    TIP_HI: 0.92,
    TIP_RISE_MAX: 0.26,

    curvatureTension: 0.042,
    tensionFrequency: 1.85,
    nodalBurls: true,
    burlRadiusScale: 1.28,
    burlFalloff: 0.022,

    ORDER1_K: 0.52,
    ORDER2_K: 0.52,
    filamentDensityMult: 3.0,
    swayLinkage: true,

    audit: function () {
      return {
        name: 'tree-shape.config',
        version: this.version,
        curvatureTension: this.curvatureTension,
        nodalBurls: this.nodalBurls,
        filamentDensityMult: this.filamentDensityMult
      };
    }
  };

  global.CLTreeShapeConfig = CLTreeShapeConfig;
})(typeof window !== 'undefined' ? window : this);
