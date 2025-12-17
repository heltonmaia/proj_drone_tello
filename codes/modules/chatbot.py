import os
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from PIL import Image
import traceback
import ollama
import io
import re
import base64
import json
from openai import OpenAI

from modules import utils
from modules.tello_control import log_messages

AI_PROVIDER = 'GEMINI'
# AI_PROVIDER = 'LOCAL'
# AI_PROVIDER = 'OPENAI'
LOCAL_MODEL_NAME = 'minicpm-v:8b'
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
OPENAI_MODEL_NAME = 'gpt-4o-mini'
OPENAI_API_KEY = utils.get_openai_key()

utils.configure_generative_ai()
config = GenerationConfig(
    temperature=0.7,
    top_p=0.95,
    top_k=40,
    max_output_tokens=2048, # Limita o tamanho da resposta para não gastar tempo/tokens
    response_mime_type="application/json"
)

# Passa a config na inicialização do modelo
model_gemini = genai.GenerativeModel( # type: ignore
    model_name=GEMINI_MODEL_NAME,
    generation_config=config,
)

client_openai = None
if AI_PROVIDER == 'OPENAI':
    if not OPENAI_API_KEY:
        print("ERRO: OPENAI_API_KEY não encontrada no utils")
    else:
        try:
            client_openai = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            print(f"Erro ao configurar OpenAI: {e}")

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
        chat_session = model_gemini.start_chat(history=[])
        print('Sessão de chat iniciada.')
    return chat_session

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

def get_ai_instruction(objective, history, height, step) -> str:
    """
    Gera o prompt para a IA com base no contexto atual.
    Args:
        objective (str): Objetivo da missão.
        history (str): Histórico de comandos.
        height (int): Altura atual do drone em cm.
        step (int): Passo atual na sequência de comandos.
    Returns:
        str: Instrução formatada para a IA.
    """
    if step == 0:
        return f"""
            ATUAR COMO PILOTO DE DRONE TELLO (Simulação Lógica).
            Objetivo: {objective}
            Histórico: {history}
            Comandos válidos: {COMMAND_LIST}
            Altura do drone: {height} (10cm geralmente significa que está no chão)

            Comandos de voo requerem argumento numérico em cm: forward 20 (para frente 20cm)
            Comandos de rotação em graus: cw 90 (girar sentido horário 90 graus)
            Comandos que não precisam de argumento: [takeoff, land]
            Valores dos argumentos devem estar entre: [20, 500], representam a distância em cm (movimentos) ou graus [1-360] (rotações)
            Avalie se é necessário continuar a missão, se não for necessário: "continua": false

            SAÍDA OBRIGATÓRIA EM JSON:
            {{
                "analise": "Explicação breve da situação e obstáculos em português.",
                "plano": "1. Passo atual, 2. Próximo passo",
                "comando": "comando valor" (ex: "forward 100" ou "none"),
                "continua": boolean (true se a missão não acabou, false se acabou)
            }}
            """
    else:
        return f"""
            CONTINUAÇÃO DA MISSÃO.
            Objetivo: {objective}
            Histórico: {history}
            Altura: {height} cm
            Passo atual: {step}

            Comandos válidos: {COMMAND_LIST}
            Regras:
            1. Comandos de movimento (up, down, forward, etc) precisam de valor em cm (20-500).
            2. Rotação (cw, ccw) em graus (1-360).
            3. Se não precisar mover, use "none".

            SAÍDA OBRIGATÓRIA EM JSON:
            {{
                "analise": "Explicação breve da situação e obstáculos em português.",
                "plano": "2 próximos passos",
                "comando": "comando valor" (ex: "forward 100" ou "none"),
                "continua": boolean (true se a missão não acabou, false se acabou)
            }}
            """

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
    
def pil_image_to_base64(image: Image.Image) -> str:
    """Para DeepSeek/OpenAI"""
    img_bytes = pil_image_to_bytes(image)
    return base64.b64encode(img_bytes).decode('utf-8')

def parse_json_response(text_response: str) -> dict:
    """
    Função unificada para parsear respostas JSON de qualquer provedor de IA.
    Args:
        text_response (str): Resposta em texto da IA.
    Returns:
        dict: Dicionário com os campos esperados.
    """
    try:
        text_response = text_response.strip()
        
        # Limpeza de markdown se houver
        if "```json" in text_response:
            text_response = text_response.split("```json")[1].split("```")[0]
        elif "```" in text_response:
             text_response = text_response.split("```")[1].split("```")[0]
        
        # Tenta carregar o JSON
        data = json.loads(text_response)
        
        return {
            "analise": data.get("analise", "Sem análise."),
            "plano": data.get("plano", ""),
            "comando": fix_command(data.get("comando")),
            "continua": data.get("continua", False)
        }
    except json.JSONDecodeError as e:
        print(f"ERRO JSON: {e}")
        print(f"Texto recebido (Raw): {text_response}")
        
        # Retorno de segurança para não travar a UI
        return {
            "analise": "Erro na comunicação (JSON Inválido). Tentando estabilizar.",
            "comando": "none",
            "continua": False
        }
    except Exception as e:
        print(f"Erro genérico no parse: {e}")
        return {
            "analise": f"Erro: {str(e)}",
            "comando": None,
            "continua": False
        }

from PIL import ImageDraw

