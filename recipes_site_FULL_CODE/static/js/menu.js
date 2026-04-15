const menuButton = document.getElementById('menuButton');
const menuPanel = document.getElementById('menuPanel');
const menuBackdrop = document.getElementById('menuBackdrop');
const menuContent = document.getElementById('menuContent');

function openMenu() {
    menuPanel.classList.add('open');
    menuBackdrop.classList.add('open');
}

function closeMenu() {
    menuPanel.classList.remove('open');
    menuBackdrop.classList.remove('open');
}

async function logout() {
    try {
        const res = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        if (res.ok) {
            window.location.href = '/';
            return;
        }
    } catch (e) {
        // fall through
    }
    alert('Ошибка выхода');
}

function userRow(username, role) {
    const safeName = escapeHtml(username || 'Гость');
    const roleLabel = role ? ` (${escapeHtml(role)})` : '';
    return `
        <div class="menu-user">
            <span class="menu-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="8" r="4"></circle>
                    <path d="M4 20c0-4 4-6 8-6s8 2 8 6"></path>
                </svg>
            </span>
            <span>${safeName}${roleLabel}</span>
        </div>
    `;
}

function menuLink(href, label) {
    return `<a class="menu-link" href="${href}">${escapeHtml(label)}</a>`;
}

function menuButtonAction(label, onClickName) {
    return `<button class="menu-link" type="button" data-action="${onClickName}">${escapeHtml(label)}</button>`;
}

function menuThemeToggle() {
    const current = (window.getTheme && window.getTheme()) || (document.documentElement.dataset.theme || 'light');
    const checked = current === 'dark' ? 'checked' : '';
    return `
        <div class="menu-theme">
            <label class="menu-theme-row">
                <span>Тёмная тема</span>
                <input id="themeToggle" type="checkbox" ${checked}>
            </label>
        </div>
    `;
}

function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

async function refreshMenu() {
    let html = '';
    try {
        const res = await fetch('/api/whoami', { credentials: 'include' });
        const data = await res.json();
        if (data.ok) {
            html += userRow(data.user.username, data.user.role);
            html += menuLink('/', 'Главная');
            html += menuLink('/my-recipes', 'Мои рецепты');
            if (data.user.role === 'admin') {
                html += menuLink('/admin/users', 'Админка');
            }
            html += menuThemeToggle();
            html += menuButtonAction('Выйти', 'logout');
        } else {
            html += userRow('Гость');
            html += menuLink('/', 'Главная');
            html += menuThemeToggle();
            html += menuLink('/auth', 'Войти или зарегистрироваться');
        }
    } catch (e) {
        html += userRow('Гость');
        html += menuLink('/', 'Главная');
        html += menuThemeToggle();
        html += menuLink('/auth', 'Войти или зарегистрироваться');
    }

    menuContent.innerHTML = html;

    const themeToggle = menuContent.querySelector('#themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('change', () => {
            const next = themeToggle.checked ? 'dark' : 'light';
            if (window.setTheme) {
                window.setTheme(next);
            } else {
                document.documentElement.dataset.theme = next;
            }
        });
    }

    const logoutBtn = menuContent.querySelector('[data-action="logout"]');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            closeMenu();
            logout();
        });
    }
}

if (menuButton) {
    menuButton.addEventListener('click', () => {
        refreshMenu();
        openMenu();
    });
}

if (menuBackdrop) {
    menuBackdrop.addEventListener('click', closeMenu);
}

window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeMenu();
    }
});
