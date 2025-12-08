import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from PIL import Image
import traceback
import ollama
import io
import re

from modules import utils
from modules.tello_control import log_messages

USE_LOCAL_AI = True
LOCAL_MODEL_NAME = 'minicpm-v:8b'
API_MODEL_NAME = 'gemini-2.5-flash'

utils.configure_generative_ai()
config = GenerationConfig(
    temperature=0.7,
    top_p=0.8,
    top_k=40,
    max_output_tokens=500, # Limita o tamanho da resposta para não gastar tempo/tokens
)

# Passa a config na inicialização do modelo
model = genai.GenerativeModel( # type: ignore
    model_name=API_MODEL_NAME,
    generation_config=config,
)

# Variável global para armazenar o objeto da sessão de chat
chat_session = None

COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]

def get_chat_session():
    """
    Inicializa e retorna a sessão de chat.
    O chat é iniciado com um histórico vazio, pois o contexto completo é fornecido em cada mensagem.
    Returns:
        ChatSession: A sessão de chat.
    """
    global chat_session
    if chat_session is None:
        chat_session = model.start_chat(history=[])
        print('Sessão de chat iniciada.')
    return chat_session

def extract_command(text):
    """
    Extrai comandos em qualquer posição da linha.
    Suporta formatos como:
      "[COMANDO] ccw 90"
      "COMANDO: forward 50"
      "ccw 90"
    """
    text = text.lower()

    pattern = r'(up|down|left|right|forward|back|cw|ccw)\s+(\d+)'
    match = re.search(pattern, text)
    if match:
        cmd = match.group(1)
        val = match.group(2)
        return f"{cmd} {val}"

    if "takeoff" in text:
        return "takeoff"
    if "land" in text:
        return "land"

    return None


def fix_command(raw_command: str) -> str | None:
    if not raw_command:
        return None
        
    parts = raw_command.lower().strip().split()
    if not parts:
        return None
        
    cmd = parts[0]

    if cmd in ['takeoff', 'land']:
        return cmd

    if len(parts) == 1:
        if cmd in ['cw', 'ccw']:
            return f"{cmd} 90"
        if cmd in ['up', 'down', 'left', 'right', 'forward', 'back']:
            return f"{cmd} 50"

    if len(parts) >= 2:
        val_str = ''.join(filter(str.isdigit, parts[1]))

        if not val_str:
            if cmd in ['cw', 'ccw']:
                return f"{cmd} 90"
            else:
                return f"{cmd} 50"

        val = int(val_str)

        if cmd in ['cw', 'ccw']:
            val = max(1, min(val, 360))
        else:
            val = max(20, min(val, 500))

        return f"{cmd} {val}"

    return None


def pil_image_to_bytes(image: Image.Image) -> bytes:
    """Converte PIL Image para bytes, redimensionando para performance local."""
    base_width = 640
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    
    img_resized = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
    
    with io.BytesIO() as buffer:
        img_resized.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()

def run_ai_local(text: str | None, frame: Image.Image) -> tuple[str, str | None, bool]:
    """
    Executa a IA localmente com Ollama.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
    Returns:
        tuple: (resposta natural, comando técnico)
    """
    try:
        user_text = text if text else 'No objective provided. Analyze the scene'

        system_prompt = f"""
            You are a ROBOT PILOT controlling a Tello Drone. You must follow the User Input STRICTLY.
            You must analyze the provided image and generate a command. Command parts are: DIRECTION and VALUE.
            
            [DIRECTION GUIDE]
            If User says: "Suba", "Cima", "Alto" -> COMMAND: up
            If User says: "Desça", "Baixo", "Chão" -> COMMAND: down
            If User says: "Frente", "Avance" -> COMMAND: forward
            If User says: "Trás", "Volte", "Recue" -> COMMAND: back
            If User says: "Vá para a esquerda" -> COMMAND: left
            If User says: "Vá para a direita" -> COMMAND: right
            If User says: "Gire pra esquerda", "Vire" -> COMMAND: ccw
            If User says: "Gire pra direita", "Vire" -> COMMAND: cw

            [VALUE RANGE]
            - ABSOLUTE LIMITS: Distance [20-500], Rotation [1-360].
            
            CURRENT SITUATION:
            - User Input: "{user_text}"
            
            INSTRUCTIONS:
            1. First, identify the direction requested in the User Input.
            2. Only look at the image to check for IMMEDIATE OBSTACLES in that direction.
            3. If the way is clear, execute the requested command.
            4. If there is no need to move, use "none" command.
            5. Write after the [] tags
            
            OUTPUT FORMAT:
            [ANÁLISE] (Explain what the user asked and if the path is clear in portuguese)
            [COMANDO] command value
            
            EXAMPLE:
            User Input: "Suba um pouco"
            Output:
            [ANÁLISE] O usuário pediu para subir. Não há obstáculos imediatos.
            [COMANDO] up 50
            """
        
        stream = ollama.chat(
            model=LOCAL_MODEL_NAME,
            messages=[
                {
                    'role': 'user',
                    'content': system_prompt,
                    'images': [pil_image_to_bytes(frame)]
                }
            ],
            stream=True,
            options={
                'temperature': 0.1,  # (0.0 a 1.0) Quanto menor, mais determinístico/lógico.
                'top_p': 0.6,
                'num_ctx': 4096,     # Tamanho da janela de contexto (memória).
                'seed': 42           # Semente fixa para tentar reproduzir sempre a mesma resposta.
            }
        )

        full_response_text = ""

        for chunk in stream:
            part = chunk['message']['content']
            full_response_text += part

        extracted_command = None
        
        lines = full_response_text.split('\n')
        for line in lines:
            line = line.strip()
            
            if '[COMANDO]' in line.upper():
                raw_command = extract_command(line)
                extracted_command = fix_command(raw_command)
        
        # Fallback de segurança: Se a IA local falhar a formatação mas escrever o comando
        if not extracted_command:
             for line in lines:
                 for valid_cmd in COMMAND_LIST:
                     if line.lower().startswith(valid_cmd):
                         if validate_command(line):
                             extracted_command = line
                             break

        return full_response_text, extracted_command, False

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"DEBUG: Erro em run_ai_local: {str(e)}\n{error_details}")
        return f"Erro Ollama: {str(e)}", None, False

