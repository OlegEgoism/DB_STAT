(function () {
    'use strict';

    const canvas = document.getElementById('hddCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d', {alpha: true});
    if (!ctx) return;

    const TAU = Math.PI * 2;
    const timeline = {duration: 5200, holdIntact: 700, explodeEnd: 1900, holdExplodedEnd: 3000, assembleEnd: 4400};
    const fragments = [
        {type: 'cover', tx: -190, ty: -125, rot: -0.85, delay: 0},
        {type: 'board', tx: 190, ty: 135, rot: 0.9, delay: 0.025},
        {type: 'platter', tx: -15, ty: -195, rot: -0.3, delay: 0.05},
        {type: 'platter', tx: 90, ty: -170, rot: 0.45, delay: 0.075},
        {type: 'arm', tx: 220, ty: -45, rot: 1.35, delay: 0.1},
        {type: 'magnet', tx: 185, ty: -145, rot: -1.2, delay: 0.125},
        {type: 'hub', tx: -130, ty: 180, rot: 0.3, delay: 0.15},
        {type: 'frame', tx: -195, ty: 120, rot: 0.65, delay: 0.175}
    ];
    const screws = [];
    const particles = [];
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 0;
    let height = 0;
    let scale = 1;
    let startedAt = performance.now();
    let frameId = 0;

    function clamp(value, min = 0, max = 1) {
        return Math.max(min, Math.min(max, value));
    }

    function easeOutCubic(value) {
        return 1 - Math.pow(1 - value, 3);
    }

    function easeInOutCubic(value) {
        return value < 0.5 ? 4 * value * value * value : 1 - Math.pow(-2 * value + 2, 3) / 2;
    }

    function roundedRect(x, y, w, h, radius) {
        const r = Math.min(radius, w / 2, h / 2);
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
    }

    function createObjects() {
        screws.length = 0;
        particles.length = 0;
        for (let index = 0; index < 26; index += 1) {
            const angle = (index / 26) * TAU + Math.sin(index * 8.1) * 0.06;
            const ring = index % 3;
            const radius = (ring === 0 ? 88 : ring === 1 ? 54 : 30) * scale;
            screws.push({
                x: Math.cos(angle) * radius,
                y: Math.sin(angle) * radius,
                tx: Math.cos(angle) * (175 + (index % 7) * 13) * scale,
                ty: Math.sin(angle) * (175 + (index % 7) * 13) * scale,
                size: (4 + (index % 4) * 0.7) * scale,
                spin: (index % 2 ? -8 : 8) + index * 0.1,
                delay: (index % 6) * 0.025
            });
        }
        for (let index = 0; index < 72; index += 1) {
            particles.push({
                angle: index * 2.399,
                distance: (80 + (index * 47) % 180) * scale,
                size: (1 + (index % 4) * 0.55) * scale,
                drift: ((index % 9) - 4) * 4 * scale
            });
        }
    }

    function resize() {
        const bounds = canvas.parentElement.getBoundingClientRect();
        width = Math.max(1, bounds.width);
        height = Math.max(1, bounds.height);
        const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        scale = Math.min(width / 520, height / 410);
        createObjects();
        if (reduceMotion.matches) draw(0);
    }

    function phase(now) {
        const elapsed = (now - startedAt) % timeline.duration;
        if (elapsed < timeline.holdIntact) return {progress: 0, flash: 0};
        if (elapsed < timeline.explodeEnd) {
            const value = (elapsed - timeline.holdIntact) / (timeline.explodeEnd - timeline.holdIntact);
            return {progress: easeOutCubic(value), flash: Math.sin(Math.PI * clamp(value * 1.5))};
        }
        if (elapsed < timeline.holdExplodedEnd) return {progress: 1, flash: 0};
        if (elapsed < timeline.assembleEnd) {
            const value = (elapsed - timeline.holdExplodedEnd) / (timeline.assembleEnd - timeline.holdExplodedEnd);
            return {progress: 1 - easeInOutCubic(value), flash: 0};
        }
        return {progress: 0, flash: 0};
    }

    function drawBase(alpha) {
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.shadowColor = 'rgba(23, 35, 50, 0.3)';
        ctx.shadowBlur = 22 * scale;
        ctx.fillStyle = '#20252b';
        roundedRect(-112 * scale, -91 * scale, 224 * scale, 182 * scale, 16 * scale);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = '#11161b';
        roundedRect(-101 * scale, -80 * scale, 202 * scale, 160 * scale, 11 * scale);
        ctx.fill();
        drawPlatter(-10 * scale, -5 * scale, 68 * scale);
        drawArm(40 * scale, 9 * scale);
        ctx.restore();
    }

    function drawPlatter(x, y, radius) {
        const gradient = ctx.createRadialGradient(x, y, 5 * scale, x, y, radius);
        gradient.addColorStop(0, '#f3f6f8');
        gradient.addColorStop(0.45, '#bfc7cc');
        gradient.addColorStop(1, '#454d53');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, TAU);
        ctx.fill();
        ctx.fillStyle = '#4d555b';
        ctx.beginPath();
        ctx.arc(x, y, 12 * scale, 0, TAU);
        ctx.fill();
    }

    function drawArm(x, y) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(-0.32);
        ctx.strokeStyle = '#c6cdd1';
        ctx.lineWidth = 10 * scale;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(50 * scale, -28 * scale);
        ctx.stroke();
        ctx.fillStyle = '#727a80';
        ctx.beginPath();
        ctx.arc(0, 0, 12 * scale, 0, TAU);
        ctx.fill();
        ctx.restore();
    }

    function drawFragment(fragment, progress) {
        const local = clamp((progress - fragment.delay) / (1 - fragment.delay));
        ctx.save();
        ctx.translate(fragment.tx * scale * local, fragment.ty * scale * local);
        ctx.rotate(fragment.rot * local);
        if (fragment.type === 'cover') {
            ctx.fillStyle = 'rgba(191, 199, 205, 0.96)';
            roundedRect(-108 * scale, -86 * scale, 216 * scale, 172 * scale, 15 * scale);
            ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
            ctx.lineWidth = 2 * scale;
            roundedRect(-94 * scale, -72 * scale, 188 * scale, 144 * scale, 10 * scale);
            ctx.stroke();
        } else if (fragment.type === 'board') {
            ctx.fillStyle = '#174b35';
            roundedRect(-90 * scale, 35 * scale, 180 * scale, 70 * scale, 9 * scale);
            ctx.fill();
            ctx.fillStyle = '#c7a85b';
            for (let index = 0; index < 7; index += 1) ctx.fillRect((-72 + index * 22) * scale, 88 * scale, 9 * scale, 12 * scale);
        } else if (fragment.type === 'platter') {
            drawPlatter(-10 * scale, -5 * scale, 64 * scale);
        } else if (fragment.type === 'arm') {
            drawArm(40 * scale, 9 * scale);
        } else if (fragment.type === 'magnet') {
            ctx.fillStyle = '#30363b';
            roundedRect(15 * scale, -55 * scale, 75 * scale, 38 * scale, 9 * scale);
            ctx.fill();
        } else if (fragment.type === 'hub') {
            ctx.fillStyle = '#bdc5ca';
            ctx.beginPath();
            ctx.arc(-10 * scale, -5 * scale, 27 * scale, 0, TAU);
            ctx.fill();
        } else {
            ctx.strokeStyle = '#555d63';
            ctx.lineWidth = 13 * scale;
            roundedRect(-106 * scale, -84 * scale, 212 * scale, 168 * scale, 14 * scale);
            ctx.stroke();
        }
        ctx.restore();
    }

    function drawEffects(progress, flash, now) {
        screws.forEach((screw, index) => {
            const local = clamp((progress - screw.delay) / (1 - screw.delay));
            ctx.save();
            ctx.translate(screw.x + screw.tx * local, screw.y + screw.ty * local);
            ctx.rotate(screw.spin * local + now * 0.003);
            ctx.fillStyle = '#cbd2d6';
            ctx.beginPath();
            ctx.arc(0, 0, screw.size, 0, TAU);
            ctx.fill();
            ctx.strokeStyle = '#5c656b';
            ctx.lineWidth = Math.max(1, 1.2 * scale);
            ctx.beginPath();
            ctx.moveTo(-screw.size * 0.55, 0);
            ctx.lineTo(screw.size * 0.55, 0);
            ctx.stroke();
            ctx.restore();
            if (index >= particles.length) return;
        });
        if (progress <= 0) return;
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        particles.forEach((particle, index) => {
            const x = Math.cos(particle.angle) * particle.distance * progress;
            const y = Math.sin(particle.angle) * particle.distance * progress + particle.drift * progress;
            ctx.globalAlpha = (1 - progress) * 0.8;
            ctx.fillStyle = index % 3 === 0 ? '#ffffff' : index % 3 === 1 ? '#88d7ff' : '#ffd788';
            ctx.beginPath();
            ctx.arc(x, y, particle.size, 0, TAU);
            ctx.fill();
        });
        if (flash > 0) {
            const radius = 145 * scale * flash;
            const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
            gradient.addColorStop(0, `rgba(255, 255, 255, ${0.8 * flash})`);
            gradient.addColorStop(0.25, `rgba(120, 210, 255, ${0.5 * flash})`);
            gradient.addColorStop(1, 'rgba(120, 210, 255, 0)');
            ctx.globalAlpha = 1;
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(0, 0, radius, 0, TAU);
            ctx.fill();
        }
        ctx.restore();
    }

    function draw(now) {
        ctx.clearRect(0, 0, width, height);
        const state = reduceMotion.matches ? {progress: 0, flash: 0} : phase(now);
        ctx.save();
        ctx.translate(width / 2, height / 2);
        const pulse = 1 + Math.sin(now * 0.003) * 0.012 * (1 - state.progress);
        ctx.scale(pulse, pulse);
        drawBase(1 - state.progress * 0.92);
        fragments.forEach(fragment => drawFragment(fragment, state.progress));
        drawEffects(state.progress, state.flash, now);
        ctx.restore();
        if (!reduceMotion.matches && !document.hidden) frameId = requestAnimationFrame(draw);
    }

    function restart() {
        cancelAnimationFrame(frameId);
        startedAt = performance.now();
        if (!document.hidden) frameId = requestAnimationFrame(draw);
    }

    new ResizeObserver(resize).observe(canvas.parentElement);
    document.addEventListener('visibilitychange', restart);
    reduceMotion.addEventListener('change', restart);
    resize();
    restart();
}());
