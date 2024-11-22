import numpy as np
import cv2
from detect_qr import process

Width = 800
Height = 600
#coordenadas do centro
CenterX = Width // 2
CenterY = Height // 2
#erro anterior
prevErrorX = 0
prevErrorY = 0
#coeficiente proporcional (obtido testando)
#determina o quanto a velocidade deve mudar em resposta ao erro atual
Kp = 0.2
#coeficiente derivativo (obtido testando)
#responsável por controlar a taxa de variação do erro
Kd = 0.2

width_detect = 0
text = ''
old_move = ''

def tracking(tello, frame):
    '''
    Processa o frame para detectar QR codes e executa comandos no drone Tello com base no texto detectado.
    Args:
        tello: Objeto representando o drone Tello, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        frame: Frame processado após a detecção e execução dos comandos.
    '''
    global prevErrorX, prevErrorY, CenterX, CenterY, Kp, Kd, text, width_detect
    _, x1, y1, x2, y2, detections, text = process(frame)
    speedFB = 0
    cxDetect = (x2 + x1) // 2
    cyDetect = (y2 + y1) // 2

    #PID - Speed Control
    width_detect = x2 - x1
    area = (x2 - x1) * (y2 - y1)
    #print(f"Area: {area}")
    #print(f"DETECTIONS: {detections}")
    #se o centro da detecção encontrar-se na esquerda, o erro na horizontal será negativo
    #se o objeto estiver na direita, o erro será positivo
    if (detections > 0):
        errorX = cxDetect - CenterX
        #print(errorX)
        errorY = CenterY - cyDetect
        #print(errorY)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
        cv2.circle(frame, (cxDetect, cyDetect), 5, (0, 0, 255), -1)
        cv2.putText(frame, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
        cv2.circle(frame, (CenterX, CenterY), 5, (0, 255, 255), -1)
        cv2.line(frame, (CenterX, CenterY), (cxDetect, cyDetect), (255, 255, 0), 2)
        if area < 20000: 
            speedFB = 25
        elif area > 80000: # menor
            speedFB = -25
            #print(f"AREA: {area}")
    else:
        errorX = 0
        errorY = 0
        #print("0 DETECTIONS")
        #print(f"AREA: {area_land}")

    #velocidade de rotação em torno do próprio eixo é calculada em relação ao erro horizontal
    speedYaw = Kp*errorX + Kd*(errorX - prevErrorX)
    speedUD = Kp*errorY + Kd*(errorY - prevErrorY)
    #não permite que a velocidade 'vaze' o intervalo -100 / 100
    speedYaw = int(np.clip(speedYaw,-100,100))
    speedUD = int(np.clip(speedUD,-100,100))
    
    #print(f"FB: {speedFB}, UD: {speedUD}, YAW: {speedYaw}")
    if(detections == 1 and text == 'dados de leitura'):
        tello.send_rc_control(0, speedFB, speedUD, speedYaw)
        print(f'FB: {speedFB}, UD: {speedUD}, Yaw: {speedYaw}')
    
    #o erro atual vira o erro anterior
    prevErrorX = errorX
    prevErrorY = errorY
    return frame


