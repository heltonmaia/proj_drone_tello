import streamlit as st
import time
import cv2
import threading
import modules.tello_control as tello_control
from tello_zune import TelloZune
import os, signal

# Função para atualizar passo nos movimentos do drone
def update_pace():
    """Atualiza o valor de tello_control.pace"""
    if "pace_input" in st.session_state:
        tello_control.pace = st.session_state.pace_input

# Função para atualizar valores
def update_values():
    """Atualiza os valores dos parâmetros dinamicamente"""
    bat, height, temph, pres, time_elapsed = tello.get_info()
    
    with right_col:
        st.session_state.battery_value.markdown(f"**{bat if bat is not None else 'N/A'}%**")
        st.session_state.height_value.markdown(f"**{height if height is not None else 'N/A'}cm**")
        st.session_state.temp_value.markdown(f"**{temph if temph is not None else 'N/A'}°C**")
        st.session_state.pres_value.markdown(f"**{pres if pres is not None else 'N/A'}hPa**")
        st.session_state.time_value.markdown(f"**{time_elapsed if time_elapsed is not None else 'N/A'}s**")

# Inicialização do Drone
if "tello" not in st.session_state:
    st.session_state.tello = TelloZune()
    st.session_state.command_log = []
    st.session_state.params_initialized = False # Controle de inicialização

tello = st.session_state.tello
st.session_state.last_update = time.time()
tello_control.enable_search = False # Ativa a busca
tello_control.stop_searching.clear()

# Iniciar o drone apenas se ele ainda não estiver conectado
if not hasattr(tello, "receiverThread") or not tello.receiverThread.is_alive():
    tello.start_tello()
    #pass
#cap = cv2.VideoCapture(0) # webcam

# Configuração da Interface
st.set_page_config(layout="wide")
left_col, right_col = st.columns([3, 1]) # 3:1 vídeo e parâmetros
frame_placeholder = left_col.empty()
log_placeholder = st.empty() # Log abaixo de todo o conteúdo

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
        os.kill(os.getpid(), signal.SIGKILL) # Encerra o programa na marra
    pace_input = st.text_input("Passo (cm): ", "50", key="pace_input", on_change=update_pace)

    st.write("---")
    st.subheader("Enviar Comando")
    command_input = st.text_input("Digite um comando para o drone:", "")
    if st.button("Enviar Comando"):
        if command_input:
            response = tello.send_cmd_return(command_input)
            time.sleep(0.1)
            st.session_state.command_log.append(f"{command_input} -> {response}")

    st.write("---")
    st.subheader("Logs")
    if st.button("Limpar Logs"):
        st.session_state.command_log.clear()

# Iniciar a busca se ainda não estiver rodando
if not tello_control.searching:
    search_thread = threading.Thread(target=tello_control.search, args=(tello,))
    search_thread.daemon = True
    search_thread.start()
    tello_control.searching = True

# Loop principal
while True:
    #ret, frame = cap.read()
    frame = tello.get_frame()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # Conversão agora é feita aqui
    frame = tello_control.moves(tello, frame)
    frame_placeholder.image(frame, channels="RGB")

    # Atualiza valores a cada 5 segundos
    if time.time() - st.session_state.last_update >= 5:
        update_values()
        st.session_state.last_update = time.time()

    # Atualiza logs
    if tello_control.log_messages:
        st.session_state.command_log.extend(tello_control.log_messages) # Da lista para o log do Streamlit
        tello_control.log_messages.clear() # Limpa a lista de mensagens
    
    log_placeholder.text("\n".join(st.session_state.command_log))
    st.session_state.fps_value.markdown(f"**{tello.calc_fps()}fps**") # Atualiza FPS a cada frame

    #time.sleep(0.001)