def add_grid_to_image(image: Image.Image) -> Image.Image:
    """
    Desenha um grid 3x3 na imagem para ajudar a IA na noção espacial.
    Args:
        image (Image.Image): Imagem original.
    Returns:
        Image.Image: Imagem com grid desenhado.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Linhas Verticais (dividir em 3)
    draw.line([(width/3, 0), (width/3, height)], fill="red", width=1)
    draw.line([(2*width/3, 0), (2*width/3, height)], fill="red", width=1)
    
    # Linhas Horizontais (dividir em 3)
    draw.line([(0, height/3), (width, height/3)], fill="red", width=1)
    draw.line([(0, 2*height/3), (width, 2*height/3)], fill="red", width=1)
    
    return img

def run_ai_local(text: str | None, frame: Image.Image) -> tuple[str, str | None, bool]:
    """
    Executa a IA localmente com Ollama retornando JSON.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
    Returns:
        tuple: (resposta formatada, comando técnico)
    """
    try:
        user_text = text if text else 'No objective provided. Analyze the scene.'

        system_prompt = f"""
            You are a DRONE PILOT AI.
            User Input: "{user_text}"

            TASK: Analyze the image and the input. Generate a flight command.
            
            RULES:
            1. Output MUST be valid JSON.
            2. "analise" and "plano" must be in Portuguese.
            3. "comando" must be technical: [direction] [value].
            4. Valid directions: up, down, forward, back, left, right, cw, ccw.
            5. If path is blocked or no action needed, command is "none".

            ### EXAMPLES (Follow this pattern):
            ### EXAMPLE 1
            Input: "Vá para a frente"
            Image: (Clear path)
            {{
                "analise": "Caminho livre à frente, sem obstáculos visíveis.",
                "plano": "Avançar 100cm com segurança.",
                "comando": "forward 100",
            }}
            ### EXAMPLE 2
            Input: "Suba um pouco"
            Image: (Ceiling is far)
            {{
                "analise": "O teto está alto, posso subir.",
                "plano": "Subir 50cm para ajustar altura.",
                "comando": "up 50",
            }}
            ### EXAMPLE 3
            Input: "Vire para a porta"
            Image: (Door is on the right)
            {{
                "analise": "Vejo a porta à direita da imagem.",
                "plano": "Girar 90 graus para alinhar com a porta.",
                "comando": "cw 90",
            }}
            ### END EXAMPLES
            """
        
        # Converte imagem
        frame_with_grid = add_grid_to_image(frame)
        img_bytes = pil_image_to_bytes(frame_with_grid)

        # Chamada ao Ollama
        response = ollama.chat(
            model=LOCAL_MODEL_NAME,
            messages=[
                {
                    'role': 'user',
                    'content': system_prompt,
                    'images': [img_bytes]
                }
            ],
            format='json', # Verificar se necessário
            options={
                'temperature': 0.0, # Menor temperatura para menores chances de alucinações
                'top_p': 0.5,
                'num_ctx': 4096,
                'seed': 42
            }
        )
        
        full_response_text = response['message']['content']

        # Usa o parser unificado criado anteriormente
        data = parse_json_response(full_response_text)

        # Formata o texto para exibição no chat da interface
        chat_display_text = f"Análise: {data['analise']}\nPlano: {data['plano']}\nComando: {data['comando']}"
        return chat_display_text, data['comando'], False

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"DEBUG: Erro em run_ai_local: {str(e)}\n{error_details}")
        # Retorno de segurança
        return f"Erro Local: {str(e)}", None, False

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
        user_text = text if text else 'Analise a cena.'
        formatted_log = ", ".join(log_messages[-3:]) if log_messages else 'Nenhum.'

        system_prompt = get_ai_instruction(user_text, formatted_log, height, step)
        frame_with_grid = add_grid_to_image(frame)

        response = current_chat.send_message([system_prompt, frame_with_grid])

        if not response.parts:
            print("\n--- DEBUG GEMINI BLOQUEADO ---")
            if hasattr(response, 'prompt_feedback'):
                print(f"Prompt Feedback: {response.prompt_feedback}")
            if hasattr(response, 'candidates') and response.candidates:
                print(f"Finish Reason: {response.candidates[0].finish_reason}")
                print(f"Safety Ratings: {response.candidates[0].safety_ratings}")
            print("------------------------------\n")
            return "Erro: Bloqueio de Segurança Rígido.", None, False
        
        # Processa o JSON
        data = parse_json_response(response.text)
        
        # Retorna formatado como a interface espera: (Texto para o chat, Comando Técnico, Bool Continua)
        chat_display_text = f"Análise: {data['analise']}\nPlano: {data['plano']}\nComando: {data['comando']}\nContinuar: {data['continua']}"
        return chat_display_text, data['comando'], data['continua']

    except Exception as e:
        return f"Erro crítico: {str(e)}", None, False
    
def run_ai_openai(text: str | None, frame: Image.Image, step: int=0, height: int=0) -> tuple[str, str | None, bool]:
    if not client_openai:
        return "Erro: OpenAI client não configurado (Verifique a API KEY).", None, False

    try:
        user_text = text if text else 'Analise.'
        frame_with_grid = add_grid_to_image(frame)
        base64_image = pil_image_to_base64(frame_with_grid)
        formatted_log = ", ".join(log_messages[-3:])

        system_prompt = get_ai_instruction(user_text, formatted_log, height, step)

        response = client_openai.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            response_format={ "type": "json_object" },
            max_tokens=300
        )

        full_text = response.choices[0].message.content
        if not full_text:
            return "Erro OpenAI: Resposta vazia.", None, False
        data = parse_json_response(full_text)
        
        chat_display_text = f"Análise: {data['analise']}\nPlano: {data['plano']}"
        return chat_display_text, data['comando'], data['continua']

    except Exception as e:
        return f"Erro OpenAI: {str(e)}", None, False
    
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
    if AI_PROVIDER == 'LOCAL':
        return run_ai_local(text, frame)
    elif AI_PROVIDER == 'OPENAI':
        return run_ai_openai(text, frame)
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