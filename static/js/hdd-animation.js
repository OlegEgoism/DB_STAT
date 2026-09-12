(function () {
    'use strict';

    const canvas = document.getElementById('hddCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d', {alpha: true});
    if (!ctx) return;

    const TAU = Math.PI * 2;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const grains = [];
    let width = 1;
    let height = 1;
    let scale = 1;
    let frameId = 0;
    let startedAt = performance.now();

    function clamp(value, min = 0, max = 1) {
        return Math.max(min, Math.min(max, value));
    }

    function smoothstep(value) {
        const x = clamp(value);
        return x * x * (3 - 2 * x);
    }

    function random(index, salt) {
        const value = Math.sin(index * 91.733 + salt * 37.719) * 43758.5453;
        return value - Math.floor(value);
    }

    function roundedRect(x, y, w, h, radius) {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, radius);
    }

    function buildGrains() {
        grains.length = 0;
        for (let index = 0; index < 520; index += 1) {
            const angle = random(index, 1) * TAU;
            const radius = Math.sqrt(random(index, 2)) * 91;
            grains.push({
                x: 27 + Math.cos(angle) * radius,
                y: -9 + Math.sin(angle) * radius,
                size: 0.45 + random(index, 3) * 2.15,
                speed: 72 + random(index, 4) * 164,
                lift: (random(index, 5) - 0.62) * 78,
                delay: random(index, 6) * 0.42,
                wobble: random(index, 7) * TAU,
                tone: Math.floor(random(index, 8) * 4)
            });
        }
    }

    function drawPlatter(dissolve) {
        const platterX = 27;
        const platterY = -9;
        const radius = 91;
        const edge = -radius + dissolve * radius * 2.3;

        ctx.save();
        ctx.beginPath();
        ctx.rect(-radius - 4, -radius - 5, clamp(edge + radius + 4, 0, radius * 2 + 8), radius * 2 + 10);
        ctx.clip();

        const metal = ctx.createRadialGradient(platterX - 22, platterY - 28, 3, platterX, platterY, radius);
        metal.addColorStop(0, '#ffffff');
        metal.addColorStop(0.24, '#cbd6de');
        metal.addColorStop(0.47, '#f8fbfc');
        metal.addColorStop(0.72, '#8796a2');
        metal.addColorStop(0.9, '#e8eef1');
        metal.addColorStop(1, '#57636c');
        ctx.fillStyle = metal;
        ctx.beginPath();
        ctx.arc(platterX, platterY, radius, 0, TAU);
        ctx.fill();

        ctx.globalAlpha = 0.24;
        ctx.strokeStyle = '#30404c';
        ctx.lineWidth = 0.8;
        for (let ring = 22; ring < 88; ring += 8) {
            ctx.beginPath();
            ctx.arc(platterX, platterY, ring, 0, TAU);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;

        const hub = ctx.createRadialGradient(platterX - 4, platterY - 5, 2, platterX, platterY, 22);
        hub.addColorStop(0, '#f9fcfd');
        hub.addColorStop(0.4, '#75838d');
        hub.addColorStop(0.62, '#d9e1e5');
        hub.addColorStop(1, '#46535d');
        ctx.fillStyle = hub;
        ctx.beginPath();
        ctx.arc(platterX, platterY, 22, 0, TAU);
        ctx.fill();
        ctx.fillStyle = '#18232c';
        ctx.beginPath();
        ctx.arc(platterX, platterY, 7, 0, TAU);
        ctx.fill();
        ctx.restore();
    }

    function drawDrive(dissolve) {
        ctx.save();
        ctx.rotate(-0.13);
        ctx.shadowColor = 'rgba(3, 12, 23, 0.55)';
        ctx.shadowBlur = 20;
        ctx.shadowOffsetY = 12;
        const caseGradient = ctx.createLinearGradient(-120, -100, 120, 105);
        caseGradient.addColorStop(0, '#56646f');
        caseGradient.addColorStop(0.18, '#171f27');
        caseGradient.addColorStop(1, '#07111b');
        ctx.fillStyle = caseGradient;
        roundedRect(-121, -101, 242, 202, 13);
        ctx.fill();
        ctx.shadowColor = 'transparent';
        ctx.strokeStyle = '#74828c';
        ctx.lineWidth = 2;
        roundedRect(-113, -93, 226, 186, 10);
        ctx.stroke();

        drawPlatter(dissolve);

        // Read/write arm and pivot, kept intact while the platter turns to dust.
        ctx.save();
        ctx.translate(-67, 42);
        ctx.rotate(-0.7);
        ctx.strokeStyle = '#d8e0e4';
        ctx.lineWidth = 13;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(88, 0);
        ctx.stroke();
        ctx.strokeStyle = '#5d6b75';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(7, 0);
        ctx.lineTo(88, 0);
        ctx.stroke();
        ctx.restore();
        ctx.fillStyle = '#aeb9c0';
        ctx.beginPath();
        ctx.arc(-67, 42, 23, 0, TAU);
        ctx.fill();
        ctx.fillStyle = '#26333c';
        ctx.beginPath();
        ctx.arc(-67, 42, 9, 0, TAU);
        ctx.fill();

        [[-101, -80], [100, -80], [-101, 80], [100, 80]].forEach(([x, y]) => {
            ctx.fillStyle = '#c4cdd2';
            ctx.beginPath();
            ctx.arc(x, y, 4.5, 0, TAU);
            ctx.fill();
            ctx.strokeStyle = '#374650';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(x - 2.5, y);
            ctx.lineTo(x + 2.5, y);
            ctx.stroke();
        });
        ctx.restore();
    }

    function drawDust(dissolve, now) {
        if (dissolve <= 0.01) return;
        const edge = -91 + dissolve * 209;
        const palette = ['#f4f8fa', '#bdcbd3', '#718491', '#dce6eb'];
        ctx.save();
        ctx.rotate(-0.13);
        grains.forEach((grain) => {
            const trigger = clamp((grain.x + 91) / 209 + grain.delay * 0.24);
            const travel = smoothstep((dissolve - trigger) / 0.34);
            const nearEdge = 1 - clamp(Math.abs(grain.x - edge) / 28);
            if (travel <= 0 && nearEdge <= 0) return;
            const distance = grain.speed * travel;
            const x = grain.x + distance;
            const y = grain.y + grain.lift * travel + Math.sin(now * 0.003 + grain.wobble) * 3 * travel;
            const fade = clamp(1 - travel * 0.72) * Math.max(travel, nearEdge * dissolve);
            ctx.globalAlpha = fade;
            ctx.fillStyle = palette[grain.tone];
            ctx.beginPath();
            ctx.arc(x, y, grain.size * (1 - travel * 0.35), 0, TAU);
            ctx.fill();
        });
        ctx.restore();
    }

    function drawAmbientDust(now) {
        ctx.save();
        for (let index = 0; index < 42; index += 1) {
            const x = random(index, 21) * width;
            const baseY = random(index, 22) * height;
            const y = (baseY + now * (0.002 + random(index, 23) * 0.004)) % height;
            const radius = 0.35 + random(index, 24) * 1.25;
            ctx.globalAlpha = 0.08 + random(index, 25) * 0.2;
            ctx.fillStyle = '#d9e8f1';
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, TAU);
            ctx.fill();
        }
        ctx.restore();
    }

    function progress(now) {
        if (reduceMotion.matches) return 0.38;
        const elapsed = (now - startedAt) % 7200;
        if (elapsed < 900) return 0;
        if (elapsed < 3900) return smoothstep((elapsed - 900) / 3000);
        if (elapsed < 4900) return 1;
        if (elapsed < 6500) return 1 - smoothstep((elapsed - 4900) / 1600);
        return 0;
    }

    function draw(now) {
        ctx.clearRect(0, 0, width, height);
        const dissolve = progress(now);
        drawAmbientDust(now);
        ctx.save();
        // The low-left drive and upper-right dust plume follow the supplied photo's composition.
        ctx.translate(width * 0.34, height * 0.58);
        ctx.scale(scale, scale);
        drawDrive(dissolve);
        drawDust(dissolve, now);
        ctx.restore();
        if (!reduceMotion.matches && !document.hidden) frameId = requestAnimationFrame(draw);
    }

    function resize() {
        const bounds = canvas.parentElement.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = Math.max(1, bounds.width);
        height = Math.max(1, bounds.height);
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        scale = Math.min(width / 440, height / 270);
        draw(performance.now());
    }

    function restart() {
        cancelAnimationFrame(frameId);
        startedAt = performance.now();
        if (!document.hidden) frameId = requestAnimationFrame(draw);
    }

    buildGrains();
    new ResizeObserver(resize).observe(canvas.parentElement);
    document.addEventListener('visibilitychange', restart);
    reduceMotion.addEventListener('change', restart);
    resize();
    restart();
}());
