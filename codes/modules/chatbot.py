import textwrap
import threading
import google.generativeai as genai
import time
import utils

utils.configureGenerativeAI()
model = genai.GenerativeModel('gemini-2.0-flash')

# Variáveis de estado
response_lock = threading.Lock()
last_response = None
new_response = False

def to_markdown(text: str) -> str:
    text = text.replace('•', '  *')
    return textwrap.indent(text, '> ', predicate=lambda _: True)

response_lock = threading.Lock()

def run_ai(prompt: str, chat_history: list):
    """Executa a IA e atualiza o histórico de forma thread-safe"""
    global last_response, new_response
    try:
        response = model.generate_content(prompt)
        time.sleep(1)
        with response_lock:
            # Atualiza o histórico dentro do lock
            chat_history.append(("ai", response.text))
            last_response = response.text
            new_response = True
    except Exception as e:
        with response_lock:
            chat_history.append(("ai", f"Erro: {str(e)}"))
            last_response = f"Erro: {str(e)}"
            new_response = True

def get_last_response():
    with response_lock:
        return last_response