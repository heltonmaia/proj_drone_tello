import streamlit as st
import time
from drone_controller import DroneController
import cv2

# Inicialização
controller = DroneController()

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
st.header("Vídeo")
frame_placeholder = st.empty()

# Variável para controle de tempo
ultimo_tempo = time.time()

try:
    while True:
        # Captura e processamento do frame
        frame = controller.get_frame()
        if frame is None:
            st.warning("Fim da captura de vídeo.")
            break

        # Atualiza informações a cada 20 segundos
        if time.time() - ultimo_tempo >= 20:
            bat, height, fps, pres, time_elapsed = controller.get_drone_info()
            update_info(bat, height, fps, pres, time_elapsed)
            ultimo_tempo = time.time()

        # Converte para exibição no Streamlit
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame, channels="RGB", use_container_width=True)

except Exception as e:
    st.error(f"Erro: {e}")
finally:
    # Finalização
    controller.release()