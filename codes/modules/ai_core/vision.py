import io
import base64
import cv2
import numpy as np
from PIL import Image, ImageDraw

_yolo_model = None  # Variável global para armazenar o modelo YOLO carregado

def get_yolo_model():
    """Carrega o YOLO sob demanda (Lazy Loading) para poupar RAM."""
    global _yolo_model
    if _yolo_model is None:
        print("Carregando modelo de visão rápida (YOLO)...")
        from ultralytics import YOLO
        _yolo_model = YOLO('yolov8n.pt')
    return _yolo_model

def extract_features_with_yolo(frame: Image.Image) -> str:
    """
    Roda o YOLO no frame e traduz a posição dos objetos para texto.
    Divide a tela em Esquerda, Centro e Direita para noção espacial.
    """
    # Converte de PIL para o formato do OpenCV/YOLO
    yolo = get_yolo_model()
    img_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
    height, width, _ = img_cv.shape
    
    # Roda a inferência (verbose=False para não sujar o terminal)
    results = yolo(img_cv, verbose=False)
    
    detecoes = []
    
    # O YOLO retorna caixas delimitadoras (bounding boxes)
    for box in results[0].boxes:
        classe = int(box.cls[0])
        nome_obj = yolo.names[classe]
        
        # Pega as coordenadas X e Y do centro do objeto
        x_center, y_center, w, h = box.xywh[0]
        
        # Calcula área para saber se o objeto está "perto" (grande na tela)
        area_pct = (w * h) / (width * height)
        distancia = "próximo/grande" if area_pct > 0.15 else "longe/pequeno"
        
        # Determina a posição horizontal
        if x_center < width / 3:
            posicao = "à esquerda"
        elif x_center > 2 * width / 3:
            posicao = "à direita"
        else:
            posicao = "no centro (caminho frontal bloqueado)"
            
        detecoes.append(f"- 1 {nome_obj} ({posicao}, {distancia})")
    
    if not detecoes:
        return "CENÁRIO: O caminho está completamente livre de obstáculos visíveis."
    
    return "CENÁRIO DETECTADO PELO SENSOR VISUAL:\n" + "\n".join(detecoes)

def add_grid_to_image(image: Image.Image) -> Image.Image:
    """
    Desenha um grid 3x3 na imagem para ajudar a IA na noção espacial.
    Args:
        image (Image.Image): Imagem original.
    Returns:
        Image.Image: Imagem com grid desenhado.
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Linhas Verticais (dividir em 3)
    draw.line([(width/3, 0), (width/3, height)], fill="red", width=1)
    draw.line([(2*width/3, 0), (2*width/3, height)], fill="red", width=1)
    
    # Linhas Horizontais (dividir em 3)
    draw.line([(0, height/3), (width, height/3)], fill="red", width=1)
    draw.line([(0, 2*height/3), (width, 2*height/3)], fill="red", width=1)
    
    return img

def pil_image_to_bytes(image: Image.Image) -> bytes:
    """Converte PIL Image para bytes, redimensionando para performance local."""
    base_width = 640
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    
    img_resized = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
    
    with io.BytesIO() as buffer:
        img_resized.save(buffer, format="JPEG", quality=80)
        return buffer.getvalue()
    
def pil_image_to_base64(image: Image.Image) -> str:
    """
    Converte uma imagem PIL para uma string base64, para uso com a API OpenAI.
    Args:
        image (Image.Image): Imagem PIL.
    Returns:
        str: Imagem codificada em base64.
    """
    img_bytes = pil_image_to_bytes(image)
    return base64.b64encode(img_bytes).decode('utf-8')

