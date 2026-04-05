"""
Módulo central do chatbot de controle do drone.

Este módulo é responsável por integrar a visão computacional, os prompts de IA,
e o parser de comandos para criar uma interface de controle inteligente para o 
drone. Ele formata os prompts, processa as respostas e extrai os comandos de 
voo. Ele é o "cérebro" que conecta a percepção visual à ação do drone, 
garantindo que as decisões sejam tomadas de forma inteligente e contextualizada.

Principais Funcionalidades:
    - Integração de visão computacional para análise de cena.
    - Chamadas unificadas para diferentes provedores de IA.
"""

import traceback
import ollama
from google import genai
from google.genai import types
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from PIL import Image

from modules.ai_core import config, prompts, parser, vision
from modules.tello_control import log_messages

# Para não quebrar compatibilidade com interface.py
AI_PROVIDER = config.AI_PROVIDER
get_model_name = config.get_model_name
validate_command = parser.validate_command

openai_history: list[ChatCompletionMessageParam] = []

# --- Inicialização de Clientes (Gemini/OpenAI) ---
client_gemini = genai.Client(api_key=config.GEMINI_API_KEY)
gemini_config = types.GenerateContentConfig(
    temperature=0.7, top_p=0.95, top_k=40, max_output_tokens=2048, response_mime_type="application/json"
)

openai_history: list[ChatCompletionMessageParam] = []

client_gemini = genai.Client(api_key=config.GEMINI_API_KEY)

# A configuração agora usa types.GenerateContentConfig
gemini_config = types.GenerateContentConfig(
    temperature=0.7,
    top_p=0.95,
    top_k=40,
    max_output_tokens=2048,
    response_mime_type="application/json"
)

client_openai = None
if config.AI_PROVIDER == 'OPENAI' and config.OPENAI_API_KEY:
    client_openai = OpenAI(api_key=config.OPENAI_API_KEY)

# Variável global para armazenar o objeto da sessão de chat
chat_session_gemini = None

def reset_openai_history():
    """Limpa o histórico e define a persona do sistema."""
    global openai_history
    openai_history = [
        {
            "role": "system",
            "content": prompts.SYSTEM_INSTRUCTION_TEXT
        }
    ]

def run_ai_local(text: str | None, frame: Image.Image) -> tuple[str, str | None, bool]:
    """
    Executa a IA localmente com Ollama retornando JSON.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
    Returns:
        tuple: (resposta formatada, comando técnico, continuar rota)
    """
    try:
        user_objective = text if text else 'Descreva a cena.'
        scene_text = vision.extract_features_with_yolo(frame)

        formatted_log = ", ".join(log_messages[-5:]) if log_messages else 'Nenhum.'

        base_instruction = prompts.get_ai_instruction(user_objective, formatted_log, height=0, step=0, max_steps=4)

        # Regras adicionais específicas para o interpretador de radar
        radar_instruction = """
        ATENÇÃO PARA O RADAR:
        - Se o caminho frontal estiver bloqueado, GIRE ('cw 90') ou SUBA ('up 50'). NUNCA vá 'forward'.
        - Se o radar acusar CEGUEIRA (parede lisa), AFASTE-SE imediatamente ('back 50').
        """

        response = ollama.chat(
            model=config.LOCAL_MODEL_NAME,
            messages=[
                {'role': 'system', 'content': base_instruction + radar_instruction},
                {'role': 'user', 'content': f"OBJETIVO: {user_objective}\n \
                DESCRIÇÃO DA CENA:{scene_text}\n \
                Gere o JSON."}
            ],
            options={'temperature': 0.1, 'num_predict': 150}
        )
        
        data = parser.parse_json_response(response['message']['content'])
        chat_display_text = (
            f"Radar: {scene_text}\n\n"
            f"Análise: {data.get('analise', 'N/A')}\n"
            f"Plano: {data.get('plano', 'Sem plano.')}\n"
            f"Comando: {data.get('comando', 'none')}"
        )

        return chat_display_text, data.get('comando', None), data.get('continua', False)
    
    except Exception as e:
        print(f"Erro em run_ai_local: {traceback.format_exc()}")
        return f"Erro Local: {str(e)}", None, False

