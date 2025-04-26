import streamlit as st
import time
import cv2
import modules.tello_control as tello_control
import modules.chatbot as chatbot
from tello_zune import TelloZune

def initialize_session() -> None:
    """
    Inicializa variáveis de sessão para drone, câmera e histórico do chatbot.
    """
    if "tello" not in st.session_state:
        st.session_state.tello = TelloZune()
        st.session_state.command_log = tello_control.log_messages
        st.session_state.params_initialized = False
        st.session_state.last_user = ""
        st.session_state.last_ai = ""

    #if "cap" not in st.session_state:
    #    st.session_state.cap = cv2.VideoCapture(0) # webcam

    st.session_state.last_update = time.time()

def configure_interface() -> tuple:
    """
    Prepara layout e placeholders.
    Returns:
        tuple: Colunas da interface, placeholders para frame, input e resposta.
    """
    st.set_page_config(layout="wide")
    left_col, right_col = st.columns([3, 1]) # Proporção 3:1
    frame_placeholder = left_col.empty()
    text_input_placeholder = st.empty()
    response_placeholder = st.empty()
    return left_col, right_col, frame_placeholder, text_input_placeholder, response_placeholder

def render_parameters(right_col) -> None:
    """
    Parâmetros do drone na coluna direita.
    Args:
        right_col: Coluna da interface onde os parâmetros serão exibidos.
    """
    if not st.session_state.params_initialized:
        with right_col:
            icons = ['battery_icon.png', 'height_icon.png', 'temp_icon.png', 'pressure_icon.png', 'time_icon.png', 'fps_icon.png']
            keys = ['battery_value', 'height_value', 'temp_value', 'pres_value', 'time_value', 'fps_value']
            for icon, key in zip(icons, keys): # Itera sobre os ícones e chaves
                with st.container():
                    c1, c2 = st.columns([1, 3]) # Proporção 1:3
                    with c1:
                        st.image(f"../images/{icon}", width=40)
                    with c2:
                        st.session_state[key] = st.empty()
        st.session_state.params_initialized = True

def render_sidebar() -> None:
    """
    Botões de controle e log na sidebar.
    """
    with st.sidebar:
        st.header("Controles")
        if st.button("Decolar"):
            st.session_state.tello.send_cmd("takeoff")
            st.session_state.command_log.append("takeoff")
        if st.button("Pousar"):
            st.session_state.tello.send_cmd("land")
            st.session_state.command_log.append("land")
        if st.button("Encerrar Drone"):
            #st.session_state.cap.release()
            st.session_state.tello.end_tello()
            st.session_state.tello.movesThread.stop()
            tello_control.stop_searching.set()
            del st.session_state.tello
            st.stop()

        st.text_input("Passo (cm): ", "50", key="pace_input", on_change=update_pace)
        st.write("---")
        st.subheader("Log")
        if st.button("Limpar Logs"):
            st.session_state.command_log.clear()
            tello_control.log_messages.clear()
        for log in st.session_state.command_log:
            st.text(log)

def update_pace() -> None:
    """Atualiza tello_control.pace."""
    tello_control.pace = st.session_state.pace_input

def render_text_input(text_input_placeholder) -> None:
    """
    Área de texto para comandos ao drone.
    Args:
        text_input_placeholder: Placeholder para o campo de entrada de texto.
    """
    with text_input_placeholder.container():
        user_input = st.text_input("Envie um comando para o drone:", key="user_input")
        if st.button("Enviar") and user_input:
            #ret, frame = st.session_state.cap.read()
            frame = st.session_state.tello.get_frame() # Por enquanto o frame é adquirido novamente
            current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            response, command = chatbot.run_ai(user_input, current_frame)
            if command and chatbot.validate_command(command):
                tello_control.process_ai_command(st.session_state.tello, command)
                tello_control.log_messages.append(command)

            # Atualiza última interação
            st.session_state.last_user = user_input
            st.session_state.last_ai = response

def render_response(response_placeholder) -> None:
    """
    Exibe interação do chatbot.
    Args:
        response_placeholder: Placeholder para exibir o histórico de chat.
    """
    with response_placeholder.container():
        if st.session_state.last_ai:
            st.markdown(f"**Você:** {st.session_state.last_user}")
            st.markdown(f"**Drone:** \n {st.session_state.last_ai}")

def render_frame(frame_placeholder) -> None:
    """
    Captura e exibe frame da webcam e drone.
    Args:
        frame_placeholder: Placeholder para exibir o frame.
    """
    #ret, frame = st.session_state.cap.read()
    frame = st.session_state.tello.get_frame()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = tello_control.moves(st.session_state.tello, frame)
    frame_placeholder.image(frame, channels="RGB")

def update_interface_values() -> None:
    """Atualiza parâmetros do drone."""
    bat, height, temph, pres, time_elapsed = st.session_state.tello.get_info()
    st.session_state.battery_value.markdown(f"**{bat if bat is not None else 'N/A'}%**")
    st.session_state.height_value.markdown(f"**{height if height is not None else 'N/A'}cm**")
    st.session_state.temp_value.markdown(f"**{temph if temph is not None else 'N/A'}°C**")
    st.session_state.pres_value.markdown(f"**{pres if pres is not None else 'N/A'}hPa**")
    st.session_state.time_value.markdown(f"**{time_elapsed if time_elapsed is not None else 'N/A'}s**")