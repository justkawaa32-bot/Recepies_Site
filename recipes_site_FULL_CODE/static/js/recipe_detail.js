const deleteBtn = document.getElementById('deleteBtn');

if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
        const recipeId = deleteBtn.dataset.recipeId;
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
                alert(data.error || 'Ошибка удаления');
                return;
            }
            window.location.href = '/';
        } catch (e) {
            alert('Ошибка соединения с сервером');
        }
    });
}
