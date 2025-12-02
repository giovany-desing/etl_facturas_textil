# app/predict.py - Invoice Predictor
# Reciclado de utils/predecir_facturas.py
import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from datetime import datetime
import pandas as pd
import shutil

from app.config import settings
from app.utils import setup_logger
from app import preprocessing

logger = setup_logger(__name__)

# Directorio raíz del proyecto
DIRECTORIO_RAIZ = settings.BASE_DIR

# Carpetas de destino según predicción
CARPETA_CORR = os.path.join(DIRECTORIO_RAIZ, "corr")  # Para clase 0
CARPETA_PREV = os.path.join(DIRECTORIO_RAIZ, "prev")  # Para clase 1

# Variable global para el modelo
modelo = None

def cargar_modelo(ruta_modelo=None):
    """Carga el modelo desde la carpeta modelos/ en la raíz del proyecto"""
    global modelo
    
    carpeta_modelos = os.path.join(DIRECTORIO_RAIZ, "modelos")
    
    if not os.path.exists(carpeta_modelos):
        raise FileNotFoundError(f"No se encontró la carpeta {carpeta_modelos}")
    
    # Buscar el modelo más reciente o usar el final
    modelos_disponibles = [f for f in os.listdir(carpeta_modelos) if f.endswith('.h5')]
    
    if not modelos_disponibles:
        raise FileNotFoundError(f"No se encontraron modelos .h5 en la carpeta {carpeta_modelos}")
    
    logger.info(f" Modelos disponibles: {modelos_disponibles}")
    
    # Orden de preferencia para seleccionar modelo
    modelos_preferidos = [
        'modelo_facturas_final.h5',
        'mejor_modelo.h5',
        'modelo_entrenado.h5'
    ]
    
    if ruta_modelo is None:
        # Buscar por orden de preferencia
        for modelo_preferido in modelos_preferidos:
            if modelo_preferido in modelos_disponibles:
                ruta_modelo = os.path.join(carpeta_modelos, modelo_preferido)
                break
        
        # Si no encuentra ninguno preferido, usar el primero
        if ruta_modelo is None:
            ruta_modelo = os.path.join(carpeta_modelos, modelos_disponibles[0])
    
    logger.info(f"🔄 Cargando modelo desde: {ruta_modelo}")
    
    if not os.path.exists(ruta_modelo):
        raise FileNotFoundError(f"El modelo no existe en: {ruta_modelo}")
    
    try:
        modelo = keras.models.load_model(ruta_modelo)
        logger.info(" Modelo cargado exitosamente")
        return modelo
    except Exception as e:
        logger.error(f" Error cargando el modelo: {e}")
        raise

def inicializar_modelo():
    """Inicializa el modelo para uso en pipeline (sin lanzar excepciones)"""
    global modelo
    try:
        if modelo is None:
            modelo = cargar_modelo()
        return True
    except Exception as e:
        logger.error(f" Error inicializando modelo: {e}")
        return False

def verificar_estructura_proyecto():
    """Verifica que la estructura del proyecto sea correcta"""
    logger.info(" Verificando estructura del proyecto...")
    
    carpetas_requeridas = [
        os.path.join(DIRECTORIO_RAIZ, "modelos"),
        os.path.join(DIRECTORIO_RAIZ, "mes en curso")
    ]
    
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f" Carpeta encontrada: {carpeta}")
            archivos = os.listdir(carpeta)
            logger.info(f"    Contenido: {archivos}")
        else:
            logger.warning(f" Carpeta no encontrada: {carpeta}")
    
    return True

def crear_carpetas_destino():
    """Crea las carpetas de destino si no existen"""
    carpetas = [CARPETA_CORR, CARPETA_PREV]
    
    for carpeta in carpetas:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
            logger.info(f" Carpeta creada: {carpeta}")
        else:
            logger.info(f" Carpeta ya existe: {carpeta}")

