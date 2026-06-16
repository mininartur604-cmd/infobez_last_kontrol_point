// Ждем загрузки DOM, чтобы элементы точно были доступны
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-upload');
    const codeInput = document.getElementById('code-input');
    const outputConsole = document.getElementById('output-console');

    // Слушаем выбор файла
    fileInput.addEventListener('change', (event) => {
        const input = event.target;
        
        if (input.files && input.files.length > 0) {
            readFileContent(input.files[0])
                .then(content => {
                    // Вставляем код в редактор
                    codeInput.value = content; 
                    outputConsole.innerText = "✅ Файл успешно загружен в редактор";
                })
                .catch(error => {
                    outputConsole.innerText = "❌ Ошибка чтения файла: " + error;
                });
        }
    });
});

/**
 * Функция для чтения текстового содержимого файла через Promise
 */
function readFileContent(file) {
    const reader = new FileReader();
    return new Promise((resolve, reject) => {
        reader.onload = event => resolve(event.target.result);
        reader.onerror = error => reject(error);
        reader.readAsText(file);
    });
}