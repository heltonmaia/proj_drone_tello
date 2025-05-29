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

        # Constrói o prompt completo para o turno atual.
        # Esta estrutura de prompt é enviada em cada turno para fornecer contexto completo.
        # O histórico do chat também será usado implicitamente pelo modelo.
        content_for_turn = [
            f"""
            ANÁLISE DE CENA PARA CONTROLE DE DRONE TELLO

            Contexto:
            - Você é um sistema de IA avançado controlando um drone Tello em um ambiente interno.
            - Objetivo Principal para esta interação: {prompt}
            - Comandos de voo disponíveis: {COMMAND_LIST}
            - Histórico de comandos enviados ao drone nesta sessão: {formatted_log_messages}
            - Unidades: Distâncias em centímetros (cm) para movimentos (ex: 'forward 50' para 50 cm para a frente). Rotações em graus (ex: 'cw 90' para 90 graus em sentido horário).

            Instruções Detalhadas:
            1.  Analise cuidadosamente a imagem fornecida (representa a visão atual do drone).
            2.  Identifique obstáculos, alvos, ou condições relevantes para o 'Objetivo Principal'.
            3.  Com base na análise, no objetivo, e no histórico de comandos, decida a próxima ação.
            4.  Gere UM ÚNICO comando técnico da lista de comandos disponíveis.
                - Para movimentos (up, down, left, right, forward, back), SEMPRE inclua a distância em cm (geralmente entre 20-500 cm). Ex: 'forward 30'.
                - Para rotações (cw, ccw), SEMPRE inclua os graus (geralmente entre 1-360 graus). Ex: 'ccw 45'.
                - 'takeoff' e 'land' não necessitam de parâmetros numéricos.
            5.  Forneça uma justificativa clara e concisa para sua decisão, explicando como ela contribui para o objetivo ou para a segurança.
            6.  Se nenhum comando for apropriado ou seguro no momento, ou se o objetivo parecer satisfeito com base na cena, o comando deve ser "Nenhum comando necessário".

            Formato Obrigatório da Resposta (use exatamente estes marcadores):
            [ANÁLISE] Descrição detalhada da cena na imagem, incluindo objetos, distâncias estimadas se possível, e sua relevância para o objetivo.
            [DECISÃO] O comando técnico exato (ex: 'forward 50', 'land', 'nenhum comando necessário').
            [JUSTIFICATIVA] Explicação concisa da decisão tomada, relacionando-a com a análise da cena e o objetivo.

            Restrições Adicionais:
            - Priorize a segurança. Evite colisões.
            - Os comandos devem ser para ações de curta a média distância, adequadas para ambientes internos.
            - Se o drone estiver muito perto de um obstáculo na direção do movimento desejado, sugira um comando alternativo ou "Nenhum comando necessário" se não houver rota segura.
            """,
            Image.fromarray(frame)
        ]

        # Envia a mensagem para a sessão de chat ativa
        response = current_chat.send_message(content_for_turn)

        # Verifica se a resposta foi bloqueada ou está vazia
        if not response.parts:
            error_message = "Resposta da IA bloqueada ou vazia."
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                error_message += f" Causa: {response.prompt_feedback.block_reason if hasattr(response.prompt_feedback, 'block_reason') else 'Não especificada'}."
                # print(f"DEBUG: Prompt Feedback: {response.prompt_feedback}")
                if hasattr(response.prompt_feedback, 'safety_ratings'):
                    for rating in response.prompt_feedback.safety_ratings:
                        if rating.probability != 'NEGLIGIBLE':
                             error_message += f" Categoria de Segurança: {rating.category}, Probabilidade: {rating.probability}."
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