def mover_archivo_segun_prediccion(ruta_origen, clase):
    """Mueve el archivo a la carpeta correspondiente según la predicción
    
    Args:
        ruta_origen: Ruta completa del archivo original
        clase: 0 para corr, 1 para prev
    
    Returns:
        ruta_destino: Ruta donde se movió el archivo o None si hubo error
    """
    try:
        nombre_archivo = os.path.basename(ruta_origen)
        
        # Determinar carpeta destino según la clase
        if clase == 0:
            carpeta_destino = CARPETA_CORR
            nombre_carpeta = "corr"
        else:  # clase == 1
            carpeta_destino = CARPETA_PREV
            nombre_carpeta = "prev"
        
        # Ruta completa de destino
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        
        # Si ya existe un archivo con el mismo nombre, agregar timestamp
        if os.path.exists(ruta_destino):
            nombre_base, extension = os.path.splitext(nombre_archivo)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo_nuevo = f"{nombre_base}_{timestamp}{extension}"
            ruta_destino = os.path.join(carpeta_destino, nombre_archivo_nuevo)
            logger.warning(f" Archivo duplicado, renombrando a: {nombre_archivo_nuevo}")
        
        # Mover el archivo
        shutil.move(ruta_origen, ruta_destino)
        logger.info(f" Archivo movido a '{nombre_carpeta}': {nombre_archivo}")
        
        return ruta_destino
        
    except Exception as e:
        logger.error(f" Error moviendo archivo {os.path.basename(ruta_origen)}: {e}")
        return None

def predecir_archivo(ruta_archivo):
    """Hace predicción para un archivo individual usando las funciones del preprocessing"""
    global modelo
    
    # Cargar modelo si no está cargado
    if modelo is None:
        if not inicializar_modelo():
            return None, None
    
    logger.info(f" Procesando: {os.path.basename(ruta_archivo)}")
    
    try:
        # Usar la función extraer_caracteristicas_imagen_preprocesamiento
        imagen_preprocesada = preprocessing.extraer_caracteristicas_imagen_preprocesamiento(ruta_archivo)
        
        if imagen_preprocesada is None:
            logger.error(f" No se pudo preprocesar el archivo: {os.path.basename(ruta_archivo)}")
            return None, None
        
        # Verificar que la forma sea correcta
        if imagen_preprocesada.shape != (224, 224, 3):
            logger.error(f" Forma incorrecta después del preprocesamiento: {imagen_preprocesada.shape}")
            return None, None
        
        # Hacer predicción
        logger.debug("🤖 Realizando predicción...")
        prediccion = modelo.predict(np.array([imagen_preprocesada]), verbose=0)
        probabilidad = float(prediccion[0][0])
        clase = 1 if probabilidad > 0.5 else 0
        
        logger.info(f" Predicción completada - Clase: {clase}, Probabilidad: {probabilidad:.4f}")
        return clase, probabilidad
        
    except Exception as e:
        logger.error(f" Error procesando {os.path.basename(ruta_archivo)}: {e}")
        return None, None


def buscar_archivos_facturas(carpeta_facturas=None):
    """Busca todos los archivos de facturas en una carpeta"""
    if carpeta_facturas is None:
        carpeta_facturas = os.path.join(DIRECTORIO_RAIZ, "mes en curso")
    
    if not os.path.exists(carpeta_facturas):
        logger.error(f" No se encontró la carpeta: {carpeta_facturas}")
        return []
    
    # Buscar archivos PDF e imágenes (usando las mismas extensiones que el preprocessing)
    archivos = []
    extensiones_permitidas = ['.pdf', '.jpg', '.jpeg', '.png']
    
    for ext in extensiones_permitidas:
        archivos.extend([f for f in os.listdir(carpeta_facturas) if f.lower().endswith(ext)])
    
    logger.info(f" Encontrados {len(archivos)} archivos en {carpeta_facturas}")
    return archivos

####################

# ========== FUNCIONES PARA PIPELINE ==========


