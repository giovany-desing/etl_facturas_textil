# app/ocr.py - OCR Processor
# Reciclado de utils/ocr.py
from pdf2image import convert_from_path
import pytesseract
import re
from typing import Dict, List
import os
from pathlib import Path

from app.utils import setup_logger
from app import database

logger = setup_logger(__name__)


def normalizar_numero(numero_str: str) -> float:
    """Convierte números en formato europeo o americano a float."""
    numero_str = numero_str.strip()
    
    if '.' in numero_str and ',' in numero_str:
        if numero_str.rindex('.') < numero_str.rindex(','):
            numero_str = numero_str.replace('.', '').replace(',', '.')
        else:
            numero_str = numero_str.replace(',', '')
    elif ',' in numero_str:
        if re.search(r',\d{2}$', numero_str):
            numero_str = numero_str.replace('.', '').replace(',', '.')
        else:
            numero_str = numero_str.replace(',', '')
    
    return float(numero_str)


def extraer_texto_pdf(pdf_path: str) -> str:
    """Extrae texto de un PDF usando OCR."""
    try:
        images = convert_from_path(pdf_path)
        if not images:
            logger.error("No se pudo convertir el PDF a imágenes")
            return ""
        
        texto_completo = ""
        for i, image in enumerate(images):
            logger.debug(f"Procesando página {i+1}/{len(images)}...")
            texto_completo += pytesseract.image_to_string(image, lang='spa') + "\n"
        
        print(f"texto completo -->> {texto_completo}")
        return texto_completo
    
    except Exception as e:
        logger.exception(f"Error al procesar PDF: {e}")
        return ""


def extraer_orden_compra(texto: str) -> str:
    """Extrae el número de orden de compra."""
    match = re.search(r'Orden\s+de\s+Compra:\s*(\d+)', texto, re.IGNORECASE)
    return match.group(1) if match else None


def extraer_fecha(texto: str) -> str:
    """Extrae y formatea la fecha de creación."""
    match = re.search(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})', texto)
    if not match:
        return None
    
    mes_str, dia, año = match.groups()
    meses = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    mes = meses.get(mes_str, '01')
    return f"{año}-{mes}-{dia.zfill(2)}"


def extraer_productos(texto: str) -> List[Dict]:
    """Extrae la lista de productos con sus detalles."""
    productos = []
    
    match_seccion = re.search(
        r'ARTÍCULO\s+CANTIDAD\s+TASA\s+CANTIDAD\s*(.+?)\s*Subtotal',
        texto,
        re.DOTALL | re.IGNORECASE
    )
    
    if not match_seccion:
        logger.warning("No se encontró la sección de productos")
        return productos
    
    lineas = match_seccion.group(1).strip().split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        match = re.search(
            r'^(.+?)\s+(\d+)\s+([0-9.,]+)\s*US\$\s+([0-9.,]+)\s*US\$',
            linea
        )
        
        if match:
            nombre = re.sub(r'(Dólares|Centavos)\s+por\s+.+$', '', match.group(1)).strip()
            cantidad = int(match.group(2))
            tasa = normalizar_numero(match.group(3))
            total = normalizar_numero(match.group(4))
            
            productos.append({
                'nombre': nombre,
                'cantidad': cantidad,
                'tasa': tasa,
                'total': total
            })
            logger.debug(f"Producto: {nombre} | Cantidad: {cantidad} | Total: ${total:,.2f}")
    
    logger.info(f"Total de productos extraídos: {len(productos)}")
    return productos


def extraer_total(texto: str) -> float:
    """Extrae el total de la factura."""
    match = re.search(r'Total\s+([0-9.,]+)\s*US\$', texto, re.IGNORECASE)
    if match:
        return normalizar_numero(match.group(1))
    
    # Intenta con subtotal
    match = re.search(r'Subtotal\s+([0-9.,]+)\s*US\$', texto, re.IGNORECASE)
    if match:
        logger.warning("Usando subtotal como total")
        return normalizar_numero(match.group(1))
    
    return 0.0


