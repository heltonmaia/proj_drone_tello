# interface.py
import streamlit as st
import time
import cv2
import threading
from datetime import datetime
import modules.tello_control as tello_control
import modules.chatbot as chatbot
from tello_zune import TelloZune

def initialize_session():
    """Inicializa as variáveis de sessão se ainda não existirem."""
    if "tello" not in st.session_state:
        st.session_state.tello = TelloZune()
        st.session_state.command_log = []
        st.session_state.params_initialized = False  # Controle de inicialização

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "cap" not in st.session_state:
        st.session_state.cap = cv2.VideoCapture(0)  # webcam
    
    if not hasattr(st.session_state.tello, "receiverThread") or not st.session_state.tello.receiverThread.is_alive():
        st.session_state.tello.start_tello()
        #pass

def build_interface():
    """Configura os elementos da interface"""
    # Configuração da Interface
    st.set_page_config(layout="wide")
    left_col, right_col = st.columns([3, 1])  # 3:1 vídeo e parâmetros
    frame_placeholder = left_col.empty()
    text_input_placeholder = st.empty() 
    response_placeholder = st.empty()

    # Inicializações
    tello = st.session_state.tello
    st.session_state.last_update = time.time()
    tello_control.enable_search = False  # Ativa a busca
    tello_control.stop_searching.clear()

    # Preparar elementos da coluna direita (ex.: baterias, altura, etc.)
    if not st.session_state.params_initialized:
        with right_col:
            # Container para bateria
            with st.container():
                bat_col1, bat_col2 = st.columns([1, 3])
                with bat_col1:
                    st.image("../images/battery_icon.png", width=40)
                with bat_col2:
                    st.session_state.battery_value = st.empty()
            # Container para altura
            with st.container():
                height_col1, height_col2 = st.columns([1, 3])
                with height_col1:
                    st.image("../images/height_icon.png", width=40)
                with height_col2:
                    st.session_state.height_value = st.empty()
            # Container para temperatura
            with st.container():
                temp_col1, temp_col2 = st.columns([1, 3])
                with temp_col1:
                    st.image("../images/temp_icon.png", width=40)
                with temp_col2:
                    st.session_state.temp_value = st.empty()
            # Container para pressão
            with st.container():
                pres_col1, pres_col2 = st.columns([1, 3])
                with pres_col1:
                    st.image("../images/pressure_icon.png", width=40)
                with pres_col2:
                    st.session_state.pres_value = st.empty()
            # Container para tempo de voo
            with st.container():
                time_col1, time_col2 = st.columns([1, 3])
                with time_col1:
                    st.image("../images/time_icon.png", width=40)
                with time_col2:
                    st.session_state.time_value = st.empty()
            # Container para FPS
            with st.container():
                fps_col1, fps_col2 = st.columns([1, 3])
                with fps_col1:
                    st.image("../images/fps_icon.png", width=40)
                with fps_col2:
                    st.session_state.fps_value = st.empty()

        st.session_state.params_initialized = True

    # Retorna os elementos utilizados no loop principal
    return {
        "frame_placeholder": frame_placeholder,
        "text_input_placeholder": text_input_placeholder,
        "response_placeholder": response_placeholder,
        "right_col": right_col,
        "tello": tello,
        "cap": st.session_state.cap
    }

def update_pace():
    """Atualiza o valor de tello_control.pace com base no input do usuário."""
    if "pace_input" in st.session_state:
        tello_control.pace = st.session_state.pace_input

def update_values(right_col, tello):
    """Atualiza os valores dos parâmetros dinamicamente (exemplo com simulação)."""
    bat, height, temph, pres, time_elapsed = 80, 100, 25, 1013, 60  # Simulação
    with right_col:
        st.session_state.battery_value.markdown(f"**{bat if bat is not None else 'N/A'}%**")
        st.session_state.height_value.markdown(f"**{height if height is not None else 'N/A'}cm**")
        st.session_state.temp_value.markdown(f"**{temph if temph is not None else 'N/A'}°C**")
        st.session_state.pres_value.markdown(f"**{pres if pres is not None else 'N/A'}hPa**")
        st.session_state.time_value.markdown(f"**{time_elapsed if time_elapsed is not None else 'N/A'}s**")

