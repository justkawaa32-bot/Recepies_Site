const recipeForm = document.getElementById('recipeForm');
const formMsg = document.getElementById('formMsg');
const imageInput = document.getElementById('image');
const imagePreview = document.getElementById('imagePreview');
const deleteBtn = document.getElementById('deleteBtn');

function showPreviewUrl(url) {
    if (!url) {
        imagePreview.textContent = 'Выберите изображение';
        return;
    }
    imagePreview.innerHTML = `<img src="${url}" alt="Предпросмотр">`;
}

async function loadRecipe(recipeId) {
    const res = await fetch(`/api/recipes/${recipeId}`, {
        credentials: 'include'
    });
    if (!res.ok) {
        window.location.href = '/';
        return;
    }
    const data = await res.json();

    document.getElementById('title').value = data.title || '';
    document.getElementById('category').value = data.category || '';
    document.getElementById('time_min').value = data.time_min || '';
    document.getElementById('level').value = data.level || '';
    document.getElementById('ingredients').value = (data.ingredients || []).join('\n');
    document.getElementById('steps').value = (data.steps || []).join('\n');
    showPreviewUrl(data.img || '/static/images/placeholder.svg');
}

if (imageInput) {
    imageInput.addEventListener('change', () => {
        const file = imageInput.files[0];
        if (!file) {
            return;
        }
        const url = URL.createObjectURL(file);
        showPreviewUrl(url);
    });
}

if (recipeForm) {
    recipeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        formMsg.textContent = '';
        formMsg.style.color = '#c0392b';

        const recipeId = recipeForm.dataset.recipeId;
        const formData = new FormData(recipeForm);

        try {
            const res = await fetch(`/api/recipes/${recipeId}` , {
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            const data = await res.json();
            if (!res.ok || data.ok === false) {
                formMsg.textContent = data.error || 'Ошибка сохранения';
                return;
            }
            formMsg.style.color = '#2e7d32';
            formMsg.textContent = 'Изменения сохранены';
        } catch (e) {
            formMsg.textContent = 'Ошибка соединения с сервером';
        }
    });
}

if (deleteBtn && recipeForm) {
    deleteBtn.addEventListener('click', async () => {
        const recipeId = recipeForm.dataset.recipeId;
        const confirmed = window.confirm('Удалить рецепт?');
        if (!confirmed) {
            return;
        }
        try {
            const res = await fetch(`/api/recipes/${recipeId}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            const data = await res.json();
            if (!res.ok || data.ok === false) {
                formMsg.textContent = data.error || 'Ошибка удаления';
                return;
            }
            window.location.href = '/';
        } catch (e) {
            formMsg.textContent = 'Ошибка соединения с сервером';
        }
    });
}

if (recipeForm) {
    loadRecipe(recipeForm.dataset.recipeId);
}
