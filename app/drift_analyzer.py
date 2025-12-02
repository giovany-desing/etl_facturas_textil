"""
Módulo de análisis de Data Drift para facturas

ROL: Contiene toda la lógica de ciencia de datos para detectar drift en distribuciones de imágenes.
     - Extracción de características de imágenes
     - Procesamiento de carpetas
     - Comparación estadística con baseline
"""
import os
import numpy as np
from scipy import stats
import cv2
from pdf2image import convert_from_path

from app.utils import setup_logger

logger = setup_logger(__name__)


def extraer_caracteristicas_imagen(ruta_imagen):
    """
    Extrae características estadísticas de una imagen
    
    Args:
        ruta_imagen: Ruta al archivo de imagen (PDF, JPG, PNG)
        
    Returns:
        dict: Diccionario con características estadísticas o None si hay error
    """
    try:
        # Leer imagen
        if ruta_imagen.endswith('.pdf'):
            images = convert_from_path(ruta_imagen, dpi=150)
            if not images:
                return None
            img = np.array(images[0])
        else:
            img = cv2.imread(ruta_imagen)
            if img is None:
                return None
        
        # Convertir a RGB si es necesario
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Redimensionar a tamaño estándar para comparación
        img_resized = cv2.resize(img, (224, 224))
        
        # Normalizar
        img_normalized = img_resized.astype(np.float32) / 255.0
        
        # Extraer características estadísticas
        caracteristicas = {
            'mean': np.mean(img_normalized),
            'std': np.std(img_normalized),
            'min': np.min(img_normalized),
            'max': np.max(img_normalized),
            'median': np.median(img_normalized),
            'mean_r': np.mean(img_normalized[:, :, 0]) if len(img_normalized.shape) == 3 else np.mean(img_normalized),
            'mean_g': np.mean(img_normalized[:, :, 1]) if len(img_normalized.shape) == 3 else np.mean(img_normalized),
            'mean_b': np.mean(img_normalized[:, :, 2]) if len(img_normalized.shape) == 3 else np.mean(img_normalized),
        }
        
        return caracteristicas
        
    except Exception as e:
        logger.debug(f"Error extrayendo características de {ruta_imagen}: {e}")
        return None


def procesar_carpeta_para_drift(ruta_carpeta):
    """
    Procesa una carpeta de facturas y extrae características
    
    Args:
        ruta_carpeta: Ruta a la carpeta con facturas
        
    Returns:
        list: Lista de diccionarios con características de cada factura
    """
    caracteristicas_lista = []
    extensiones_validas = ['.pdf', '.jpg', '.jpeg', '.png']
    
    if not os.path.exists(ruta_carpeta):
        logger.warning(f"Carpeta no existe: {ruta_carpeta}")
        return caracteristicas_lista
    
    # Recorrer archivos recursivamente
    for root, dirs, files in os.walk(ruta_carpeta):
        for archivo in files:
            _, ext = os.path.splitext(archivo)
            if ext.lower() in extensiones_validas:
                ruta_completa = os.path.join(root, archivo)
                try:
                    caracteristicas = extraer_caracteristicas_imagen(ruta_completa)
                    if caracteristicas:
                        caracteristicas_lista.append(caracteristicas)
                except Exception as e:
                    logger.debug(f"Error procesando {archivo}: {e}")
                    continue
    
    return caracteristicas_lista


