import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from PIL import Image
import traceback
import ollama
import io

from modules import utils
from modules.tello_control import log_messages

USE_LOCAL_AI = False
LOCAL_MODEL_NAME = 'minicpm-v:8b'
API_MODEL_NAME = 'gemini-2.0-flash'

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

def pil_image_to_bytes(image: Image.Image) -> bytes:
    """Converte PIL Image para bytes, redimensionando para performance local."""
    base_width = 640
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    
    img_resized = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
    
    with io.BytesIO() as buffer:
        img_resized.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()

def run_ai_local(text: str | None, frame: Image.Image, step: int=0, height: int=0) -> tuple[str, str | None, bool]:
    """
    Executa a IA localmente com Ollama.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        frame (Image.Image): Frame da câmera do drone.
        step (int): Passo atual na sequência de comandos.
        height (int): Altura atual do drone em cm.
    Returns:
        tuple: (resposta natural, comando técnico, continuar rota)
    """
    try:
        user_text = text if text else 'No objective provided. Analyze the scene'
        formatted_log_messages = ", ".join(log_messages) if log_messages else 'Empty.'

        system_prompt = f"""
            You are an advanced drone pilot AI controlling a Tello Drone.
            
            CURRENT MISSION CONTEXT:
            - Input/Objective: "{user_text}"
            - Command History: {formatted_log_messages}
            
            INSTRUCTIONS:
            1. Analyze the image to find obstacles or targets related to the Objective.
            2. Plan the next move safely. 
            3. OUTPUT FORMAT (Strictly followed):

            [ANÁLISE] (Write this in Portuguese) Visual description and status.
            [PLANO] (Write this in Portuguese) 1. Next step. 2. Future steps.
            [COMANDO] command value
            [CONTINUA] (Tag mandatory only if more steps are needed)

            AVAILABLE COMMANDS (Use EXACTLY these words):
            - Movement: forward, back, left, right, up, down (val: 20-500)
            - Rotation: cw, ccw (val: 1-360)
            - System: takeoff, land

            EXAMPLES:
            
            Input: "Vá para a porta" (Turn 1)
            ## EXAMPLE OUTPUT TURN 1 ##
            [ANÁLISE] Vejo uma cadeira bloqueando o caminho.
            [PLANO] 1. Girar para desviar. 2. Avançar.
            [COMANDO] cw 20
            [CONTINUA]
            ## END EXAMPLE OUTPUT TURN 1 ##

            Input: "Vá para a porta. ANÁLISE ANTERIOR: Girei para desviar." (Turn 2)
            ## EXAMPLE OUTPUT TURN 2 ##
            [ANÁLISE] Caminho livre agora. Vejo a porta.
            [PLANO] 1. Avançar até a porta.
            [COMANDO] forward 100
            [CONTINUA]
            ## END EXAMPLE OUTPUT TURN 2 ##
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
                'temperature': 0.6,  # (0.0 a 1.0) Quanto menor, mais determinístico/lógico.
                'top_p': 0.8,        # (0.0 a 1.0) Considera apenas as top 50% probabilidades.
                'num_ctx': 4096,     # Tamanho da janela de contexto (memória).
                'seed': 42           # Semente fixa para tentar reproduzir sempre a mesma resposta.
            }
        )

        full_response_text = ""

        for chunk in stream:
            part = chunk['message']['content']
            full_response_text += part

        extracted_command = None
        continue_route = False
        
        lines = full_response_text.split('\n')
        for line in lines:
            line = line.strip()
            
            if '[COMANDO]' in line.upper():
                raw_content = line.split(']')[-1].strip()
                
                parts = raw_content.split()
                
                if len(parts) >= 1:
                    cmd = parts[0].lower()
                    
                    if cmd in ['land', 'takeoff']:
                        extracted_command = cmd
                    
                    elif len(parts) >= 2:
                        val = parts[1]
                        val_clean = ''.join(filter(str.isdigit, val))
                        
                        candidate = f"{cmd} {val_clean}"
                        
                        if validate_command(candidate):
                            extracted_command = candidate
            
            if '[CONTINUA]' in line.upper():
                continue_route = True
        
        # Fallback de segurança: Se a IA local falhar a formatação mas escrever o comando
        if not extracted_command:
             for line in lines:
                 for valid_cmd in COMMAND_LIST:
                     if line.lower().startswith(valid_cmd):
                         if validate_command(line):
                             extracted_command = line
                             break

        return full_response_text, extracted_command, continue_route

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
                ANÁLISE DE CENA E COMANDO PARA DRONE TELLO

                Contexto:
                - Você é um sistema de IA avançado controlando um drone Tello. Sua missão é navegar em um ambiente interno para cumprir um objetivo.
                - Comandos disponíveis: {COMMAND_LIST}
                - Comandos enviados até agora: {formatted_log_messages}
                - Altura do drone: {height} cm. Normalmente, por imprecisão, 10cm significa que ele está no chão.

                Objetivo Principal:
                {user_text}

                Instruções de Raciocínio Passo a Passo:
                1.  Observar: Analise a imagem atual. Onde estão os principais objetos? Onde estão os obstáculos?
                2.  Orientar: Compare sua observação com o 'Objetivo Principal'. O drone está virado para a direção certa? Se o objetivo é 'ir para a cadeira' e a cadeira está à sua direita, a primeira ação DEVE ser girar para a direita.
                3.  Planejar: Crie um plano simples com os próximos 1-2 movimentos para se aproximar do objetivo. O plano deve ser seguro.
                4.  Decidir: Com base no seu plano, escolha APENAS o primeiro comando a ser executado AGORA.
                Obs:
                    1. Comandos de movimento obrigatoriamente necessitam da distância ou ângulo (ex: "forward 100", "ccw 90") (de 10 a 500). Comandos sem parâmetros (ex: "takeoff", "land") não necessitam.
                    2. Sinalizar: Se o seu plano tem mais de um passo, adicione a linha "[CONTINUA]". Se este comando único completa a tarefa, omita a linha.
                    3. A imagem que você vê é uma foto enviada no momento do envio de cada comando.

                Exemplo de Raciocínio para "vá para a mesa":
                ## RESPOSTA EXEMPLO TURNO 1 ##
                [ANÁLISE] Vejo uma mesa à minha esquerda e uma parede em frente.
                [PLANO] 1. Girar 90 graus para a esquerda (ccw 90) para encarar a mesa. 2. Avançar em direção à mesa (forward 100).
                [COMANDO] ccw 90
                [CONTINUA]
                ## FIM RESPOSTA EXEMPLO TURNO 1 ##

                ## RESPOSTA EXEMPLO TURNO 2 ##
                [ANÁLISE] Agora estou encarando a mesa, que está a cerca de 100 cm de distância.
                [PLANO] 1. Avançar 100 cm para alcançar a mesa. 2. Nenhum outro passo necessário.
                [COMANDO] forward 100
                ## FIM RESPOSTA EXEMPLO TURNO 2 ##

                Formato Obrigatório da Resposta:
                [ANÁLISE] Descrição da cena e sua orientação em relação ao objetivo.
                [PLANO] Seu plano de 1 a 2 passos para alcançar o objetivo.
                [COMANDO] O comando técnico exato para o PRIMEIRO passo do seu plano.
                [CONTINUA] Opcional. Adicione esta linha apenas se o seu plano tiver mais passos.
                Estou testando o programa, não decole o drone
                """
        else:
            system_prompt = f"""
                CONTINUAÇÃO DE COMANDO
                Você sinalizou que sua tarefa não estava completa. Continue seu raciocínio e planejamento com base na imagem atual.
                Lembre-se de revisar o 'Objetivo Principal' e ajustar seu plano conforme necessário.
                Objetivo Principal:
                {user_text}
                Comandos enviados até agora: {formatted_log_messages}
                Altura: {height} cm.
                Forneça sua próxima decisão de comando seguindo o mesmo formato rigoroso.
                Formato Obrigatório da Resposta:
                [ANÁLISE] Descrição da cena e sua orientação em relação ao objetivo.
                [PLANO] Seu plano de 1 a 2 passos para alcançar o objetivo.
                [COMANDO] O comando técnico exato para o PRIMEIRO passo do seu plano.
                [CONTINUA] Opcional. Adicione esta linha apenas se o seu plano tiver mais passos.
                """

        # Constrói o prompt para o turno atual.
        content_for_turn = [system_prompt, frame]
        
        # Envia a mensagem para a sessão de chat ativa
        response = current_chat.send_message(content_for_turn)

        # Verifica se a resposta foi bloqueada ou está vazia
        # Se falhar, vamos imprimir EXATAMENTE o que o Google retornou
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
            if line.startswith('[COMANDO]'):
                command_text = line.replace('[COMANDO]', '').strip()
                if command_text.lower() == 'nenhum comando necessário' or not command_text:
                    extracted_command = None
                else:
                    extracted_command = command_text
                continue
            
            elif line.startswith('[CONTINUA]'):
                continue_route = True
        
        return natural_response_text, extracted_command, continue_route

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"DEBUG: Erro em run_ai: {str(e)}\n{error_details}")
        return f"Erro crítico ao processar com IA: {str(e)}", None, False
    
def run_ai(text: str | None, frame: Image.Image, step: int=0, height: int=0) -> tuple[str, str | None, bool]:
    """Função Mestra que decide qual IA usar."""
    if USE_LOCAL_AI:
        return run_ai_local(text, frame, step, height)
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