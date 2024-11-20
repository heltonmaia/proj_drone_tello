from tracking_base import tracking
from detect_qr import process
import time

old_move = ''
pace = ' 20'
pace_moves = ['up', 'down', 'left', 'right', 'forward', 'back']
start_time = time.time()  # Inicializa o tempo
searching = False

def timer():
    '''
    Função que verifica se o timer de 5 segundos expirou.
    Returns:
        Booleano que indica se o timer expirou.
    '''
    global start_time
    if time.time() - start_time >= 5:
        start_time = time.time()  # Reinicia o timer
        return True
    return False

def search(tello, frame):
    '''
    Função de busca que é chamada quando não há detecção de QR code após o timer expirar.
    Executa uma rotação para procurar QR codes.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        frame: Frame processado após a execução da rotação
    '''
    response = tello.send_cmd('ccw 20')  # Rotaciona 20 graus
    time.sleep(0.01)                     # testar se resposta é exibida
    print(f"Rotação enviada: {response}")
    return frame

def moves(tello, frame):
    '''
    Processa o frame para detectar QR codes e executa comandos no drone Tello com base no texto detectado.
    Args:
        tello: Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        frame: Frame processado após a detecção e execução dos comandos.
    '''
    global old_move, pace, pace_moves, searching, start_time
    
    frame, _, _, _, _, detections, text = process(frame)

    if detections > 0:
        searching = False
        start_time = time.time()
    
    elif detections == 0 and old_move != 'land':
        if timer():
            searching = True
            frame = search(tello, frame)
        elif old_move == 'follow': # necessário para que o drone não continue a se movimentar sem detecção de follow
            tello.send_rc_control(0, 0, 0, 0)

    if text == 'follow':
        frame = tracking(tello, frame)
    
    if detections == 1 and text == 'land':
        while float(tello.get_state_field('h')) >= 13:
            tello.send_rc_control(0, 0, -70, 0)
        tello.send_cmd(str(text))
    
    elif detections == 1 and text == 'takeoff' and old_move != 'takeoff':
        response = tello.send_cmd_return(text)
        print(f"{text}' '{response}")
    
    elif detections == 1 and text in pace_moves:
        response = tello.send_cmd_return(f"{text}{pace}")
        print(f"{text}{pace}' '{response}")

    old_move = text
    return frame