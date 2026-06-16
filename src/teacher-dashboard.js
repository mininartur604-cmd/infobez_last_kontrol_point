document.addEventListener('DOMContentLoaded', async () => {
    const teacherNameSpan = document.getElementById('teacher-name');
    const logoutBtn = document.getElementById('logout-btn');
    
    async function loadTeacherProfile() {
        try {
            const response = await fetch('/api/profile', {
                credentials: 'include'
            });
            
            if (!response.ok) {
                if (response.status === 401 || response.status === 403) {
                    window.location.href = '1.html';
                    return;
                }
                throw new Error('Ошибка загрузки профиля');
            }
            
            const data = await response.json();
            
            if (!data.ok || !data.profile) {
                throw new Error('Некорректный ответ сервера');
            }
            
            const profile = data.profile;
            
            // Проверяем, что пользователь действительно учитель
            if (profile.role !== 'teacher' && profile.role !== 'admin') {
                alert('У вас нет доступа к этой странице');
                window.location.href = '3.html';
                return;
            }
            
            const fullName = `${profile.second_name} ${profile.first_name}`;
            teacherNameSpan.textContent = fullName || 'Преподаватель';
            
        } catch (err) {
            console.error('Ошибка:', err);
            teacherNameSpan.textContent = 'Ошибка загрузки';
            
            // Показываем сообщение об ошибке
            const gridDiv = document.querySelector('.grid');
            if (gridDiv) {
                gridDiv.innerHTML = '<div style="color: #a89b93; text-align: center; padding: 40px;">❌ Ошибка загрузки профиля. Возможно, сессия истекла. <a href="1.html" style="color: #7a2d3a;">Войти заново</a></div>';
            }
        }
    }
    
    async function logout() {
        try {
            const response = await fetch('/logout', {
                method: 'POST',
                credentials: 'include'
            });
            
            if (response.ok) {
                window.location.href = '1.html';
            } else {
                window.location.href = '1.html';
            }
        } catch (err) {
            console.error('Ошибка:', err);
            window.location.href = '1.html';
        }
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }
    
    await loadTeacherProfile();
});