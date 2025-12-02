# app/preprocessing.py - Image Preprocessing
# Reciclado de utils/preprocessing_data.py
import os
import numpy as np
import pandas as pd
from pdf2image import convert_from_path
import cv2
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from datetime import datetime

from app.config import settings
from app.utils import setup_logger

logger = setup_logger(__name__)




#Se descargan las carpetas que contienen la infomacion para el entrenamiento
#conect_drive.descargar_carpeta('invoices_train')
#conect_drive.descargar_carpeta('invoices_test')

# ========== CONFIGURACIÓN ==========
# Obtener la ruta del directorio raíz del proyecto
DIRECTORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rutas de carpetas (en la raíz del proyecto)
CARPETA_ENTRENAMIENTO = os.path.join(DIRECTORIO_RAIZ, "invoices_train")
CARPETA_PRUEBA = os.path.join(DIRECTORIO_RAIZ, "invoices_test") 
CARPETA_SALIDA = os.path.join(DIRECTORIO_RAIZ, "train_data")

# Configuración de imágenes
TAMAÑO_IMAGEN = (224, 224)
CANALES = 3
RANGO_NORMALIZACION = (0, 1)

# Mapeo de etiquetas - SOLO 0 Y 1
MAPEO_ETIQUETAS = {
    '0': 0,  # facturas corr
    '1': 1   # facturas prev
}

# Extensiones permitidas
EXTENSIONES_PERMITIDAS = ['.pdf', '.jpg', '.jpeg', '.png']

# ========== FUNCIONES DE VERIFICACIÓN DEL ENTORNO ==========

# ========== FUNCIONES DE VERIFICACIÓN ==========
def verificar_estructura_proyecto_preprocesamiento(): # -->>check
    """Verifica que la estructura del proyecto sea correcta"""
    logger.info("Verificando estructura del proyecto...")
    logger.info(f"Directorio raíz: {DIRECTORIO_RAIZ}")
    
    carpetas_requeridas = [CARPETA_ENTRENAMIENTO, CARPETA_PRUEBA]
    
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f" Carpeta encontrada: {carpeta}")
        else:
            logger.error(f" Carpeta no encontrada: {carpeta}")
            return False
    
    # Verificar subcarpetas de etiquetas (0 y 1)
    for etiqueta in MAPEO_ETIQUETAS.keys():
        carpeta_entrenamiento_etiqueta = os.path.join(CARPETA_ENTRENAMIENTO, etiqueta)
        carpeta_prueba_etiqueta = os.path.join(CARPETA_PRUEBA, etiqueta)
        
        if os.path.exists(carpeta_entrenamiento_etiqueta):
            logger.info(f" Subcarpeta encontrada: invoices_train/{etiqueta}")
            # Contar archivos en la subcarpeta
            archivos = []
            for ext in EXTENSIONES_PERMITIDAS:
                archivos.extend([f for f in os.listdir(carpeta_entrenamiento_etiqueta) if f.lower().endswith(ext)])
            logger.info(f"    {len(archivos)} archivos en invoices_train/{etiqueta}")
        else:
            logger.warning(f" Subcarpeta no encontrada: invoices_train/{etiqueta}")
            
        if os.path.exists(carpeta_prueba_etiqueta):
            logger.info(f" Subcarpeta encontrada: invoices_test/{etiqueta}")
            # Contar archivos en la subcarpeta
            archivos = []
            for ext in EXTENSIONES_PERMITIDAS:
                archivos.extend([f for f in os.listdir(carpeta_prueba_etiqueta) if f.lower().endswith(ext)])
            logger.info(f"    {len(archivos)} archivos en invoices_test/{etiqueta}")
        else:
            logger.warning(f" Subcarpeta no encontrada: invoices_test/{etiqueta}")
    
    return True

def verificar_poppler_preprocesamiento(): # -->>check
    """Verifica si poppler está disponible"""
    try:
        from pdf2image import pdfinfo_from_path
        logger.info("Poppler está correctamente instalado")
        return True
    except Exception as e:
        logger.error("Poppler no está instalado o no está en PATH")
        logger.info("Soluciones:")
        logger.info("   - Windows: conda install -c conda-forge poppler")
        logger.info("   - Linux: sudo apt-get install poppler-utils")
        logger.info("   - Mac: brew install poppler")
        return False

