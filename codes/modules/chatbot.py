import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from PIL import Image, ImageDraw
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
ACCEPTED_ROTATIONS = [10, 15, 30, 45, 90, 135, 180, 360]
COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]
SYSTEM_INSTRUCTION_TEXT = f"""
VOCÊ É UM PILOTO DE DRONE TELLO.
Comandos válidos: {COMMAND_LIST}
Argumentos numéricos em cm [20-500] ou graus [1-360].
Exemplos: 'forward 100', 'cw 90', 'takeoff', 'land'.

SAÍDA OBRIGATÓRIA EM JSON:
{{
    "analise": "Breve descrição visual e do status em português.",
    "plano": "O que fará a seguir.",
    "comando": "comando valor" (ou "none"),
    "continua": boolean (true se a missão não acabou)
}}
"""
openai_history = []

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
chat_session_gemini = None

def get_chat_session():
    """
    Inicializa e retorna a sessão de chat.
    O chat é iniciado com um histórico vazio, pois o contexto completo é fornecido em cada mensagem.
    Returns:
        ChatSession: A sessão de chat.
    """
    global chat_session_gemini
    if chat_session_gemini is None:
        chat_session_gemini = model_gemini.start_chat(history=[])
        print('Sessão de chat iniciada.')
    return chat_session_gemini

def reset_openai_history():
    """Limpa o histórico da OpenAI para iniciar nova missão."""
    global openai_history
    openai_history = []

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

