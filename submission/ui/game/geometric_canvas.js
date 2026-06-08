(function () {
    const API_BASE = "/api";
    const WORLD_W = 960;
    const WORLD_H = 620;
    const CORRIDOR_Y = 500;
    const PLAYER_SPEED = 180;

    const rooms = [
        {
            agent: "strategist",
            name: "Soren",
            role: "Strategist",
            title: "Blueprint Room",
            x: 34,
            y: 48,
            w: 276,
            h: 384,
            color: 0x38bdf8,
            fill: 0x0c2236,
            approachX: 172,
            approachY: 302,
            doorX: 172,
        },
        {
            agent: "designer",
            name: "Dahlia",
            role: "Designer",
            title: "UX Lab",
            x: 342,
            y: 48,
            w: 276,
            h: 384,
            color: 0xc084fc,
            fill: 0x21163d,
            approachX: 480,
            approachY: 302,
            doorX: 480,
        },
        {
            agent: "marketer",
            name: "Maddox",
            role: "Marketer",
            title: "Outreach Core",
            x: 650,
            y: 48,
            w: 276,
            h: 384,
            color: 0xfde047,
            fill: 0x2b2410,
            approachX: 788,
            approachY: 302,
            doorX: 788,
        },
    ];

    const ui = {
        company: document.getElementById("geo-company"),
        pitch: document.getElementById("geo-pitch"),
        start: document.getElementById("geo-start"),
        autoplay: document.getElementById("geo-autoplay"),
        run: document.getElementById("geo-run"),
        approve: document.getElementById("geo-approve"),
        reject: document.getElementById("geo-reject"),
        reset: document.getElementById("geo-reset"),
        status: document.getElementById("geo-status"),
        quest: document.getElementById("geo-quest"),
        artifact: document.getElementById("geo-artifact"),
        log: document.getElementById("geo-log"),
    };

    let game;
    let sceneRef;
    let cursors;
    let wasd;
    let player;
    let routeLine;
    let routeMarker;
    let interactionPrompt;
    let thinkingTimer;
    let isBusy = false;
    let isAutoplay = false;
    let currentState = null;
    let roomViews = {};
    let agentViews = {};
    let graphNodes = [];
    let audioCtx = null;
    let ambientNodes = null;
    let thinkingNodes = null;

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[char]));
    }

    async function api(path, options = {}) {
        const res = await fetch(`${API_BASE}${path}`, options);
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text || `${path} failed`);
        }
        return res.json();
    }

    function getQuest() {
        return currentState?.active_quest || null;
    }

    function getActiveStep() {
        const quest = getQuest();
        if (!quest || quest.current_step_index >= quest.steps.length) return null;
        return quest.steps[quest.current_step_index];
    }

    function getRoom(agent) {
        return rooms.find((room) => room.agent === agent) || null;
    }

    function getActiveRoom() {
        return getRoom(getActiveStep()?.assigned_to);
    }

    function log(message, color = "text-slate-400") {
        const row = document.createElement("div");
        row.className = `${color} mb-1`;
        row.textContent = message;
        ui.log.appendChild(row);
        ui.log.scrollTop = ui.log.scrollHeight;
    }

    function ensureAudio() {
        if (audioCtx) {
            if (audioCtx.state === "suspended") audioCtx.resume();
            return audioCtx;
        }
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return null;
        audioCtx = new Ctx();
        return audioCtx;
    }

    function playTone(freq, delay, duration, type = "sine", gainValue = 0.045) {
        const ctx = ensureAudio();
        if (!ctx) return;
        const start = ctx.currentTime + delay;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(gainValue, start + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        osc.connect(gain).connect(ctx.destination);
        osc.start(start);
        osc.stop(start + duration + 0.03);
    }

    function playCue(cue) {
        ensureAudio();
        if (cue === "activate") {
            playTone(392, 0, 0.12, "triangle", 0.035);
            playTone(523.25, 0.09, 0.16, "triangle", 0.04);
        } else if (cue === "approve") {
            playTone(523.25, 0, 0.1, "sine", 0.045);
            playTone(659.25, 0.08, 0.1, "sine", 0.045);
            playTone(783.99, 0.16, 0.18, "sine", 0.05);
        } else if (cue === "reject") {
            playTone(220, 0, 0.18, "sawtooth", 0.035);
            playTone(164.81, 0.12, 0.22, "sawtooth", 0.03);
        } else if (cue === "complete") {
            [392, 493.88, 587.33, 783.99].forEach((freq, idx) => playTone(freq, idx * 0.08, 0.16, "triangle", 0.04));
        } else if (cue === "reveal") {
            playTone(880, 0, 0.08, "sine", 0.025);
            playTone(1174.66, 0.07, 0.14, "sine", 0.025);
        }
    }

    function startAmbient() {
        const ctx = ensureAudio();
        if (!ctx || ambientNodes) return;
        const gain = ctx.createGain();
        gain.gain.value = 0.012;
        const low = ctx.createOscillator();
        const high = ctx.createOscillator();
        low.type = "sine";
        high.type = "triangle";
        low.frequency.value = 82.41;
        high.frequency.value = 164.81;
        low.connect(gain);
        high.connect(gain);
        gain.connect(ctx.destination);
        low.start();
        high.start();
        ambientNodes = { low, high, gain };
    }

    function startThinkingAudio() {
        const ctx = ensureAudio();
        if (!ctx || thinkingNodes) return;
        const gain = ctx.createGain();
        gain.gain.value = 0.018;
        const osc = ctx.createOscillator();
        osc.type = "square";
        osc.frequency.value = 220;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        const interval = setInterval(() => {
            if (!thinkingNodes) return;
            const choices = [220, 246.94, 293.66, 329.63];
            osc.frequency.setValueAtTime(choices[Math.floor(Math.random() * choices.length)], ctx.currentTime);
        }, 140);
        thinkingNodes = { osc, gain, interval };
    }

    function stopThinkingAudio() {
        if (!thinkingNodes) return;
        clearInterval(thinkingNodes.interval);
        thinkingNodes.gain.gain.setTargetAtTime(0.0001, audioCtx.currentTime, 0.04);
        window.setTimeout(() => {
            try { thinkingNodes.osc.stop(); } catch (_) {}
            thinkingNodes = null;
        }, 120);
    }

    function createGame() {
        game = new Phaser.Game({
            type: Phaser.AUTO,
            parent: "geometric-canvas",
            width: WORLD_W,
            height: WORLD_H,
            backgroundColor: "#04070f",
            scale: {
                mode: Phaser.Scale.FIT,
                autoCenter: Phaser.Scale.CENTER_BOTH,
            },
            physics: {
                default: "arcade",
                arcade: { gravity: { y: 0 }, debug: false },
            },
            scene: {
                create,
                update,
            },
        });
    }

    function create() {
        sceneRef = this;
        drawBackground(this);
        rooms.forEach((room, idx) => {
            roomViews[room.agent] = drawRoom(this, room, idx);
            agentViews[room.agent] = drawAgent(this, room);
        });
        player = drawPlayer(this, rooms[0].doorX, CORRIDOR_Y + 44);
        this.physics.world.enable(player);
        player.body.setCollideWorldBounds(true);
        cursors = this.input.keyboard.createCursorKeys();
        wasd = this.input.keyboard.addKeys({
            up: Phaser.Input.Keyboard.KeyCodes.W,
            left: Phaser.Input.Keyboard.KeyCodes.A,
            down: Phaser.Input.Keyboard.KeyCodes.S,
            right: Phaser.Input.Keyboard.KeyCodes.D,
            interact: Phaser.Input.Keyboard.KeyCodes.E,
        });
        this.input.keyboard.on("keydown-E", () => runActiveAgent());
        routeLine = this.add.graphics().setDepth(40);
        renderWorld();
    }

    function update() {
        if (!player) return;
        player.body.setVelocity(0);
        let dx = 0;
        let dy = 0;
        if (cursors.left.isDown || wasd.left.isDown) dx = -1;
        else if (cursors.right.isDown || wasd.right.isDown) dx = 1;
        if (cursors.up.isDown || wasd.up.isDown) dy = -1;
        else if (cursors.down.isDown || wasd.down.isDown) dy = 1;
        player.body.setVelocity(dx * PLAYER_SPEED, dy * PLAYER_SPEED);
        if (dx && dy) player.body.velocity.normalize().scale(PLAYER_SPEED);
        player.x = Phaser.Math.Clamp(player.x, 20, WORLD_W - 20);
        player.y = Phaser.Math.Clamp(player.y, 42, WORLD_H - 20);
        updateRoute();
        updateInteractionPrompt();
    }

    function drawBackground(scene) {
        const g = scene.add.graphics();
        g.fillStyle(0x050914, 1).fillRect(0, 0, WORLD_W, WORLD_H);
        g.lineStyle(1, 0x10203a, 0.45);
        for (let x = -WORLD_H; x < WORLD_W; x += 28) g.lineBetween(x, 0, x + WORLD_H, WORLD_H);
        g.fillStyle(0x0b1729, 1).fillRect(22, CORRIDOR_Y, WORLD_W - 44, 92);
        g.lineStyle(2, 0x1f3554, 1).strokeRect(22, CORRIDOR_Y, WORLD_W - 44, 92);
        scene.add.text(WORLD_W / 2, 22, "GEOMETRIC COMPANY DUNGEON", {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "16px",
            color: "#5eead4",
        }).setOrigin(0.5).setAlpha(0.8);
    }

    function drawRoom(scene, room, idx) {
        const container = scene.add.container(room.x, room.y).setDepth(10);
        const floor = scene.add.rectangle(0, 0, room.w, room.h, room.fill, 1).setOrigin(0);
        const border = scene.add.rectangle(0, 0, room.w, room.h, 0x000000, 0).setOrigin(0).setStrokeStyle(2, room.color, 0.45);
        const grid = scene.add.graphics();
        grid.lineStyle(1, 0xffffff, 0.06);
        for (let x = 24; x < room.w; x += 24) grid.lineBetween(x, 0, x, room.h);
        for (let y = 24; y < room.h; y += 24) grid.lineBetween(0, y, room.w, y);
        const overlay = scene.add.rectangle(0, 0, room.w, room.h, 0x000000, 0.45).setOrigin(0);
        const title = scene.add.text(room.w / 2, 20, room.title.toUpperCase(), {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "16px",
            color: "#e2e8f0",
        }).setOrigin(0.5);
        const role = scene.add.text(room.w / 2, 42, `${room.name} / ${room.role}`, {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "12px",
            color: "#94a3b8",
        }).setOrigin(0.5);
        const doorLeft = scene.add.rectangle(room.doorX - room.x - 19, room.h, 36, 18, room.color, 0.95).setOrigin(0.5);
        const doorRight = scene.add.rectangle(room.doorX - room.x + 19, room.h, 36, 18, room.color, 0.95).setOrigin(0.5);
        const node = scene.add.circle(room.doorX - room.x, CORRIDOR_Y + 44 - room.y, 16, 0x07101e, 1)
            .setStrokeStyle(2, room.color, 0.5);
        const nodeLabel = scene.add.text(room.doorX - room.x, CORRIDOR_Y + 44 - room.y, String(idx + 1), {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "14px",
            color: "#94a3b8",
        }).setOrigin(0.5);
        container.add([floor, grid, border, overlay, title, role, doorLeft, doorRight, node, nodeLabel]);
        return { container, overlay, border, doorLeft, doorRight, node, nodeLabel, state: "locked" };
    }

    function drawAgent(scene, room) {
        const container = scene.add.container(room.approachX, room.approachY - 72).setDepth(30);
        const halo = scene.add.circle(0, 0, 34, room.color, 0.08).setStrokeStyle(2, room.color, 0.45);
        const body = scene.add.circle(0, 0, 16, 0x111827, 1).setStrokeStyle(2, room.color, 0.95);
        const core = scene.add.circle(0, 0, 7, room.color, 0.85);
        const eyeL = scene.add.circle(-5, -5, 2, 0xffffff, 0.9);
        const eyeR = scene.add.circle(5, -5, 2, 0xffffff, 0.9);
        const label = scene.add.text(0, -48, room.name, {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "13px",
            color: "#e2e8f0",
            backgroundColor: "#050914cc",
            padding: { x: 5, y: 2 },
        }).setOrigin(0.5);
        container.add([halo, body, core, eyeL, eyeR, label]);
        scene.tweens.add({ targets: container, y: container.y - 4, yoyo: true, repeat: -1, duration: 1200, ease: "Sine.easeInOut" });
        return { container, halo, body, core };
    }

    function drawPlayer(scene, x, y) {
        const container = scene.add.container(x, y).setDepth(35);
        const body = scene.add.circle(0, 0, 17, 0x0f172a, 1).setStrokeStyle(3, 0x2dd4bf, 1);
        const visor = scene.add.ellipse(0, -4, 18, 8, 0xfbbf24, 0.95);
        const label = scene.add.text(0, -34, "Founder", {
            fontFamily: "Share Tech Mono, monospace",
            fontSize: "11px",
            color: "#ccfbf1",
            backgroundColor: "#050914cc",
            padding: { x: 4, y: 2 },
        }).setOrigin(0.5);
        container.add([body, visor, label]);
        return container;
    }

    function currentRoomState(room) {
        const quest = getQuest();
        if (!quest?.steps?.length) return "locked";
        const idx = quest.steps.findIndex((step) => step.assigned_to === room.agent);
        if (idx < 0) return "locked";
        if (idx < quest.current_step_index) return "cleared";
        if (idx === quest.current_step_index) {
            const step = quest.steps[idx];
            return step.artifact_data ? "artifact" : isBusy ? "running" : "active";
        }
        return "locked";
    }

    function renderWorld() {
        rooms.forEach((room) => {
            const view = roomViews[room.agent];
            const state = currentRoomState(room);
            if (!view || view.state === state) return;
            view.state = state;
            const active = state === "active" || state === "running" || state === "artifact";
            const cleared = state === "cleared";
            view.overlay.setAlpha(cleared ? 0.03 : active ? 0.08 : 0.52);
            view.border.setStrokeStyle(active ? 3 : 2, cleared ? 0x34d399 : room.color, active ? 0.95 : 0.45);
            view.node.setStrokeStyle(2, cleared ? 0x34d399 : active ? 0xfbbf24 : room.color, active || cleared ? 0.95 : 0.35);
            view.nodeLabel.setText(cleared ? "OK" : active ? "!" : String(rooms.indexOf(room) + 1));
            view.nodeLabel.setColor(cleared ? "#34d399" : active ? "#fbbf24" : "#94a3b8");
            if (active || cleared) openDoor(view);
            else closeDoor(view, room);
            setAgentState(room.agent, state);
        });
        updateCompanyGraph();
    }

    function openDoor(view) {
        const leftTarget = view.doorLeft.x - 18;
        const rightTarget = view.doorRight.x + 18;
        sceneRef.tweens.add({ targets: view.doorLeft, x: leftTarget, alpha: 0.42, duration: 350, ease: "Cubic.easeOut" });
        sceneRef.tweens.add({ targets: view.doorRight, x: rightTarget, alpha: 0.42, duration: 350, ease: "Cubic.easeOut" });
    }

    function closeDoor(view, room) {
        sceneRef.tweens.add({ targets: view.doorLeft, x: room.doorX - room.x - 19, alpha: 0.95, duration: 250 });
        sceneRef.tweens.add({ targets: view.doorRight, x: room.doorX - room.x + 19, alpha: 0.95, duration: 250 });
    }

    function setAgentState(agent, state) {
        const room = getRoom(agent);
        const view = agentViews[agent];
        if (!room || !view) return;
        const running = state === "running";
        const cleared = state === "cleared";
        const color = cleared ? 0x34d399 : running ? 0xfbbf24 : room.color;
        view.halo.setFillStyle(color, running ? 0.18 : 0.08);
        view.halo.setStrokeStyle(running ? 3 : 2, color, running ? 1 : 0.45);
        view.core.setFillStyle(color, cleared ? 0.95 : 0.85);
        if (running && !view.focusTween) {
            view.focusTween = sceneRef.tweens.add({
                targets: view.halo,
                scale: { from: 0.9, to: 1.45 },
                alpha: { from: 1, to: 0.35 },
                duration: 560,
                yoyo: true,
                repeat: -1,
            });
        } else if (!running && view.focusTween) {
            view.focusTween.stop();
            view.focusTween = null;
            view.halo.setScale(1).setAlpha(1);
        }
    }

    function updateRoute() {
        if (!routeLine || !player) return;
        const room = getActiveRoom();
        routeLine.clear();
        if (!room || isBusy || getActiveStep()?.artifact_data) {
            if (routeMarker) routeMarker.setVisible(false);
            return;
        }
        const dist = Phaser.Math.Distance.Between(player.x, player.y, room.approachX, room.approachY);
        if (dist < 72) {
            if (routeMarker) routeMarker.setVisible(false);
            return;
        }
        routeLine.lineStyle(2, room.color, 0.7);
        const segments = Math.max(4, Math.floor(dist / 28));
        for (let i = 0; i < segments; i += 2) {
            const a = i / segments;
            const b = Math.min((i + 1) / segments, 1);
            routeLine.lineBetween(
                Phaser.Math.Linear(player.x, room.approachX, a),
                Phaser.Math.Linear(player.y, room.approachY, a),
                Phaser.Math.Linear(player.x, room.approachX, b),
                Phaser.Math.Linear(player.y, room.approachY, b)
            );
        }
        if (!routeMarker) {
            routeMarker = sceneRef.add.circle(room.approachX, room.approachY, 10, room.color, 0.2).setStrokeStyle(2, room.color, 0.9).setDepth(41);
            sceneRef.tweens.add({ targets: routeMarker, scale: 1.35, yoyo: true, repeat: -1, duration: 650 });
        }
        routeMarker.setVisible(true).setPosition(room.approachX, room.approachY).setFillStyle(room.color, 0.2).setStrokeStyle(2, room.color, 0.9);
    }

    function updateInteractionPrompt() {
        const room = getActiveRoom();
        const step = getActiveStep();
        const near = room && player && Phaser.Math.Distance.Between(player.x, player.y, room.approachX, room.approachY) < 74;
        const shouldShow = Boolean(near && step && !step.artifact_data && !isBusy);
        if (!shouldShow) {
            if (interactionPrompt) interactionPrompt.setVisible(false);
            return;
        }
        if (!interactionPrompt) {
            interactionPrompt = sceneRef.add.text(room.approachX, room.approachY - 86, "E", {
                fontFamily: "Share Tech Mono, monospace",
                fontSize: "18px",
                color: "#050914",
                backgroundColor: "#fbbf24",
                padding: { x: 9, y: 5 },
            }).setOrigin(0.5).setDepth(60);
            sceneRef.tweens.add({ targets: interactionPrompt, y: interactionPrompt.y - 6, yoyo: true, repeat: -1, duration: 520 });
        }
        interactionPrompt.setVisible(true).setPosition(room.approachX, room.approachY - 86);
    }

    function startThinking() {
        if (!sceneRef) return;
        stopThinking();
        startThinkingAudio();
        thinkingTimer = sceneRef.time.addEvent({
            delay: 95,
            loop: true,
            callback: () => {
                const room = getActiveRoom();
                if (!room) return;
                const x = room.approachX + Phaser.Math.Between(-18, 18);
                const y = room.approachY - 74 + Phaser.Math.Between(-12, 10);
                const dot = sceneRef.add.circle(x, y, Phaser.Math.Between(2, 4), room.color, 0.85).setDepth(50);
                sceneRef.tweens.add({
                    targets: dot,
                    y: dot.y - Phaser.Math.Between(24, 52),
                    alpha: 0,
                    scale: 0.3,
                    duration: Phaser.Math.Between(650, 980),
                    onComplete: () => dot.destroy(),
                });
            },
        });
    }

    function stopThinking() {
        stopThinkingAudio();
        if (thinkingTimer) {
            thinkingTimer.remove(false);
            thinkingTimer = null;
        }
    }

    function updateCompanyGraph() {
        if (!sceneRef) return;
        graphNodes.forEach((node) => node.destroy());
        graphNodes = [];
        const quest = getQuest();
        if (!quest?.steps?.length) return;
        const completed = quest.steps.filter((step, idx) => idx < quest.current_step_index || step.status === "completed");
        completed.forEach((step, idx) => {
            const x = 132 + idx * 118;
            const y = 560;
            const room = getRoom(step.assigned_to) || rooms[idx % rooms.length];
            const c = sceneRef.add.container(x, y).setDepth(25);
            const node = sceneRef.add.circle(0, 0, 18, 0x06111f, 1).setStrokeStyle(2, room.color, 0.95);
            const label = sceneRef.add.text(0, 0, shortArtifactLabel(step), {
                fontFamily: "Share Tech Mono, monospace",
                fontSize: "9px",
                color: "#e2e8f0",
            }).setOrigin(0.5);
            c.add([node, label]);
            if (idx > 0) {
                const line = sceneRef.add.line(0, 0, x - 118, y, x - 20, y, 0x34d399, 0.55).setOrigin(0).setDepth(24);
                graphNodes.push(line);
            }
            graphNodes.push(c);
        });
    }

    function shortArtifactLabel(step) {
        if (step.artifact_type === "email") return "GTM";
        if (step.artifact_type === "url") return "PAGE";
        return "ICP";
    }

    function renderQuest() {
        const quest = getQuest();
        ui.quest.innerHTML = "";
        if (!quest?.steps?.length) return;
        quest.steps.forEach((step, idx) => {
            const active = idx === quest.current_step_index;
            const cleared = idx < quest.current_step_index;
            const card = document.createElement("div");
            card.className = [
                "rounded border p-2 text-center",
                cleared ? "border-emerald-500/50 bg-emerald-950/20" : active ? "border-amber-400/60 bg-amber-950/20" : "border-slate-700 bg-slate-900/80",
            ].join(" ");
            card.innerHTML = `
                <div class="text-[10px] uppercase ${cleared ? "text-emerald-300" : active ? "text-amber-300" : "text-slate-500"}">${escapeHTML(step.assigned_to)}</div>
                <div class="text-[11px] text-slate-200 truncate">${escapeHTML(step.title)}</div>
                <div class="text-[10px] text-slate-500">${cleared ? "cleared" : active ? "active" : "locked"}</div>
            `;
            ui.quest.appendChild(card);
        });
    }

    function renderArtifact() {
        const step = getActiveStep();
        if (!step) {
            ui.artifact.innerHTML = `<div class="text-emerald-300">Quest complete. The company graph is validated.</div>`;
            ui.approve.disabled = true;
            ui.reject.disabled = true;
            return;
        }
        if (!step.artifact_data) {
            ui.artifact.innerHTML = `<div class="text-slate-500">Walk to ${escapeHTML(step.assigned_to)} and run the agent turn.</div>`;
            ui.approve.disabled = true;
            ui.reject.disabled = true;
            return;
        }
        ui.artifact.innerHTML = renderArtifactObject(step.artifact_data, step.validation_results);
        ui.approve.disabled = false;
        ui.reject.disabled = false;
    }

    function renderArtifactObject(artifact, validation) {
        const checks = validation?.checks || {};
        const score = validation?.score ?? "--";
        let html = `
            <div class="mb-3 rounded border border-teal-500/30 bg-teal-950/20 p-3">
                <div class="text-[10px] uppercase tracking-[0.18em] text-teal-300">Validator Score</div>
                <div class="text-2xl text-white">${escapeHTML(score)}/100</div>
                <div class="grid grid-cols-2 gap-1 mt-2">
                    ${Object.entries(checks).map(([key, val]) => `
                        <div class="text-[10px] ${val ? "text-emerald-300" : "text-rose-300"}">${val ? "PASS" : "FAIL"} ${escapeHTML(key)}</div>
                    `).join("")}
                </div>
            </div>
        `;
        html += `<div class="space-y-3">`;
        Object.entries(artifact || {}).forEach(([key, value]) => {
            html += `<div><div class="text-[10px] uppercase tracking-[0.16em] text-amber-300 mb-1">${escapeHTML(key.replaceAll("_", " "))}</div>`;
            html += renderValue(key, value);
            html += `</div>`;
        });
        html += `</div>`;
        return html;
    }

    function renderValue(key, value) {
        if (Array.isArray(value) && value.every((item) => typeof item === "object" && item !== null)) {
            return `<div class="space-y-2">${value.map((item) => renderObjectCard(item)).join("")}</div>`;
        }
        if (typeof value === "object" && value !== null) {
            const numericList = findNumericList(value);
            if (numericList) return renderMiniChart(numericList, key);
            return renderObjectCard(value);
        }
        return `<div class="artifact-pre">${escapeHTML(value)}</div>`;
    }

    function renderObjectCard(obj) {
        return `
            <div class="rounded border border-[#1f2a44] bg-[#07101e] p-2">
                ${Object.entries(obj).map(([key, value]) => `
                    <div class="mb-1">
                        <span class="text-slate-500">${escapeHTML(key)}:</span>
                        <span class="text-slate-100">${escapeHTML(typeof value === "object" ? JSON.stringify(value) : value)}</span>
                    </div>
                `).join("")}
            </div>
        `;
    }

    function findNumericList(obj) {
        for (const value of Object.values(obj)) {
            if (Array.isArray(value) && value.length >= 3 && value.every((item) => typeof item === "number")) return value;
        }
        return null;
    }

    function renderMiniChart(values, label) {
        const max = Math.max(...values, 1);
        return `
            <div class="rounded border border-[#1f2a44] bg-[#07101e] p-2">
                <div class="text-[10px] text-slate-400 mb-2">${escapeHTML(label)} trend</div>
                <div class="flex items-end gap-1 h-28">
                    ${values.map((value) => `
                        <div class="flex-1 bg-teal-400/70 border border-teal-200/30" style="height:${Math.max(8, (value / max) * 100)}%"></div>
                    `).join("")}
                </div>
            </div>
        `;
    }

    function renderState() {
        const step = getActiveStep();
        ui.status.textContent = isBusy ? "Reasoning" : step ? `${step.assigned_to}: ${step.artifact_data ? "Review" : "Ready"}` : currentState ? "Complete" : "Idle";
        ui.run.disabled = !step || Boolean(step.artifact_data) || isBusy;
        renderQuest();
        renderArtifact();
        renderWorld();
    }

    async function startQuest() {
        ensureAudio();
        startAmbient();
        ui.start.disabled = true;
        try {
            const data = await api("/init", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pitch: ui.pitch.value.trim(), company_name: ui.company.value.trim() }),
            });
            currentState = data.state;
            log("[system] Quest initialized.", "text-teal-300");
            playCue("activate");
            renderState();
        } catch (e) {
            log(`[error] ${e.message || e}`, "text-rose-300");
        } finally {
            ui.start.disabled = false;
        }
    }

    async function runActiveAgent() {
        const step = getActiveStep();
        if (!step || step.artifact_data || isBusy) return;
        const room = getRoom(step.assigned_to);
        if (!room || Phaser.Math.Distance.Between(player.x, player.y, room.approachX, room.approachY) > 76) {
            log(`[game] Approach ${step.assigned_to} before running the turn.`, "text-amber-300");
            playCue("reject");
            return;
        }
        isBusy = true;
        playCue("activate");
        startThinking();
        renderState();
        try {
            const data = await api("/step/execute", { method: "POST" });
            currentState = data.state;
            playCue("reveal");
            log(`[${step.assigned_to}] Artifact created. Review gate open.`, "text-teal-300");
        } catch (e) {
            log(`[error] ${e.message || e}`, "text-rose-300");
            playCue("reject");
        } finally {
            isBusy = false;
            stopThinking();
            renderState();
        }
    }

    async function approve() {
        if (!getActiveStep()?.artifact_data) return;
        try {
            const data = await api("/step/approve", { method: "POST" });
            currentState = data.state;
            playCue(getActiveStep() ? "approve" : "complete");
            burstAtPlayer();
            log("[human] Artifact approved. Door opened.", "text-emerald-300");
            renderState();
        } catch (e) {
            log(`[error] ${e.message || e}`, "text-rose-300");
        }
    }

    async function reject() {
        if (!getActiveStep()?.artifact_data) return;
        try {
            const data = await api("/step/reject", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ feedback: "Needs a sharper pass." }),
            });
            currentState = data.state;
            playCue("reject");
            sceneRef.cameras.main.shake(180, 0.004);
            log("[human] Artifact rejected. Room remains active.", "text-rose-300");
            renderState();
        } catch (e) {
            log(`[error] ${e.message || e}`, "text-rose-300");
        }
    }

    function burstAtPlayer() {
        if (!sceneRef || !player) return;
        for (let i = 0; i < 18; i++) {
            const dot = sceneRef.add.circle(player.x, player.y, 3, 0xfde047, 0.95).setDepth(55);
            const angle = (Math.PI * 2 * i) / 18;
            sceneRef.tweens.add({
                targets: dot,
                x: player.x + Math.cos(angle) * Phaser.Math.Between(24, 62),
                y: player.y + Math.sin(angle) * Phaser.Math.Between(24, 62),
                alpha: 0,
                duration: 620,
                onComplete: () => dot.destroy(),
            });
        }
        sceneRef.cameras.main.shake(160, 0.003);
    }

    async function autoplay() {
        if (isAutoplay) {
            isAutoplay = false;
            return;
        }
        isAutoplay = true;
        ensureAudio();
        startAmbient();
        if (!currentState) await startQuest();
        while (isAutoplay && getActiveStep()) {
            const step = getActiveStep();
            const room = getRoom(step.assigned_to);
            if (!room) break;
            await tweenPlayer(room.approachX, room.approachY);
            if (!step.artifact_data) await runActiveAgent();
            await sleep(650);
            if (getActiveStep()?.artifact_data) await approve();
            await sleep(650);
        }
        isAutoplay = false;
    }

    function tweenPlayer(x, y) {
        return new Promise((resolve) => {
            if (!sceneRef || !player) return resolve();
            sceneRef.tweens.add({
                targets: player,
                x,
                y,
                duration: Math.max(260, Math.min(1400, Phaser.Math.Distance.Between(player.x, player.y, x, y) * 5)),
                ease: "Sine.easeInOut",
                onComplete: resolve,
            });
        });
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    async function reset() {
        await api("/reset", { method: "POST" });
        currentState = null;
        ui.log.innerHTML = "";
        ui.artifact.textContent = "Start a quest to generate artifacts.";
        ui.quest.innerHTML = "";
        ui.status.textContent = "Idle";
        log("[system] Reset complete.", "text-slate-300");
        if (player) player.setPosition(rooms[0].doorX, CORRIDOR_Y + 44);
        renderState();
    }

    ui.start.addEventListener("click", startQuest);
    ui.run.addEventListener("click", runActiveAgent);
    ui.approve.addEventListener("click", approve);
    ui.reject.addEventListener("click", reject);
    ui.autoplay.addEventListener("click", autoplay);
    ui.reset.addEventListener("click", reset);

    createGame();
})();
