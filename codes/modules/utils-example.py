"""
Crie sua chave do Gemini aqui: https://aistudio.google.com/apikey.
A chave da OpenAI pode ser criada em: https://platform.openai.com/account/api-keys.
Cole as chaves nas variáveis OPENAI_KEY e GEMINI_KEY abaixo.
"""
import google.generativeai as genai

GEMINI_KEY = 'chave_gemini_aqui'
OPENAI_KEY = 'chave_openai_aqui'

def configure_generative_ai():
    """Configura a chave da API do Google GenerativeAI."""
    genai.configure(api_key=GEMINI_KEY)

def get_openai_key():
    """Retorna a chave da OpenAI para uso em outros módulos."""
    return OPENAI_KEY

