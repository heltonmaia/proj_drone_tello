import streamlit as st
import time
import cv2
import threading
from datetime import datetime
import modules.tello_control as tello_control
import modules.chatbot as chatbot
from tello_zune import TelloZune

# Inicialização do Drone
if "tello" not in st.session_state:
    st.session_state.tello = TelloZune()
    st.session_state.command_log = []
    st.session_state.params_initialized = False # Controle de inicialização

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

tello = st.session_state.tello
st.session_state.last_update = time.time()
tello_control.enable_search = False # Ativa a busca
tello_control.stop_searching.clear()
#tello.simulate = True # Modo simulação

# Configuração da Interface
st.set_page_config(layout="wide")
left_col, right_col = st.columns([3, 1]) # 3:1 vídeo e parâmetros
frame_placeholder = left_col.empty()
text_input_placeholder = st.empty() 
response_placeholder = st.empty()

# Iniciar o drone apenas se ele ainda não estiver conectado
if not hasattr(tello, "receiverThread") or not tello.receiverThread.is_alive():
    tello.start_tello()
    #pass
#if "cap" not in st.session_state:
#    st.session_state.cap = cv2.VideoCapture(0) # webcam
#cap = st.session_state.cap

# Funções auxiliares
def update_pace():
    """Atualiza o valor de tello_control.pace"""
    if "pace_input" in st.session_state:
        tello_control.pace = st.session_state.pace_input

# Função para atualizar valores
def update_values():
    """Atualiza os valores dos parâmetros dinamicamente"""
    bat, height, temph, pres, time_elapsed = tello.get_info()
    #bat, height, temph, pres, time_elapsed = 80, 100, 25, 1013, 60 # Simulação
    
    with right_col:
        st.session_state.battery_value.markdown(f"**{bat if bat is not None else 'N/A'}%**")
        st.session_state.height_value.markdown(f"**{height if height is not None else 'N/A'}cm**")
        st.session_state.temp_value.markdown(f"**{temph if temph is not None else 'N/A'}°C**")
        st.session_state.pres_value.markdown(f"**{pres if pres is not None else 'N/A'}hPa**")
        st.session_state.time_value.markdown(f"**{time_elapsed if time_elapsed is not None else 'N/A'}s**")

# Inicialização dos elementos da coluna direita
if not st.session_state.params_initialized:
    with right_col:
        # Container para bateria
        with st.container():
            bat_col1, bat_col2 = st.columns([1, 3]) # 1:3 ícone e valor
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

with text_input_placeholder.container():
    user_input = st.text_input("Envie um comando para o drone:", key="user_input")
    
    chat_history_lock = threading.Lock()
    shared_chat_history = st.session_state.chat_history.copy()

    if st.button("Enviar") and user_input:
        #ret, frame = cap.read()
        frame = tello.get_frame()
        current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        natural_response, command = chatbot.run_ai(user_input, current_frame)
        tello_control.log_messages.append(command)

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = { # Dicionário para armazenar a mensagem
            "user": user_input,
            "ai": natural_response,
            "command": command,
            "timestamp": timestamp,
            "status": "queued" if command else "error"
        }

        if command and chatbot.validate_command(command):
            print(f"Comando validado: {command}")
            tello_control.process_ai_command(tello, command)
            st.session_state.command_log.append(command)
            entry["execution"] = f"Comando enfileirado: {command}"

        with chat_history_lock:
            st.session_state.chat_history.append(entry)

# Sidebar
with st.sidebar:
    st.header("Controles")
    if st.button("Decolar"):
        tello.send_cmd("takeoff")
        st.session_state.command_log.append("takeoff")
    if st.button("Pousar"):
        tello.send_cmd("land")
        st.session_state.command_log.append("land")
    if st.button("Encerrar Drone"):
        #cap.release()
        tello.end_tello()
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
    logs = st.session_state.command_log #+ tello_control.log_messages
    if st.session_state.command_log:
        for log in logs:
            st.text(log)

# Iniciar a busca se ainda não estiver rodando
if not tello_control.searching and tello_control.enable_search:
    search_thread = threading.Thread(target=tello_control.search, args=(tello,))
    search_thread.daemon = True
    search_thread.start()
    tello_control.searching = True

# Loop principal
while not tello.stop_receiving.is_set():
    # Atualizar valores
    if time.time() - st.session_state.last_update >= 5:
        update_values()
        st.session_state.last_update = time.time()

    # Atualizar resposta da IA
    with response_placeholder.container():
        for entry in st.session_state.chat_history:
            # Mensagem do usuário
            st.markdown(f"**{entry['timestamp']} - Você:** {entry['user']}")
            
            # Resposta do drone com tratamento de status
            if entry['status'] == 'processing':
                with st.spinner(entry['ai']):
                    time.sleep(0.1)  # Mantém o spinner animado
            else:
                st.markdown(f"**{entry['timestamp']} - Drone:** {entry['ai']}")
                st.write("\n")

    # Atualizar frame
    frame = tello.get_frame()
    #ret, frame = cap.read()
    #if not ret:
    #    break
    #frame = tello.get_frame()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # Conversão agora é feita aqui
    frame = tello_control.moves(tello, frame)
    frame_placeholder.image(frame, channels="RGB")
    
    # Atualizar FPS
    st.session_state.fps_value.markdown(f"**{tello.calc_fps()} FPS**")