def crear_carpetas_preprocesamiento(): # -->>check
    """Crea las carpetas necesarias si no existen"""
    carpetas = [CARPETA_SALIDA]
    for carpeta in carpetas:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
            logger.info(f"Carpeta creada: {carpeta}")

# ========== FUNCIONES DE PROCESAMIENTO DE IMÁGENES ==========
def pdf_a_imagen_preprocesamiento(pdf_path, dpi=200): # -->> check
    """Convierte la primera página del PDF a imagen CON CORRECCIÓN DE COLOR"""
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"Archivo no encontrado: {pdf_path}")
            return None
        
        logger.debug(f"Convirtiendo PDF a imagen: {os.path.basename(pdf_path)}")
        
        # Convertir PDF a imagen (solo primera página)
        imagenes = convert_from_path(
            pdf_path, 
            dpi=dpi, 
            first_page=1, 
            last_page=1,
            fmt='jpeg'
        )
        
        if imagenes:
            imagen = imagenes[0]
            
            #  CORRECCIÓN: Detectar y convertir escala de grises falsa
            if hasattr(imagen, 'mode') and imagen.mode == 'RGB':
                # Convertir a array para verificar canales
                img_array = np.array(imagen)
                
                # Verificar si los 3 canales son idénticos (RGB falso)
                if (len(img_array.shape) == 3 and img_array.shape[2] == 3 and
                    np.array_equal(img_array[:,:,0], img_array[:,:,1]) and 
                    np.array_equal(img_array[:,:,1], img_array[:,:,2])):
                    
                    logger.debug(f" Convirtiendo RGB falso a escala de grises real: {os.path.basename(pdf_path)}")
                    # Convertir a escala de grises real y luego a RGB
                    imagen_gris = imagen.convert('L')
                    imagen = imagen_gris.convert('RGB')
            
            logger.debug(f"PDF convertido exitosamente: {os.path.basename(pdf_path)}")
            return imagen
        else:
            logger.error(f"No se pudieron generar imágenes del PDF: {os.path.basename(pdf_path)}")
            return None
            
    except Exception as e:
        logger.error(f"Error convirtiendo {os.path.basename(pdf_path)}: {str(e)}")
        return None

def redimensionar_imagen_preprocesamiento(imagen, tamaño_objetivo=TAMAÑO_IMAGEN):
    """Redimensiona la imagen al tamaño objetivo manteniendo la relación de aspecto"""
    logger.debug(f"Redimensionando imagen a {tamaño_objetivo}")
    
    # Convertir a array numpy si es PIL Image
    if hasattr(imagen, 'size'):
        img_array = np.array(imagen)
    else:
        img_array = imagen
    
    # Redimensionar usando interpolación de área (mejor para reducción)
    img_redimensionada = cv2.resize(
        img_array, 
        tamaño_objetivo, 
        interpolation=cv2.INTER_AREA
    )
    
    return img_redimensionada

def normalizar_imagen_preprocesamiento(imagen, rango=RANGO_NORMALIZACION):
    """Normaliza los valores de píxeles al rango especificado"""
    logger.debug(f"Normalizando imagen al rango {rango}")
    
    imagen = imagen.astype(np.float32)
    
    if rango == (0, 1):
        # Normalizar a [0, 1]
        imagen = imagen / 255.0
    elif rango == (-1, 1):
        # Normalizar a [-1, 1]
        imagen = (imagen / 127.5) - 1.0
    
    return imagen

