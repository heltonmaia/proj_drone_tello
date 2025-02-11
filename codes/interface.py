import streamlit as st
import time
import cv2
import threading
import modules.tello_control as tello_control
from tello_zune import TelloZune

# Inicialização do Drone
if "tello" not in st.session_state:
    st.session_state.tello = TelloZune()
    st.session_state.tello.simulate = True
    st.session_state.command_log = []  # Inicializa o log
    #st.session_state.enable_search = True  # Ativa a busca

tello = st.session_state.tello
st.session_state.last_update = time.time()
tello_control.enable_search = True
tello_control.stop_searching.clear()

# Iniciar o drone apenas se ele ainda não estiver conectado
if not hasattr(tello, "receiverThread") or not tello.receiverThread.is_alive():
    tello.start_tello()
#cap = cv2.VideoCapture(0)

# Configuração da Interface
st.set_page_config(layout="wide")  

# Placeholders para vídeo, informações e log
frame_placeholder = st.empty()
fps_placeholder = st.empty()
info_placeholder = st.empty()
log_placeholder = st.empty()

# Função para atualizar as informações do drone (exemplo com dados fictícios)
def update_info():
    #bat, height, fps, pres, time_elapsed = 20, 50, 30, 1000, 100
    bat, height, temph, pres, time_elapsed = tello.get_info()
    info_str = (
        f"Bateria: {bat if bat is not None else 'N/A'}%\n"
        f"Altura: {height if height is not None else 'N/A'} cm\n"
        f"Temperatura: {temph if temph is not None else 'N/A'}C\n"
        f"Pressão: {pres if pres is not None else 'N/A'}\n"
        f"Tempo de voo: {time_elapsed if time_elapsed is not None else 'N/A'} s\n"
        "\n"
        "# Log\n"
    )
    return info_str

# Sidebar: Botões de controle e entrada de comando
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
        st.session_state.tello.stop_receiving.set()
        tello.moves_thread.join()
        del st.session_state.tello
        st.stop()
    
    st.write("---")
    st.subheader("Enviar Comando")
    command_input = st.text_input("Digite um comando para o drone:", "")
    if st.button("Enviar Comando"):
        if command_input:
            response = tello.send_cmd_return(command_input)
            st.session_state.command_log.append(f"{command_input} -> {response}")
            st.write(response)

# Iniciar a busca se ainda não estiver rodando
if not tello_control.searching:
    search_thread = threading.Thread(target=tello_control.search, args=(tello,))
    search_thread.daemon = True
    search_thread.start()
    tello_control.searching = True

# Loop principal da interface
while True:
    #ret, frame = cap.read()
    frame = tello.get_frame()
    frame = tello_control.moves(tello, frame)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_placeholder.image(frame, channels="RGB")
    
    fps = tello.calc_fps()
    fps_placeholder.text(f"FPS: {fps}")

    # Atualiza informações do drone a cada 5 segundos
    if time.time() - st.session_state.last_update >= 5:
        st.session_state.last_update = time.time()
        info_placeholder.text(update_info())

    # Pegar logs da variável global e transferir para o session_state
    if "command_log" not in st.session_state:
        st.session_state.command_log = []
    
    if tello_control.log_messages:
        st.session_state.command_log.extend(tello_control.log_messages)
        tello_control.log_messages.clear()

    log_placeholder.text("\n".join(st.session_state.command_log))

    time.sleep(0.001)  # Reduz a frequência do loop para evitar sobrecarga