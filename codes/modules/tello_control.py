import logging
import time
import threading
from .tracking_base import follow, draw
from .qr_processing import process

old_move = ''
pace = ' 50'
pace_moves = ['up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw']
searching = False
enable_search = False
stop_searching = threading.Event()
response = ''
log_messages = []
last_command_time = {} # Dicionário para armazenar o tempo do último envio de cada comando

def search(tello: object):
    '''
    Procura por QR codes rotacionando o drone Tello em 20 graus para a direita e 40 graus para a esquerda.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
    '''
    timer = time.time()
    i = 0
    commands = ['ccw 20', 'cw 50']
    while not stop_searching.is_set() and not tello.stop_receiving.is_set() and enable_search:
        if time.time() - timer >= 10:                # 10 segundos
            response = tello.send_cmd(commands[i])   # Rotaciona
            time.sleep(0.1)                          # Testar se resposta é exibida
            print(f"{commands[i]}, {response}")
            #logging.info(response)
            log_messages.append(f"{commands[i]}, {response}\n")
            timer = time.time()
            i = (i + 1) % 2                          # Alterna entre 0 e 1
            time.sleep(0.01)
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
    global old_move, pace, pace_moves, searching, response, enable_search
    frame, x1, y1, x2, y2, detections, text = process(frame) # Agora process() retorna os valores de x1, y1, x2, y2, para ser chamada apenas uma vez

    if detections == 0 and old_move != 'land': # Se pousou, não deve rotacionar
        if not searching:
            stop_searching.clear()                                         # Reseta o evento de parada
            search_thread = threading.Thread(target=search, args=(tello,)) # Cria a thread de busca
            search_thread.daemon = True                                    # Define como daemon (encerra quando a thread principal encerra)
            search_thread.start()                                          # Inicia a thread
            searching = True

        elif old_move == 'follow': # Necessário para que o drone não continue a se movimentar sem detecção de follow
            tello.send_rc_control(0, 0, 0, 0)

    elif detections == 1:
        if searching:
            stop_searching.set() # Setar evento de parada
            searching = False    # Parar busca

        if text == 'follow':
            frame = follow(tello, frame, x1, y1, x2, y2, detections, text)
            logging.info(text)
            log_messages.append(text)

        elif text == 'land' and old_move != 'land':
            tello.land() # Atualizado
            print(text)
            logging.info(text)
            log_messages.append(text)

        elif text == 'takeoff' and old_move != 'takeoff':
            tello.send_cmd(text)
            time.sleep(0.1)
            print(text)
            #logging.info(text)
            log_messages.append(text)

        elif text in pace_moves:
            frame = draw(frame, x1, y1, x2, y2, text)
            current_time = time.time()
            last_time = last_command_time.get(text, 0)               # Se não existir, retorna 0
            if old_move != text or (current_time - last_time >= 10): # Se o comando for diferente do anterior ou se passaram 10 segundos desde o repetido
                with tello.queue_lock:                               # Bloqueia a fila de comandos
                    tello.command_queue.append(f"{text}{pace}")      # Adiciona o comando à fila
                    #print(command_queue)
                time.sleep(1)
                logging.info(f"{text}{pace}, {response}")
                log_messages.append(f"{text}{pace}, {response}\n")
                last_command_time[text] = current_time               # Atualiza o tempo do último comando de text

    old_move = text
    #print(f"Old move: {old_move}")
    return frame