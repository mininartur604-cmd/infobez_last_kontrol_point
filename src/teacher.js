document.addEventListener('DOMContentLoaded', async () => {
    const teacherNameSpan = document.getElementById('teacher-name');
    const saveBtn = document.getElementById('save-task-btn');
    const logoutBtn = document.getElementById('logout-btn');
    
    // Загрузка профиля учителя
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
            
            if (data.ok && data.profile) {
                const profile = data.profile;
                
                // Проверка что это учитель или админ
                if (profile.role !== 'teacher' && profile.role !== 'admin') {
                    alert('У вас нет доступа к этой странице');
                    window.location.href = '3.html';
                    return;
                }
                
                const fullName = `${profile.second_name} ${profile.first_name}`;
                teacherNameSpan.textContent = fullName || 'Преподаватель';
                
                // Если админ - показываем что он в режиме учителя
                if (profile.role === 'admin') {
                    teacherNameSpan.textContent += ' (админ)';
                }
            }
        } catch (err) {
            console.error('Ошибка:', err);
            teacherNameSpan.textContent = 'Ошибка загрузки';
        }
    }
    
    // Загрузка ТОЛЬКО групп учителя
    async function loadGroups() {
        try {
            const response = await fetch('/api/teacher/groups', {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.ok && data.groups && data.groups.length > 0) {
                    const groupsSelect = document.getElementById('task-groups');
                    groupsSelect.innerHTML = '';
                    
                    data.groups.forEach(group => {
                        const option = document.createElement('option');
                        option.value = group.group_number;
                        option.textContent = `Группа ${group.group_number}`;
                        groupsSelect.appendChild(option);
                    });
                    
                    if (data.groups.length === 1) {
                        groupsSelect.size = 1;
                    }
                } else {
                    const groupsSelect = document.getElementById('task-groups');
                    groupsSelect.innerHTML = '<option disabled>❌ У вас нет привязанных групп</option>';
                }
            } else if (response.status === 404) {
                const groupsSelect = document.getElementById('task-groups');
                groupsSelect.innerHTML = '<option disabled>❌ У вас нет привязанных групп</option>';
            } else {
                throw new Error('Ошибка загрузки групп');
            }
        } catch (err) {
            console.error('Ошибка загрузки групп:', err);
            const groupsSelect = document.getElementById('task-groups');
            groupsSelect.innerHTML = '<option disabled>❌ Ошибка загрузки групп</option>';
        }
    }
    
    // Создание задания
    async function createTask() {
        const title = document.getElementById('task-title').value.trim();
        const description = document.getElementById('task-desc').value.trim();
        const deadlineValue = document.getElementById('task-deadline').value;
        
        const groupsSelect = document.getElementById('task-groups');
        const selectedGroups = Array.from(groupsSelect.selectedOptions)
            .filter(opt => opt.value && !opt.disabled)
            .map(opt => opt.value);
        
        if (!title) {
            alert("❌ Введите название задания");
            return;
        }
        
        if (!description) {
            alert("❌ Введите описание задания");
            return;
        }
        
        if (selectedGroups.length === 0) {
            alert("❌ Выберите хотя бы одну группу");
            return;
        }
        
        const payload = {
            title: title,
            description: description,
            deadline: deadlineValue || null,
            group_numbers: selectedGroups
        };
        
        try {
            saveBtn.disabled = true;
            saveBtn.textContent = "⏳ ПУБЛИКАЦИЯ...";
            
            const response = await fetch('/api/task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            
            if (response.ok && result.ok) {
                alert(`✅ Задание "${title}" успешно создано для групп: ${selectedGroups.join(', ')}`);
                
                // Очистка формы
                document.getElementById('task-title').value = '';
                document.getElementById('task-desc').value = '';
                document.getElementById('task-deadline').value = '';
                
                // Снимаем выделение с групп
                Array.from(groupsSelect.options).forEach(opt => {
                    opt.selected = false;
                });
            } else {
                alert("❌ Ошибка: " + (result.detail || result.msg || "Не удалось сохранить"));
            }
        } catch (err) {
            console.error("Ошибка:", err);
            alert("❌ Ошибка соединения с сервером");
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = "Создать задание";
        }
    }
    
    // Выход
    async function logout() {
        try {
            const response = await fetch('/logout', {
                method: 'POST',
                credentials: 'include'
            });
            window.location.href = '1.html';
        } catch (err) {
            window.location.href = '1.html';
        }
    }
    
    // Обработчики
    if (saveBtn) {
        saveBtn.addEventListener('click', createTask);
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }
    
    // Загружаем данные
    await loadTeacherProfile();
    await loadGroups();
});