import textwrap
import threading
import google.generativeai as genai

genai.configure(api_key='AIzaSyCfNSj6Pf3A1etNVUUykphjdOrqIOeE5uw')
model = genai.GenerativeModel('gemini-2.0-flash')

# Variável global com lock para armazenar a resposta da IA
last_response = None

def to_markdown(text: str) -> str:
    """Converte o texto para Markdown"""
    text = text.replace('•', '  *')
    return textwrap.indent(text, '> ', predicate=lambda _: True)

def run_ai(prompt: str):
    """Executa a IA em uma thread separada"""
    global last_response
    response = model.generate_content(prompt)
    last_response = response.text

def get_last_response():
    return last_response
