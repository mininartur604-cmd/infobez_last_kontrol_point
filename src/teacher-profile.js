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
            
            // Проверка что это учитель или админ
            if (profile.role !== 'teacher' && profile.role !== 'admin') {
                alert('У вас нет доступа к этой странице');
                window.location.href = '3.html';
                return;
            }
            
            // Заполняем данные
            document.getElementById('profile-login').textContent = profile.login || '—';
            document.getElementById('profile-email').textContent = profile.email || '—';
            document.getElementById('profile-first-name').textContent = profile.first_name || '—';
            document.getElementById('profile-second-name').textContent = profile.second_name || '—';
            document.getElementById('profile-middle-name').textContent = profile.middle_name || '—';
            
            // Отображаем группы учителя
            let groupsText = '—';
            if (profile.group_number) {
                if (Array.isArray(profile.group_number)) {
                    groupsText = profile.group_number.join(', ');
                } else {
                    groupsText = profile.group_number;
                }
            }
            document.getElementById('profile-groups').textContent = groupsText;
            
            // Обновляем имя в шапке
            const fullName = `${profile.second_name} ${profile.first_name}`;
            teacherNameSpan.textContent = fullName || 'Преподаватель';
            
            // Если админ зашел в учительский профиль
            if (profile.role === 'admin') {
                teacherNameSpan.textContent += ' (админ)';
                const adminNote = document.createElement('div');
                adminNote.style.cssText = 'margin-top: 15px; padding: 10px; background: rgba(92, 35, 45, 0.3); border-radius: 5px; text-align: center;';
                adminNote.innerHTML = '👑 Вы вошли как администратор. <a href="12.html" style="color: #7a2d3a;">Перейти в админ-панель</a>';
                document.querySelector('.profile').appendChild(adminNote);
            }
            
        } catch (err) {
            console.error('Ошибка:', err);
            teacherNameSpan.textContent = 'Ошибка загрузки';
            const infoDiv = document.getElementById('profile-info');
            infoDiv.innerHTML = '<div style="color: #a89b93; text-align: center; padding: 20px;">❌ Ошибка загрузки профиля. Возможно, сессия истекла. <a href="1.html" style="color: #7a2d3a;">Войти заново</a></div>';
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