import google.generativeai as genai
from PIL import Image
import traceback
from modules import utils
from modules.tello_control import log_messages

utils.configure_generative_ai()
model = genai.GenerativeModel('gemini-1.5-flash')

# Variável global para armazenar o objeto da sessão de chat
chat_session = None

COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]

def get_chat_session():
    """
    Inicializa e retorna a sessão de chat.
    O chat é iniciado com um histórico vazio, pois o contexto completo é fornecido em cada mensagem.
    """
    global chat_session
    if chat_session is None:
        chat_session = model.start_chat(history=[])
        print("Sessão de chat iniciada.")
    return chat_session

def run_ai(prompt: str, frame: object) -> tuple:
    """
    Executa a IA para gerar comandos de controle do drone.
    Args:
        prompt (str): Descrição do que o drone deve fazer.
        frame (object): Frame da câmera atual.
    Returns:
        tuple: (resposta natural, comando técnico)
    """
    try:
        current_chat = get_chat_session()

        # Garante que log_messages seja uma string formatada para o prompt
        formatted_log_messages = ", ".join(log_messages) if log_messages and isinstance(log_messages, list) else "Nenhum comando enviado anteriormente nesta sessão."

        user_prompt = prompt if prompt else "Nenhum objetivo fornecido. Analise a cena e sugira uma ação segura."

        # Constrói o prompt do sistema para o turno atual
        system_prompt = f"""
            ANÁLISE DE CENA E COMANDO PARA DRONE TELLO

            Contexto:
            - Você é um sistema de IA avançado controlando um drone Tello em um ambiente interno.
            - Sua tarefa é analisar a imagem da câmera do drone e um objetivo fornecido (por texto ou áudio) para gerar o próximo comando de voo.
            - Histórico de comandos enviados ao drone nesta sessão: {formatted_log_messages}
            - Comandos de voo disponíveis: {COMMAND_LIST}
            - Unidades: Distâncias em cm, rotações em graus.

            Objetivo Principal para esta interação:
            {user_prompt}

            Instruções Detalhadas:
            1.  Analise cuidadosamente a imagem fornecida (representa a visão atual do drone).
            2.  Identifique obstáculos, alvos, ou condições relevantes para o 'Objetivo Principal'.
            3.  Com base na análise, no objetivo, e no histórico de comandos, decida a próxima ação.
            4.  Gere UM ÚNICO comando técnico da lista de comandos disponíveis.
                - Para movimentos (up, down, left, right, forward, back), SEMPRE inclua a distância em cm (geralmente entre 20-500 cm). Ex: 'forward 30'.
                - Para rotações (cw, ccw), SEMPRE inclua os graus (geralmente entre 1-360 graus). Ex: 'ccw 45'.
                - 'takeoff' e 'land' não necessitam de parâmetros numéricos.
            5.  Forneça uma justificativa clara e concisa para sua decisão, explicando como ela contribui para o objetivo ou para a segurança.
            6.  Se nenhum comando for apropriado ou seguro no momento, ou se o objetivo parecer satisfeito com base na cena, o comando deve ser "nenhum comando necessário".

            Formato Obrigatório da Resposta:
            [ANÁLISE] Descrição da cena e sua relevância para o objetivo.
            [DECISÃO] O comando técnico exato.
            [JUSTIFICATIVA] Explicação da decisão.
            """

        # Constrói o prompt completo para o turno atual.
        # Esta estrutura de prompt é enviada em cada turno para fornecer contexto completo.
        # O histórico do chat também será usado implicitamente pelo modelo.
        content_for_turn = [
            system_prompt,
            Image.fromarray(frame)
        ]

        # Envia a mensagem para a sessão de chat ativa
        response = current_chat.send_message(content_for_turn)

        # Verifica se a resposta foi bloqueada ou está vazia
        if not response.parts:
            error_message = "Resposta da IA bloqueada ou vazia."
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                error_message += f" Causa: {response.prompt_feedback.block_reason if hasattr(response.prompt_feedback, 'block_reason') else 'Não especificada'}."
            return error_message, None

        natural_response_text = response.text
        extracted_command = None

        # Extração do comando
        response_lines = natural_response_text.split('\n')
        for line in response_lines:
            if line.startswith("[DECISÃO]"):
                command_text = line.replace("[DECISÃO]", "").strip()
                if command_text.lower() == "nenhum comando necessário" or not command_text:
                    extracted_command = None
                else:
                    extracted_command = command_text
                break
        
        return natural_response_text, extracted_command

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"DEBUG: Erro em run_ai: {str(e)}\n{error_details}")
        return f"Erro crítico ao processar com IA: {str(e)}", None
    
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
                if not (20 <= val <= 500): return False
        except ValueError:
            return False # Não é um número inteiro
    # Comandos que não requerem argumento numérico
    elif base_cmd in ['land', 'takeoff']:
        if len(parts) != 1:
            return False

    return True