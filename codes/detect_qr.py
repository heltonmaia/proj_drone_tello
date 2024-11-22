from pyzbar.pyzbar import decode

data = []
x, y, w, h = 0, 0, 0, 0

"""
Recebe um frame, detecta os códigos desenhando as bordas e o texto,
armazena o texto em uma lista e retorna o frame
"""
def process(frame):
    '''
    Recebe um frame, detecta os códigos desenhando as bordas e o texto,
    armazena o texto em uma lista e retorna o frame
    Args:
        frame: Frame de vídeo a ser processado para detecção de QR codes.
    Returns:
        [frame, x, y, x+w, y+h, len(decoded_objects), qr_text]
    '''
    decoded_objects = decode(frame)
    global x, y, w, h, data, qr_text
    qr_text = ''
    for obj in decoded_objects:
        (x, y, w, h) = obj.rect
        qr_text = obj.data.decode('utf-8')
        #print(qr_text)
        if qr_text not in data:
            data.append(qr_text)
    #print(data)
    return [frame, x, y, x+w, y+h, len(decoded_objects), qr_text]

#cv2.namedWindow('QR Code', cv2.WINDOW_AUTOSIZE)