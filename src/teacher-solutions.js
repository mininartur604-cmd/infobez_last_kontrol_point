document.addEventListener('DOMContentLoaded', async () => {
    // Получаем ID задачи из URL
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task');
    
    if (!taskId) {
        document.getElementById('solutions-list').innerHTML = '<div style="text-align: center; padding: 40px; color: red;">❌ ID задачи не указан</div>';
        return;
    }
    
    const taskTitleSpan = document.getElementById('task-title');
    const solutionsListDiv = document.getElementById('solutions-list');
    const logoutBtn = document.getElementById('logout-btn');
    
    async function loadTaskInfo() {
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки задания');
            }
            
            const data = await response.json();
            
            if (data.ok && data.task) {
                taskTitleSpan.textContent = data.task.title || `Задание ${taskId}`;
                document.getElementById('page-title').textContent = `РЕШЕНИЯ: ${data.task.title}`;
            } else {
                taskTitleSpan.textContent = `Задание ${taskId}`;
            }
        } catch (err) {
            console.error('Ошибка:', err);
            taskTitleSpan.textContent = `Задание ${taskId}`;
        }
    }
    
    async function loadSolutions() {
        try {
            // Получаем всех студентов, которые сдали это задание
            const response = await fetch(`/api/task/${taskId}/solutions`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                if (response.status === 404) {
                    solutionsListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">📭 Решений пока нет</div>';
                    return;
                }
                throw new Error('Ошибка загрузки решений');
            }
            
            const data = await response.json();
            
            if (!data.ok || !data.solutions || data.solutions.length === 0) {
                solutionsListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">📭 Решений пока нет</div>';
                return;
            }
            
            solutionsListDiv.innerHTML = '';
            
            for (const solution of data.solutions) {
                const solutionEl = document.createElement('a');
                solutionEl.className = 'solution';
                solutionEl.href = `9.html?task=${taskId}&student=${solution.student_id}`;
                
                // Статус проверки
                let statusText = '';
                let statusClass = '';
                if (solution.grade_value === null) {
                    statusText = '⏳ Не проверено';
                    statusClass = 'status-pending';
                } else {
                    statusText = `✅ Проверено • Оценка: ${solution.grade_value}`;
                    statusClass = 'status-graded';
                }
                
                solutionEl.innerHTML = `
                    <div class="solution-title">👤 ${solution.student_name}</div>
                    <div class="solution-meta">
                        Группа: ${solution.group_number || '—'} • ${statusText}
                    </div>
                    <div class="solution-date">📅 Сдано: ${solution.submitted_at || '—'}</div>
                `;
                solutionsListDiv.appendChild(solutionEl);
            }
            
        } catch (err) {
            console.error('Ошибка:', err);
            solutionsListDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: #a89b93;">❌ Ошибка загрузки решений</div>';
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
    
    await loadTaskInfo();
    await loadSolutions();
});