def run_ai_gemini(text: str | None, frame: Image.Image, step: int=0, height: int=0, max_steps: int=4) -> tuple[str, str | None, bool]:
    """
    Executa a IA para gerar comandos de controle do drone via Gemini.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
        step (int): Passo atual na sequência de comandos.
        height (int): Altura atual do drone em cm.
        max_steps (int): Número máximo de passos permitidos.
    Returns:
        tuple: (resposta natural, comando técnico, continuar rota)
    """
    try:
        user_text = text if text else 'Analise a cena.'
        formatted_log = ", ".join(log_messages[-5:]) if log_messages else 'Nenhum.'

        system_prompt = prompts.get_ai_instruction(user_text, formatted_log, height, step, max_steps)
        frame_grid = vision.add_grid_to_image(frame)

        # MUDANÇA AQUI: Chamada stateless (direta) em vez de chat_session
        response = client_gemini.models.generate_content(
            model=config.GEMINI_MODEL_NAME,
            contents=[system_prompt, frame_grid],
            config=gemini_config
        )

        if not response.candidates or not response.candidates[0].content:
            return "Erro: Bloqueio de Segurança Rígido.", None, False
        
        data = parser.parse_json_response(response.text) # type: ignore
        
        chat_display_text = (
            f"Análise: {data.get('analise', 'N/A')}\n"
            f"Plano: {data.get('plano', 'Sem plano.')}\n"
            f"Comando: {data.get('comando', 'none')}\n"
            f"Continuar: {data.get('continua', False)}"
        )
        return chat_display_text, data['comando'], data['continua']

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Erro crítico: {str(e)}", None, False
    
def run_ai_openai(text: str | None, frame: Image.Image, step: int=0, height: int=0, last_action: str="Nenhuma", max_steps: int=4) -> tuple[str, str | None, bool]:
    global openai_history
    if not client_openai: return "Erro OpenAI Client.", None, False

    try:
        if step == 0:
            reset_openai_history()
        if not text:
            text = "Analise a cena."
        prompt = prompts.get_step_prompt(text, last_action, height, step, max_steps)

        frame_grid = vision.add_grid_to_image(frame)
        base64_img = vision.pil_image_to_base64(frame_grid)

        current_user_msg: ChatCompletionMessageParam = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_img}",
                        "detail": "low"
                    }
                }
            ]
        }
        openai_history.append(current_user_msg)

        response = client_openai.chat.completions.create(
            model=config.OPENAI_MODEL_NAME,
            messages=openai_history,
            response_format={ "type": "json_object" },
            max_tokens=300,
            temperature=0.7,
        )

        full_text = response.choices[0].message.content
        if not full_text:
            return "Erro OpenAI: Resposta vazia.", None, False
        data = parser.parse_json_response(full_text)

        openai_history.append({"role": "assistant", "content": full_text})
        
        last_user_index = len(openai_history) - 2
        if openai_history[last_user_index]['role'] == 'user':
            openai_history[last_user_index]['content'] = f"[Passo {step}] Prompt: {prompt} | Imagem processada."

        chat_text = f"Análise: {data['analise']}\nPlano: {data['plano']}\nComando: {data['comando']}\nContinuar: {data['continua']}"
        return chat_text, data['comando'], data['continua']

    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return f"Erro OpenAI: {str(e)}", None, False

def run_ai(text: str | None, frame: Image.Image, step: int=0, height: int=0, last_action: str="Nenhuma", max_steps: int=4) -> tuple[str, str | None, bool | None]:
    """
    Função Mestra que decide qual IA usar.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
        step (int): Passo atual na sequência de comandos.
        height (int): Altura atual do drone em cm.
        last_action (str): Último comando executado pelo drone.
    Returns:
        tuple: (resposta natural, comando técnico, continuar rota)
    """
    if config.AI_PROVIDER == 'LOCAL':
        return run_ai_local(text, frame)
    elif config.AI_PROVIDER == 'OPENAI':
        return run_ai_openai(text, frame, step, height, last_action, max_steps)
    else:
        return run_ai_gemini(text, frame, step, height, max_steps)