def get_ai_instruction(objective: str, history: str, height: int, step: int, max_steps: int) -> str:
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
            Passo: {step}/{max_steps}

            Comandos válidos: {COMMAND_LIST}

            SAÍDA OBRIGATÓRIA EM JSON:
            {{
                "analise": "Explicação breve da situação e obstáculos em português.",
                "plano": "2 próximos passos",
                "comando": "comando valor" (ex: "forward 100" ou "none"),
                "continua": boolean (true se a missão não acabou, false se acabou)
            }}
            """
    
def get_step_prompt(objective: str, last_action: str, height: int, step: int, max_steps: int) -> str:
    """
    Gera apenas o delta do prompt para o passo atual.
    Args:
        objective (str): Objetivo da missão.
        last_action (str): Última ação executada pelo drone.
        height (int): Altura atual do drone em cm.
        step (int): Passo atual na sequência de comandos.
        max_steps (int): Número máximo de passos permitidos.
    Returns:
        str: Prompt formatado para o passo atual.
    """
    return f"""
    STATUS ATUAL:
    - Objetivo Global: "{objective}"
    - Passo: {step + 1}/{max_steps}
    - Altura: {height} cm
    - Última Ação Executada: "{last_action}"
    
    Analise a imagem atual e determine o próximo comando.
    Siga a formatação JSON obrigatória.
    """

def _snap_to_closest(value: int, allowed_values: list[int]) -> int:
    """
    Encontra o valor mais próximo dentro de uma lista de permitidos.
    Args:
        value (int): Valor a ser ajustado.
        allowed_values (list[int]): Lista de valores permitidos.
    Returns:
        int: Valor ajustado mais próximo.
    """
    return min(allowed_values, key=lambda x: abs(x - value))

def extract_command(text: str) -> str | None:
    """
    Extrai comandos em qualquer posição da linha.
    Args:
        text (str): Texto bruto.
    Returns:
        str | None: Comando extraído ou None se inválido.
    """
    if not text: return None
    text = text.lower()

    pattern = r'(up|down|left|right|forward|back|cw|ccw)[^\d]*(\d+)'
    match = re.search(pattern, text)
    
    if match:
        cmd = match.group(1)
        val = match.group(2)
        return f"{cmd} {val}"

    # Comandos sem valor
    if "takeoff" in text:
        return "takeoff"
    if "land" in text:
        return "land"
    
    # Tratamento para "none" ou falha
    return None

def fix_command(raw_command: str) -> str | None:
    """
    Ajusta o comando recebido para o formato técnico esperado.
    Args:
        raw_command (str): Comando bruto recebido da IA.
    Returns:
        str | None: Comando ajustado ou None se inválido.
    """
    if not raw_command:
        return None
        
    clean_text = raw_command.lower().strip()
    
    if clean_text == "none" or not clean_text:
        return None
        
    parts = clean_text.split()
    cmd = parts[0]

    # Comandos de sistema (sem valor)
    if cmd in ['takeoff', 'land']:
        return cmd

    # Tratamento de valor
    val = 0
    
    # Comandos que requerem valor
    # Caso 1: Comando veio sem número -> Aplica padrão
    if len(parts) == 1:
        if cmd in ['cw', 'ccw']:
            val = 90
        elif cmd in ['up', 'down', 'left', 'right', 'forward', 'back']:
            val = 50
    
    # Caso 2: Comando com número -> Aplica Snapping
    elif len(parts) >= 2:
        val_str = ''.join(filter(str.isdigit, parts[1])) # Extrai apenas dígitos
        if not val_str:
            val = 90 if cmd in ['cw', 'ccw'] else 50 # Se falhar em achar número, usa padrão
        else:
            val = int(val_str)

    final_val = val

    # Rotações: Arredonda para valores aceitos
    if cmd in ['cw', 'ccw']:
        val = max(1, min(val, 360)) # Garante limites absolutos antes de arredondar
        final_val = _snap_to_closest(val, ACCEPTED_ROTATIONS)

    # Movimentos: Arredonda para múltiplos de 10
    elif cmd in ['up', 'down', 'left', 'right', 'forward', 'back']:
        final_val = int(round(val / 10.0) * 10) # Arredonda para a dezena mais próxima
        final_val = max(20, min(final_val, 500)) # Garante limites do SDK Tello (20-500)

    return f"{cmd} {final_val}"

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
    """
    Converte uma imagem PIL para uma string base64, para uso com a API OpenAI.
    Args:
        image (Image.Image): Imagem PIL.
    Returns:
        str: Imagem codificada em base64.
    """
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
        frame_grid = add_grid_to_image(frame)
        img_bytes = pil_image_to_bytes(frame_grid)

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
                'top_p': 0.9,
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

def run_ai_gemini(text: str | None, frame: Image.Image, step: int=0, height: int=0, max_steps: int=7) -> tuple[str, str | None, bool]:
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
        current_chat = get_chat_session()
        user_text = text if text else 'Analise a cena.'
        formatted_log = ", ".join(log_messages[-5:]) if log_messages else 'Nenhum.'

        system_prompt = get_ai_instruction(user_text, formatted_log, height, step, max_steps)
        frame_grid = add_grid_to_image(frame)

        response = current_chat.send_message([system_prompt, frame_grid])

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
    
def run_ai_openai(text: str | None, frame: Image.Image, step: int=0, height: int=0, last_action: str="Nenhuma", max_steps: int=7) -> tuple[str, str | None, bool]:
    global openai_history
    if not client_openai: return "Erro OpenAI Client.", None, False

    try:
        if step == 0:
            reset_openai_history()
        if not text:
            text = "Analise a cena."
        prompt = get_step_prompt(text, last_action, height, step, max_steps)

        frame_grid = add_grid_to_image(frame)
        base64_img = pil_image_to_base64(frame_grid)

        current_user_msg = {
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
            model=OPENAI_MODEL_NAME,
            messages=openai_history,
            response_format={ "type": "json_object" },
            max_tokens=300,
            temperature=0.7,
        )

        full_text = response.choices[0].message.content
        if not full_text:
            return "Erro OpenAI: Resposta vazia.", None, False
        data = parse_json_response(full_text)

        openai_history.append({"role": "assistant", "content": full_text})
        
        last_user_index = len(openai_history) - 2
        if openai_history[last_user_index]['role'] == 'user':
            openai_history[last_user_index]['content'] = f"[Passo {step}] Prompt: {prompt} | Imagem processada."

        chat_text = f"Análise: {data['analise']}\nPlano: {data['plano']}"
        return chat_text, data['comando'], data['continua']

    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return f"Erro OpenAI: {str(e)}", None, False

def run_ai(text: str | None, frame: Image.Image, step: int=0, height: int=0, last_action: str="Nenhuma", max_steps: int=7) -> tuple[str, str | None, bool | None]:
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
    if AI_PROVIDER == 'LOCAL':
        return run_ai_local(text, frame)
    elif AI_PROVIDER == 'OPENAI':
        return run_ai_openai(text, frame, step, height, last_action, max_steps)
    else:
        return run_ai_gemini(text, frame, step, height, max_steps)

def validate_command(cmd: str) -> bool:
    """
    Valida o comando recebido.
    Args:
        cmd (str): Comando recebido.
    Returns:
        bool: True se o comando for válido, False caso contrário.
    """
    if not cmd: return False
    
    parts = cmd.lower().split()
    if not parts or parts[0] not in COMMAND_LIST:
        return False

    base_cmd = parts[0]

    # Comandos de Sistema (sem argumento)
    if base_cmd in ['takeoff', 'land']:
        return len(parts) == 1

    # Comandos de Movimento/Rotação (precisam de 1 argumento numérico)
    return len(parts) == 2 and parts[1].isdigit()