def run_ai_gemini(text: str | None, frame: Image.Image, step: int=0, height: int=0) -> tuple[str, str | None, bool]:
    """
    Executa a IA para gerar comandos de controle do drone.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
        step (int): Passo atual na sequência de comandos.
        height (int): Altura atual do drone em cm.
    Returns:
        tuple: (resposta natural, comando técnico, continuar rota)
    """

    try:
        current_chat = get_chat_session()
        
        user_text = text if text else 'Nenhum objetivo fornecido. Analise a cena e sugira uma ação segura.'

        formatted_log_messages = ", ".join(log_messages) if log_messages else 'Nenhum comando enviado.'

        if step == 0:
            system_prompt = f"""
                ATUAR COMO PILOTO DE DRONE TELLO (Simulação Lógica).
                Objetivo: {user_text}
                Histórico: {formatted_log_messages}
                Comandos válidos: {COMMAND_LIST}
                Altura do drone: {height} (10cm geralmente significa que está no chão)

                Comandos de voo requerem argumento numérico em cm: forward 20 (para frente 20cm)
                Comandos que não precisam de argumento: [takeoff, land]
                Valores dos argumentos devem estar entre: [11, 500], representam a distância em cm (movimentos) ou graus (rotações)
                
                FORMATO DE RESPOSTA (Obrigatório):
                [ANÁLISE] (Descreva o que vê e a relação com o objetivo aqui)
                [PLANO] (1. Passo atual. 2. Próximo passo)
                [COMANDO] (Ex: forward 100 ou cw 90)
                [CONTINUA] Use se a missão não acabou
                """
        else:
            system_prompt = f"""
                CONTINUAÇÃO DA MISSÃO.
                {user_text} (contém o contexto anterior).
                
                Analise se a ação anterior funcionou observando a nova imagem.
                Responda no mesmo formato: 
                [ANÁLISE] (Nova análise da sua visão)
                [PLANO] (2 próximos passos planejados)
                [COMANDO] (Comando de voo)
                [CONTINUA] Caso deva continuar após esse passo
                """

        # Constrói o prompt para o turno atual.
        content_for_turn = [system_prompt, frame]
        
        # Envia a mensagem para a sessão de chat ativa
        response = current_chat.send_message(content_for_turn)

        # Verifica se a resposta foi bloqueada ou está vazia
        if not response.parts:
            print("\n--- DEBUG GEMINI BLOQUEADO ---")
            if hasattr(response, 'prompt_feedback'):
                print(f"Prompt Feedback: {response.prompt_feedback}")
            if hasattr(response, 'candidates') and response.candidates:
                print(f"Finish Reason: {response.candidates[0].finish_reason}")
                print(f"Safety Ratings: {response.candidates[0].safety_ratings}")
            print("------------------------------\n")
            return "Erro: Bloqueio de Segurança Rígido.", None, False

        natural_response_text = response.text
        extracted_command = None
        continue_route = False

        # Extração do comando
        response_lines = natural_response_text.split('\n')
        for line in response_lines:
            if '[COMANDO]' in line.upper():
                raw_command = extract_command(line)
                extracted_command = fix_command(raw_command)

            elif line.startswith('[CONTINUA]'):
                continue_route = True
        
        return natural_response_text, extracted_command, continue_route

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"DEBUG: Erro em run_ai: {str(e)}\n{error_details}")
        return f"Erro crítico ao processar com IA: {str(e)}", None, False
    
def run_ai(text: str | None, frame: Image.Image, step: int=0, height: int=0) -> tuple[str, str | None, bool | None]:
    """
    Função Mestra que decide qual IA usar.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
        step (int): Passo atual na sequência de comandos.
        height (int): Altura atual do drone em cm.
    Returns:
        tuple: (resposta natural, comando técnico, continuar rota)
    """
    if USE_LOCAL_AI:
        return run_ai_local(text, frame)
    else:
        return run_ai_gemini(text, frame, step, height)
    
def validate_command(cmd: str) -> bool:
    """
    Valida o comando recebido.
    Args:
        cmd (str): Comando recebido.
    Returns:
        bool: True se o comando for válido, False caso contrário.
    """
    if not cmd: # Trata comando None ou vazio
        return False
        
    parts = cmd.strip().split() # Divide o comando
    if not parts:
        return False

    base_cmd = parts[0].lower()

    if base_cmd not in COMMAND_LIST:
        return False

    # Comandos que requerem um argumento numérico
    if base_cmd in ['up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw']:
        if len(parts) != 2:
            return False
        try:
            val = int(parts[1])
            if base_cmd in ['cw', 'ccw']: # Rotação em graus
                if not (1 <= val <= 360): return False
            else: # Movimento em cm
                if not (10 <= val <= 500): return False
        except ValueError:
            return False # Não é um número inteiro
    # Comandos que não requerem argumento numérico
    elif base_cmd in ['land', 'takeoff']:
        if len(parts) != 1:
            return False

    return True