import numpy as np
import cv2

Width = 960
Height = 720

# Coordenadas do centro
CenterX = Width // 2
CenterY = Height // 2

# Erro anterior
prevErrorX = 0
prevErrorY = 0

# Coeficiente proporcional (obtido testando)
# Determina o quanto a velocidade deve mudar em resposta ao erro atual
Kp = 0.2

# Coeficiente derivativo (obtido testando)
# Responsável por controlar a taxa de variação do erro
Kd = 0.2

width_detect = 0
text = ''

def follow(tello: object, frame: object, x1: int, y1: int, x2: int, y2: int, detections: int, text: str) -> object:
    """
    Processa o frame para detectar QR codes e executa comandos no drone Tello com base no texto detectado.
    Args:
        tello: Objeto representando o drone Tello, que possui métodos para enviar comandos e obter estado.
        frame: Frame de vídeo a ser processado para detecção de QR codes.
        x1: Coordenada x do canto superior esquerdo do retângulo.
        y1: Coordenada y do canto superior esquerdo do retângulo.
        x2: Coordenada x do canto inferior direito do retângulo.
        y2: Coordenada y do canto inferior direito do retângulo.
        detections: Número de QR codes detectados no frame.
        text: Texto detectado nos QR codes.
    Returns:
        frame: Frame processado após a detecção e execução dos comandos.
    """
    global prevErrorX, prevErrorY, CenterX, CenterY, Kp, Kd
    
    speedFB = 0
    cxDetect = (x2 + x1) // 2
    cyDetect = (y2 + y1) // 2

    min_active_area = 20000
    max_active_area = 80000

    area = (x2 - x1) * (y2 - y1)
    
    if area > min_active_area and area < max_active_area:
        errorX = cxDetect - CenterX
        errorY = CenterY - cyDetect
        
        # Suavização de erro para evitar movimentos bruscos
        errorX = errorX * 0.8 + prevErrorX * 0.2
        errorY = errorY * 0.8 + prevErrorY * 0.2
        
        # Limite máximo de correção
        errorX = np.clip(errorX, -200, 200)
        errorY = np.clip(errorY, -200, 200)
    else:
        errorX = 0
        errorY = 0
        speedFB = 0  # Mantém velocidade zero se fora da área ideal

    # Cálculos de velocidade com limites dinâmicos
    speedYaw = int(np.clip(Kp*errorX + Kd*(errorX - prevErrorX), -100, 100))
    speedUD = int(np.clip(Kp*errorY + Kd*(errorY - prevErrorY), -100, 100))
    
    # Ajuste fino na velocidade frontal
    if area < min_active_area and speedFB == 0:
        speedFB = 15  # Pequeno impulso para frente
    elif area > max_active_area:
        speedFB = -15  # Pequeno recuo

    # Atualiza controles apenas se dentro da área operacional
    if area > min_active_area and area < max_active_area:
        tello.send_rc_control(0, speedFB, speedUD, speedYaw)
    else:
        tello.send_rc_control(0, 0, 0, 0)  # Para completamente se fora da área

    # Atualiza visualização
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
    cv2.circle(frame, (cxDetect, cyDetect), 5, (0, 0, 255), -1)
    cv2.putText(frame, f"Tracking: {text}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
    cv2.circle(frame, (CenterX, CenterY), 5, (0, 255, 255), -1)
    cv2.line(frame, (CenterX, CenterY), (cxDetect, cyDetect), (255, 255, 0), 2)

    # Atualiza erros anteriores
    prevErrorX = errorX
    prevErrorY = errorY
    
    return frame

def draw(frame: object, x1: int, y1: int, x2: int, y2: int, text: str) -> object:
    """
    Desenha um retângulo e o texto detectado no frame.
    Args:
        frame: Frame de vídeo a ser processado.
        x1: Coordenada x do canto superior esquerdo do retângulo.
        y1: Coordenada y do canto superior esquerdo do retângulo.
        x2: Coordenada x do canto inferior direito do retângulo.
        y2: Coordenada y do canto inferior direito do retângulo.
        text: Texto a ser exibido no frame.
    Returns:
        frame: Frame com o retângulo e o texto desenhados.
    """
    # Desenha o retângulo e o texto
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
    cv2.putText(frame, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
    return frame

