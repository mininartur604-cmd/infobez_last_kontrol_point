document.addEventListener('DOMContentLoaded', async () => {
    const tasksList = document.getElementById('tasks-list');
    
    try {
        // Запрос к исправленному бэкенду
        const response = await fetch('/api/my-tasks');
        const data = await response.json();

        if (!data.ok) {
            tasksList.innerHTML = '<p>❌ Ошибка загрузки заданий</p>';
            return;
        }

        const tasks = data.tasks;

        if (!tasks || tasks.length === 0) {
            tasksList.innerHTML = '<p>📭 Для вашей группы пока нет заданий</p>';
            return;
        }

        tasksList.innerHTML = '';

        tasks.forEach(task => {
            const taskEl = document.createElement('a');
            taskEl.className = 'task';
            taskEl.href = `4.html?task=${task.id}`;
            
            // Форматируем дедлайн
            let deadlineHtml = '';
            if (task.deadline) {
                const deadline = new Date(task.deadline);
                deadlineHtml = `<div class="task-deadline">⏰ Дедлайн: ${deadline.toLocaleString()}</div>`;
            }
            
            // Оценка
            const gradeValue = task.grade !== null && task.grade !== undefined ? task.grade : '—';
            
            taskEl.innerHTML = `
                <div class="task-title">📌 ${task.title}</div>
                <div class="task-desc">${task.description || 'Нет описания'}</div>
                ${deadlineHtml}
                <div class="task-grade">⭐ Оценка: ${gradeValue}</div>
            `;
            tasksList.appendChild(taskEl);
        });
        
    } catch (err) {
        console.error('Ошибка:', err);
        tasksList.innerHTML = '<p>❌ Ошибка загрузки заданий. Попробуйте позже.</p>';
    }
});