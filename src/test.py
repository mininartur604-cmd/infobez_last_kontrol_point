from pyscript import window, document, when
import sys
from io import StringIO

# Глобальное пространство для переменных
user_namespace = {}

@when("click", "#run-button")
def run_python_code(event):
    input_control = document.querySelector("#code-input")
    output_control = document.querySelector("#output-console")
    
    source_code = input_control.value.strip()
    if not source_code:
        output_control.innerText = "⚠️ Введите код для запуска"
        return

    # Очистка консоли перед запуском
    output_control.innerText = "Выполнение..."

    # Подготовка к перехвату print()
    buffer = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer

    try:
        # Решаем, использовать exec или eval
        if "\n" in source_code or "print" in source_code or "import" in source_code:
            exec(source_code, user_namespace)
            output = buffer.getvalue()
        else:
            try:
                result = eval(source_code, user_namespace)
                output = buffer.getvalue()
                if result is not None:
                    output += str(result)
            except:
                exec(source_code, user_namespace)
                output = buffer.getvalue()

        if not output:
            output = "✅ Выполнено (нет вывода)"
        
        output_control.innerText = output
        
    except Exception as e:
        output_control.innerText = f"❌ Ошибка в коде:\n{str(e)}"
    
    finally:
        sys.stdout = old_stdout