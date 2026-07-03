import cv2
import pytesseract
import numpy as np
import re
from PIL import Image

def processar_imagem_nf(imagem_upload):
    """
    Recebe o arquivo do Streamlit, limpa a imagem com OpenCV e extrai o texto com Tesseract.
    """
    # Converte o arquivo do Streamlit para um array do OpenCV
    file_bytes = np.asarray(bytearray(imagem_upload.read()), dtype=np.uint8)
    img_cv = cv2.imdecode(file_bytes, 1)

    # 1. Pré-processamento (OpenCV)
    # Converte para tons de cinza
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Binarização (Deixa o fundo branco e a letra preta, ignorando sombras)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 2. OCR (Tesseract) - Usando o idioma português
    texto_extraido = pytesseract.image_to_string(thresh, lang='por')
    
    return texto_extraido

def auditar_dados_nf(texto_extraido):
    """
    Procura padrões de CNPJ e Valor Total no texto bruto.
    """
    resultados = {
        "cnpj_encontrado": None,
        "valor_total_encontrado": None,
        "texto_bruto": texto_extraido
    }

    # Regex para CNPJ: XX.XXX.XXX/XXXX-XX
    padrao_cnpj = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
    cnpjs = re.findall(padrao_cnpj, texto_extraido)
    if cnpjs:
        resultados["cnpj_encontrado"] = cnpjs[0]

    # Regex para Valor: R$ XXX,XX ou variações com espaços
    padrao_valor = r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    valores = re.findall(padrao_valor, texto_extraido)
    
    if valores:
        # Pega o maior valor encontrado na nota (geralmente o Total)
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores]
        resultados["valor_total_encontrado"] = max(valores_float)

    return resultados