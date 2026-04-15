let mode = 'login'; // login | register

const title = document.getElementById('title');
const btn = document.getElementById('actionBtn');
const msg = document.getElementById('msg');
const switchText = document.getElementById('switchText');
const switchLink = document.getElementById('switchLink');

switchLink.onclick = () => {
    if (mode === 'login') {
        mode = 'register';
        title.textContent = 'Регистрация';
        btn.textContent = 'Зарегистрироваться';
        switchText.textContent = 'Уже есть аккаунт?';
        switchLink.textContent = 'Войти';
        msg.textContent = '';
    } else {
        mode = 'login';
        title.textContent = 'Вход';
        btn.textContent = 'Войти';
        switchText.textContent = 'Нет аккаунта?';
        switchLink.textContent = 'Регистрация';
        msg.textContent = '';
    }
};

btn.onclick = async () => {
    msg.style.color = 'red';
    msg.textContent = '';
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
        msg.textContent = 'Заполните все поля';
        return;
    }

    try {
        const res = await fetch(
            mode === 'login' ? '/api/login' : '/api/register',
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ username, password })
            }
        );

        const data = await res.json();

        if (!res.ok || data.ok === false) {
            msg.textContent = data.error || 'Неверный логин или пароль';
            return;
        }

        if (mode === 'login') {
            location.href = '/';
        } else {
            msg.style.color = 'green';
            msg.textContent = 'Регистрация успешна, можно войти';
        }

    } catch (e) {
        msg.textContent = 'Ошибка соединения с сервером';
    }
};

async function checkAuth() {
    try {
        const res = await fetch('/api/whoami', {
            credentials: 'include'
        });
        const data = await res.json();

        if (data.ok) {
            window.location.href = '/';
        }
    } catch (e) {
        console.log('Ошибка проверки авторизации');
    }
}

checkAuth();
