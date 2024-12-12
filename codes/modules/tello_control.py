import logging
import time
import threading
from modules.tracking_base import follow, draw
from modules.qr_processing import process

old_move = ''
pace = ' 70'
pace_moves = ['up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw']
searching = False
stop_searching = threading.Event()
stop_receiving = threading.Event()
last_command = ''
command_queue = []
queue_lock = threading.Lock()
response = None

def readQueue(tello: object):
    while not stop_receiving.is_set():
        with queue_lock:   # Evita que a lista seja alterada enquanto é lida
            if command_queue:
                command = command_queue.pop(0)
                print(command)
        if command:        # Se houver comando na fila
            response = tello.send_cmd_return(command)
            print(f"{command}, {response}")
        time.sleep(0.1)

def search(tello: object):
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
            logging.info(response)
            timer = time.time()
            i = (i + 1) % 2                          # Alterna entre 0 e 1
        #print((time.time() - timer).__round__(2)) # Ver contagem regressiva

def moves(tello: object, frame: object) -> object:
    '''
    Processa o frame para detectar QR codes e executa comandos no drone Tello com base no texto detectado.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        frame: Frame processado após a detecção e execução dos comandos.
    '''
    global old_move, pace, pace_moves, searching, response
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
            frame = follow(tello, frame, x1, y1, x2, y2, detections, text)
            logging.info(text)

        elif text == 'land':
            while float(tello.get_state_field('h')) >= 13:
                tello.send_rc_control(0, 0, -70, 0)
            tello.send_cmd(str(text))
            logging.info(text)

        elif text == 'takeoff' and old_move != 'takeoff':
            response = tello.send_cmd_return(text)
            time.sleep(1)
            print(response)
            logging.info(response)

        elif text in pace_moves:
            frame = draw(frame, x1, y1, x2, y2, text)
            if old_move != text: # Não deve fazer comandos repetidos
                with queue_lock:
                    command_queue.append(f"{text}{pace}")
                print(f"{text}{pace}, {response}")
                logging.info(f"{text}{pace}, {response}")

    old_move = text
    #print(f"Old move: {old_move}")
    return frame