def detectar_drift(
    rutas_datos,
    ruta_baseline,
    umbral_p_value=0.05,
    umbral_statistic=0.3,
    caracteristicas_claves=None
):
    """
    Detecta drift comparando distribuciones de características con baseline
    
    Args:
        rutas_datos: Dict con rutas de carpetas {tipo: ruta}
        ruta_baseline: Ruta al archivo .npy con baseline
        umbral_p_value: Umbral de significancia estadística (default: 0.05)
        umbral_statistic: Umbral de diferencia en distribución (default: 0.3)
        caracteristicas_claves: Lista de características a comparar (default: ['mean', 'std', 'mean_r', 'mean_g', 'mean_b'])
        
    Returns:
        tuple: (drift_detectado: bool, resultados_drift: dict, todas_caracteristicas: dict)
    """
    if caracteristicas_claves is None:
        caracteristicas_claves = ['mean', 'std', 'mean_r', 'mean_g', 'mean_b']
    
    # Procesar carpetas y extraer características
    todas_caracteristicas = {}
    
    for carpeta_nombre, ruta in rutas_datos.items():
        if ruta and os.path.exists(ruta):
            logger.info(f"📊 Procesando características de: {carpeta_nombre}")
            caracteristicas = procesar_carpeta_para_drift(ruta)
            todas_caracteristicas[carpeta_nombre] = caracteristicas
            logger.info(f"   ✅ {len(caracteristicas)} facturas procesadas")
        else:
            logger.warning(f"⚠️ Carpeta {carpeta_nombre} no disponible")
    
    if not todas_caracteristicas:
        raise Exception("No se pudieron extraer características de ninguna carpeta")
    
    drift_detectado = False
    resultados_drift = {}
    
    # Si existe baseline, comparar
    if os.path.exists(ruta_baseline):
        logger.info("📊 Comparando con datos de referencia (baseline)")
        baseline_caracteristicas = np.load(ruta_baseline, allow_pickle=True).item()
        
        # Comparar cada tipo de factura
        for tipo_factura, caracteristicas_actuales in todas_caracteristicas.items():
            if tipo_factura not in baseline_caracteristicas:
                logger.warning(f"⚠️ No hay baseline para {tipo_factura}")
                continue
            
            baseline = baseline_caracteristicas[tipo_factura]
            
            if len(caracteristicas_actuales) == 0 or len(baseline) == 0:
                logger.warning(f"⚠️ Datos insuficientes para comparar {tipo_factura}")
                continue
            
            drift_en_tipo = False
            comparaciones = {}
            
            for clave in caracteristicas_claves:
                valores_actuales = [c[clave] for c in caracteristicas_actuales if clave in c]
                valores_baseline = [c[clave] for c in baseline if clave in c]
                
                if len(valores_actuales) < 10 or len(valores_baseline) < 10:
                    continue
                
                # Prueba estadística: Kolmogorov-Smirnov
                try:
                    statistic, p_value = stats.ks_2samp(valores_actuales, valores_baseline)
                    
                    es_diferente = p_value < umbral_p_value and statistic > umbral_statistic
                    
                    comparaciones[clave] = {
                        'statistic': float(statistic),
                        'p_value': float(p_value),
                        'drift': es_diferente
                    }
                    
                    if es_diferente:
                        drift_en_tipo = True
                        logger.warning(
                            f"   ⚠️ DRIFT detectado en {tipo_factura}.{clave}: "
                            f"statistic={statistic:.3f}, p={p_value:.4f}"
                        )
                    
                except Exception as e:
                    logger.debug(f"Error en comparación estadística para {clave}: {e}")
                    continue
            
            resultados_drift[tipo_factura] = {
                'drift_detectado': drift_en_tipo,
                'comparaciones': comparaciones,
                'n_actuales': len(caracteristicas_actuales),
                'n_baseline': len(baseline)
            }
            
            if drift_en_tipo:
                drift_detectado = True
                logger.warning(f"⚠️ DRIFT DETECTADO en {tipo_factura}")
            else:
                logger.info(f"✅ No se detectó drift en {tipo_factura}")
    
    else:
        # Si no hay baseline, guardar características actuales como nuevo baseline
        logger.info("📝 No se encontró baseline. Guardando características actuales como nuevo baseline")
        os.makedirs(os.path.dirname(ruta_baseline), exist_ok=True)
        np.save(ruta_baseline, todas_caracteristicas)
        logger.info(f"✅ Baseline guardado en: {ruta_baseline}")
        drift_detectado = False  # Sin baseline, no podemos detectar drift
    
    return drift_detectado, resultados_drift, todas_caracteristicas


def run_drift_detection(rutas_datos, ruta_baseline, umbral_p_value, umbral_statistic):
    """
    Función principal para ejecutar detección de drift
    Wrapper que llama a detectar_drift con los parámetros correctos
    
    Args:
        rutas_datos: Dict con rutas de carpetas {tipo: ruta}
        ruta_baseline: Ruta al archivo .npy con baseline
        umbral_p_value: Umbral de significancia estadística
        umbral_statistic: Umbral de diferencia en distribución
        
    Returns:
        tuple: (drift_detectado: bool, resultados_drift: dict)
    """
    drift_detectado, resultados_drift, _ = detectar_drift(
        rutas_datos=rutas_datos,
        ruta_baseline=ruta_baseline,
        umbral_p_value=umbral_p_value,
        umbral_statistic=umbral_statistic
    )
    
    return drift_detectado, resultados_drift


