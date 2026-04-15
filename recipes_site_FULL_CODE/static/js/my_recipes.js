function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

function renderSkeletonCards(container, count = 6) {
    if (!container) return;
    const amount = Math.max(1, count);
    container.innerHTML = '';
    for (let i = 0; i < amount; i += 1) {
        const card = document.createElement('div');
        card.className = 'skeleton-card';
        card.innerHTML = `
            <div class="skeleton-img skeleton-shimmer"></div>
            <div class="skeleton-content">
                <div class="skeleton-line title skeleton-shimmer"></div>
                <div class="skeleton-line meta skeleton-shimmer"></div>
                <div class="skeleton-badges">
                    <div class="skeleton-badge skeleton-shimmer"></div>
                    <div class="skeleton-badge skeleton-shimmer"></div>
                </div>
            </div>
        `;
        container.appendChild(card);
    }
}

async function loadMyRecipes() {
    const container = document.getElementById('myRecipes');
    if (!container) return;
    renderSkeletonCards(container, 7);
    try {
        const res = await fetch('/api/my-recipes', { credentials: 'include' });
        if (res.status === 401) {
            window.location.href = '/auth';
            return;
        }
        const data = await res.json();
        container.innerHTML = '';
        container.classList.remove('fade-in-list');
        void container.offsetWidth;
        container.classList.add('fade-in-list');
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<p>Пока нет ваших рецептов.</p>';
            return;
        }
        data.forEach((r) => {
            const card = document.createElement('a');
            card.className = 'recipe-card';
            card.href = `/recipe/${r.id}`;
            const imgSrc = r.img || '/static/images/placeholder.svg';
            card.innerHTML = `
                <img src="${imgSrc}" alt="${escapeHtml(r.title)}">
                <div class="content">
                    <h3>${escapeHtml(r.title)}</h3>
                    <div class="meta">${escapeHtml(r.username || '—')}</div>
                    <div class="badges">
                        <span class="badge">${escapeHtml(r.category || 'Без категории')}</span>
                        <span class="badge">${r.time_min || 0} мин</span>
                        <span class="badge">${escapeHtml(r.level || '—')}</span>
                        <span class="badge">★ ${(Number(r.avg_rating) || 0).toFixed(1)} (${r.reviews_count || 0})</span>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        container.innerHTML = '<p>Ошибка загрузки рецептов.</p>';
    }
}

loadMyRecipes();
