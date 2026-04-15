function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

function formatStars(avg) {
    const v = Math.max(0, Math.min(5, Number(avg) || 0));
    const full = Math.round(v);
    return '★'.repeat(full) + '☆'.repeat(5 - full);
}

function setRatingUI(avg, count) {
    const starsEl = document.getElementById('ratingStars');
    const textEl = document.getElementById('ratingText');
    if (starsEl) starsEl.textContent = formatStars(avg);
    if (textEl) textEl.textContent = `${(Number(avg) || 0).toFixed(1)} (${count || 0})`;
}

async function whoami() {
    try {
        const res = await fetch('/api/whoami', { credentials: 'include' });
        return await res.json();
    } catch (e) {
        return { ok: false };
    }
}

function renderReviews(reviews) {
    const list = document.getElementById('reviewsList');
    if (!list) return;
    if (!Array.isArray(reviews) || reviews.length === 0) {
        list.innerHTML = '<div class="review-item">Пока нет отзывов.</div>';
        return;
    }
    list.innerHTML = reviews.map(r => {
        const headLeft = `${escapeHtml(r.username || '—')} • ${'★'.repeat(r.rating || 0)}${'☆'.repeat(5 - (r.rating || 0))}`;
        const updated = r.updated_at ? new Date(r.updated_at).toLocaleString() : '';
        const text = r.text ? escapeHtml(r.text) : '—';
        return `
            <div class="review-item">
                <div class="review-head">
                    <div>${headLeft}</div>
                    <div>${escapeHtml(updated)}</div>
                </div>
                <div class="review-text">${text}</div>
            </div>
        `;
    }).join('');
}

async function loadReviews(recipeId) {
    const res = await fetch(`/api/recipes/${recipeId}/reviews`, { credentials: 'include' });
    if (!res.ok) {
        return;
    }
    const data = await res.json();
    if (!data.ok) return;
    setRatingUI(data.avg_rating, data.reviews_count);
    renderReviews(data.reviews);

    const form = document.getElementById('reviewForm');
    const myRating = document.getElementById('myRating');
    const myText = document.getElementById('myText');
    const deleteBtn = document.getElementById('deleteReviewBtn');

    if (form) form.style.display = 'block';
    if (data.my_review) {
        if (myRating) myRating.value = String(data.my_review.rating || 5);
        if (myText) myText.value = data.my_review.text || '';
        if (deleteBtn) deleteBtn.disabled = false;
    } else {
        if (deleteBtn) deleteBtn.disabled = true;
    }
}

async function saveReview(recipeId) {
    const msg = document.getElementById('reviewMsg');
    const myRating = document.getElementById('myRating');
    const myText = document.getElementById('myText');
    if (msg) {
        msg.style.color = '#c0392b';
        msg.textContent = '';
    }

    const rating = Number(myRating?.value || 5);
    const text = (myText?.value || '').trim();

    const res = await fetch(`/api/recipes/${recipeId}/reviews`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating, text })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
        if (msg) msg.textContent = data.error || 'Ошибка сохранения';
        return;
    }
    if (msg) {
        msg.style.color = '#2e7d32';
        msg.textContent = 'Сохранено';
    }
    await loadReviews(recipeId);
}

async function deleteReview(recipeId) {
    const msg = document.getElementById('reviewMsg');
    if (msg) {
        msg.style.color = '#c0392b';
        msg.textContent = '';
    }
    const confirmed = window.confirm('Удалить ваш отзыв?');
    if (!confirmed) return;

    const res = await fetch(`/api/recipes/${recipeId}/reviews`, {
        method: 'DELETE',
        credentials: 'include'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
        if (msg) msg.textContent = data.error || 'Ошибка удаления';
        return;
    }
    const myRating = document.getElementById('myRating');
    const myText = document.getElementById('myText');
    if (myRating) myRating.value = '5';
    if (myText) myText.value = '';
    if (msg) {
        msg.style.color = '#2e7d32';
        msg.textContent = 'Удалено';
    }
    await loadReviews(recipeId);
}

async function initReviews() {
    const recipeId = window.__RECIPE_ID__;
    if (!recipeId) return;

    setRatingUI(window.__RECIPE_AVG__ || 0, window.__RECIPE_REVIEWS_COUNT__ || 0);

    const me = await whoami();
    const form = document.getElementById('reviewForm');
    const list = document.getElementById('reviewsList');
    if (!me.ok) {
        if (form) form.style.display = 'none';
        if (list) list.innerHTML = '<div class="review-item">Войдите, чтобы оставить отзыв.</div>';
        await loadReviews(recipeId);
        return;
    }

    const saveBtn = document.getElementById('saveReviewBtn');
    const deleteBtn = document.getElementById('deleteReviewBtn');
    if (saveBtn) saveBtn.addEventListener('click', () => saveReview(recipeId));
    if (deleteBtn) deleteBtn.addEventListener('click', () => deleteReview(recipeId));

    await loadReviews(recipeId);
}

initReviews();
