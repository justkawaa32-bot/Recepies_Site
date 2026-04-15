let currentPage = 1;
const PAGE_SIZE = 21;
const MAX_CARDS_PER_PAGE = 21;
const MIN_PAGES = 20;

function buildQueryParams() {
    const q = (document.getElementById('searchQuery')?.value || '').trim();
    const category = (document.getElementById('filterCategory')?.value || '').trim();
    const area = (document.getElementById('filterArea')?.value || '').trim();
    const ingredient = (document.getElementById('filterIngredient')?.value || '').trim();

    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (category) params.set('category', category);
    if (area) params.set('area', area);
    if (ingredient) params.set('ingredient', ingredient);
    params.set('page', String(currentPage));
    params.set('page_size', String(PAGE_SIZE));
    return params.toString();
}

async function fetchMealdbRecipes(limit = MAX_CARDS_PER_PAGE) {
    const q = (document.getElementById('searchQuery')?.value || '').trim();
    const MEALDB_LIMIT = Math.max(0, Number(limit) || 0);
    if (MEALDB_LIMIT === 0) return [];
    try {
        if (q.length >= 2) {
            const query = buildQueryParams();
            const res = await fetch(`/api/mealdb/search?${query}`, { credentials: 'include' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.ok === false) return [];
            return Array.isArray(data.recipes) ? data.recipes.slice(0, MEALDB_LIMIT) : [];
        }
        const hasExtraFilters = Boolean(
            (document.getElementById('filterCategory')?.value || '').trim() ||
            (document.getElementById('filterArea')?.value || '').trim() ||
            (document.getElementById('filterIngredient')?.value || '').trim()
        );
        if (hasExtraFilters) {
            const query = buildQueryParams();
            const res = await fetch(`/api/mealdb/search?${query}`, { credentials: 'include' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.ok === false) return [];
            return Array.isArray(data.recipes) ? data.recipes.slice(0, MEALDB_LIMIT) : [];
        }
        const randomCalls = Array.from({ length: MEALDB_LIMIT }, () => fetch('/api/mealdb/random', { credentials: 'include' })
            .then(r => r.json().catch(() => ({})))
            .catch(() => ({ ok: false })));
        const results = await Promise.all(randomCalls);
        const recipes = [];
        results.forEach(item => {
            if (item && item.ok && Array.isArray(item.recipes) && item.recipes[0]) {
                recipes.push(item.recipes[0]);
            }
        });
        const seen = new Set();
        return recipes.filter(r => {
            const id = String(r.meal_id || r.id || '');
            if (!id || seen.has(id)) return false;
            seen.add(id);
            return true;
        }).slice(0, MEALDB_LIMIT);
    } catch (e) {
        return [];
    }
}

function renderSkeletonCards(container, count = 8) {
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

async function loadRecipes() {
    try {
        const container = document.getElementById('recipes');
        renderSkeletonCards(container, 9);
        const mealdbItems = await fetchMealdbRecipes(MAX_CARDS_PER_PAGE);
        container.innerHTML = '';
        container.classList.remove('fade-in-list');
        void container.offsetWidth;
        container.classList.add('fade-in-list');
        if (mealdbItems.length === 0) {
            container.innerHTML = '<p>Рецептов пока нет.</p>';
        }
        let allIndex = 0;
        mealdbItems.forEach(r => {
            const card = document.createElement('a');
            card.className = 'recipe-card';
            card.href = `/mealdb/${encodeURIComponent(r.meal_id)}`;
            card.style.animationDelay = `${allIndex * 40}ms`;
            card.classList.add('reveal');
            const imgSrc = r.img || '/static/images/placeholder.svg';
            card.innerHTML = `
                <img src="${imgSrc}" alt="${escapeHtml(r.title || 'TheMealDB')}">
                <div class="content">
                    <h3>${escapeHtml(r.title || 'TheMealDB')}</h3>
                    <div class="meta">${escapeHtml(r.subtitle || 'TheMealDB')}</div>
                    <div class="badges">
                        <span class="badge">TheMealDB</span>
                        ${r.category ? `<span class="badge">${escapeHtml(r.category)}</span>` : ''}
                        ${r.area ? `<span class="badge">${escapeHtml(r.area)}</span>` : ''}
                    </div>
                </div>
            `;
            container.appendChild(card);
            allIndex += 1;
        });
        renderPagination({
            page: currentPage,
            total_pages: MIN_PAGES,
            total_count: 0,
        });
    } catch (e) {
        document.getElementById('recipes').innerHTML = '<p>Ошибка загрузки рецептов</p>';
        const pagination = document.getElementById('recipesPagination');
        if (pagination) pagination.innerHTML = '';
    }
}

function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

loadRecipes();

function debounce(fn, waitMs) {
    let t = null;
    return (...args) => {
        if (t) clearTimeout(t);
        t = setTimeout(() => fn(...args), waitMs);
    };
}

function loadFromFirstPage() {
    currentPage = 1;
    loadRecipes();
}

const debouncedLoad = debounce(loadFromFirstPage, 250);

function bindFilters() {
    const q = document.getElementById('searchQuery');
    const category = document.getElementById('filterCategory');
    const area = document.getElementById('filterArea');
    const ingredient = document.getElementById('filterIngredient');
    const reset = document.getElementById('resetFilters');

    if (q) q.addEventListener('input', debouncedLoad);
    if (category) category.addEventListener('input', debouncedLoad);
    if (area) area.addEventListener('input', debouncedLoad);
    if (ingredient) ingredient.addEventListener('input', debouncedLoad);
    if (reset) {
        reset.addEventListener('click', () => {
            if (q) q.value = '';
            if (category) category.value = '';
            if (area) area.value = '';
            if (ingredient) ingredient.value = '';
            currentPage = 1;
            loadFromFirstPage();
        });
    }
}

bindFilters();

function renderPagination(payload) {
    const wrap = document.getElementById('recipesPagination');
    if (!wrap) return;
    const apiTotalPages = Number(payload?.total_pages || 1);
    const totalPages = Math.max(MIN_PAGES, apiTotalPages);
    const page = Number(payload?.page || currentPage || 1);
    const totalCount = Number(payload?.total_count || 0);
    currentPage = page;

    if (totalCount === 0 && totalPages <= 1) {
        wrap.innerHTML = '';
        return;
    }

    const prevDisabled = page <= 1 ? 'disabled' : '';
    const nextDisabled = page >= totalPages ? 'disabled' : '';
    wrap.innerHTML = `
        <button type="button" data-page="${page - 1}" ${prevDisabled}>← Назад</button>
        <span>Страница ${page} из ${totalPages}${totalCount ? ` • ${totalCount} локальных рецептов` : ''}</span>
        <button type="button" data-page="${page + 1}" ${nextDisabled}>Вперёд →</button>
    `;

    wrap.querySelectorAll('button[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
            const next = Number(btn.dataset.page || page);
            if (next < 1 || next > totalPages || next === currentPage) {
                return;
            }
            currentPage = next;
            loadRecipes();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

function updateFavButton(btn, active) {
    btn.dataset.active = active ? '1' : '0';
    const span = btn.querySelector('span');
    if (span) span.textContent = active ? '❤' : '♡';
}

function bindFavoriteButtons() {
    document.querySelectorAll('.fav-btn').forEach(btn => {
        if (btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            const recipeId = btn.dataset.recipeId;
            const isActive = btn.dataset.active === '1';
            updateFavButton(btn, !isActive);
            try {
                const res = await fetch(`/api/favorites/${recipeId}`, {
                    method: isActive ? 'DELETE' : 'POST',
                    credentials: 'include'
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || data.ok === false) {
                    updateFavButton(btn, isActive);
                    alert(data.error || 'Ошибка избранного');
                    return;
                }
                // пересоберём списки, чтобы избранное синхронизировалось везде
                loadRecipes();
            } catch (err) {
                updateFavButton(btn, isActive);
                alert('Ошибка соединения с сервером');
            }
        });
    });
}
