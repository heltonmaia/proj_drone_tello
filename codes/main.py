import cv2
import threading
from tello_zune import TelloZune
import modules.tello_control as tello_control
from modules.utils import configureLogging
"""
Módulo principal para controle do drone Tello.

Este arquivo inicializa a captura de vídeo, faz as configurações iniciais e direciona o fluxo de controle do drone.

Funcionalidades principais:
- Captura e exibição de vídeo em tempo real.
- Processamento de QR codes para controle do drone.
- Decolagem, pouso, busca e movimentação com base nos comandos recebidos.
- Registro de todos os comandos enviados ao drone em um arquivo de log.

Classes:
- TelloZune: Interface principal para controle do drone.

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
tello.start_tello() # Inicia a comunicação com o drone
configureLogging() # Configura o logging

# Inicia a thread de movimentos
moves_thread = threading.Thread(target=tello_control.readQueue, args=(tello,))
moves_thread.start()

try:
    while True:
        # Captura
        #ret, frame = cap.read() # Captura de vídeo da webcam
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
    # Finalização
    #cap.release()
    tello.end_tello()
    cv2.destroyAllWindows()
    moves_thread.join() # Aguarda a thread de movimentos encerrar

