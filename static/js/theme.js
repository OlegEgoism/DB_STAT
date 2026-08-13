(function () {
    'use strict';

    const storageKey = 'db_stat_theme';
    const themes = new Set(['default', 'dark', 'gray']);

    function getSavedTheme() {
        try {
            const value = localStorage.getItem(storageKey);
            return themes.has(value) ? value : 'default';
        } catch (error) {
            return 'default';
        }
    }

    function applyTheme(theme, options = {}) {
        const normalizedTheme = themes.has(theme) ? theme : 'default';
        document.documentElement.dataset.theme = normalizedTheme;
        document.documentElement.style.colorScheme = normalizedTheme === 'dark' ? 'dark' : 'light';

        if (options.persist !== false) {
            try {
                localStorage.setItem(storageKey, normalizedTheme);
            } catch (error) {
                // The theme still works for this page when storage is unavailable.
            }
        }

        document.dispatchEvent(new CustomEvent('dbstat:themechange', {
            detail: {theme: normalizedTheme}
        }));
        return normalizedTheme;
    }

    window.DBStatTheme = {apply: applyTheme, get: getSavedTheme, themes: Array.from(themes)};
    applyTheme(getSavedTheme(), {persist: false});
}());
