document.addEventListener('DOMContentLoaded', async () => {
    // Получаем параметры из URL
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task');
    const studentId = urlParams.get('student');
    
    const logoutBtn = document.getElementById('logout-btn');
    const gradeInput = document.getElementById('grade-value');
    const saveGradeBtn = document.getElementById('save-grade-btn');
    const gradeStatus = document.getElementById('grade-status');
    const filesContainer = document.getElementById('files-container');
    const codeViewer = document.getElementById('code-viewer');
    const codeContent = document.getElementById('code-content');
    const currentFileName = document.getElementById('current-file-name');
    
    let currentSolutionPath = null;
    let currentGroupNumber = null;
    
    if (!taskId || !studentId) {
        alert('❌ Ошибка: не указан ID задания или студента');
        return;
    }
    
    // Загрузка информации о студенте и задании
    async function loadStudentInfo() {
        try {
            // Получаем профиль студента
            const response = await fetch(`/api/user/${studentId}`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки данных студента');
            }
            
            const data = await response.json();
            
            if (data.ok && data.user) {
                document.getElementById('student-name').textContent = data.user.second_name + ' ' + data.user.first_name;
                document.getElementById('student-group').textContent = data.user.group_number || 'Не назначена';
                currentGroupNumber = data.user.group_number;
            }
        } catch (err) {
            console.error('Ошибка:', err);
            document.getElementById('student-name').textContent = 'Ошибка загрузки';
        }
    }
    
    // Загрузка информации о задании
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
                document.getElementById('task-title').textContent = data.task.title;
            }
        } catch (err) {
            console.error('Ошибка:', err);
            document.getElementById('task-title').textContent = 'Ошибка загрузки';
        }
    }
    
    // Загрузка оценки студента
    async function loadGrade() {
        try {
            const response = await fetch(`/api/solution/${taskId}/student/${studentId}/grade`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.grade_value !== null && data.grade_value !== undefined) {
                    gradeInput.value = data.grade_value;
                    document.getElementById('current-grade').textContent = data.grade_value;
                    gradeStatus.textContent = '✅ Оценка уже выставлена';
                } else {
                    document.getElementById('current-grade').textContent = '—';
                    gradeStatus.textContent = '⏳ Ожидает проверки';
                }
            } else if (response.status === 404) {
                document.getElementById('current-grade').textContent = '—';
                gradeStatus.textContent = '⏳ Решение не найдено';
            }
        } catch (err) {
            console.error('Ошибка:', err);
        }
    }
    
    // Загрузка списка файлов решения
    async function loadSolutionFiles() {
        if (!currentGroupNumber) {
            filesContainer.innerHTML = '<div style="color: #a89b93;">⏳ Сначала загружается информация о группе...</div>';
            return;
        }
        
        try {
            const response = await fetch(`/api/solution/files-list?group_number=${currentGroupNumber}&student_id=${studentId}&task_id=${taskId}`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                if (response.status === 404) {
                    filesContainer.innerHTML = '<div style="color: #a89b93;">📭 Решение еще не загружено</div>';
                    return;
                }
                throw new Error('Ошибка загрузки файлов');
            }
            
            const data = await response.json();
            
            if (!data.files || data.files.length === 0) {
                filesContainer.innerHTML = '<div style="color: #a89b93;">📭 Нет загруженных файлов</div>';
                return;
            }
            
            // Показываем список файлов
            filesContainer.innerHTML = '';
            const fileList = document.createElement('div');
            fileList.style.display = 'flex';
            fileList.style.flexDirection = 'column';
            fileList.style.gap = '8px';
            
            for (const file of data.files) {
                const fileBtn = document.createElement('button');
                fileBtn.className = 'file-btn';
                fileBtn.textContent = `📄 ${file}`;
                fileBtn.style.cssText = `
                    background: #181416;
                    border: 1px solid #46353a;
                    padding: 8px 12px;
                    text-align: left;
                    cursor: pointer;
                    color: #ddd6cf;
                `;
                fileBtn.onclick = () => loadFileContent(file);
                fileList.appendChild(fileBtn);
            }
            
            filesContainer.appendChild(fileList);
            
        } catch (err) {
            console.error('Ошибка:', err);
            filesContainer.innerHTML = '<div style="color: #a89b93;">❌ Ошибка загрузки файлов</div>';
        }
    }
    
    // Загрузка содержимого файла
    async function loadFileContent(filePath) {
        try {
            codeViewer.style.display = 'block';
            currentFileName.textContent = `📄 ${filePath}`;
            codeContent.textContent = '⏳ Загрузка...';
            
            const response = await fetch(`/api/solution/read-file?group_number=${currentGroupNumber}&student_id=${studentId}&task_id=${taskId}&file_relative_path=${encodeURIComponent(filePath)}&as_text=true`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки файла');
            }
            
            const content = await response.text();
            codeContent.textContent = content;
            
        } catch (err) {
            console.error('Ошибка:', err);
            codeContent.textContent = '❌ Ошибка загрузки содержимого файла';
        }
    }
    
    // Сохранение оценки
    async function saveGrade() {
        const gradeValue = parseInt(gradeInput.value);
        
        if (isNaN(gradeValue)) {
            alert('❌ Введите оценку (число от 0 до 100)');
            return;
        }
        
        if (gradeValue < 0 || gradeValue > 100) {
            alert('❌ Оценка должна быть от 0 до 100');
            return;
        }
        
        saveGradeBtn.disabled = true;
        saveGradeBtn.textContent = '⏳ СОХРАНЕНИЕ...';
        
        try {
            const response = await fetch(`/api/solution/${taskId}/student/${studentId}/grade`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include',
                body: JSON.stringify({ grade_value: gradeValue })
            });
            
            const data = await response.json();
            
            if (response.ok && data.ok) {
                document.getElementById('current-grade').textContent = gradeValue;
                gradeStatus.textContent = '✅ Оценка сохранена!';
                gradeStatus.style.color = '#4caf50';
                alert('✅ Оценка успешно сохранена!');
            } else {
                throw new Error(data.detail || data.msg || 'Ошибка сохранения');
            }
        } catch (err) {
            console.error('Ошибка:', err);
            gradeStatus.textContent = '❌ Ошибка сохранения: ' + err.message;
            gradeStatus.style.color = '#f44336';
            alert('❌ Ошибка: ' + err.message);
        } finally {
            saveGradeBtn.disabled = false;
            saveGradeBtn.textContent = '💾 СОХРАНИТЬ ОЦЕНКУ';
        }
    }
    
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
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }
    
    if (saveGradeBtn) {
        saveGradeBtn.addEventListener('click', saveGrade);
    }
    
    // Загружаем все данные
    await loadStudentInfo();
    await loadTaskInfo();
    await loadGrade();
    
    // Ждем группу, потом загружаем файлы
    const waitForGroup = setInterval(async () => {
        if (currentGroupNumber) {
            clearInterval(waitForGroup);
            await loadSolutionFiles();
        }
    }, 500);
});