def convertir_a_rgb_preprocesamiento(imagen):
    """Convierte la imagen a formato RGB (3 canales) - VERSIÓN SIMPLIFICADA"""
    logger.debug("Convirtiendo imagen a formato RGB")
    
    # Si es PIL Image, convertir a numpy
    if hasattr(imagen, 'size'):
        imagen = np.array(imagen)
        logger.debug(f"Convertida PIL Image a numpy: {imagen.shape}")
    
    #  CORRECCIÓN: Detección más simple de canales idénticos
    if len(imagen.shape) == 3 and imagen.shape[2] == 3:
        # Verificación rápida de canales idénticos
        if np.array_equal(imagen[:,:,0], imagen[:,:,1]):
            logger.warning(" Detectado RGB con canales idénticos. Forzando conversión...")
            # Tomar primer canal y convertir a RGB real
            imagen = imagen[:,:,0]
            return cv2.cvtColor(imagen, cv2.COLOR_GRAY2RGB)
        else:
            logger.debug(" Imagen ya es RGB con canales diferentes")
            return imagen
    
    elif len(imagen.shape) == 2:
        logger.debug("Convirtiendo escala de grises a RGB")
        return cv2.cvtColor(imagen, cv2.COLOR_GRAY2RGB)
    
    elif len(imagen.shape) == 3 and imagen.shape[2] == 4:
        logger.debug("Convirtiendo RGBA a RGB")
        return cv2.cvtColor(imagen, cv2.COLOR_RGBA2RGB)
    
    else:
        logger.warning(f"Formato de imagen no reconocido: {imagen.shape}")
        return imagen

def preprocesar_imagen_completo_preprocesamiento(imagen):
    """Aplica todo el pipeline de preprocesamiento a una imagen"""
    if imagen is None:
        logger.warning("Imagen es None, no se puede preprocesar")
        return None
    
    try:
        logger.debug("Iniciando preprocesamiento completo de imagen")
        
        # 1. Convertir a array numpy (manejar PIL Image)
        if hasattr(imagen, 'size'):
            img_array = np.array(imagen)
            logger.debug(f"Imagen PIL convertida a numpy: {img_array.shape}")
        else:
            img_array = imagen
        
        # 2. VERIFICACIÓN CRÍTICA: Loggear forma original
        logger.debug(f"Forma original de la imagen: {img_array.shape}")
        
        # 3. Convertir a RGB (usar función corregida)
        img_rgb = convertir_a_rgb_preprocesamiento(img_array)
        logger.debug(f"Después de conversión RGB: {img_rgb.shape}")
        
        # 4. VERIFICACIÓN: Asegurar que tenemos 3 canales REALES
        if len(img_rgb.shape) != 3 or img_rgb.shape[2] != 3:
            logger.error(f"ERROR: No se pudo convertir a 3 canales. Forma: {img_rgb.shape}")
            # Forzar corrección de emergencia
            if len(img_rgb.shape) == 2:
                img_rgb = np.stack([img_rgb] * 3, axis=-1)
            elif img_rgb.shape[2] == 1:
                img_rgb = np.repeat(img_rgb, 3, axis=2)
            logger.debug(f"Forma después de corrección de emergencia: {img_rgb.shape}")
        
        # 5. Redimensionar
        img_redimensionada = redimensionar_imagen_preprocesamiento(img_rgb, TAMAÑO_IMAGEN)
        logger.debug(f"Después de redimensionar: {img_redimensionada.shape}")
        
        # 6. Normalizar
        img_normalizada = normalizar_imagen_preprocesamiento(img_redimensionada, RANGO_NORMALIZACION)
        
        # VERIFICACIÓN FINAL
        expected_shape = TAMAÑO_IMAGEN + (3,)
        if img_normalizada.shape != expected_shape:
            logger.error(f"FORMA INCORRECTA: {img_normalizada.shape} vs esperado: {expected_shape}")
            return None
        
        logger.debug(" Preprocesamiento de imagen completado exitosamente")
        return img_normalizada
        
    except Exception as e:
        logger.error(f"Error en preprocesamiento de imagen: {e}")
        return None

