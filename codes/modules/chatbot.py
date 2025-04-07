import google.generativeai as genai
from PIL import Image
import streamlit as st
from modules import utils
import threading

utils.configureGenerativeAI()
model = genai.GenerativeModel('gemini-1.5-flash')

COMMAND_LIST = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]

def run_ai(prompt: str, frame, timestamp: str, chat_history: list, lock: threading.Lock):
    try:
        pil_image = Image.fromarray(frame)
        response = model.generate_content([prompt, pil_image])

        # Atualiza histórico de forma segura
        with lock:
            for entry in chat_history:
                if entry["timestamp"] == timestamp and entry["status"] == "processing":
                    entry["ai"] = response.text
                    entry["status"] = "completed"
                    break

    except Exception as e:
        with lock:
            for entry in chat_history:
                if entry["timestamp"] == timestamp and entry["status"] == "processing":
                    entry["ai"] = f"Erro1: {str(e)}"
                    entry["status"] = "error"
                    break

    except Exception as e:
        update_chat_history(
            response=f"Erro2: {str(e)}",
            timestamp=timestamp
        )

def update_chat_history(response: str, timestamp: str):
    """Atualiza o histórico de forma thread-safe"""
    for entry in st.session_state.chat_history:
        if entry["timestamp"] == timestamp and entry["status"] == "processing":
            entry["ai"] = response
            entry["status"] = "completed"
            break

def generate_drone_command(prompt: str, frame) -> tuple:
    """
    Retorna:
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

            Os comandos de movimentos precisam necessariamente de um passo em cm, land e takeoff não precisam de passo
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