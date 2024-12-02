import logging
import time
import threading
from tracking_base import tracking, draw
from detect_qr import process

old_move = ''
pace = ' 70'
pace_moves = ['up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw']
searching = False
stop_searching = threading.Event()
stop_receiving = threading.Event()
last_command = ''

logging.basicConfig(
    filename="codes/log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S"
)

def log_command(command, response=None):
    '''
    Registra o comando enviado ao drone e a resposta recebida.
    Args:
        command (str): Comando enviado ao drone.
        response (str, opcional): Resposta recebida do drone.
    '''
    #global last_command
    if command != old_move:
        logging.info(f"{command}, {response}")
        #last_command = command

def search(tello):
    '''
    Procura por QR codes rotacionando o drone Tello em 20 graus para a direita e 40 graus para a esquerda.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
    '''
    timer = time.time()
    i = 0
    commands = ['cw 20', 'ccw 40']
    while not stop_searching.is_set() and not stop_receiving.is_set():
        if time.time() - timer >= 10:                 # 5 segundos
            response = tello.send_cmd(commands[i])   # Rotaciona 20 graus
            time.sleep(0.1)                          # Testar se resposta é exibida
            print(f"{commands[i]}, {response}")
            log_command(commands[i], response)
            timer = time.time()
            i = (i + 1) % 2                          # Alterna entre 0 e 1
        #print((time.time() - timer).__round__(2)) # Ver contagem regressiva

def moves(tello, frame):
    '''
    Processa o frame para detectar QR codes e executa comandos no drone Tello com base no texto detectado.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        frame: Frame processado após a detecção e execução dos comandos.
    '''
    global old_move, pace, pace_moves, searching
    frame, x1, y1, x2, y2, detections, text = process(frame) # Agora process() retorna os valores de x1, y1, x2, y2, para ser chamada apenas uma vez
    #frame, _, _, _, _, detections, text = process(frame)        

    if detections == 0 and old_move != 'land': # Se pousou, não deve rotacionar
        if not searching:
            stop_searching.clear()                                         # Reseta o evento de parada
            search_thread = threading.Thread(target=search, args=(tello,)) # Cria a thread de busca
            search_thread.start()                                          # Inicia a thread
            searching = True

        elif old_move == 'follow': # Necessário para que o drone não continue a se movimentar sem detecção de follow
            tello.send_rc_control(0, 0, 0, 0)
            #log_command('rc 0 0 0 0')

    elif detections == 1:
        if searching:
            stop_searching.set() # Setar evento de parada
            searching = False    # Parar busca

        if text == 'follow':
            frame = tracking(tello, frame, x1, y1, x2, y2, detections, text)
            log_command(text)

        elif text == 'land':
            while float(tello.get_state_field('h')) >= 13:
                tello.send_rc_control(0, 0, -70, 0)
            tello.send_cmd(str(text))
            log_command(text)

        elif text == 'takeoff' and old_move != 'takeoff':
            response = tello.send_cmd_return(text)
            time.sleep(1)
            print(f"{text}, {response}")
            log_command(f"{text}, {response}")

        elif text in pace_moves:
            response = tello.send_cmd_return(f"{text}{pace}")
            frame = draw(frame, x1, y1, x2, y2, text)
            print(f"{text}{pace}, {response}")
            log_command(f"{text}{pace}, {response}")

    old_move = text
    #print(f"Old move: {old_move}")
    return frame