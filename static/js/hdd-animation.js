(function () {
    'use strict';

    const animation = document.getElementById('serverAnimation');
    if (!animation) return;

    const tiles = animation.querySelector('[data-server-tiles]');
    const pixels = animation.querySelector('[data-server-pixels]');

    for (let row = 0; row < 4; row += 1) {
        for (let column = 0; column < 5; column += 1) {
            const tile = document.createElement('div');
            tile.className = 'home-server-tile';
            tile.style.setProperty('--server-col', column);
            tile.style.setProperty('--server-row', row);
            tiles.appendChild(tile);
        }
    }

    for (let index = 0; index < 54; index += 1) {
        const pixel = document.createElement('i');
        const size = 2 + Math.random() * 5;
        pixel.className = 'home-server-pixel';
        pixel.style.setProperty('--server-size', `${size}px`);
        pixel.style.setProperty('--server-pixel-left', `${8 + Math.random() * 84}%`);
        pixel.style.setProperty('--server-pixel-top', `${8 + Math.random() * 84}%`);
        pixel.style.setProperty('--server-dx', `${(Math.random() - 0.5) * 220}px`);
        pixel.style.setProperty('--server-dy', `${(Math.random() - 0.5) * 170}px`);
        pixel.style.setProperty('--server-delay', `${Math.random() * 900}ms`);
        pixels.appendChild(pixel);
    }

    const buttons = animation.querySelectorAll('[data-server-mode]');
    const scenes = animation.querySelectorAll('[data-server-scene]');

    buttons.forEach(button => {
        button.addEventListener('click', () => {
            buttons.forEach(item => {
                const isActive = item === button;
                item.classList.toggle('active', isActive);
                item.setAttribute('aria-pressed', String(isActive));
            });
            scenes.forEach(scene => {
                scene.classList.toggle('active', scene.dataset.serverScene === button.dataset.serverMode);
            });
        });
    });
}());
