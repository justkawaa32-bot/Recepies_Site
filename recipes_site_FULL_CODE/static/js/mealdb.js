function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

async function fetchJson(url) {
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json().catch(() => ({}));
    return { res, data };
}

function renderMealdbCards(container, recipes) {
    if (!container) return;
    if (!Array.isArray(recipes) || recipes.length === 0) {
        container.innerHTML = '<p>Ничего не найдено в TheMealDB.</p>';
        return;
    }
    container.innerHTML = '';
    recipes.forEach((r, idx) => {
        const card = document.createElement('a');
        card.className = 'recipe-card reveal';
        card.href = `/mealdb/${encodeURIComponent(r.meal_id)}`;
        card.style.animationDelay = `${idx * 35}ms`;
        const imgSrc = r.img || '/static/images/placeholder.svg';
        card.innerHTML = `
            <img src="${imgSrc}" alt="${escapeHtml(r.title)}">
            <div class="content">
                <h3>${escapeHtml(r.title)}</h3>
                <div class="meta">${escapeHtml(r.subtitle || 'TheMealDB')}</div>
                <div class="badges">
                    <span class="badge">TheMealDB</span>
                    ${r.category ? `<span class="badge">${escapeHtml(r.category)}</span>` : ''}
                    ${r.area ? `<span class="badge">${escapeHtml(r.area)}</span>` : ''}
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

async function initMealdbOnIndex() {
    const container = document.getElementById('mealdbRecipes');
    if (!container) return;

    container.innerHTML = '<p>Загрузка из TheMealDB…</p>';
    const { res, data } = await fetchJson('/api/mealdb/random');
    if (!res.ok || data.ok === false) {
        container.innerHTML = '<p>TheMealDB временно недоступен.</p>';
        return;
    }
    renderMealdbCards(container, data.recipes || []);

    const qInput = document.getElementById('searchQuery');
    if (qInput) {
        let t = null;
        qInput.addEventListener('input', () => {
            if (t) clearTimeout(t);
            t = setTimeout(async () => {
                const q = (qInput.value || '').trim();
                if (q.length < 2) {
                    // keep random on empty/too short
                    const r2 = await fetchJson('/api/mealdb/random');
                    if (r2.res.ok && r2.data.ok) renderMealdbCards(container, r2.data.recipes || []);
                    return;
                }
                const { res: sRes, data: sData } = await fetchJson(`/api/mealdb/search?q=${encodeURIComponent(q)}`);
                if (!sRes.ok || sData.ok === false) {
                    container.innerHTML = '<p>TheMealDB временно недоступен.</p>';
                    return;
                }
                renderMealdbCards(container, sData.recipes || []);
            }, 350);
        });
    }
}

async function initMealdbDetailPage() {
    const mealId = window.__MEAL_ID__;
    if (!mealId) return;

    const { res, data } = await fetchJson(`/api/mealdb/${encodeURIComponent(mealId)}`);
    if (!res.ok || data.ok === false) {
        document.getElementById('title').textContent = 'Рецепт не найден';
        return;
    }
    const r = data.recipe;
    document.title = `${r.title} — TheMealDB`;
    const hero = document.getElementById('hero');
    if (hero) {
        hero.innerHTML = `<img src="${escapeHtml(r.img || '')}" alt="${escapeHtml(r.title)}">`;
    }
    document.getElementById('title').textContent = r.title || '—';
    document.getElementById('meta').textContent = r.subtitle || 'TheMealDB';

    const links = document.getElementById('links');
    if (links) {
        let html = '';
        if (r.youtube) html += `<a href="${escapeHtml(r.youtube)}" target="_blank" rel="noreferrer">YouTube</a>`;
        if (r.source) html += `<a href="${escapeHtml(r.source)}" target="_blank" rel="noreferrer">Источник</a>`;
        links.innerHTML = html;
    }

    const ing = document.getElementById('ingredients');
    ing.innerHTML = (r.ingredients || []).map(i => `<li>${escapeHtml(i)}</li>`).join('') || '<li>—</li>';
    const steps = document.getElementById('steps');
    steps.innerHTML = (r.steps || []).map(s => `<li>${escapeHtml(s)}</li>`).join('') || '<li>—</li>';
}

initMealdbOnIndex();
initMealdbDetailPage();

