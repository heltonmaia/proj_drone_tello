import cv2
from tello_zune import TelloZune
import modules.tello_control as tello_control
import time
"""
Módulo principal para controle do drone Tello.
Este arquivo inicializa a captura de vídeo, faz as configurações iniciais e direciona o fluxo de controle do drone.

Funcionalidades principais:
- Captura e exibição de vídeo em tempo real.
- Processamento de QR codes para controle do drone.
- Decolagem, pouso, busca e movimentação com base nos comandos recebidos.
- Registro de todos os comandos enviados ao drone em um arquivo de log.

Módulos utilizados:
- tello_control: Contém funções para movimentação e lógica de controle.
- tracking_base: Funções para detectar e seguir QR codes.
- qr_processing: Processamento de QR codes.
- utils: Configuração de logging.

Como executar:
- Execute o arquivo main.py já conectado à rede Wi-Fi do drone Tello.
"""

# Inicialização
#cap = cv2.VideoCapture(0) # Captura de vídeo da webcam
tello = TelloZune() # Cria objeto da classe TelloZune
tello.simulate = False # False: o drone decola; True: simula o voo
tello.start_tello() # Inicia a comunicação com o drone
#tello_control.enable_search = True # Ativa a busca
timer = time.time()
bat, height, temph, pres, time_elapsed = tello.get_info()

try:
    while True:
        # Captura
        #ret, frame = cap.read() # Captura de vídeo da webcam
        frame = tello.get_frame()
        #frame = cv2.resize(frame, (960, 720))

        # Tratamento
        frame = tello_control.moves(tello, frame)
        fps = tello.calc_fps()
        cv2.putText(frame, f"FPS: {fps}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)
        cv2.putText(frame, f"Bat: {bat}%", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)
        cv2.putText(frame, f"Height: {height}cm", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)
        cv2.putText(frame, f"Max. Temp.: {temph}C", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)
        cv2.putText(frame, f"Press.: {pres}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)
        cv2.putText(frame, f"TOF: {time_elapsed}s", (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, (10, 255, 0), 2)

        # Atualização
        if time.time() - timer > 10:
            timer = time.time()
            bat, height, temph, pres, time_elapsed = tello.get_info()

        # Exibição
        cv2.imshow('QR Code', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            tello.stop_receiving.set()
            tello_control.stop_searching.set()
            break
finally:
    # Finalização
    #cap.release()
    tello.end_tello()
    cv2.destroyAllWindows()
    tello.moves_thread.join() # Aguarda a thread de movimentos encerrar