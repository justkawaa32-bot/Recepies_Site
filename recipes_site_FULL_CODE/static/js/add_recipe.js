const recipeForm = document.getElementById('recipeForm');
const formMsg = document.getElementById('formMsg');
const imageInput = document.getElementById('image');
const imagePreview = document.getElementById('imagePreview');

async function checkAuth() {
    try {
        const res = await fetch('/api/whoami', {
            credentials: 'include'
        });
        const data = await res.json();
        if (!data.ok) {
            window.location.href = '/auth';
        }
    } catch (e) {
        window.location.href = '/auth';
    }
}

function showPreview(file) {
    if (!file) {
        imagePreview.textContent = 'Выберите изображение';
        return;
    }
    const url = URL.createObjectURL(file);
    imagePreview.innerHTML = `<img src="${url}" alt="Предпросмотр">`;
}

if (imageInput) {
    imageInput.addEventListener('change', () => {
        showPreview(imageInput.files[0]);
    });
}

if (recipeForm) {
    recipeForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        formMsg.textContent = '';
        formMsg.style.color = '#c0392b';

        const formData = new FormData(recipeForm);
        try {
            const res = await fetch('/api/recipes', {
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            const data = await res.json();
            if (!res.ok || data.ok === false) {
                formMsg.textContent = data.error || 'Ошибка сохранения';
                return;
            }
            window.location.href = '/';
        } catch (e) {
            formMsg.textContent = 'Ошибка соединения с сервером';
        }
    });
}

checkAuth();
