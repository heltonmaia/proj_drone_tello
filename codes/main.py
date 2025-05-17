import time
import threading
import streamlit as st
import modules.tello_control as tello_control
import interface

interface.initialize_session()
tello_control.enable_search = False
tello_control.stop_searching.clear()
tello_control.searching = False

if not hasattr(st.session_state.tello, "receiverThread") or not st.session_state.tello.receiverThread.is_alive():
    print("Iniciando o drone...")
    st.session_state.tello.start_tello()
    #pass #webcam

left_col, right_col, frame_placeholder, text_input_placeholder, response_placeholder = interface.configure_interface()

interface.render_parameters(right_col)
interface.render_sidebar()
interface.render_text_input(text_input_placeholder)

while True: # Loop principal
    if time.time() - st.session_state.last_update >= 5: # Atualiza a cada 5 segundos
        interface.update_interface_values()
        st.session_state.last_update = time.time()

    interface.render_response(response_placeholder) # Atualiza resposta

    interface.render_frame(frame_placeholder) # Atualiza frame

    st.session_state.fps_value.markdown(f"**{st.session_state.tello.calc_fps()} FPS**") # Atualiza FPS

    # Pequena pausa para evitar uso excessivo de CPU
    #time.sleep(0.01)

