"""
Módulo de Configurações e Constantes para o Núcleo de IA.

Este módulo centraliza as configurações, chaves de API, nomes de modelos 
e outras constantes relacionadas à inteligência artificial utilizada no projeto.
Ele é importado por outros módulos para garantir consistência e facilitar 
a manutenção.

Principais Funcionalidades:
    - Definição do provedor de IA (Gemini, OpenAI, Local).
    - Armazenamento de chaves de API e nomes de modelos.
    - Função utilitária para obter o nome do modelo atualmente em uso.
"""

from modules import utils

AI_PROVIDER = 'GEMINI'
#AI_PROVIDER = 'LOCAL'
# AI_PROVIDER = 'OPENAI'

LOCAL_MODEL_NAME = 'llama3'
GEMINI_MODEL_NAME = 'gemini-3.0-flash'
OPENAI_MODEL_NAME = 'gpt-4o-mini'

OPENAI_API_KEY = utils.get_openai_key()
GEMINI_API_KEY = utils.get_gemini_key()

ACCEPTED_ROTATIONS = [10, 15, 30, 45, 90, 135, 180, 360]
COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]

def get_model_name():
    """
    Retorna o nome do modelo de IA atualmente em uso.
    Returns:
        str: Nome do modelo.
    """
    if AI_PROVIDER == 'LOCAL':
        return LOCAL_MODEL_NAME
    elif AI_PROVIDER == 'OPENAI':
        return OPENAI_MODEL_NAME
    else:
        return GEMINI_MODEL_NAME