# ========== FUNCIONES DE MANEJO DE ARCHIVOS ==========
def obtener_rutas_etiquetadas_preprocesamiento(carpeta_base):
    """Obtiene todas las rutas de archivos con sus etiquetas numéricas (0 y 1)"""
    logger.debug(f"Buscando archivos en: {carpeta_base}")
    rutas = []
    etiquetas = []
    
    # Buscar en subcarpetas según mapeo de etiquetas (0 y 1)
    for etiqueta_str, etiqueta_int in MAPEO_ETIQUETAS.items():
        carpeta_etiqueta = os.path.join(carpeta_base, etiqueta_str)
        
        if os.path.exists(carpeta_etiqueta):
            # Buscar archivos con extensiones permitidas
            archivos = []
            for ext in EXTENSIONES_PERMITIDAS:
                archivos.extend([f for f in os.listdir(carpeta_etiqueta) if f.lower().endswith(ext)])
            
            logger.debug(f"Encontrados {len(archivos)} archivos en {carpeta_etiqueta} -> etiqueta {etiqueta_int}")
            
            for archivo in archivos:
                ruta_completa = os.path.join(carpeta_etiqueta, archivo)
                rutas.append(ruta_completa)
                etiquetas.append(etiqueta_int)
        else:
            logger.warning(f"Directorio no encontrado: {carpeta_etiqueta}")
    
    logger.info(f"Total de archivos encontrados en {os.path.basename(carpeta_base)}: {len(rutas)}")
    
    # Mostrar distribución de etiquetas
    if etiquetas:
        etiquetas_array = np.array(etiquetas)
        conteo_etiquetas = {etiqueta: np.sum(etiquetas_array == etiqueta) for etiqueta in MAPEO_ETIQUETAS.values()}
        logger.info(f"Distribución de etiquetas en {os.path.basename(carpeta_base)}: {conteo_etiquetas}")
    
    return rutas, etiquetas

def extraer_caracteristicas_imagen_preprocesamiento(ruta_archivo):
    """Extrae y preprocesa completamente la imagen de un archivo (PDF o imagen)"""
    logger.debug(f"Extrayendo características de: {os.path.basename(ruta_archivo)}")
    
    # Verificar extensión del archivo
    extension = os.path.splitext(ruta_archivo)[1].lower()
    
    if extension == '.pdf':
        # Convertir PDF a imagen
        imagen = pdf_a_imagen_preprocesamiento(ruta_archivo)
        if imagen is not None:
            logger.debug(f"PDF convertido. Tipo: {type(imagen)}")
    elif extension in ['.jpg', '.jpeg', '.png']:
        # Cargar imagen directamente
        try:
            imagen = cv2.imread(ruta_archivo)
            if imagen is None:
                logger.warning(f"No se pudo cargar la imagen: {os.path.basename(ruta_archivo)}")
                return None
            imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
            logger.debug(f"Imagen cargada. Forma: {imagen.shape}")
        except Exception as e:
            logger.error(f"Error cargando imagen {os.path.basename(ruta_archivo)}: {e}")
            return None
    else:
        logger.warning(f"Extensión no soportada: {extension}")
        return None
    
    if imagen is None:
        logger.warning(f"No se pudo procesar el archivo: {os.path.basename(ruta_archivo)}")
        return None
    
    # Aplicar preprocesamiento completo CORREGIDO
    return preprocesar_imagen_completo_preprocesamiento(imagen)

def preprocesar_conjunto_datos_preprocesamiento(carpeta_base, nombre_conjunto="entrenamiento"):
    """Preprocesa todo un conjunto de datos (entrenamiento o prueba)"""
    logger.info(f"Iniciando preprocesamiento de datos de {nombre_conjunto}")
    
    # Obtener rutas y etiquetas
    rutas, etiquetas = obtener_rutas_etiquetadas_preprocesamiento(carpeta_base)
    
    if not rutas:
        logger.warning(f"No se encontraron archivos en {os.path.basename(carpeta_base)}")
        return np.array([]), np.array([])
    
    logger.info(f"Encontrados {len(rutas)} archivos para {nombre_conjunto}")
    
    # Procesar imágenes
    imagenes = []
    etiquetas_validas = []
    errores = 0
    
    for i, (ruta, etiqueta) in enumerate(zip(rutas, etiquetas)):
        nombre_archivo = os.path.basename(ruta)
        logger.debug(f"Procesando [{i+1}/{len(rutas)}]: {nombre_archivo} (etiqueta: {etiqueta})")
        
        # Extraer y preprocesar imagen
        caracteristicas = extraer_caracteristicas_imagen_preprocesamiento(ruta)
        
        if caracteristicas is not None:
            # VERIFICACIÓN FINAL DE FORMA
            expected_shape = TAMAÑO_IMAGEN + (3,)
            if caracteristicas.shape != expected_shape:
                logger.warning(f"Forma incorrecta en {nombre_archivo}: {caracteristicas.shape}. Esperado: {expected_shape}")
                errores += 1
                continue
                
            imagenes.append(caracteristicas)
            etiquetas_validas.append(etiqueta)
            logger.debug(f" Procesado exitosamente: {nombre_archivo} - Forma: {caracteristicas.shape}")
        else:
            logger.error(f" Error al procesar: {nombre_archivo}")
            errores += 1
    
    tasa_exito = (len(imagenes) / len(rutas)) * 100 if len(rutas) > 0 else 0
    logger.info(f"Procesamiento de {nombre_conjunto} completado: "
                f"{len(imagenes)} exitosos, {errores} errores "
                f"({tasa_exito:.1f}% de éxito)")
    
    return np.array(imagenes), np.array(etiquetas_validas)

