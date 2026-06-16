document.getElementById('regButton').addEventListener('click', async () => {
    const data = {
        login: document.getElementById('login').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        first_name: document.getElementById('first_name').value,
        second_name: document.getElementById('second_name').value,
        middle_name: document.getElementById('middle_name').value
    };

    // Простая проверка пароля
    if (data.password !== document.getElementById('password_confirm').value) {
        alert("Пароли не совпадают!");
        return;
    }

    // Определяем эндпоинт в зависимости от роли
    const role = document.getElementById('role').value;
    const endpoint = role === '/student' ? '/students' : '/teachers';

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (response.ok) {
            alert("Успешно! Аккаунт создан.");
            window.location.href = "1.html"; // Переход после успеха
        } else {
            alert("Ошибка: " + (result.detail || "Неизвестная ошибка"));
        }
    } catch (err) {
        alert("Ошибка сети или сервера");
    }
});