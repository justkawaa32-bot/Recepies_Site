const usersBody = document.getElementById('usersBody');
const msg = document.getElementById('msg');

async function loadUsers() {
    msg.textContent = '';
    try {
        const res = await fetch('/api/admin/users', { credentials: 'include' });
        const data = await res.json();
        if (!res.ok || !data.ok) {
            window.location.href = '/';
            return;
        }

        usersBody.innerHTML = '';
        data.users.forEach(user => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${escapeHtml(user.username)}</td>
                <td>
                    <select data-user-id="${user.id}">
                        <option value="user">user</option>
                        <option value="moderator">moderator</option>
                        <option value="admin">admin</option>
                    </select>
                </td>
                <td><button data-save-id="${user.id}">Сохранить</button></td>
            `;
            const select = tr.querySelector('select');
            select.value = user.role || 'user';
            const button = tr.querySelector('button');
            button.addEventListener('click', () => updateRole(user.id, select.value));
            usersBody.appendChild(tr);
        });
    } catch (e) {
        msg.textContent = 'Ошибка загрузки пользователей';
    }
}

function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

async function updateRole(userId, role) {
    msg.textContent = '';
    try {
        const res = await fetch(`/api/admin/users/${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ role })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
            msg.textContent = data.error || 'Ошибка сохранения';
            return;
        }
        msg.style.color = '#2e7d32';
        msg.textContent = 'Роль обновлена';
    } catch (e) {
        msg.textContent = 'Ошибка соединения с сервером';
    }
}

loadUsers();