# ========== FUNCIONES DE UTILIDAD ==========
def mostrar_estadisticas_imagenes_preprocesamiento(imagenes, etiquetas, nombre_conjunto):
    """Muestra estadísticas del conjunto de imágenes preprocesadas"""
    if len(imagenes) == 0:
        logger.warning(f"No hay imágenes para mostrar estadísticas en {nombre_conjunto}")
        return
    
    logger.info(f"Estadísticas - {nombre_conjunto}:")
    logger.info(f"  Número de imágenes: {len(imagenes)}")
    logger.info(f"  Forma de las imágenes: {imagenes.shape}")
    logger.info(f"  Rango de valores: [{imagenes.min():.3f}, {imagenes.max():.3f}]")
    
    # Distribución de etiquetas numéricas (0 y 1)
    etiquetas_array = np.array(etiquetas)
    conteo_etiquetas = {etiqueta: np.sum(etiquetas_array == etiqueta) for etiqueta in [0, 1]}
    logger.info(f"  Distribución de etiquetas: {conteo_etiquetas}")
    
    # Estadísticas por canal
    if len(imagenes.shape) == 4:  # (batch, height, width, channels)
        for canal in range(imagenes.shape[3]):
            canal_data = imagenes[:, :, :, canal]
            logger.info(f"  Canal {canal}: media={canal_data.mean():.3f}, "
                       f"std={canal_data.std():.3f}")

def mostrar_ejemplos_preprocesados_preprocesamiento(imagenes, etiquetas, titulo, n_ejemplos=6):
    """Muestra ejemplos de las imágenes después del preprocesamiento"""
    if len(imagenes) == 0:
        logger.warning(f"No hay imágenes para mostrar ejemplos: {titulo}")
        return
        
    logger.info(f"Mostrando ejemplos: {titulo}")
    
    # Seleccionar ejemplos aleatorios
    indices = np.random.choice(len(imagenes), min(n_ejemplos, len(imagenes)), replace=False)
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.ravel()
    
    for i, idx in enumerate(indices):
        img = imagenes[idx]
        etiqueta = etiquetas[idx]
        
        # Para visualización, desnormalizar si es necesario
        if img.min() >= 0 and img.max() <= 1:
            img_show = (img * 255).astype(np.uint8)
        else:
            img_show = img.astype(np.uint8)
        
        axes[i].imshow(img_show)
        axes[i].set_title(f'Etiqueta: {etiqueta}\nForma: {img.shape}')
        axes[i].axis('off')
    
    # Ocultar ejes vacíos
    for i in range(len(indices), 6):
        axes[i].axis('off')
    
    plt.tight_layout()
    plt.show()

