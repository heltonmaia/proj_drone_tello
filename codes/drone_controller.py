import cv2
import threading
from tello_zune import TelloZune
import modules.tello_control as tello_control
from modules.utils import configureLogging

class DroneController:
    def __init__(self: object) -> None:
        self.tello = TelloZune()  # Cria objeto da classe TelloZune
        configureLogging()  # Configura o logging
        self.cap = cv2.VideoCapture(0)  # Captura de vídeo da webcam
        self.moves_thread = threading.Thread(target=tello_control.readQueue, args=(self.tello,))
        self.moves_thread.start()

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        frame = cv2.resize(frame, (960, 720))
        frame = tello_control.moves(self.tello, frame)
        return frame

    def get_drone_info(self):
        # Exemplo de dados do drone (substitua pelos dados reais)
        bat = self.tello.get_battery()
        height = float(self.tello.get_state_field("h"))
        fps = 30  # Exemplo
        pres = self.tello.get_state_field("baro")
        time_elapsed = self.tello.get_state_field("time")
        return bat, height, fps, pres, time_elapsed

    def release(self):
        self.cap.release()
        self.tello.end_tello()
        cv2.destroyAllWindows()
        self.moves_thread.join()