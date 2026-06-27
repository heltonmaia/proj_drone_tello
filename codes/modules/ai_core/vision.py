"""
Módulo de Processamento Visual e Extração de Features.

Este módulo é responsável por atuar como os "olhos" do drone Tello. 
Ele utiliza visão computacional clássica (OpenCV) e modelos de aprendizado 
profundo (YOLOv8) para analisar os frames da câmera, detectar obstáculos, 
e converter o mundo visual em relatórios textuais compreensíveis para as LLMs.

Funcionalidades Principais:
    - Carregamento sob demanda (Lazy Loading) do modelo YOLOv8.
    - Detecção de objetos e mapeamento espacial (esquerda, centro, direita).
    - Detecção de proximidade crítica via variância de pixels.
    - Conversão e formatação de imagens PIL para APIs de IA.
"""

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

def extract_features_with_yolo(frame: Image.Image, draw_boxes: bool = True) -> tuple[str, Image.Image]:
    """
    Roda o YOLO no frame e traduz a posição dos objetos para texto.
    Agora retorna também a imagem anotada com bounding boxes.

    Args:
        frame (Image.Image): Imagem atual capturada pela câmera
        draw_boxes (bool): Se True, a função anota as bounding boxes

    Returns:
        tuple: (descrição textual, imagem PIL anotada)
    """
    yolo = get_yolo_model()
    img_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    variancia = np.var(gray)
    
    # Cópia para desenhar as boxes
    annotated_cv = img_cv.copy() if draw_boxes else img_cv
    
    if variancia < 100:
        # Desenha aviso vermelho na imagem mesmo no caso de cegueira
        if draw_boxes:
            cv2.putText(annotated_cv, "CEGUEIRA / COLISAO IMINENTE", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        annotated_pil = Image.fromarray(cv2.cvtColor(annotated_cv, cv2.COLOR_BGR2RGB))
        return ("ALERTA CRÍTICO DE COLISÃO: A câmera está cega, provavelmente a "
                "centímetros de uma parede lisa ou obstáculo. O caminho frontal "
                "ESTÁ BLOQUEADO. Ação obrigatória: cw 90 ou back 20."), annotated_pil

    height, width, _ = img_cv.shape
    results = yolo(img_cv, verbose=False)
    
    detecoes = []
    colors = {}  # Cor consistente por classe
    
    for box in results[0].boxes:
        classe = int(box.cls[0])
        nome_obj = yolo.names[classe]
        
        x_center, y_center, w, h = box.xywh[0]
        x_center, y_center, w, h = float(x_center), float(y_center), float(w), float(h)
        
        area_pct = (w * h) / (width * height)
        distancia = "próximo/grande" if area_pct > 0.15 else "longe/pequeno"
        
        if x_center < width / 3:
            posicao = "à esquerda"
        elif x_center > 2 * width / 3:
            posicao = "à direita"
        else:
            posicao = "no centro (caminho frontal bloqueado)"
            
        detecoes.append(f"- 1 {nome_obj} ({posicao}, {distancia})")
        
        if draw_boxes:
            # Cor por classe (hash simples)
            if nome_obj not in colors:
                np.random.seed(hash(nome_obj) % 2**32)
                colors[nome_obj] = tuple(int(c) for c in np.random.randint(0, 255, 3))
            color = colors[nome_obj]
            
            x1 = int(x_center - w/2)
            y1 = int(y_center - h/2)
            x2 = int(x_center + w/2)
            y2 = int(y_center + h/2)
            
            cv2.rectangle(annotated_cv, (x1, y1), (x2, y2), color, 2)
            label = f"{nome_obj} {posicao}"
            cv2.putText(annotated_cv, label, (x1, max(y1-5, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Converte de volta para PIL RGB
    annotated_pil = Image.fromarray(cv2.cvtColor(annotated_cv, cv2.COLOR_BGR2RGB))
    
    if not detecoes:
        return "CENÁRIO: O caminho está completamente livre de obstáculos visíveis.", annotated_pil
    
    return "CENÁRIO DETECTADO PELO SENSOR VISUAL:\n" + "\n".join(detecoes), annotated_pil

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