def predecir():
    """
    Función principal - Clasificación uno por uno con logging y movimiento de archivos
    Retorna un diccionario con información de clasificación para cada archivo
    
    Returns:
        dict: {
            'archivos_correctivos': [lista de nombres de archivos],
            'archivos_preventivos': [lista de nombres de archivos],
            'archivos_procesados': [lista de todos los archivos procesados]
        }
    """
    logger.info(" CLASIFICADOR DE FACTURAS - RED NEURONAL")
    logger.info("="*50)
    
    resultado_clasificacion = {
        'archivos_correctivos': [],
        'archivos_preventivos': [],
        'archivos_procesados': []
    }
    
    try:
        # Verificar estructura del proyecto
        verificar_estructura_proyecto()
        
        # Crear carpetas de destino
        crear_carpetas_destino()
        
        # Cargar modelo primero
        if not inicializar_modelo():
            logger.error(" No se pudo cargar el modelo")
            return resultado_clasificacion
        
        # Definir carpeta de facturas
        carpeta_facturas = os.path.join(DIRECTORIO_RAIZ, "mes en curso")
        
        if not os.path.exists(carpeta_facturas):
            logger.error(f" No se encontró la carpeta '{carpeta_facturas}'")
            logger.info("💡 Por favor, crea la carpeta 'mes en curso' en la raíz del proyecto")
            logger.info("   y coloca allí las facturas a clasificar (PDF/JPG/PNG)")
            return resultado_clasificacion
        
        # Buscar archivos
        logger.info(f" Buscando facturas en: {carpeta_facturas}/")
        archivos = buscar_archivos_facturas(carpeta_facturas)
        
        if not archivos:
            logger.warning(f" No se encontraron archivos en: {carpeta_facturas}")
            return resultado_clasificacion
        
        logger.info(f" Total de archivos encontrados: {len(archivos)}")
        logger.info("="*70)
        logger.info(" INICIANDO PREDICCIONES UNO POR UNO")
        logger.info("="*70)
        
        # Procesar uno por uno
        resultados = []
        conectar_0_count = 0
        conectar_1_count = 0
        movidos_exitosamente = 0
        errores_movimiento = 0
        
        for i, archivo in enumerate(archivos, 1):
            ruta_completa = os.path.join(carpeta_facturas, archivo)
            
            logger.info(f"\n[{i}/{len(archivos)}] Procesando: {archivo}")
            
            # Predecir archivo
            clase, probabilidad = predecir_archivo(ruta_completa)
            
            if clase is not None:
                # Log según la clase
                if clase == 0:
                    logger.info(f" CONECTAR A 0 (CORRECTIVA) - {archivo} (Probabilidad: {probabilidad:.4f})")
                    conectar_0_count += 1
                    resultado_clasificacion['archivos_correctivos'].append(archivo)
                else:  # clase == 1
                    logger.info(f" CONECTAR A 1 (PREVENTIVA) - {archivo} (Probabilidad: {probabilidad:.4f})")
                    conectar_1_count += 1
                    resultado_clasificacion['archivos_preventivos'].append(archivo)
                
                # Agregar a archivos procesados
                resultado_clasificacion['archivos_procesados'].append(archivo)
                
                # Mover archivo a la carpeta correspondiente
                ruta_destino = mover_archivo_segun_prediccion(ruta_completa, clase)
                
                if ruta_destino:
                    movidos_exitosamente += 1
                else:
                    errores_movimiento += 1
                
                # Guardar resultado
                confianza = probabilidad if clase == 1 else 1 - probabilidad
                resultado = {
                    'archivo': archivo,
                    'clase': clase,
                    'probabilidad': probabilidad,
                    'confianza': confianza,
                    'carpeta_destino': 'corr' if clase == 0 else 'prev',
                    'movido_exitosamente': ruta_destino is not None
                }
                resultados.append(resultado)
            else:
                logger.error(f" No se pudo procesar: {archivo}")
        
        # Resumen final
        logger.info("\n" + "="*70)
        logger.info(" RESUMEN FINAL DE PREDICCIONES Y MOVIMIENTOS")
        logger.info("="*70)
        logger.info(f" Total procesados: {len(resultados)}/{len(archivos)}")
        logger.info(f" CONECTAR A 0 (CORRECTIVA - carpeta 'corr'): {conectar_0_count} archivos")
        logger.info(f" CONECTAR A 1 (PREVENTIVA - carpeta 'prev'): {conectar_1_count} archivos")
        logger.info(f" Archivos movidos exitosamente: {movidos_exitosamente}")
        
        if errores_movimiento > 0:
            logger.warning(f" Errores al mover archivos: {errores_movimiento}")
        
        if len(resultados) > 0:
            porcentaje_0 = (conectar_0_count / len(resultados)) * 100
            porcentaje_1 = (conectar_1_count / len(resultados)) * 100
            logger.info(f" Distribución: {porcentaje_0:.1f}% correctivas, {porcentaje_1:.1f}% preventivas")
        
        logger.info("="*70)
        logger.info("🎉 ¡Clasificación completada!")
        logger.info(f" Archivos clase 0 (correctivos) en: {CARPETA_CORR}")
        logger.info(f" Archivos clase 1 (preventivos) en: {CARPETA_PREV}")
        
    except Exception as e:
        logger.error(f" Error durante la clasificación: {e}", exc_info=True)
    
    return resultado_clasificacion

if __name__ == "__main__":
    # Verificar argumentos de línea de comandos
        predecir()