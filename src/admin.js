// Конфигурация полей для разных действий
const formsConfig = {
    student: {
        title: "➕ Добавить ученика",
        endpoint: "/students",
        fields: ["login", "email", "password", "first_name", "second_name", "middle_name"]
    },
    admin: {
        title: "👑 Добавить админа",
        endpoint: "/api/admins",
        fields: ["login", "email", "password", "first_name", "second_name", "middle_name"]
    },
    teacher: {
        title: "👨‍🏫 Добавить учителя",
        endpoint: "/teachers",
        fields: ["login", "email", "password", "first_name", "second_name", "middle_name", "group_numbers"]
    },
    group: {
        title: "📁 Создать группу",
        endpoint: "/groups",
        fields: ["group_number"]
    },
    assignGroup: {
        title: "📎 Назначить группу ученику",
        endpoint: "/api/admin/assign-group",
        fields: ["login", "group_number"]
    },
    changePassword: {
        title: "🔑 Сменить пароль пользователя",
        endpoint: "/api/admin/change-password",
        fields: ["login", "new_password"]
    },
    teacherGroup: {
        title: "👥 Добавить группы учителю",
        endpoint: "/admins/add-groups",
        fields: ["login", "group_numbers"]
    },
    deleteUser: {
        title: "🗑️ УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ",
        endpoint: "/api/admin/user",
        fields: ["login"],
        isDelete: true,
        method: "DELETE"
    }
};

let currentAction = null;

function openModal(action) {
    console.log("openModal called with action:", action);
    
    const config = formsConfig[action];
    
    if (!config) {
        console.error("Action not found:", action);
        alert("Ошибка: действие '" + action + "' не найдено. Доступные действия: " + Object.keys(formsConfig).join(", "));
        return;
    }
    
    currentAction = action;
    
    const modalTitle = document.getElementById('modal-title');
    const formContainer = document.getElementById('modal-form');
    const modalOverlay = document.getElementById('modal-overlay');
    
    if (!modalTitle || !formContainer || !modalOverlay) {
        console.error("Modal elements not found!");
        alert("Ошибка: элементы модального окна не найдены");
        return;
    }
    
    modalTitle.innerText = config.title;
    formContainer.innerHTML = '';

    // Генерируем поля ввода
    config.fields.forEach(field => {
        const label = document.createElement('label');
        label.innerText = field.toUpperCase().replace('_', ' ');
        
        const input = document.createElement('input');
        
        if (field === 'group_numbers') {
            input.type = 'text';
            input.placeholder = '101, 102 (через запятую)';
        } else if (field.includes('password')) {
            input.type = 'password';
            input.placeholder = `Введите ${field.replace('_', ' ')}`;
        } else {
            input.type = 'text';
            input.placeholder = `Введите ${field.replace('_', ' ')}`;
        }
        
        input.id = `input-${field}`;
        input.className = 'modal-input';
        
        formContainer.appendChild(label);
        formContainer.appendChild(input);
    });

    // Добавляем предупреждение для удаления
    if (config.isDelete) {
        const warning = document.createElement('div');
        warning.style.cssText = 'margin-top: 15px; padding: 10px; background: rgba(244, 67, 54, 0.2); border: 1px solid #f44336; border-radius: 4px; color: #f44336; font-size: 12px; text-align: center;';
        warning.innerHTML = '⚠️ ВНИМАНИЕ! Это действие НЕОБРАТИМО. Будут удалены все данные пользователя и его решения.';
        formContainer.appendChild(warning);
    }

    modalOverlay.style.display = 'flex';
}

function closeModal() {
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.style.display = 'none';
    }
    currentAction = null;
}

// Отправка данных на сервер
function setupSubmitButton() {
    const submitBtn = document.getElementById('modal-submit');
    if (!submitBtn) return;
    
    // Удаляем старый обработчик, если есть
    const newSubmitBtn = submitBtn.cloneNode(true);
    submitBtn.parentNode.replaceChild(newSubmitBtn, submitBtn);
    
    newSubmitBtn.addEventListener('click', async () => {
        const config = formsConfig[currentAction];
        if (!config) {
            alert("Ошибка: действие не найдено");
            closeModal();
            return;
        }
        
        let payload = {};

        // Собираем данные из инпутов
        for (const field of config.fields) {
            const input = document.getElementById(`input-${field}`);
            if (!input) continue;
            
            const val = input.value.trim();
            
            if (field === 'group_numbers') {
                payload[field] = val ? val.split(',').map(s => s.trim()) : [];
            } else {
                payload[field] = val;
            }
        }

        // Валидация
        for (const field of config.fields) {
            const val = payload[field];
            if (field !== 'middle_name' && field !== 'group_numbers') {
                if (!val || (Array.isArray(val) && val.length === 0)) {
                    alert(`❌ Поле "${field}" обязательно для заполнения`);
                    return;
                }
            }
        }

        // Подтверждение для удаления
        if (config.isDelete) {
            const confirmed = confirm(`⚠️ ВНИМАНИЕ! Вы уверены, что хотите удалить пользователя "${payload.login}"? Это действие НЕОБРАТИМО!`);
            if (!confirmed) return;
        }

        try {
            let response;
            
            if (config.method === "DELETE") {
                response = await fetch(`${config.endpoint}?login=${encodeURIComponent(payload.login)}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                });
            } else {
                response = await fetch(config.endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
            }

            const data = await response.json();
            
            if (response.ok && data.ok) {
                alert("✅ Успешно: " + (data.msg || "Выполнено"));
                closeModal();
                setTimeout(() => window.location.reload(), 1000);
            } else {
                alert("❌ Ошибка: " + (data.detail || data.msg || "Неизвестная ошибка"));
            }
        } catch (err) {
            console.error("Ошибка:", err);
            alert("❌ Ошибка соединения с сервером");
        }
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM loaded, initializing admin.js");
    
    // Настройка кнопки отправки
    setupSubmitButton();
    
    // Кнопка выхода
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await fetch('/logout', { method: 'POST', credentials: 'include' });
            } catch (err) {}
            window.location.href = '1.html';
        });
    }
    
    // Закрытие модалки по клику на крестик
    const closeBtn = document.querySelector('.close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    
    // Закрытие по клику на оверлей
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeModal();
        });
    }
    
    console.log("Admin.js ready, available actions:", Object.keys(formsConfig));
});

// Глобальные функции для вызова из HTML
window.openModal = openModal;
window.closeModal = closeModal;

// Сброс базы данных
window.rebuildDB = async function() {
    if (confirm("⚠️ ВНИМАНИЕ! Это удалит ВСЕ данные из базы. Вы уверены?")) {
        try {
            const response = await fetch('/setup_database', { 
                method: 'POST',
                credentials: 'include'
            });
            const data = await response.json();
            alert(data.msg || "База данных сброшена");
            window.location.href = '1.html';
        } catch (err) {
            console.error("Ошибка:", err);
            alert("❌ Ошибка при сбросе базы данных");
        }
    }
};