def procesar_carpeta_facturas(nombre_carpeta: str) -> Dict[str, Dict]:
    """
    Procesa todos los PDFs en una carpeta y extrae información de facturas.
    
    Args:
        nombre_carpeta: Nombre de la carpeta con los PDFs
        
    Returns:
        Diccionario con resultados por cada archivo PDF
    """
    # Configurar ruta
    proyecto_root = Path(__file__).parent.parent
    carpeta_path = proyecto_root / nombre_carpeta
    
    if not carpeta_path.exists() or not carpeta_path.is_dir():
        logger.error(f"La carpeta '{nombre_carpeta}' no existe o no es válida")
        return {}
    
    archivos_pdf = list(carpeta_path.glob("*.pdf"))
    logger.info(f"Se encontraron {len(archivos_pdf)} archivos PDF")
    
    resultados = {}
    
    for pdf_path in archivos_pdf:
        logger.info(f"\n{'='*60}\nProcesando: {pdf_path.name}\n{'='*60}")
        
        # 1. Extraer texto
        texto = extraer_texto_pdf(str(pdf_path))
        if not texto:
            logger.error(f"No se pudo extraer texto de {pdf_path.name}")
            continue
        
        # 2. Extraer información
        orden_compra = extraer_orden_compra(texto)
        fecha_creacion = extraer_fecha(texto)
        productos = extraer_productos(texto)
        total = extraer_total(texto)
        
        # 3. Si no hay total, calcularlo desde productos
        if total == 0.0 and productos:
            total = sum(p['total'] for p in productos)
            logger.info(f"Total calculado desde productos: ${total:,.2f}")
        
        # 4. Formatear resultado
        resultado = {
            'orden_compra': orden_compra,
            'fecha_creacion': fecha_creacion,
            'productos': [p['nombre'] for p in productos],
            'cantidades': [p['cantidad'] for p in productos],
            'totales': [p['total'] for p in productos],
            'total': total
        }
        
        # 5. Log de resumen
        print(f"\n✓ Orden de compra: {orden_compra}")
        print(f"✓ Fecha: {fecha_creacion}")
        print(f"✓ Productos: {resultado['productos']}")
        print(f"✓ Cantidades: {resultado['cantidades']}")
        print(f"✓ Totales: {resultado['totales']}")
        print(f"✓ Total global: ${total:,.2f}\n")

        productos = resultado['productos']
        cantidades = resultado['cantidades']
        totales = resultado['totales']
        
        # Validar datos antes de insertar
        if not orden_compra:
            logger.error(f"  No se pudo extraer orden de compra de {pdf_path.name}. Saltando inserción.")
            resultados[pdf_path.name] = resultado
            continue
        
        if not productos or len(productos) == 0:
            logger.warning(f"  No se encontraron productos en {pdf_path.name}. Saltando inserción de productos.")
        else:
            # Insertar en MySQL
            nombre_tabla = "ventas_preventivas" if nombre_carpeta == "prev" else "ventas_correctivas"
            logger.info(f"💾 Insertando orden {orden_compra} en MySQL (tabla: {nombre_tabla})...")
            exito_fecha = database.actualizar_orden_fecha(orden_compra, fecha_creacion, productos, cantidades, totales, nombre_carpeta)
            if exito_fecha:
                logger.info(f" Orden {orden_compra} insertada exitosamente en {nombre_tabla}")
            else:
                logger.error(f" Error al insertar orden {orden_compra} en {nombre_tabla}")
        
        # Nota: El total ya se guarda en cada registro de producto, no necesita tabla separada
        logger.debug(f"Total de orden {orden_compra}: ${total:,.2f} (ya incluido en cada producto)")
        
        resultados[pdf_path.name] = resultado
    
    logger.info(f"\n{'='*60}\nProcesamiento completo: {len(resultados)} facturas procesadas\n{'='*60}")
    return resultados


if __name__ == "__main__":
   resultados = procesar_carpeta_facturas("corr")