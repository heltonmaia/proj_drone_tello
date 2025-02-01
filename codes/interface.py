import streamlit as st
import time
import cv2
import modules.tello_control as tello_control
from tello_zune import TelloZune

# Inicialização
tello = TelloZune()
#cap = cv2.VideoCapture(0)
tello.start_tello()
tello.simulate = True

# Configuração do layout da interface
st.title("DJI Tello")
st.sidebar.header("Informações do Drone")

# Espaços reservados para exibição das informações
bat_placeholder = st.sidebar.empty()
height_placeholder = st.sidebar.empty()
fps_placeholder = st.sidebar.empty()
pres_placeholder = st.sidebar.empty()
time_placeholder = st.sidebar.empty()

# Função para atualizar as informações
def update_info(bat, height, fps, pres, time_elapsed):
    bat_placeholder.write(f"Bateria: {bat}%")
    height_placeholder.write(f"Altura: {height} cm")
    fps_placeholder.write(f"FPS: {fps}")
    pres_placeholder.write(f"Pressão: {pres}")
    time_placeholder.write(f"Tempo de voo: {time_elapsed} s")

# Exibição do vídeo capturado
st.header("Câmera")
frame_placeholder = st.empty()
takeoff = st.button("Decolar")
land = st.button("Pousar")

# Variável para controle de tempo
timer = time.time()

try:
    while True:
        # Captura e processamento do frame
        #ret, frame = cap.read()
        frame = tello.get_frame()
        if frame is None:
            st.warning("Fim da captura de vídeo.")
            break

        # Atualiza informações a cada 20 segundos
        if time.time() - timer >= 20:
            bat, height, fps, pres, time_elapsed = tello.get_info()
            update_info(bat, height, fps, pres, time_elapsed)
            timer = time.time()

        # Processamento
        frame = tello_control.moves(tello, frame)

        # Botões de controle
        if takeoff:
            tello.send_cmd("takeoff")
            takeoff = False
        if land:
            tello.send_cmd("land")
            land = False

        # Converte para exibição no Streamlit
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame, channels="RGB", use_container_width=True)

except Exception as e:
    st.error(f"Erro: {e}")
finally:
    # Finalização
    tello.end_tello()
    tello.moves_thread.join()