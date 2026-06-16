document.addEventListener('DOMContentLoaded', async () => {
    const teacherNameSpan = document.getElementById('teacher-name');
    const tasksListDiv = document.getElementById('tasks-list');
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
            
            if (profile.role !== 'teacher' && profile.role !== 'admin') {
                alert('У вас нет доступа к этой странице');
                window.location.href = '3.html';
                return;
            }
            
            const fullName = `${profile.second_name} ${profile.first_name}`;
            teacherNameSpan.textContent = fullName || 'Преподаватель';
            
            return profile;
            
        } catch (err) {
            console.error('Ошибка:', err);
            teacherNameSpan.textContent = 'Ошибка загрузки';
            return null;
        }
    }
    
    async function loadTeacherTasks() {
        try {
            // Получаем все задания, которые создал учитель
            // Или можно получить задания по группам учителя
            const response = await fetch('/api/teacher/tasks', {
                credentials: 'include'
            });
            
            if (!response.ok) {
                if (response.status === 404) {
                    tasksListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">📭 У вас пока нет созданных заданий</div>';
                    return;
                }
                throw new Error('Ошибка загрузки заданий');
            }
            
            const data = await response.json();
            
            if (!data.ok || !data.tasks) {
                tasksListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">📭 У вас пока нет созданных заданий</div>';
                return;
            }
            
            const tasks = data.tasks;
            
            if (tasks.length === 0) {
                tasksListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">📭 У вас пока нет созданных заданий</div>';
                return;
            }
            
            // Отображаем задания
            tasksListDiv.innerHTML = '';
            
            for (const task of tasks) {
                // Получаем количество студентов, сдавших задание
                const submissionsCount = await getSubmissionsCount(task.id);
                
                const taskEl = document.createElement('a');
                taskEl.className = 'task';
                taskEl.href = `8.html?task=${task.id}`;
                
                // Форматируем дедлайн
                let deadlineHtml = '';
                if (task.deadline) {
                    const deadline = new Date(task.deadline);
                    deadlineHtml = `<div class="task-deadline">⏰ Дедлайн: ${deadline.toLocaleString()}</div>`;
                }
                
                taskEl.innerHTML = `
                    <div class="task-title">📌 ${task.title}</div>
                    <div class="task-desc">${task.description ? task.description.substring(0, 100) + (task.description.length > 100 ? '...' : '') : 'Нет описания'}</div>
                    ${deadlineHtml}
                    <div class="task-meta">📊 Решений: ${submissionsCount} | 👥 Группы: ${task.group_numbers ? task.group_numbers.join(', ') : '—'}</div>
                    <div class="task-action">→ Открыть решения</div>
                `;
                tasksListDiv.appendChild(taskEl);
            }
            
        } catch (err) {
            console.error('Ошибка:', err);
            tasksListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">❌ Ошибка загрузки заданий. Попробуйте позже.</div>';
        }
    }
    
    async function getSubmissionsCount(taskId) {
        try {
            // Здесь нужно получить количество решений для задачи
            // Пока возвращаем заглушку, потом можно реализовать
            return '?';
        } catch (err) {
            return '?';
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
    await loadTeacherTasks();
});