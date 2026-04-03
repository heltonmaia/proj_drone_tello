from modules import utils

AI_PROVIDER = 'GEMINI'
#AI_PROVIDER = 'LOCAL'
# AI_PROVIDER = 'OPENAI'

LOCAL_MODEL_NAME = 'minicpm-v:8b'
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
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