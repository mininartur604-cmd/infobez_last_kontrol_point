document.addEventListener('DOMContentLoaded', async () => {
    // Получаем основные элементы
    const codeInput = document.getElementById('code-input');
    const outputConsole = document.getElementById('output-console');
    const taskTitle = document.getElementById('task-title');
    const taskDesc = document.getElementById('task-desc');
    
    const fileInput = document.getElementById('file-upload');
    const fileTrigger = document.getElementById('file-trigger');
    const saveBtn = document.getElementById('save-button');
    const runBtn = document.getElementById('run-button');

    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task') || urlParams.get('id'); 

    if (!taskId) {
        outputConsole.innerText = "❌ Ошибка: ID задания не найден (используйте ?task=X)";
        return;
    }

    // --- 1. ЗАГРУЗКА ДАННЫХ ЗАДАНИЯ ИЗ БД ---
    async function fetchTaskInfo() {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            
            // ПРОВЕРЯЕМ СТАТУС ОТВЕТА
            if (!response.ok) {
                const errorText = await response.text();
                console.error("Server error:", errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const result = await response.json();
            console.log("Response from server:", result);

            if (result.ok && result.task) {
                const task = result.task;
                taskTitle.innerText = task.title || "Без названия";
                taskDesc.innerText = task.description || "Нет описания";
            } else {
                outputConsole.innerText = "❌ Задание не найдено или вернулся некорректный ответ";
            }
        } catch (err) {
            console.error("Ошибка при получении задания:", err);
            outputConsole.innerText = `❌ Ошибка загрузки: ${err.message}`;
        }
    }

    await fetchTaskInfo();

    // --- 2. ОБРАБОТКА ЛОКАЛЬНОГО ФАЙЛА ---
    if (fileTrigger && fileInput) {
        fileTrigger.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    codeInput.value = e.target.result;
                    outputConsole.innerText = `✅ Файл "${file.name}" загружен`;
                };
                reader.readAsText(file);
            }
        });
    }

    // --- 3. ОТПРАВКА РЕШЕНИЯ В БД ---
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const solutionCode = codeInput.value;
            if (!solutionCode.trim()) {
                alert("Сначала напишите код!");
                return;
            }

            outputConsole.innerText = "⏳ Сохранение...";

            const blob = new Blob([solutionCode], { type: 'text/plain' });
            const file = new File([blob], "main.py");

            const formData = new FormData();
            formData.append("files", file); 

            try {
                const response = await fetch(`/api/solution/${taskId}`, {
                    method: 'POST',
                    body: formData 
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP ${response.status}: ${errorText}`);
                }

                const result = await response.json();

                if (result.ok) {
                    alert("Решение успешно отправлено!");
                    outputConsole.innerText = "✅ Решение успешно сохранено на сервере";
                } else {
                    throw new Error(result.msg || "Ошибка при сохранении");
                }
            } catch (err) {
                console.error("Ошибка сети:", err);
                alert("Ошибка: " + err.message);
                outputConsole.innerText = "❌ " + err.message;
            }
        });
    }

    // --- 4. ВЫПОЛНЕНИЕ КОДА ---
    if (runBtn) {
        runBtn.addEventListener('click', async () => {
            const code = codeInput.value;
            outputConsole.innerText = "⏳ Запуск...";
            try {
                // Безопасная проверка наличия pyscript
                if (typeof pyscript === 'undefined' || !pyscript.interpreter) {
                    outputConsole.innerText = "❌ PyScript не инициализирован. Проверьте подключение библиотеки.";
                    return;
                }
                const pyResult = await pyscript.interpreter.runPython(code);
                outputConsole.innerText = pyResult || "✅ Выполнено (без вывода)";
            } catch (err) {
                outputConsole.innerText = "❌ Ошибка в коде:\n" + err;
            }
        });
    }
});