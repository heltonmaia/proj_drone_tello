import google.generativeai as genai
from PIL import Image
import numpy as np
import traceback
from scipy.io.wavfile import write
import io

from modules import utils
from modules.tello_control import log_messages

utils.configure_generative_ai()
model = genai.GenerativeModel(model_name='gemini-1.5-flash') # type: ignore

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

def run_ai(text: str | None, audio: np.ndarray | None, frame: Image.Image) -> tuple[str, str | None, bool]:
    """
    Executa a IA para gerar comandos de controle do drone.
    Args:
        text (str | None): Descrição do que o drone deve fazer.
        audio (np.ndarray | None): Áudio do usuário.
        frame (Image.Image): Frame da câmera atual.
    Returns:
        tuple: (resposta natural, comando técnico)
    """

    try:
        current_chat = get_chat_session()
        content_for_turn = []
        SAMPLE_RATE = 44100

        # Garante que log_messages seja uma string formatada para o prompt
        formatted_log_messages = ", ".join(log_messages) if log_messages and isinstance(log_messages, list) else 'Nenhum comando enviado anteriormente nesta sessão.'

        if audio is not None:
            print("Áudio detectado.")
            
            mem_wav = io.BytesIO()
            write(mem_wav, SAMPLE_RATE, audio)
            wav_data = mem_wav.getvalue()

            # A API do Gemini espera um dicionário com 'mime_type' e 'data' para os "parts"
            audio_part = {
                "mime_type": "audio/wav",
                "data": wav_data,
            }
            content_for_turn.append(audio_part)
            
            user_text = 'O objetivo principal foi fornecido por áudio. Analise o arquivo de áudio anexado e use-o como o principal objetivo para esta interação.'
        else:
            # Se não houver áudio, usa a lógica de texto
            user_text = text if text else 'Nenhum objetivo fornecido. Analise a cena e sugira uma ação segura, sem comandos de movimento'

        system_prompt = f"""
            ANÁLISE DE CENA E COMANDO PARA DRONE TELLO

            Contexto:
            - Você é um sistema de IA avançado controlando um drone Tello em um ambiente interno.
            - Sua tarefa é analisar a imagem da câmera do drone e um objetivo fornecido (por texto ou áudio) para gerar o próximo comando de voo.
            - Histórico de comandos enviados ao drone nesta sessão: {formatted_log_messages}
            - Comandos de voo disponíveis: {COMMAND_LIST}
            - Unidades: Distâncias em cm, rotações em graus.

            Objetivo Principal para esta interação:
            {user_text}

            Instruções Detalhadas:
            1.  Analise cuidadosamente a imagem fornecida, que representa a visão atual do drone.
            2.  Identifique obstáculos, alvos, ou condições relevantes para o objetivo principal.
            3.  Com base na análise, no objetivo, e no histórico de comandos, decida a próxima ação.
            4.  Gere um comando técnico da lista de comandos disponíveis.
                - Para movimentos (up, down, left, right, forward, back), SEMPRE inclua a distância em cm (geralmente entre 20-500 cm). Ex: 'forward 30'.
                - Para rotações (cw, ccw), SEMPRE inclua os graus (entre 1-360 graus). Ex: 'ccw 45'.
                - 'takeoff' e 'land' não necessitam de parâmetros numéricos.
            5.  Forneça uma justificativa para sua decisão, explicando como ela contribui para o objetivo ou para a segurança.
            6.  Se nenhum comando for apropriado ou seguro no momento, ou se o objetivo parecer satisfeito com base na cena (como: "descreva a imagem"), o comando deve ser "nenhum comando necessário".
            7.  Caso o objetivo não possa ser cumprido com um único movimento, sinalize que a rota deve continuar da seguinte forma: adicione o marcador "[CONTINUA]", isso inicia o processo de comandos compostos. Priorize movimentos simples, sem continuação.
            8.  Caso nenhum comando seja necessário, não deve ter continuação de rota.
            9.  Em comandos compostos, evite fazer movimentos para direções fora de seu campo de visão. Primeiro avalie a cena.

            Formato Obrigatório da Resposta:
            [ANÁLISE] Descrição da cena.
            [DECISÃO] O comando técnico exato.
            [JUSTIFICATIVA] Explicação da decisão.
            [CONTINUA] Caso seja necessário continuar a trajetória. Caso contrário, omita esta linha.
            """

        # Constrói o prompt para o turno atual.
        content_for_turn.insert(0, system_prompt)
        
        content_for_turn.append(frame)

        # Envia a mensagem para a sessão de chat ativa
        response = current_chat.send_message(content_for_turn)

        # Verifica se a resposta foi bloqueada ou está vazia
        if not response.parts:
            error_message = "Resposta da IA bloqueada ou vazia."
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                error_message += f" Causa: {response.prompt_feedback.block_reason if hasattr(response.prompt_feedback, 'block_reason') else 'Não especificada'}."
            return error_message, None, False

        natural_response_text = response.text
        extracted_command = None
        continue_route = False

        # Extração do comando
        response_lines = natural_response_text.split('\n')
        for line in response_lines:
            if line.startswith('[DECISÃO]'):
                command_text = line.replace('[DECISÃO]', '').strip()
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