def verificar_calidad_preprocesamiento_preprocesamiento(imagenes, etiquetas, nombre_conjunto):
    """Verifica la calidad del preprocesamiento"""
    logger.info(f"=== VERIFICACIÓN DE CALIDAD - {nombre_conjunto} ===")
    
    if len(imagenes) == 0:
        logger.warning("No hay imágenes para verificar")
        return False
    
    # Verificar forma individual
    expected_shape = TAMAÑO_IMAGEN + (3,)
    sample_shape = imagenes[0].shape
    
    if sample_shape != expected_shape:
        logger.error(f" Forma incorrecta: {sample_shape} vs esperado: {expected_shape}")
        return False
    
    # Verificar canales
    sample = imagenes[0]
    if len(sample.shape) == 3 and sample.shape[2] == 3:
        canal1 = sample[:,:,0]
        canal2 = sample[:,:,1]
        canal3 = sample[:,:,2]
        
        # Verificar si los canales son idénticos
        iguales_1_2 = np.array_equal(canal1, canal2)
        iguales_2_3 = np.array_equal(canal2, canal3)
        
        if iguales_1_2 and iguales_2_3:
            logger.error(" PROBLEMA CRÍTICO: Los 3 canales son IDÉNTICOS")
            logger.error("   Las imágenes tienen escala de grises repetida 3 veces")
            return False
        else:
            logger.info(" Canales correctos: RGB real con canales diferentes")
    
    # Verificar distribución de etiquetas
    etiquetas_array = np.array(etiquetas)
    conteo_etiquetas = {etiqueta: np.sum(etiquetas_array == etiqueta) for etiqueta in [0, 1]}
    logger.info(f"Distribución de etiquetas verificada: {conteo_etiquetas}")
    
    logger.info(" Preprocesamiento de calidad verificado")
    return True

def guardar_datos_preprocesados_preprocesamiento(X_entrenamiento, y_entrenamiento, X_prueba, y_prueba, prefijo="facturas"):
    """Guarda los datos preprocesados en archivos numpy en la carpeta train_data"""
    logger.info("Guardando datos preprocesados...")
    
    # Asegurar que la carpeta existe
    crear_carpetas_preprocesamiento()
    
    if len(X_entrenamiento) > 0:
        ruta_x_entrenamiento = os.path.join(CARPETA_SALIDA, f'{prefijo}_X_entrenamiento.npy')
        ruta_y_entrenamiento = os.path.join(CARPETA_SALIDA, f'{prefijo}_y_entrenamiento.npy')
        
        np.save(ruta_x_entrenamiento, X_entrenamiento)
        np.save(ruta_y_entrenamiento, y_entrenamiento)
        
        logger.info(f"Archivos guardados en {CARPETA_SALIDA}:")
        logger.info(f"  - {prefijo}_X_entrenamiento.npy: {X_entrenamiento.shape}")
        logger.info(f"  - {prefijo}_y_entrenamiento.npy: {y_entrenamiento.shape}")
    
    if len(X_prueba) > 0:
        ruta_x_prueba = os.path.join(CARPETA_SALIDA, f'{prefijo}_X_prueba.npy')
        ruta_y_prueba = os.path.join(CARPETA_SALIDA, f'{prefijo}_y_prueba.npy')
        
        np.save(ruta_x_prueba, X_prueba)
        np.save(ruta_y_prueba, y_prueba)
        
        logger.info(f"  - {prefijo}_X_prueba.npy: {X_prueba.shape}")
        logger.info(f"  - {prefijo}_y_prueba.npy: {y_prueba.shape}")
    
    # Guardar también el mapeo de etiquetas para referencia
    ruta_mapeo = os.path.join(CARPETA_SALIDA, f'{prefijo}_mapeo_etiquetas.npy')
    np.save(ruta_mapeo, MAPEO_ETIQUETAS)
    logger.info(f"  - {prefijo}_mapeo_etiquetas.npy: {MAPEO_ETIQUETAS}")

