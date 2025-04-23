import google.generativeai as genai
from PIL import Image
import streamlit as st
from modules import utils
import threading

utils.configure_generative_ai()
model = genai.GenerativeModel('gemini-1.5-flash')

COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]

def update_chat_history(response: str, timestamp: str):
    """
    Atualiza o histórico de forma thread-safe.
    Args:
        response (str): Resposta da IA.
        timestamp (str): Timestamp da mensagem.
    """
    for entry in st.session_state.chat_history:
        if entry["timestamp"] == timestamp and entry["status"] == "processing":
            entry["ai"] = response # Atualiza a resposta da IA
            entry["status"] = "completed" # Atualiza o status para completo
            break

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
        response = model.generate_content([
            f"""
            ANÁLISE DE CENA PARA CONTROLE DE DRONE
            
            Contexto:
            - Você é um controlador de drone autônomo
            - Objetivo: {prompt}
            - Comandos disponíveis: {COMMAND_LIST}
            - Unidades: centímetros para movimentos e graus para rotações
            
            Instruções:
            1. Analise a imagem atual
            2. Identifique obstáculos/alvos
            3. Gere o comando apropriado
            4. Justifique a decisão
            5. Dê comandos de curta distância (ex: 'forward 50') ou de rotação (ex: 'cw 90'), pois o ambiente é indoor
            
            Formato da Resposta:
            [ANÁLISE] Descrição da cena
            [DECISÃO] Comando técnico (ex: 'forward 50')
            [JUSTIFICATIVA] Explicação da ação

            Os comandos de movimentos precisam necessariamente de um passo em cm, land e takeoff não precisam de passo.
            Caso não seja necessário nenhum movimento, retorne apenas a análise.
            """,
            Image.fromarray(frame)
        ])

        # Processa a resposta
        parts = response.text.split('\n')
        natural_response = "\n".join(parts)
        command = None
        for p in parts:
            if "[DECISÃO]" in p:
                try:
                    # Tenta dividir por qualquer separador após o marcador
                    decision_part = p.split("[DECISÃO]")[1].strip() # Pega tudo após o marcador [DECISÃO]
                    command = decision_part                         # Retorna o comando completo
                    break
                except (IndexError, AttributeError):
                    continue

        return natural_response, command

    except Exception as e:
        return f"Erro3: {str(e)}", None
    
def validate_command(cmd: str) -> bool:
    """
    Valida o comando recebido
    Args:
        cmd (str): Comando recebido
    Returns:
        bool: True se o comando for válido, False caso contrário
    """
    parts = cmd.strip().split()
    if not parts:
        return False

    base_cmd = parts[0].lower()

    if base_cmd not in COMMAND_LIST:
        return False

    if base_cmd in ['up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw']:
        if len(parts) != 2 or not parts[1].isdigit():
            return False

    return True