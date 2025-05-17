"""
Crie sua chave aqui: https://aistudio.google.com/apikey.
Substitua 'sua_chave_api_aqui' pela sua chave de API real
Você pode armazenar a chave em um arquivo de configuração ou variável de ambiente
para maior segurança
e evitar expô-la diretamente no código.
"""
import google.generativeai as genai

def configure_generative_ai():
    """
    Configura a chave da API do Google GenerativeAI.
    Args:
        api_key: Chave da API.
    """
    genai.configure(api_key='sua_chave_api_aqui')

