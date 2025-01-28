import cv2
from drone_controller import DroneController

# Inicialização
controller = DroneController()

try:
    while True:
        # Captura e processamento do frame
        frame = controller.get_frame()
        if frame is None:
            print("Fim da captura de vídeo.")
            break

        # Exibição local
        cv2.imshow('DJI Tello', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    # Finalização
    controller.release()