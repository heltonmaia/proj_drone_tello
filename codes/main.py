from tello_zune import TelloZune
import cv2, threading
import modules.tello_control as tello_control
from modules.utils import configure_logging

# Inicialização
#cap = cv2.VideoCapture(0)
tello = TelloZune()
tello.start_tello()
configure_logging()

# Inicia a thread de movimentos
moves_thread = threading.Thread(target=tello_control.readQueue, args=(tello,))
moves_thread.start()

try:
    while True:
        # Captura
        #ret, frame = cap.read()
        frame = tello.get_frame()
        tello.calc_fps(frame)
        # Tratamento
        frame = cv2.resize(frame, (960, 720))
        frame = tello_control.moves(tello, frame)
        # Exibição
        cv2.imshow('QR Code', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            tello_control.stop_receiving.set() # Para encerrar a thread de busca
            break
finally:
    #cap.release()
    tello.end_tello()
    cv2.destroyAllWindows()
    moves_thread.join() # Aguarda a thread de movimentos encerrar

