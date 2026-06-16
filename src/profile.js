document.addEventListener('DOMContentLoaded', async () => {
    const studentNameSpan = document.getElementById('student-name');
    const logoutBtn = document.getElementById('logout-btn');
    
    async function loadProfile() {
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
            
            document.getElementById('profile-login').textContent = profile.login || '—';
            document.getElementById('profile-email').textContent = profile.email || '—';
            document.getElementById('profile-group').textContent = profile.group_number || 'Не назначена';
            document.getElementById('profile-first-name').textContent = profile.first_name || '—';
            document.getElementById('profile-second-name').textContent = profile.second_name || '—';
            document.getElementById('profile-middle-name').textContent = profile.middle_name || '—';
            
            const fullName = `${profile.second_name} ${profile.first_name}`;
            studentNameSpan.textContent = fullName || 'Студент';
            
        } catch (err) {
            console.error('Ошибка:', err);
            studentNameSpan.textContent = 'Ошибка загрузки';
            const infoDiv = document.getElementById('profile-info');
            infoDiv.innerHTML = '<div style="color: #a89b93; text-align: center; padding: 20px;">❌ Ошибка загрузки профиля. Возможно, сессия истекла. <a href="1.html" style="color: #7a2d3a;">Войти заново</a></div>';
        }
    }
async function updateNavForAdmin() {
    try {
        const response = await fetch('/api/profile', {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.ok && data.profile && data.profile.role === 'admin') {
            const nav = document.querySelector('.nav');
            if (nav && !document.querySelector('a[href="12.html"]')) {
                const adminLink = document.createElement('a');
                adminLink.href = '12.html';
                adminLink.textContent = 'АДМИНКА';
                // Вставить перед выходом
                const logoutLink = nav.querySelector('a[href="1.html"]');
                if (logoutLink) {
                    nav.insertBefore(adminLink, logoutLink);
                } else {
                    nav.appendChild(adminLink);
                }
            }
        }
    } catch (err) {
        console.error('Ошибка:', err);
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
    
    await loadProfile();
    
    await updateNavForAdmin();
});