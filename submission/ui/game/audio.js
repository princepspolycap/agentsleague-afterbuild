// Synthesized game audio for "Your Company Is the Dungeon".
//
// Pure Web Audio API: every sound is generated from oscillators at runtime, so
// there are zero audio files, zero licensing risk, and it runs offline after a
// fresh git clone. Cues are bound to the streamed reasoning phases (thinking
// pulse during the live Foundry call, a tick per validator check, a chime on a
// passing score) so the audio narrates the agent's reasoning rather than just
// decorating the UI.
//
// Browser autoplay policy: the AudioContext can only start after a user
// gesture, so we lazily create/resume it on the first interaction.

(function () {
    "use strict";

    let ctx = null;
    let masterGain = null;
    let muted = false;
    let thinkingNodes = null; // active "thinking" loop, if any

    function ensureContext() {
        if (ctx) {
            if (ctx.state === "suspended") ctx.resume();
            return ctx;
        }
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        ctx = new AC();
        masterGain = ctx.createGain();
        masterGain.gain.value = muted ? 0 : 0.5;
        masterGain.connect(ctx.destination);
        return ctx;
    }

    // Play a single tone. freq Hz, dur seconds, type waveform, gain 0-1.
    function tone(freq, dur, type, gain, when) {
        const c = ensureContext();
        if (!c) return;
        const start = when ?? c.currentTime;
        const osc = c.createOscillator();
        const g = c.createGain();
        osc.type = type || "sine";
        osc.frequency.setValueAtTime(freq, start);
        // Soft attack + exponential release to avoid clicks.
        g.gain.setValueAtTime(0.0001, start);
        g.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain ?? 0.2), start + 0.012);
        g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
        osc.connect(g);
        g.connect(masterGain);
        osc.start(start);
        osc.stop(start + dur + 0.02);
    }

    function arpeggio(freqs, step, type, gain) {
        const c = ensureContext();
        if (!c) return;
        freqs.forEach((f, i) => tone(f, step * 1.6, type || "triangle", gain ?? 0.18, c.currentTime + i * step));
    }

    const DungeonAudio = {
        // Called from a user gesture (e.g. launch click) to unlock audio.
        unlock() {
            ensureContext();
        },

        isMuted() {
            return muted;
        },

        setMuted(value) {
            muted = !!value;
            if (masterGain && ctx) {
                masterGain.gain.setTargetAtTime(muted ? 0 : 0.5, ctx.currentTime, 0.02);
            }
            return muted;
        },

        toggleMute() {
            return this.setMuted(!muted);
        },

        // A low, slow pulse loop while an agent is reasoning (the live call).
        thinkingStart() {
            const c = ensureContext();
            if (!c || thinkingNodes) return;
            const osc = c.createOscillator();
            const lfo = c.createOscillator();
            const lfoGain = c.createGain();
            const g = c.createGain();
            osc.type = "sine";
            osc.frequency.value = 110; // low hum
            lfo.type = "sine";
            lfo.frequency.value = 2.2;  // pulse rate
            lfoGain.gain.value = 0.04;
            g.gain.value = 0.0001;
            lfo.connect(lfoGain);
            lfoGain.connect(g.gain);
            osc.connect(g);
            g.connect(masterGain);
            g.gain.setTargetAtTime(0.05, c.currentTime, 0.1);
            osc.start();
            lfo.start();
            thinkingNodes = { osc, lfo, g };
        },

        thinkingStop() {
            const c = ensureContext();
            if (!c || !thinkingNodes) return;
            const { osc, lfo, g } = thinkingNodes;
            thinkingNodes = null;
            g.gain.setTargetAtTime(0.0001, c.currentTime, 0.08);
            const stopAt = c.currentTime + 0.25;
            try { osc.stop(stopAt); lfo.stop(stopAt); } catch (_) {}
        },

        // Short tick when a deterministic validator check lands.
        tick(passed) {
            tone(passed === false ? 320 : 880, 0.07, "square", 0.10);
        },

        // Rising chime when the artifact passes scoring.
        chime() {
            arpeggio([660, 880, 1175], 0.08, "triangle", 0.16);
        },

        // Success cue on artifact approval.
        approve() {
            arpeggio([523, 659, 784], 0.07, "triangle", 0.18);
        },

        // Bright fanfare when the founder levels up.
        levelUp() {
            arpeggio([523, 659, 784, 1046], 0.09, "sawtooth", 0.16);
        },

        // Soft descending buzz on rejection.
        reject() {
            tone(220, 0.16, "sawtooth", 0.16);
            tone(165, 0.22, "sawtooth", 0.14, (ctx ? ctx.currentTime : 0) + 0.1);
        },

        // Triumphant run when the whole quest line completes.
        complete() {
            arpeggio([523, 659, 784, 1046, 1318], 0.11, "triangle", 0.18);
        },
    };

    window.DungeonAudio = DungeonAudio;
})();