# ========== FUNCIÓN PRINCIPAL ==========
def ejecutar_preprocesamiento_completo():
    """Función principal que ejecuta todo el pipeline de preprocesamiento"""
    logger.info("=== INICIANDO PREPROCESAMIENTO DE FACTURAS ===")
    logger.info(f"Directorio raíz: {DIRECTORIO_RAIZ}")
    logger.info(f"Configuración: Tamaño {TAMAÑO_IMAGEN}, Canales: {CANALES}")
    logger.info(f"Etiquetas: {MAPEO_ETIQUETAS}")
    
    # Verificar estructura del proyecto
    if not verificar_estructura_proyecto_preprocesamiento():
        logger.error("Estructura del proyecto incorrecta. Verifica las carpetas.")
        return None, None, None, None
    
    # Crear carpetas necesarias
    crear_carpetas_preprocesamiento()
    
    # Verificar dependencias
    if not verificar_poppler_preprocesamiento():
        logger.warning("Poppler no está instalado. Solo se procesarán imágenes JPG/PNG.")
    
    # Preprocesar datos de entrenamiento
    X_entrenamiento, y_entrenamiento = preprocesar_conjunto_datos_preprocesamiento(
        CARPETA_ENTRENAMIENTO, "entrenamiento"
    )
    
    # Preprocesar datos de prueba
    X_prueba, y_prueba = preprocesar_conjunto_datos_preprocesamiento(
        CARPETA_PRUEBA, "prueba"
    )
    
    # VERIFICACIÓN DE CALIDAD CRÍTICA
    calidad_entrenamiento = True
    calidad_prueba = True
    
    if len(X_entrenamiento) > 0:
        calidad_entrenamiento = verificar_calidad_preprocesamiento_preprocesamiento(X_entrenamiento, y_entrenamiento, "ENTRENAMIENTO")
        mostrar_estadisticas_imagenes_preprocesamiento(X_entrenamiento, y_entrenamiento, "ENTRENAMIENTO")
        if calidad_entrenamiento:
            logger.info("=== DATOS DE ENTRENAMIENTO PROCESADOS CON EXITOSO ===")
            #mostrar_ejemplos_preprocesados_preprocesamiento(X_entrenamiento, y_entrenamiento, "EJEMPLOS DE ENTRENAMIENTO")
    
    if len(X_prueba) > 0:
        calidad_prueba = verificar_calidad_preprocesamiento_preprocesamiento(X_prueba, y_prueba, "PRUEBA")
        mostrar_estadisticas_imagenes_preprocesamiento(X_prueba, y_prueba, "PRUEBA")
        if calidad_prueba:
            logger.info("=== DATOS DE PRUEBA PROCESADOS CON EXITOSO ===")
            #mostrar_ejemplos_preprocesados_preprocesamiento(X_prueba, y_prueba, "EJEMPLOS DE PRUEBA")
    
    # Resumen final
    logger.info("=== RESUMEN FINAL DEL PREPROCESAMIENTO ===")
    logger.info(f"Datos de entrenamiento: {len(X_entrenamiento)} imágenes - Calidad: {'' if calidad_entrenamiento else ''}")
    logger.info(f"Datos de prueba: {len(X_prueba)} imágenes - Calidad: {'' if calidad_prueba else ''}")
    
    if len(X_entrenamiento) > 0:
        logger.info(f"  - Forma: {X_entrenamiento.shape}")
        etiquetas_array = np.array(y_entrenamiento)
        conteo_etiquetas = {etiqueta: np.sum(etiquetas_array == etiqueta) for etiqueta in [0, 1]}
        logger.info(f"  - Distribución entrenamiento: {conteo_etiquetas}")
    
    if len(X_prueba) > 0:
        logger.info(f"  - Forma: {X_prueba.shape}")
        etiquetas_array = np.array(y_prueba)
        conteo_etiquetas = {etiqueta: np.sum(etiquetas_array == etiqueta) for etiqueta in [0, 1]}
        logger.info(f"  - Distribución prueba: {conteo_etiquetas}")
    
    if not calidad_entrenamiento or not calidad_prueba:
        logger.error(" PROBLEMA DE CALIDAD DETECTADO - Revisa los logs anteriores")
    else:
        logger.info(" Preprocesamiento completado con CALIDAD VERIFICADA")
    
    return X_entrenamiento, y_entrenamiento, X_prueba, y_prueba

# ========== EJECUCIÓN PRINCIPAL ==========
if __name__ == "__main__":
    try:
        # Ejecutar preprocesamiento completo
        X_entrenamiento, y_entrenamiento, X_prueba, y_prueba = ejecutar_preprocesamiento_completo()
        
        # Guardar datos preprocesados
        if X_entrenamiento is not None and len(X_entrenamiento) > 0:
            guardar_datos_preprocesados_preprocesamiento(X_entrenamiento, y_entrenamiento, X_prueba, y_prueba)
        
        logger.info("🎉 Proceso de preprocesamiento completado exitosamente")
        
    except Exception as e:
        logger.error(f"Error durante la ejecución principal: {e}")
        raise