def sidebar_elements(tello):
    """Cria a sidebar com controles e log."""
    with st.sidebar:
        st.header("Controles")
        if st.button("Decolar"):
            tello.send_cmd("takeoff")
            st.session_state.command_log.append("takeoff")
        if st.button("Pousar"):
            tello.send_cmd("land")
            st.session_state.command_log.append("land")
        if st.button("Encerrar Drone"):
            st.session_state.cap.release()
            tello.stop_receiving.set()
            tello_control.stop_searching.set()
            tello.moves_thread.join()
            del st.session_state.tello
            st.stop()
        pace_input = st.text_input("Passo (cm): ", "50", key="pace_input", on_change=update_pace)
        st.write("---")
        st.subheader("Log")
        if st.button("Limpar Logs"):
            st.session_state.command_log.clear()
            tello_control.log_messages.clear()
        # Exibir logs centralizados para evitar duplicações
        logs = st.session_state.command_log  # Centralizamos os logs nesta variável
        for log in logs:
            st.text(log)

def text_input_elements(cap, tello):
    """Cria os elementos de entrada de comandos e atualiza o histórico."""
    with st.container():
        user_input = st.text_input("Envie um comando para o drone:", key="user_input")
        chat_history_lock = threading.Lock()
        if st.button("Enviar") and user_input:
            ret, frame = cap.read()
            # Converte o frame para RGB
            current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            natural_response, command = chatbot.run_ai(user_input, current_frame)
            # Adiciona o comando diretamente ao log central
            if command and chatbot.validate_command(command):
                print(f"Comando validado: {command}")
                tello_control.process_ai_command(tello, command)
                st.session_state.command_log.append(command)
                execution_msg = f"Comando enfileirado: {command}"
            else:
                execution_msg = f"Erro no comando"
            timestamp = datetime.now().strftime("%H:%M:%S")
            entry = {
                "user": user_input,
                "ai": natural_response,
                "command": command,
                "timestamp": timestamp,
                "status": "queued" if command else "error",
                "execution": execution_msg
            }
            with chat_history_lock:
                st.session_state.chat_history.append(entry)

def update_response(response_placeholder):
    """Atualiza a área de resposta mostrando o histórico de mensagens."""
    with response_placeholder.container():
        for entry in st.session_state.chat_history:
            st.markdown(f"**{entry['timestamp']} - Você:** {entry['user']}")
            if entry['status'] == 'processing':
                with st.spinner(entry['ai']):
                    time.sleep(0.1)  # Mantém o spinner animado
            else:
                st.markdown(f"**{entry['timestamp']} - Drone:** {entry['ai']}")
                st.write("---")

def run_interface():
    """
    Função que configura a interface e executa o loop principal de atualização.
    Separa as responsabilidades: a configuração dos elementos, o loop de frames
    e a atualização dos parâmetros.
    """
    initialize_session()
    elements = build_interface()
    frame_placeholder = elements["frame_placeholder"]
    text_input_placeholder = elements["text_input_placeholder"]
    response_placeholder = elements["response_placeholder"]
    right_col = elements["right_col"]
    tello = elements["tello"]
    cap = elements["cap"]
    

    # Inicia a busca (se habilitada)
    if not tello_control.searching and tello_control.enable_search:
        search_thread = threading.Thread(target=tello_control.search, args=(tello,))
        search_thread.daemon = True
        search_thread.start()
        tello_control.searching = True

    # Loop principal
    while not tello.stop_receiving.is_set():
        if time.time() - st.session_state.last_update >= 5:
            update_values(right_col, tello)
            st.session_state.last_update = time.time()

        update_response(response_placeholder)

        #ret, frame = cap.read()
        frame = tello.get_frame()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = tello_control.moves(tello, frame)
        frame_placeholder.image(frame, channels="RGB")
        st.session_state.fps_value.markdown(f"**{tello.calc_fps()} FPS**")

        # Elementos de entrada e sidebar são processados a cada ciclo
        text_input_elements(cap, tello)
        sidebar_elements(tello)
        
        # Uma pequena pausa para não travar o loop
        #time.sleep(0.1)
