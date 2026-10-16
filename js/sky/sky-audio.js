(function (g) {
  'use strict';

  var STORAGE_MUTED_KEY = 'cl_sky_audio_muted';
  var STORAGE_VOL_KEY = 'cl_sky_audio_volume';

  var AudioContextClass = g.AudioContext || g.webkitAudioContext;

  function AudioCinemaSynthesizer() {
    this.ctx = null;
    this.masterGain = null;
    this.compressor = null;
    this.unlocked = false;
    this.isMuted = false;
    this.volume = 0.72;

    this.drone = null;
    this.warpEngine = null;
    this.crystalEngine = null;
    this.hapticEngine = null;

    this.btnEl = null;
    this.eqBars = [];

    this._readSettings();
    this._bindGestureUnlock();
    this._bindSystemEvents();
    this._bindKeyboardShortcut();
  }

  AudioCinemaSynthesizer.prototype._readSettings = function () {
    try {
      var savedMuted = localStorage.getItem(STORAGE_MUTED_KEY);
      if (savedMuted !== null) {
        this.isMuted = (savedMuted === 'true');
      }
      var savedVol = localStorage.getItem(STORAGE_VOL_KEY);
      if (savedVol !== null) {
        var v = parseFloat(savedVol);
        if (!isNaN(v) && v >= 0 && v <= 1) this.volume = v;
      }
    } catch (e) {
    }
  };

  AudioCinemaSynthesizer.prototype.ensureContext = function () {
    if (!AudioContextClass) return null;
    if (!this.ctx) {
      try {
        var options = { latencyHint: 'interactive' };
        this.ctx = new AudioContextClass(options);

        this.compressor = this.ctx.createDynamicsCompressor();
        this.compressor.threshold.setValueAtTime(-14, this.ctx.currentTime);
        this.compressor.knee.setValueAtTime(8, this.ctx.currentTime);
        this.compressor.ratio.setValueAtTime(3.2, this.ctx.currentTime);
        this.compressor.attack.setValueAtTime(0.003, this.ctx.currentTime);
        this.compressor.release.setValueAtTime(0.24, this.ctx.currentTime);

        this.masterGain = this.ctx.createGain();
        var initialVol = this.isMuted ? 0.0001 : this.volume;
        this.masterGain.gain.setValueAtTime(initialVol, this.ctx.currentTime);

        this.masterGain.connect(this.compressor);
        this.compressor.connect(this.ctx.destination);

        this.drone = new SubBassDrone(this.ctx, this.masterGain);
        this.warpEngine = new GravitationalWarp(this.ctx, this.masterGain);
        this.crystalEngine = new CrystalResonance(this.ctx, this.masterGain);
        this.hapticEngine = new HapticClicks(this.ctx, this.masterGain);

        if (!this.isMuted && this.ctx.state === 'running') {
          this.drone.start();
        }
      } catch (err) {
        console.warn('[SkyAudio] AudioContext initialization deferred:', err);
        return null;
      }
    }

    if (this.ctx && this.ctx.state === 'suspended') {
      var self = this;
      this.ctx.resume().then(function () {
        self.unlocked = true;
        if (!self.isMuted && self.drone && !self.drone.isRunning) {
          self.drone.start();
        }
        self._updateHudState();
      }).catch(function () {});
    } else if (this.ctx && this.ctx.state === 'running') {
      this.unlocked = true;
    }

    return this.ctx;
  };

  AudioCinemaSynthesizer.prototype._bindGestureUnlock = function () {
    var self = this;
    var unlockHandler = function () {
      self.ensureContext();
      if (self.ctx && self.ctx.state === 'running') {
        ['pointerdown', 'keydown', 'touchstart', 'click', 'wheel'].forEach(function (evtName) {
          window.removeEventListener(evtName, unlockHandler, true);
        });
      }
    };

    ['pointerdown', 'keydown', 'touchstart', 'click', 'wheel'].forEach(function (evtName) {
      window.addEventListener(evtName, unlockHandler, { capture: true, passive: true });
    });
    var pre = function () { if (!self.ctx) self.ensureContext(); };
    setTimeout(function () {
      if (self.ctx) return;
      if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(pre, { timeout: 4000 }); else pre();
    }, 3000);
  };

  AudioCinemaSynthesizer.prototype._bindKeyboardShortcut = function () {
    var self = this;
    window.addEventListener('keydown', function (e) {
      var tag = e.target && e.target.tagName ? e.target.tagName.toUpperCase() : '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable)) {
        return;
      }
      if (e.key === 'm' || e.key === 'M') {
        if (!e.ctrlKey && !e.metaKey && !e.altKey) {
          e.preventDefault();
          self.toggleMute();
        }
      }
    }, false);
  };

  AudioCinemaSynthesizer.prototype._bindSystemEvents = function () {
    var self = this;

    document.addEventListener('cl:sky-plot', function (e) {
      self.ensureContext();
      var isOn = e && e.detail && e.detail.on;
      self.warp(isOn ? 1.0 : 0.8, isOn ? 'inward' : 'outward');
    });

    document.addEventListener('cl:sky-compass', function (e) {
      self.ensureContext();
      var charName = (e && e.detail && e.detail.name) || '';
      self.crystal(432, 1.0);
      self.warp(0.65, 'focus');
    });

    document.addEventListener('cl:plot-bead', function () {
      self.ensureContext();
      self.click('fine', 3400);
    });
    document.addEventListener('cl:plot-thread', function () {
      self.ensureContext();
      self.click('subtle', 2900);
    });

    document.addEventListener('cl:graph-ready', function () {
      self.ensureContext();
      if (!self.isMuted && self.drone && !self.drone.isRunning) {
        self.drone.start();
      }
    });

    var mountNow = function () { self.mountHud(); };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', mountNow);
    } else {
      mountNow();
    }

    if (typeof MutationObserver !== 'undefined') {
      var domObserver = new MutationObserver(function () {
        var actions = document.querySelector('.sky-actions');
        if (actions && (!self.btnEl || self.btnEl.parentNode !== actions)) {
          self.mountHud();
        }
      });
      domObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });
    }
  };


  AudioCinemaSynthesizer.prototype.warp = function (intensity, direction) {
    if (this.isMuted) return;
    this.ensureContext();
    if (this.warpEngine) {
      this.warpEngine.trigger(intensity || 1.0, direction || 'inward');
    }
  };

  AudioCinemaSynthesizer.prototype.crystal = function (baseFreq, resonance) {
    if (this.isMuted) return;
    this.ensureContext();
    if (this.crystalEngine) {
      this.crystalEngine.strike(baseFreq || 432, resonance || 1.0);
    }
  };

  AudioCinemaSynthesizer.prototype.click = function (variant, pitch) {
    if (this.isMuted) return;
    this.ensureContext();
    if (this.hapticEngine) {
      this.hapticEngine.trigger(variant || 'standard', pitch);
    }
  };

  AudioCinemaSynthesizer.prototype.toggleMute = function () {
    this.setMuted(!this.isMuted);
  };

  AudioCinemaSynthesizer.prototype.setMuted = function (muted) {
    this.isMuted = !!muted;
    try {
      localStorage.setItem(STORAGE_MUTED_KEY, String(this.isMuted));
    } catch (e) {}

    if (this.ctx && this.masterGain) {
      var now = this.ctx.currentTime;
      this.masterGain.gain.cancelScheduledValues(now);
      if (this.isMuted) {
        this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now);
        this.masterGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12);
        if (this.drone && this.drone.isRunning) {
          this.drone.pause();
        }
      } else {
        this.ensureContext();
        var targetVol = Math.max(0.01, this.volume);
        this.masterGain.gain.setValueAtTime(0.0001, now);
        this.masterGain.gain.exponentialRampToValueAtTime(targetVol, now + 0.25);
        if (this.drone) {
          this.drone.start();
        }
      }
    } else if (!this.isMuted) {
      this.ensureContext();
    }

    this._updateHudState();
  };

  AudioCinemaSynthesizer.prototype.setVolume = function (vol) {
    var v = Math.max(0, Math.min(1, vol));
    this.volume = v;
    try {
      localStorage.setItem(STORAGE_VOL_KEY, String(v));
    } catch (e) {}

    if (this.ctx && this.masterGain && !this.isMuted) {
      var now = this.ctx.currentTime;
      this.masterGain.gain.cancelScheduledValues(now);
      this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, now);
      this.masterGain.gain.linearRampToValueAtTime(Math.max(0.0001, v), now + 0.05);
    }
  };

  AudioCinemaSynthesizer.prototype.getState = function () {
    return {
      isMuted: this.isMuted,
      volume: this.volume,
      unlocked: this.unlocked,
      contextState: this.ctx ? this.ctx.state : 'uninitialized',
      droneRunning: this.drone ? this.drone.isRunning : false
    };
  };

  AudioCinemaSynthesizer.prototype.mountHud = function () {
    var actionsContainer = document.querySelector('.sky-actions');
    var skyTools = document.getElementById('skyTools');

    if (this.btnEl && document.body.contains(this.btnEl)) {
      if (actionsContainer && this.btnEl.parentNode !== actionsContainer) {
        this.btnEl.classList.remove('sky-audio-floating');
        var reAnchor = document.getElementById('skyLabBtn') || skyTools;
        if (reAnchor && reAnchor.parentNode === actionsContainer) {
          actionsContainer.insertBefore(this.btnEl, reAnchor);
        } else {
          actionsContainer.appendChild(this.btnEl);
        }
      }
      return;
    }

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'skyAudioToggle';
    btn.className = 'sky-icon sky-audio-toggle' + (this.isMuted ? ' is-muted' : '');
    btn.setAttribute('aria-pressed', String(!this.isMuted));
    btn.setAttribute('title', '深空声场 [快捷键 M]（' + (this.isMuted ? '已静音' : '播放中') + '）');

    btn.innerHTML =
      '<span class="sky-audio-glyph" aria-hidden="true">' +
        '<svg viewBox="0 0 24 24" class="sky-audio-icon">' +
          '<path class="gl-base" d="M11 5L6 9H2v6h4l5 4V5z"/>' +
          '<path class="gl-wave gl-wave-1" d="M15.54 8.46a5 5 0 0 1 0 7.07"/>' +
          '<path class="gl-wave gl-wave-2" d="M19.07 4.93a10 10 0 0 1 0 14.14"/>' +
          '<line class="gl-slash" x1="2" y1="2" x2="22" y2="22"/>' +
        '</svg>' +
      '</span>' +
      '<span class="sky-audio-eq" aria-hidden="true">' +
        '<i class="sky-eq-bar b1"></i>' +
        '<i class="sky-eq-bar b2"></i>' +
        '<i class="sky-eq-bar b3"></i>' +
        '<i class="sky-eq-bar b4"></i>' +
      '</span>' +
      '<span class="sky-audio-label">声场</span>';

    var self = this;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      self.ensureContext();
      self.toggleMute();
    });

    if (actionsContainer) {
      var anchor = document.getElementById('skyLabBtn') || skyTools;
      if (anchor && anchor.parentNode === actionsContainer) {
        actionsContainer.insertBefore(btn, anchor);
      } else {
        actionsContainer.appendChild(btn);
      }
    } else {
      var fallbackHost = document.getElementById('stage') || document.body;
      btn.classList.add('sky-audio-floating');
      fallbackHost.appendChild(btn);

      var checkCount = 0;
      var relocateTimer = setInterval(function () {
        var actions = document.querySelector('.sky-actions');
        if (actions) {
          clearInterval(relocateTimer);
          self.mountHud();
        } else if (++checkCount > 30) {
          clearInterval(relocateTimer);
        }
      }, 300);
    }

    this.btnEl = btn;
    this.eqBars = btn.querySelectorAll('.sky-eq-bar');
    this._updateHudState();

    this._bindTimelineScrubClicks();
  };

  AudioCinemaSynthesizer.prototype._bindTimelineScrubClicks = function () {
    var scrub = document.getElementById('skyScrub');
    if (!scrub) {
      var self = this;
      var retries = 0;
      var timer = setInterval(function () {
        scrub = document.getElementById('skyScrub');
        if (scrub || ++retries > 20) {
          clearInterval(timer);
          if (scrub) self._attachScrubEvents(scrub);
        }
      }, 500);
      return;
    }
    this._attachScrubEvents(scrub);
  };

  AudioCinemaSynthesizer.prototype._attachScrubEvents = function (scrub) {
    if (scrub._audioBound) return;
    scrub._audioBound = true;
    var self = this;
    var lastVal = scrub.value;

    scrub.addEventListener('input', function () {
      var curVal = scrub.value;
      if (curVal !== lastVal) {
        lastVal = curVal;
        self.click('standard', 2800 + ((+curVal % 12) * 40));
      }
    }, { passive: true });

    var playBtn = document.getElementById('skyPlay');
    if (playBtn && !playBtn._audioBound) {
      playBtn._audioBound = true;
      playBtn.addEventListener('click', function () {
        self.click('fine', 3600);
      });
    }
  };

  AudioCinemaSynthesizer.prototype._updateHudState = function () {
    if (!this.btnEl) return;
    if (this.isMuted) {
      this.btnEl.classList.add('is-muted');
      this.btnEl.classList.remove('is-active');
      this.btnEl.setAttribute('aria-pressed', 'false');
      this.btnEl.setAttribute('title', '深空声场 [快捷键 M]（已静音）');
    } else {
      this.btnEl.classList.remove('is-muted');
      this.btnEl.classList.add('is-active');
      this.btnEl.setAttribute('aria-pressed', 'true');
      this.btnEl.setAttribute('title', '深空声场 [快捷键 M]（播放中）');
    }
  };

  function SubBassDrone(ctx, destination) {
    this.ctx = ctx;
    this.dest = destination;
    this.isRunning = false;

    this.droneGain = null;
    this.filter = null;
    this.lfo = null;
    this.lfoGain = null;
    this.osc1 = null;
    this.osc2 = null;
    this.osc3 = null;
    this.osc4 = null;
    this.noiseNode = null;
  }

  SubBassDrone.prototype.start = function () {
    if (this.isRunning || !this.ctx) return;
    this.isRunning = true;

    var ctx = this.ctx;
    var now = ctx.currentTime;

    this.droneGain = ctx.createGain();
    this.droneGain.gain.setValueAtTime(0.0001, now);
    this.droneGain.gain.exponentialRampToValueAtTime(0.42, now + 3.0);

    this.filter = ctx.createBiquadFilter();
    this.filter.type = 'lowpass';
    this.filter.frequency.setValueAtTime(105, now);
    this.filter.Q.setValueAtTime(2.8, now);

    this.lfo = ctx.createOscillator();
    this.lfo.type = 'sine';
    this.lfo.frequency.setValueAtTime(0.05, now);

    this.lfoGain = ctx.createGain();
    this.lfoGain.gain.setValueAtTime(48, now);

    this.lfo.connect(this.lfoGain);
    this.lfoGain.connect(this.filter.frequency);

    this.osc1 = ctx.createOscillator();
    this.osc1.type = 'sine';
    this.osc1.frequency.setValueAtTime(34.0, now);
    var panner1 = createPanner(ctx, -0.28);

    this.osc2 = ctx.createOscillator();
    this.osc2.type = 'sine';
    this.osc2.frequency.setValueAtTime(35.2, now);
    var panner2 = createPanner(ctx, 0.28);

    this.osc3 = ctx.createOscillator();
    this.osc3.type = 'triangle';
    this.osc3.frequency.setValueAtTime(68.4, now);
    var gain3 = ctx.createGain();
    gain3.gain.setValueAtTime(0.12, now);

    this.osc4 = ctx.createOscillator();
    this.osc4.type = 'sine';
    this.osc4.frequency.setValueAtTime(103.0, now);
    var gain4 = ctx.createGain();
    gain4.gain.setValueAtTime(0.045, now);

    this.noiseNode = createPinkNoiseBed(ctx, 4.0);
    var noiseFilter = ctx.createBiquadFilter();
    noiseFilter.type = 'lowpass';
    noiseFilter.frequency.setValueAtTime(80, now);
    var noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(0.028, now);

    if (this.noiseNode) {
      this.noiseNode.connect(noiseFilter);
      noiseFilter.connect(noiseGain);
      noiseGain.connect(this.filter);
    }

    this.osc1.connect(panner1);
    panner1.connect(this.filter);

    this.osc2.connect(panner2);
    panner2.connect(this.filter);

    this.osc3.connect(gain3);
    gain3.connect(this.filter);

    this.osc4.connect(gain4);
    gain4.connect(this.filter);

    this.filter.connect(this.droneGain);
    this.droneGain.connect(this.dest);

    this.lfo.start(now);
    this.osc1.start(now);
    this.osc2.start(now);
    this.osc3.start(now);
    this.osc4.start(now);
    if (this.noiseNode) this.noiseNode.start(now);
  };

  SubBassDrone.prototype.pause = function () {
    if (!this.isRunning || !this.ctx || !this.droneGain) return;
    var now = this.ctx.currentTime;
    this.droneGain.gain.cancelScheduledValues(now);
    this.droneGain.gain.setValueAtTime(this.droneGain.gain.value, now);
    this.droneGain.gain.exponentialRampToValueAtTime(0.0001, now + 1.2);
    var self = this;
    setTimeout(function () {
      self._stopImmediate();
    }, 1300);
  };

  SubBassDrone.prototype._stopImmediate = function () {
    try {
      if (this.osc1) { this.osc1.stop(); this.osc1.disconnect(); }
      if (this.osc2) { this.osc2.stop(); this.osc2.disconnect(); }
      if (this.osc3) { this.osc3.stop(); this.osc3.disconnect(); }
      if (this.osc4) { this.osc4.stop(); this.osc4.disconnect(); }
      if (this.lfo) { this.lfo.stop(); this.lfo.disconnect(); }
      if (this.noiseNode) { this.noiseNode.stop(); this.noiseNode.disconnect(); }
      if (this.droneGain) { this.droneGain.disconnect(); }
    } catch (e) {}
    this.isRunning = false;
  };

  function GravitationalWarp(ctx, destination) {
    this.ctx = ctx;
    this.dest = destination;
  }

  GravitationalWarp.prototype.trigger = function (intensity, direction) {
    var ctx = this.ctx;
    if (!ctx) return;
    var now = ctx.currentTime;
    var dur = 1.15;

    var bufferSize = Math.floor(ctx.sampleRate * dur);
    var noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    var output = noiseBuffer.getChannelData(0);
    var b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (var i = 0; i < bufferSize; i++) {
      var white = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + white * 0.0555179;
      b1 = 0.99332 * b1 + white * 0.0750759;
      b2 = 0.96900 * b2 + white * 0.1538520;
      b3 = 0.86650 * b3 + white * 0.3104856;
      b4 = 0.55000 * b4 + white * 0.5329522;
      b5 = -0.7616 * b5 - white * 0.0168980;
      output[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.09;
      b6 = white * 0.115926;
    }

    var noiseSource = ctx.createBufferSource();
    noiseSource.buffer = noiseBuffer;

    var filter1 = ctx.createBiquadFilter();
    filter1.type = 'bandpass';
    filter1.Q.setValueAtTime(4.2, now);

    var filter2 = ctx.createBiquadFilter();
    filter2.type = 'bandpass';
    filter2.Q.setValueAtTime(3.8, now);

    var startFreq = direction === 'outward' ? 1800 : 135;
    var peakFreq = direction === 'outward' ? 2400 : 2100;
    var endFreq = direction === 'outward' ? 110 : 80;

    filter1.frequency.setValueAtTime(startFreq, now);
    filter2.frequency.setValueAtTime(startFreq, now);

    filter1.frequency.exponentialRampToValueAtTime(peakFreq, now + 0.38);
    filter2.frequency.exponentialRampToValueAtTime(peakFreq, now + 0.38);

    filter1.frequency.exponentialRampToValueAtTime(endFreq, now + dur);
    filter2.frequency.exponentialRampToValueAtTime(endFreq, now + dur);

    var panner = createPanner(ctx, direction === 'outward' ? 0.6 : -0.6);
    if (panner.pan) {
      panner.pan.setValueAtTime(direction === 'outward' ? 0.6 : -0.6, now);
      panner.pan.linearRampToValueAtTime(direction === 'outward' ? -0.6 : 0.6, now + dur);
    }

    var warpGain = ctx.createGain();
    var peakGain = 0.36 * Math.max(0.2, Math.min(1.5, intensity));
    warpGain.gain.setValueAtTime(0.0001, now);
    warpGain.gain.linearRampToValueAtTime(peakGain, now + 0.04);
    warpGain.gain.exponentialRampToValueAtTime(0.0001, now + dur);

    var subOsc = ctx.createOscillator();
    subOsc.type = 'sine';
    subOsc.frequency.setValueAtTime(140, now);
    subOsc.frequency.exponentialRampToValueAtTime(28, now + 0.65);

    var subGain = ctx.createGain();
    subGain.gain.setValueAtTime(0.0001, now);
    subGain.gain.linearRampToValueAtTime(0.24 * intensity, now + 0.03);
    subGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.7);

    noiseSource.connect(filter1);
    filter1.connect(filter2);
    filter2.connect(warpGain);
    warpGain.connect(panner);
    panner.connect(this.dest);

    subOsc.connect(subGain);
    subGain.connect(this.dest);

    noiseSource.start(now);
    noiseSource.stop(now + dur);
    subOsc.start(now);
    subOsc.stop(now + 0.75);
  };

  function CrystalResonance(ctx, destination) {
    this.ctx = ctx;
    this.dest = destination;
  }

  CrystalResonance.prototype.strike = function (baseFreq, resonance) {
    var ctx = this.ctx;
    if (!ctx) return;
    var now = ctx.currentTime;
    baseFreq = baseFreq || 432;
    var decayTime = 3.4 * (resonance || 1.0);

    var harmonics = [
      [1.0, 0.32, 0.0],
      [2.0, 0.21, 2.4],
      [3.0, 0.08, -1.8],
      [4.0, 0.032, 3.1]
    ];

    var chimeMaster = ctx.createGain();
    chimeMaster.gain.setValueAtTime(0.9, now);

    var delayL = ctx.createDelay();
    delayL.delayTime.setValueAtTime(0.038, now);
    var delayR = ctx.createDelay();
    delayR.delayTime.setValueAtTime(0.052, now);

    var feedbackL = ctx.createGain();
    feedbackL.gain.setValueAtTime(0.36, now);
    var feedbackR = ctx.createGain();
    feedbackR.gain.setValueAtTime(0.34, now);

    var dampFilter = ctx.createBiquadFilter();
    dampFilter.type = 'lowpass';
    dampFilter.frequency.setValueAtTime(2800, now);

    delayL.connect(feedbackL);
    feedbackL.connect(dampFilter);
    dampFilter.connect(delayL);

    delayR.connect(feedbackR);
    feedbackR.connect(delayR);

    var pannerL = createPanner(ctx, -0.35);
    var pannerR = createPanner(ctx, 0.35);
    delayL.connect(pannerL);
    delayR.connect(pannerR);
    pannerL.connect(chimeMaster);
    pannerR.connect(chimeMaster);

    harmonics.forEach(function (h) {
      var mult = h[0];
      var relGain = h[1];
      var detuneCents = h[2];

      var osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(baseFreq * mult, now);
      if (detuneCents !== 0) {
        osc.detune.setValueAtTime(detuneCents, now);
      }

      var env = ctx.createGain();
      var harmonicDecay = decayTime / Math.pow(mult, 0.65);
      env.gain.setValueAtTime(0.0001, now);
      env.gain.linearRampToValueAtTime(relGain, now + 0.012);
      env.gain.exponentialRampToValueAtTime(0.0001, now + harmonicDecay);

      osc.connect(env);
      env.connect(chimeMaster);
      env.connect(delayL);
      env.connect(delayR);

      osc.start(now);
      osc.stop(now + harmonicDecay + 0.05);
    });

    chimeMaster.connect(this.dest);
  };

  function HapticClicks(ctx, destination) {
    this.ctx = ctx;
    this.dest = destination;
    this.lastTriggerTime = 0;
  }

  HapticClicks.prototype.trigger = function (variant, pitch) {
    var ctx = this.ctx;
    if (!ctx) return;
    var now = ctx.currentTime;

    if (now - this.lastTriggerTime < 0.026) return;
    this.lastTriggerTime = now;

    var basePitch = pitch || 2800;
    if (variant === 'fine') basePitch = 3400;
    else if (variant === 'subtle') basePitch = 2400;
    else if (variant === 'heavy') basePitch = 1800;

    var jitter = 1.0 + (Math.random() * 0.07 - 0.035);
    var finalPitch = basePitch * jitter;

    var osc = ctx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(finalPitch, now);

    var filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(finalPitch, now);
    filter.Q.setValueAtTime(6.5, now);

    var env = ctx.createGain();
    var ampJitter = 0.09 * (1.0 + (Math.random() * 0.1 - 0.05));
    env.gain.setValueAtTime(0.0001, now);
    env.gain.linearRampToValueAtTime(ampJitter, now + 0.0006);
    env.gain.exponentialRampToValueAtTime(0.00001, now + 0.0055);

    osc.connect(filter);
    filter.connect(env);
    env.connect(this.dest);

    osc.start(now);
    osc.stop(now + 0.007);
  };

  function createPanner(ctx, panVal) {
    if (ctx.createStereoPanner) {
      var p = ctx.createStereoPanner();
      p.pan.setValueAtTime(panVal, ctx.currentTime);
      return p;
    }
    var merger = ctx.createChannelMerger(2);
    var gainL = ctx.createGain();
    var gainR = ctx.createGain();
    var normPan = (panVal + 1) / 2;
    gainL.gain.setValueAtTime(Math.cos(normPan * Math.PI / 2), ctx.currentTime);
    gainR.gain.setValueAtTime(Math.sin(normPan * Math.PI / 2), ctx.currentTime);
    gainL.connect(merger, 0, 0);
    gainR.connect(merger, 0, 1);
    return {
      connect: function (dest) { merger.connect(dest); },
      pan: { setValueAtTime: function () {} }
    };
  }

  function createPinkNoiseBed(ctx, durationSeconds) {
    try {
      var bufferSize = Math.floor(ctx.sampleRate * durationSeconds);
      var buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
      var data = buffer.getChannelData(0);
      var b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
      for (var i = 0; i < bufferSize; i++) {
        var white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.08;
        b6 = white * 0.115926;
      }
      var node = ctx.createBufferSource();
      node.buffer = buffer;
      node.loop = true;
      return node;
    } catch (e) {
      return null;
    }
  }

  var instance = new AudioCinemaSynthesizer();
  g.CLSkyAudio = instance;
  g.SkyAudio = instance;

})(typeof window !== 'undefined' ? window : this);
