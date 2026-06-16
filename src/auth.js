document.getElementById('loginBtn').addEventListener('click', async () => {
    const login = document.getElementById('login').value;
    const password = document.getElementById('password').value;
    
    const data = { login, password };

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            // Тестовый алерт перед редиректом
            alert(`Роль: ${result.role}. Сейчас будет редирект!`);
            
            // Принудительный редирект
            if (result.role === 'admin') {
                window.location.href = '12.html';
            } else if (result.role === 'teacher') {
                window.location.href = '11.html';
            } else {
                window.location.href = '3.html';
            }
        } else {
            alert("Ошибка входа");
        }
    } catch (err) {
        alert("Ошибка: " + err);
    }
});