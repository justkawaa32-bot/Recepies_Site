(() => {
    const STORAGE_KEY = 'theme';

    function applyTheme(theme) {
        const t = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.dataset.theme = t;
        try {
            localStorage.setItem(STORAGE_KEY, t);
        } catch (e) {
            // ignore
        }
        return t;
    }

    function getStoredTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function getPreferredTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    function initTheme() {
        const stored = getStoredTheme();
        const theme = stored || getPreferredTheme();
        applyTheme(theme);
    }

    window.setTheme = (theme) => applyTheme(theme);
    window.getTheme = () => document.documentElement.dataset.theme || 'light';
    window.toggleTheme = () => applyTheme(window.getTheme() === 'dark' ? 'light' : 'dark');

    initTheme();
})();
