import streamlit as st
import time
import cv2
import modules.tello_control as tello_control
from tello_zune import TelloZune

# Inicialização do Drone
if "tello" not in st.session_state:
    st.session_state.tello = TelloZune()
    #st.session_state.tello.start_tello()
    st.session_state.tello.simulate = True  # Simulação ativa
    st.session_state.command_log = []  # Armazena os comandos enviados

tello = st.session_state.tello
st.session_state.last_update = time.time()

# Inicialização da webcam
cap = cv2.VideoCapture(0)

# Configuração da Interface
st.set_page_config(layout="wide")  # Define a interface para ocupar toda a largura

# Layout: 70% vídeo / 30% comandos
col1, col2 = st.columns([3, 2])

with col1:
    st.title("DJI Tello")
    st.header("Câmera")
    frame_placeholder = st.empty()

with col2:
    st.sidebar.header("Info")
    bat_placeholder = st.sidebar.empty()
    height_placeholder = st.sidebar.empty()
    fps_placeholder = st.sidebar.empty()
    pres_placeholder = st.sidebar.empty()
    time_placeholder = st.sidebar.empty()
    
    st.sidebar.header("Log")
    command_log_placeholder = st.sidebar.empty()

# Atualiza Informações
def update_info():
    #bat, height, fps, pres, time_elapsed = tello.get_info()
    bat, height, fps, pres, time_elapsed = 20, 50, 30, 1000, 100

    bat_placeholder.write(f"Bateria: {bat if bat is not None else 'N/A'}%")
    height_placeholder.write(f"Altura: {float(height) if height is not None else 'N/A'} cm")
    fps_placeholder.write(f"FPS: {fps if fps is not None else 'N/A'}")
    pres_placeholder.write(f"Pressão: {pres if pres is not None else 'N/A'}")
    time_placeholder.write(f"Tempo de voo: {time_elapsed if time_elapsed is not None else 'N/A'} s")
    print("Atualizado")

# Função para registrar comandos
def log_command(command):
    st.session_state.command_log.append(command)
    print("append")
    command_log_placeholder.write("\n".join(st.session_state.command_log))

# Botões de Controle
if st.button("Decolar"):
    tello.send_cmd("takeoff")
    log_command("takeoff")

if st.button("Pousar"):
    tello.send_cmd("land")
    log_command("land")

# Atualiza informações do drone a cada 10 segundos
if "last_update" not in st.session_state:
    st.session_state.last_update = time.time()

if time.time() - st.session_state.last_update >= 10:
    update_info()
    st.session_state.last_update = time.time()

# Finalização segura
if st.button("Encerrar Drone"):
    #tello.end_tello()
    cap.release()
    del st.session_state.tello  # Remove a instância do drone
    st.stop()  # Encerra a execução do script

# Atualização contínua sem um loop infinito
while True:
    ret, frame = cap.read()
    if ret:
        frame = tello_control.moves(tello, frame)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame, channels="RGB", use_container_width=True)
    else:
        st.warning("Sem imagem da webcam.")
    
    update_info()
    time.sleep(0.001)  # Ajuste no tempo para evitar sobrecarga
