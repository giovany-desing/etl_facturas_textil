"""
FastAPI Main Application
Unifica api_procesar_facturas.py y api_train_pipeline.py
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Tuple
from datetime import datetime
import os
import subprocess

from app.config import settings
from app.utils import setup_logger
from app import drive, preprocessing, model, predict, ocr, database
from app import s3_utils
import shutil

logger = setup_logger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API unificada para ETL y entrenamiento de facturas",
    version=settings.VERSION
)

# ========== ESTADOS GLOBALES ==========

processing_status = {
    "estado": "inactivo",
    "etapa_actual": None,
    "progreso": 0,
    "mensaje": None,
    "inicio": None,
    "fin": None,
    "error": None
}

training_status = {
    "estado": "inactivo",
    "etapa_actual": None,
    "progreso": 0,
    "mensaje": None,
    "inicio": None,
    "fin": None,
    "error": None
}


# ========== MODELOS PYDANTIC ==========

class ProcessingStatus(BaseModel):
    estado: str
    etapa_actual: Optional[str] = None
    progreso: int
    mensaje: Optional[str] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    error: Optional[str] = None


class ProcessingResponse(BaseModel):
    mensaje: str
    estado: str


# ========== FUNCIONES DE LIMPIEZA ==========

def limpiar_carpeta_temporal(ruta_carpeta: str, nombre_carpeta: str = None) -> bool:
    """
    Elimina una carpeta temporal si existe
    
    Args:
        ruta_carpeta: Ruta completa a la carpeta a eliminar
        nombre_carpeta: Nombre de la carpeta para logging (opcional)
    
    Returns:
        bool: True si se eliminó exitosamente o no existía, False si hubo error
    """
    nombre = nombre_carpeta or os.path.basename(ruta_carpeta)
    
    try:
        if os.path.exists(ruta_carpeta):
            if os.path.isdir(ruta_carpeta):
                shutil.rmtree(ruta_carpeta)
                logger.info(f"✅ Carpeta temporal eliminada: {nombre}")
                return True
            else:
                logger.warning(f"⚠️  La ruta existe pero no es una carpeta: {ruta_carpeta}")
                return False
        else:
            logger.debug(f"📁 Carpeta no existe (ya fue limpiada): {nombre}")
            return True
    except Exception as e:
        logger.error(f"❌ Error al eliminar carpeta {nombre}: {str(e)}")
        return False


def limpiar_carpetas_entrenamiento():
    """
    Limpia todas las carpetas temporales usadas en el entrenamiento:
    - invoices_test
    - invoices_train
    - train_data
    """
    logger.info("🧹 Limpiando carpetas temporales de entrenamiento...")
    
    carpetas_a_limpiar = [
        os.path.join(settings.BASE_DIR, "invoices_test"),
        os.path.join(settings.BASE_DIR, "invoices_train"),
        os.path.join(settings.BASE_DIR, "train_data"),
    ]
    
    for carpeta in carpetas_a_limpiar:
        limpiar_carpeta_temporal(carpeta)
    
    logger.info("✅ Limpieza de carpetas de entrenamiento completada")


def limpiar_carpetas_procesamiento():
    """
    Limpia todas las carpetas temporales usadas en el procesamiento:
    - prev
    - corr
    - 'mes en curso'
    """
    logger.info("🧹 Limpiando carpetas temporales de procesamiento...")
    
    carpetas_a_limpiar = [
        os.path.join(settings.BASE_DIR, "prev"),
        os.path.join(settings.BASE_DIR, "corr"),
        os.path.join(settings.BASE_DIR, "mes en curso"),
    ]
    
    for carpeta in carpetas_a_limpiar:
        limpiar_carpeta_temporal(carpeta)
    
    logger.info("✅ Limpieza de carpetas de procesamiento completada")


def limpiar_carpeta_bentoml():
    """
    Limpia la carpeta bentoml si existe (no se usa en el proyecto)
    """
    carpeta_bentoml = os.path.join(settings.BASE_DIR, "bentoml")
    if os.path.exists(carpeta_bentoml):
        logger.info("🧹 Eliminando carpeta bentoml (no se usa en el proyecto)...")
        limpiar_carpeta_temporal(carpeta_bentoml, "bentoml")


# ========== FUNCIONES DE VERIFICACIÓN PREVIA ==========

def verificar_conexion_drive() -> Tuple[bool, str]:
    """
    Verifica la conexión a Google Drive
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    try:
        logger.info("🔍 Verificando conexión a Google Drive...")
        drive_service = drive.autenticar_drive()
        # Intentar obtener información del usuario para verificar conexión
        about = drive_service.about().get(fields="user").execute()
        user_email = about.get('user', {}).get('emailAddress', 'Desconocido')
        logger.info(f"✅ Conexión a Google Drive exitosa. Usuario: {user_email}")
        return True, f"Conexión exitosa. Usuario: {user_email}"
    except Exception as e:
        error_msg = f"Error al conectar con Google Drive: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verificar_conexion_mysql() -> Tuple[bool, str]:
    """
    Verifica la conexión a MySQL
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    try:
        logger.info("🔍 Verificando conexión a MySQL...")
        from sqlalchemy import text
        db = database.get_db()
        # Ejecutar query simple para verificar conexión
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("✅ Conexión a MySQL exitosa")
        return True, "Conexión exitosa"
    except Exception as e:
        error_msg = f"Error al conectar con MySQL: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verificar_conexion_s3() -> Tuple[bool, str]:
    """
    Verifica la conexión a AWS S3
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    try:
        logger.info("🔍 Verificando conexión a AWS S3...")
        from app import s3_utils
        
        # Intentar obtener cliente S3
        s3_client = s3_utils.obtener_cliente_s3()
        
        if s3_client is None:
            error_msg = "No se pudo crear cliente S3. Verifica las credenciales de AWS."
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        # Intentar listar el bucket para verificar conexión
        try:
            bucket_name = settings.S3_BUCKET_NAME
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"✅ Conexión a S3 exitosa. Bucket: {bucket_name}")
            return True, f"Conexión exitosa. Bucket: {bucket_name}"
        except Exception as e:
            error_msg = f"Error al acceder al bucket S3 '{bucket_name}': {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error al verificar conexión con S3: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verificar_modelo_h5() -> Tuple[bool, str, Optional[str]]:
    """
    Verifica si existe un modelo .h5 en la carpeta modelos/
    
    Returns:
        tuple[bool, str, Optional[str]]: (existe, mensaje, ruta_modelo)
    """
    try:
        logger.info("🔍 Verificando existencia de modelo .h5...")
        carpeta_modelos = os.path.join(settings.BASE_DIR, settings.MODELS_DIR)
        
        if not os.path.exists(carpeta_modelos):
            error_msg = f"No se encontró la carpeta {carpeta_modelos}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg, None
        
        # Buscar modelos .h5
        modelos_disponibles = [f for f in os.listdir(carpeta_modelos) if f.endswith('.h5')]
        
        if not modelos_disponibles:
            error_msg = f"No se encontraron modelos .h5 en {carpeta_modelos}"
            logger.warning(f"⚠️  {error_msg}")
            return False, error_msg, None
        
        # Orden de preferencia
        modelos_preferidos = [
            'modelo_facturas_final.h5',
            'mejor_modelo.h5',
            'modelo_entrenado.h5'
        ]
        
        ruta_modelo = None
        for modelo_preferido in modelos_preferidos:
            if modelo_preferido in modelos_disponibles:
                ruta_modelo = os.path.join(carpeta_modelos, modelo_preferido)
                break
        
        if ruta_modelo is None:
            ruta_modelo = os.path.join(carpeta_modelos, modelos_disponibles[0])
        
        logger.info(f"✅ Modelo encontrado: {os.path.basename(ruta_modelo)}")
        return True, f"Modelo encontrado: {os.path.basename(ruta_modelo)}", ruta_modelo
        
    except Exception as e:
        error_msg = f"Error al verificar modelo: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg, None


def descargar_modelo_dvc() -> Tuple[bool, str]:
    """
    Descarga el modelo desde S3 usando DVC pull
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    try:
        logger.info("📥 Descargando modelo desde S3 con DVC pull...")
        
        # Verificar que DVC está instalado
        try:
            subprocess.run(['dvc', '--version'], check=True, capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            error_msg = "DVC no está instalado o no está disponible"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        carpeta_modelos = os.path.join(settings.BASE_DIR, settings.MODELS_DIR)
        
        # Buscar archivos .dvc de modelos .h5
        archivos_dvc = []
        
        # Buscar en la carpeta modelos
        if os.path.exists(carpeta_modelos):
            archivos_dvc = [f for f in os.listdir(carpeta_modelos) if f.endswith('.dvc')]
            # Filtrar solo archivos .dvc de modelos .h5
            modelos_dvc = [f for f in archivos_dvc if f.replace('.dvc', '').endswith('.h5')]
            if modelos_dvc:
                archivos_dvc = modelos_dvc
        
        # Si no hay en modelos/, buscar en la raíz del proyecto
        if not archivos_dvc:
            if os.path.exists(settings.BASE_DIR):
                archivos_dvc = [f for f in os.listdir(settings.BASE_DIR) if f.endswith('.dvc')]
                modelos_dvc = [f for f in archivos_dvc if f.replace('.dvc', '').endswith('.h5')]
                if modelos_dvc:
                    archivos_dvc = modelos_dvc
        
        # Verificar que hay un remote configurado antes de hacer pull
        logger.info("Verificando configuración de remote de DVC...")
        resultado_remote = subprocess.run(
            ['dvc', 'remote', 'list'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if resultado_remote.returncode != 0 or not resultado_remote.stdout.strip():
            error_msg = "No hay remotes configurados en DVC. Configura un remote de S3 antes de hacer pull."
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        logger.info(f"Remotes disponibles: {resultado_remote.stdout.strip()}")
        
        if not archivos_dvc:
            # Si no hay archivos .dvc específicos, intentar dvc pull general (descarga todo)
            logger.warning("⚠️  No se encontraron archivos .dvc específicos de modelos. Intentando dvc pull general...")
            resultado = subprocess.run(
                ['dvc', 'pull'],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos timeout para descarga completa
            )
        else:
            # Ejecutar dvc pull del modelo específico
            # Priorizar modelo_facturas_final.h5
            modelo_preferido = None
            for archivo in archivos_dvc:
                if 'modelo_facturas_final' in archivo:
                    modelo_preferido = archivo
                    break
            
            archivo_dvc = modelo_preferido if modelo_preferido else archivos_dvc[0]
            logger.info(f"Ejecutando: dvc pull {archivo_dvc}")
            resultado = subprocess.run(
                ['dvc', 'pull', archivo_dvc],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos timeout
            )
        
        if resultado.returncode == 0:
            logger.info("✅ Modelo descargado exitosamente desde S3 con DVC")
            return True, "Modelo descargado exitosamente desde S3"
        else:
            error_msg = f"Error al ejecutar dvc pull: {resultado.stderr}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        error_msg = "Timeout al ejecutar dvc pull (más de 10 minutos)"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Error inesperado al descargar modelo con DVC: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def subir_modelo_dvc(ruta_modelo: str) -> Tuple[bool, str]:
    """
    Sube el modelo a S3 usando DVC add y dvc push
    
    Args:
        ruta_modelo: Ruta completa al archivo del modelo .h5
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    try:
        logger.info(f"📤 Subiendo modelo a S3 con DVC: {ruta_modelo}")
        
        # Verificar que DVC está instalado
        try:
            subprocess.run(['dvc', '--version'], check=True, capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            error_msg = "DVC no está instalado o no está disponible"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        # Verificar que el archivo existe
        if not os.path.exists(ruta_modelo):
            error_msg = f"El archivo del modelo no existe: {ruta_modelo}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        # Obtener nombre del archivo y ruta relativa del modelo desde la raíz del proyecto
        nombre_archivo = os.path.basename(ruta_modelo)
        ruta_relativa_modelo = os.path.relpath(ruta_modelo, settings.BASE_DIR)
        
        # Ejecutar dvc add desde la raíz del proyecto
        logger.info(f"Ejecutando: dvc add {ruta_relativa_modelo} (desde {settings.BASE_DIR})")
        resultado_add = subprocess.run(
            ['dvc', 'add', ruta_relativa_modelo],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos timeout
        )
        
        if resultado_add.returncode != 0:
            error_msg = f"Error al ejecutar dvc add: {resultado_add.stderr}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        logger.info("✅ dvc add ejecutado exitosamente")
        
        # Verificar que hay un remote configurado antes de hacer push
        logger.info("Verificando configuración de remote de DVC...")
        resultado_remote = subprocess.run(
            ['dvc', 'remote', 'list'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if resultado_remote.returncode != 0 or not resultado_remote.stdout.strip():
            error_msg = "No hay remotes configurados en DVC. Configura un remote de S3 antes de hacer push."
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        logger.info(f"Remotes disponibles: {resultado_remote.stdout.strip()}")
        
        # Ejecutar dvc push para subir a S3
        logger.info("Ejecutando: dvc push")
        resultado_push = subprocess.run(
            ['dvc', 'push'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos timeout para subida a S3
        )
        
        if resultado_push.returncode == 0:
            logger.info("✅ Modelo subido exitosamente a S3 con DVC")
            return True, f"Modelo {nombre_archivo} subido exitosamente a S3"
        else:
            error_msg = f"Error al ejecutar dvc push: {resultado_push.stderr}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        error_msg = "Timeout al ejecutar dvc push (más de 10 minutos)"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Error inesperado al subir modelo con DVC: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def verificar_prerequisitos_entrenamiento() -> Tuple[bool, str]:
    """
    Verifica todos los prerrequisitos antes de ejecutar el entrenamiento:
    1. Conexión a Google Drive
    2. Conexión a MySQL
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN DE PRERREQUISITOS PARA ENTRENAMIENTO")
    logger.info("=" * 60)
    
    # 1. Verificar Google Drive
    drive_ok, drive_msg = verificar_conexion_drive()
    if not drive_ok:
        return False, f"Fallo en verificación de Google Drive: {drive_msg}"
    
    # 2. Verificar MySQL
    mysql_ok, mysql_msg = verificar_conexion_mysql()
    if not mysql_ok:
        return False, f"Fallo en verificación de MySQL: {mysql_msg}"
    
    logger.info("✅ Todos los prerrequisitos para entrenamiento verificados exitosamente")
    return True, "Prerrequisitos verificados exitosamente"


def verificar_prerequisitos_etl() -> Tuple[bool, str]:
    """
    Verifica todos los prerrequisitos antes de ejecutar el ETL:
    1. Conexión a Google Drive
    2. Conexión a MySQL
    3. Conexión a S3
    4. Existencia del modelo .h5 (si no existe, intenta descargarlo con DVC)
    
    Returns:
        tuple[bool, str]: (éxito, mensaje)
    """
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN DE PRERREQUISITOS PARA ETL")
    logger.info("=" * 60)
    
    # 1. Verificar Google Drive
    drive_ok, drive_msg = verificar_conexion_drive()
    if not drive_ok:
        return False, f"Fallo en verificación de Google Drive: {drive_msg}"
    
    # 2. Verificar MySQL
    mysql_ok, mysql_msg = verificar_conexion_mysql()
    if not mysql_ok:
        return False, f"Fallo en verificación de MySQL: {mysql_msg}"
    
    # 3. Verificar S3
    s3_ok, s3_msg = verificar_conexion_s3()
    if not s3_ok:
        return False, f"Fallo en verificación de S3: {s3_msg}"
    
    # 4. Verificar modelo .h5
    modelo_ok, modelo_msg, ruta_modelo = verificar_modelo_h5()
    
    if not modelo_ok:
        logger.warning("⚠️  Modelo .h5 no encontrado. Intentando descargar con DVC...")
        dvc_ok, dvc_msg = descargar_modelo_dvc()
        
        if not dvc_ok:
            return False, f"Fallo al descargar modelo: {dvc_msg}"
        
        # Verificar nuevamente después de DVC pull
        modelo_ok, modelo_msg, ruta_modelo = verificar_modelo_h5()
        if not modelo_ok:
            return False, f"Modelo no disponible después de DVC pull: {modelo_msg}"
    
    logger.info("=" * 60)
    logger.info("✅ TODOS LOS PRERREQUISITOS VERIFICADOS EXITOSAMENTE")
    logger.info("=" * 60)
    
    return True, "Todos los prerrequisitos verificados exitosamente"


# ========== FUNCIONES DE PIPELINE ETL ==========

def ejecutar_procesamiento_completo():
    """Pipeline completo de procesamiento de facturas"""
    global processing_status

    try:
        processing_status.update({
            "estado": "ejecutando",
            "etapa_actual": "verificando_prerrequisitos",
            "progreso": 0,
            "mensaje": "Verificando prerrequisitos (Drive, MySQL, Modelo)",
            "inicio": datetime.now().isoformat(),
            "fin": None,
            "error": None
        })
        logger.info("Pipeline de procesamiento iniciado")
        
        # VERIFICACIÓN DE PRERREQUISITOS (OBLIGATORIO)
        processing_status.update({
            "etapa_actual": "verificando_prerrequisitos",
            "progreso": 5,
            "mensaje": "Verificando conexión a Google Drive, MySQL y modelo .h5"
        })
        
        prerequisitos_ok, prerequisitos_msg = verificar_prerequisitos_etl()
        
        if not prerequisitos_ok:
            error_msg = f"Fallo en verificación de prerrequisitos: {prerequisitos_msg}"
            logger.error(error_msg)
            processing_status.update({
                "estado": "error",
                "etapa_actual": "verificando_prerrequisitos",
                "mensaje": "Error en verificación de prerrequisitos",
                "error": error_msg,
                "fin": datetime.now().isoformat()
            })
            return
        
        logger.info("✅ Prerrequisitos verificados. Iniciando procesamiento...")
        
        # Limpiar carpeta bentoml si existe (no se usa)
        limpiar_carpeta_bentoml()
        
        processing_status.update({
            "etapa_actual": "iniciando",
            "progreso": 10,
            "mensaje": "Prerrequisitos verificados. Iniciando procesamiento"
        })

        # FASE 1: Descarga desde S3
        processing_status.update({
            "etapa_actual": "descarga_s3",
            "progreso": 10,
            "mensaje": "Descargando facturas desde S3 (bucket, carpeta 'mes en curso')"
        })
        carpeta_local = os.path.join(settings.BASE_DIR, "mes en curso")
        os.makedirs(carpeta_local, exist_ok=True)
        
        exito_descarga, archivos_descargados = s3_utils.descargar_carpeta_s3(
            carpeta_s3=settings.S3_PREFIX_FACTURAS if settings.S3_PREFIX_FACTURAS else None,
            ruta_local=carpeta_local
        )
        
        if not exito_descarga or not archivos_descargados:
            error_msg = "No se pudieron descargar archivos desde S3 o no hay archivos para procesar"
            logger.error(f"❌ {error_msg}")
            processing_status.update({
                "estado": "error",
                "mensaje": error_msg,
                "error": error_msg,
                "fin": datetime.now().isoformat()
            })
            return
        
        logger.info(f"✅ {len(archivos_descargados)} archivos descargados desde S3")
        processing_status["progreso"] = 15

        # FASE 2: Predicción de facturas (clasificación)
        processing_status.update({
            "etapa_actual": "prediccion",
            "progreso": 20,
            "mensaje": "Clasificando facturas con el modelo (correctivas/preventivas)"
        })
        resultado_clasificacion = predict.predecir()
        processing_status["progreso"] = 40
        
        archivos_correctivos = resultado_clasificacion.get('archivos_correctivos', [])
        archivos_preventivos = resultado_clasificacion.get('archivos_preventivos', [])
        archivos_procesados = resultado_clasificacion.get('archivos_procesados', [])
        
        logger.info(f"📊 Clasificación: {len(archivos_correctivos)} correctivas, {len(archivos_preventivos)} preventivas")

        # FASE 3: Procesamiento OCR
        processing_status.update({
            "etapa_actual": "procesamiento_ocr",
            "progreso": 45,
            "mensaje": "Procesando facturas con OCR e insertando en MySQL"
        })
        ocr.procesar_carpeta_facturas("corr")
        processing_status["progreso"] = 60
        ocr.procesar_carpeta_facturas("prev")
        processing_status["progreso"] = 70

        # FASE 4: Subir a Google Drive según clasificación
        processing_status.update({
            "etapa_actual": "subir_drive",
            "progreso": 75,
            "mensaje": "Subiendo archivos a Google Drive (historico, correctivos, preventivos)"
        })
        
        # Subir todos los archivos a histórico y según clasificación
        drive.subir_archivos_a_drive_segun_clasificacion(
            archivos_correctivos=archivos_correctivos,
            archivos_preventivos=archivos_preventivos,
            carpeta_local_base=carpeta_local
        )
        processing_status["progreso"] = 85

        # FASE 5: Limpieza local de carpetas temporales
        processing_status.update({
            "etapa_actual": "limpieza_local",
            "progreso": 90,
            "mensaje": "Eliminando carpetas temporales locales (prev, corr, mes en curso)"
        })
        limpiar_carpetas_procesamiento()
        processing_status["progreso"] = 95

        # FASE 6: Limpieza S3 (eliminar archivos procesados del bucket)
        processing_status.update({
            "etapa_actual": "limpieza_s3",
            "progreso": 97,
            "mensaje": "Eliminando archivos procesados del bucket S3"
        })
        logger.info("🗑️  Eliminando archivos procesados del bucket S3...")
        exito_eliminacion, cantidad_eliminados = s3_utils.eliminar_archivos_s3(
            archivos=archivos_procesados,
            carpeta_s3=settings.S3_PREFIX_FACTURAS if settings.S3_PREFIX_FACTURAS else None
        )
        
        if exito_eliminacion:
            logger.info(f"✅ {cantidad_eliminados} archivos eliminados del bucket S3")
        else:
            logger.warning(f"⚠️  No se pudieron eliminar todos los archivos del S3")
        
        processing_status["progreso"] = 99

        # Completado
        processing_status.update({
            "estado": "completado",
            "etapa_actual": "finalizado",
            "progreso": 100,
            "mensaje": "Procesamiento completado exitosamente",
            "fin": datetime.now().isoformat()
        })
        logger.info("Pipeline completado exitosamente")

    except Exception as e:
        error_msg = f"Error en el procesamiento: {str(e)}"
        logger.error(error_msg, exc_info=True)
        processing_status.update({
            "estado": "error",
            "mensaje": "Error durante el procesamiento",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })


def ejecutar_entrenamiento_completo():
    """Pipeline completo de entrenamiento"""
    global training_status

    try:
        training_status.update({
            "estado": "ejecutando",
            "etapa_actual": "iniciando",
            "progreso": 0,
            "mensaje": "Iniciando pipeline de entrenamiento",
            "inicio": datetime.now().isoformat(),
            "fin": None,
            "error": None
        })
        logger.info("Pipeline de entrenamiento iniciado")
        
        # Limpiar carpeta bentoml si existe (no se usa)
        limpiar_carpeta_bentoml()

        # FASE 1: Descarga desde Drive
        training_status.update({
            "etapa_actual": "descarga_drive",
            "progreso": 10,
            "mensaje": "Descargando datos desde Google Drive"
        })
        drive.descargar_carpeta('invoices_test')
        training_status["progreso"] = 20
        drive.descargar_carpeta('invoices_train')
        training_status["progreso"] = 30

        # FASE 2: Preprocesamiento
        training_status.update({
            "etapa_actual": "preprocesamiento",
            "progreso": 40,
            "mensaje": "Preprocesando datos"
        })
        X_train, y_train, X_test, y_test = preprocessing.ejecutar_preprocesamiento_completo()
        training_status["progreso"] = 60
        preprocessing.guardar_datos_preprocesados_preprocesamiento(X_train, y_train, X_test, y_test)
        training_status["progreso"] = 70

        # FASE 3: Entrenamiento
        training_status.update({
            "etapa_actual": "entrenamiento",
            "progreso": 80,
            "mensaje": "Entrenando modelo"
        })
        logger.info("🔵 Iniciando entrenamiento del modelo (esto puede tardar varios minutos)...")
        try:
            model.entrenar_modelo()
            training_status["progreso"] = 85
            logger.info("✅ Entrenamiento del modelo completado exitosamente")
        except Exception as e:
            error_msg = f"Error durante el entrenamiento del modelo: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            training_status.update({
                "estado": "error",
                "mensaje": "Error durante el entrenamiento",
                "error": error_msg,
                "fin": datetime.now().isoformat()
            })
            raise
        
        # FASE 3.5: Subir modelo a S3 con DVC (CD)
        training_status.update({
            "etapa_actual": "subir_modelo_s3",
            "progreso": 87,
            "mensaje": "Subiendo modelo a S3 con DVC"
        })
        
        # Buscar el modelo entrenado
        carpeta_modelos = os.path.join(settings.BASE_DIR, settings.MODELS_DIR)
        ruta_modelo_final = os.path.join(carpeta_modelos, 'modelo_facturas_final.h5')
        
        if os.path.exists(ruta_modelo_final):
            logger.info("📤 Iniciando subida del modelo a S3 con DVC...")
            dvc_ok, dvc_msg = subir_modelo_dvc(ruta_modelo_final)
            
            if not dvc_ok:
                logger.warning(f"⚠️  No se pudo subir el modelo a S3: {dvc_msg}")
                # No fallar el entrenamiento si falla el push, solo advertir
                training_status["mensaje"] = f"Entrenamiento completado, pero falló subida a S3: {dvc_msg}"
            else:
                logger.info(f"✅ {dvc_msg}")
                training_status["mensaje"] = "Entrenamiento completado y modelo subido a S3"
                
                # Actualizar tracking en BD para marcar dvc_push_completed = True
                # Nota: Esto requeriría obtener el ID del tracking recién insertado
                # Por ahora, el tracking se guarda antes del push, así que dvc_push_completed será False
                # Si necesitas que sea True, deberías actualizar el registro después del push exitoso
        else:
            logger.warning(f"⚠️  No se encontró el modelo en {ruta_modelo_final} para subir a S3")
        
        training_status["progreso"] = 90

        # FASE 4: Limpieza de carpetas temporales
        training_status.update({
            "etapa_actual": "limpieza",
            "progreso": 95,
            "mensaje": "Limpiando carpetas temporales de entrenamiento"
        })
        limpiar_carpetas_entrenamiento()
        training_status["progreso"] = 98

        # Completado
        training_status.update({
            "estado": "completado",
            "etapa_actual": "finalizado",
            "progreso": 100,
            "mensaje": "Entrenamiento completado exitosamente",
            "fin": datetime.now().isoformat()
        })
        logger.info("Entrenamiento completado")

    except Exception as e:
        error_msg = f"Error en el entrenamiento: {str(e)}"
        logger.error(error_msg, exc_info=True)
        training_status.update({
            "estado": "error",
            "mensaje": "Error durante el entrenamiento",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })


# ========== ENDPOINTS ETL ==========

@app.post("/procesar_facturas", response_model=ProcessingResponse)
async def procesar_facturas(background_tasks: BackgroundTasks):
    """Inicia el procesamiento completo de facturas"""
    global processing_status

    if processing_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="Ya hay un procesamiento en ejecución"
        )

    # Verificar prerrequisitos antes de iniciar
    prerequisitos_ok, prerequisitos_msg = verificar_prerequisitos_etl()
    
    if not prerequisitos_ok:
        error_msg = f"Fallo en verificación de prerrequisitos: {prerequisitos_msg}"
        logger.error(error_msg)
        processing_status.update({
            "estado": "error",
            "etapa_actual": "verificando_prerrequisitos",
            "mensaje": "Error en verificación de prerrequisitos",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    
    logger.info("✅ Prerrequisitos verificados. Iniciando procesamiento...")

    processing_status.update({
        "estado": "en_cola",
        "etapa_actual": "pendiente",
        "progreso": 0
    })

    background_tasks.add_task(ejecutar_procesamiento_completo)

    return ProcessingResponse(
        mensaje="Procesamiento iniciado en segundo plano",
        estado="en_cola"
    )


@app.get("/procesar_facturas/status", response_model=ProcessingStatus)
async def get_processing_status():
    """Obtiene el estado actual del procesamiento"""
    return ProcessingStatus(**processing_status)


@app.post("/procesar_facturas/reset")
async def reset_processing_status():
    """Resetea el estado del procesamiento"""
    global processing_status

    # Solo prevenir reset si está ejecutando activamente
    if processing_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="No se puede resetear mientras está ejecutándose"
        )
    
    # Permitir reset si está completado, error, en_cola, o inactivo
    # Si ya está inactivo, simplemente confirmar el reset (idempotente)
    if processing_status["estado"] == "inactivo":
        return {"mensaje": "Estado ya está inactivo (reset idempotente)"}

    processing_status.update({
        "estado": "inactivo",
        "etapa_actual": None,
        "progreso": 0,
        "mensaje": None,
        "inicio": None,
        "fin": None,
        "error": None
    })

    return {"mensaje": "Estado reseteado correctamente"}


# ========== ENDPOINTS TRAINING ==========

@app.post("/train_model", response_model=ProcessingResponse)
async def train_model(background_tasks: BackgroundTasks):
    """Inicia el entrenamiento del modelo"""
    global training_status

    if training_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="Ya hay un entrenamiento en ejecución"
        )

    # Verificar prerrequisitos antes de iniciar
    prerequisitos_ok, prerequisitos_msg = verificar_prerequisitos_entrenamiento()
    
    if not prerequisitos_ok:
        error_msg = f"Fallo en verificación de prerrequisitos: {prerequisitos_msg}"
        logger.error(error_msg)
        training_status.update({
            "estado": "error",
            "etapa_actual": "verificando_prerrequisitos",
            "mensaje": "Error en verificación de prerrequisitos",
            "error": error_msg,
            "fin": datetime.now().isoformat()
        })
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )
    
    logger.info("✅ Prerrequisitos verificados. Iniciando entrenamiento...")

    training_status.update({
        "estado": "en_cola",
        "etapa_actual": "pendiente",
        "progreso": 0
    })

    background_tasks.add_task(ejecutar_entrenamiento_completo)

    return ProcessingResponse(
        mensaje="Entrenamiento iniciado en segundo plano",
        estado="en_cola"
    )


@app.get("/train_model/status", response_model=ProcessingStatus)
async def get_training_status():
    """Obtiene el estado actual del entrenamiento"""
    return ProcessingStatus(**training_status)


@app.post("/train_model/reset")
async def reset_training_status():
    """Resetea el estado del entrenamiento"""
    global training_status

    if training_status["estado"] == "ejecutando":
        raise HTTPException(
            status_code=409,
            detail="No se puede resetear mientras está ejecutándose"
        )

    training_status.update({
        "estado": "inactivo",
        "etapa_actual": None,
        "progreso": 0,
        "mensaje": None,
        "inicio": None,
        "fin": None,
        "error": None
    })

    return {"mensaje": "Estado reseteado correctamente"}


# ========== ENDPOINTS DVC (PRUEBAS) ==========

@app.get("/dvc/test")
async def test_dvc():
    """
    Endpoint de prueba para verificar que DVC funciona correctamente
    sin ejecutar el flujo completo de los endpoints principales.
    
    Verifica:
    - Instalación de DVC
    - Configuración de DVC (.dvc/config)
    - Remotes configurados
    - Conexión a S3 (credenciales AWS)
    - Archivos .dvc existentes
    """
    resultados = {
        "dvc_instalado": False,
        "dvc_version": None,
        "config_existe": False,
        "remotes_configurados": False,
        "remotes_list": [],
        "archivos_dvc_encontrados": [],
        "conexion_s3": False,
        "mensaje_s3": None,
        "errores": []
    }
    
    try:
        # 1. Verificar que DVC está instalado
        try:
            resultado_version = subprocess.run(
                ['dvc', '--version'],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=5
            )
            if resultado_version.returncode == 0:
                resultados["dvc_instalado"] = True
                resultados["dvc_version"] = resultado_version.stdout.strip()
            else:
                resultados["errores"].append(f"DVC no está instalado: {resultado_version.stderr}")
        except FileNotFoundError:
            resultados["errores"].append("DVC no está instalado o no está en el PATH")
        except Exception as e:
            resultados["errores"].append(f"Error al verificar DVC: {str(e)}")
        
        # 2. Verificar que existe .dvc/config
        ruta_config = os.path.join(settings.BASE_DIR, '.dvc', 'config')
        if os.path.exists(ruta_config):
            resultados["config_existe"] = True
        else:
            resultados["errores"].append(f"Archivo .dvc/config no encontrado en {ruta_config}")
        
        # 3. Verificar remotes configurados
        if resultados["dvc_instalado"]:
            try:
                resultado_remote = subprocess.run(
                    ['dvc', 'remote', 'list'],
                    cwd=settings.BASE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if resultado_remote.returncode == 0 and resultado_remote.stdout.strip():
                    resultados["remotes_configurados"] = True
                    resultados["remotes_list"] = [r.strip() for r in resultado_remote.stdout.strip().split('\n') if r.strip()]
                else:
                    resultados["errores"].append("No hay remotes configurados en DVC")
            except Exception as e:
                resultados["errores"].append(f"Error al verificar remotes: {str(e)}")
        
        # 4. Buscar archivos .dvc en el proyecto
        archivos_dvc = []
        carpetas_buscar = [
            os.path.join(settings.BASE_DIR, 'modelos'),
            os.path.join(settings.BASE_DIR, 'data'),
            settings.BASE_DIR
        ]
        
        for carpeta in carpetas_buscar:
            if os.path.exists(carpeta):
                for archivo in os.listdir(carpeta):
                    if archivo.endswith('.dvc'):
                        ruta_completa = os.path.join(carpeta, archivo)
                        archivos_dvc.append({
                            "nombre": archivo,
                            "ruta": os.path.relpath(ruta_completa, settings.BASE_DIR),
                            "existe_archivo_destino": os.path.exists(ruta_completa.replace('.dvc', ''))
                        })
        
        resultados["archivos_dvc_encontrados"] = archivos_dvc
        
        # 5. Verificar conexión a S3 (usando boto3 para verificar credenciales)
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Intentar crear un cliente S3
            try:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
                )
                
                # Intentar listar buckets (operación ligera que verifica credenciales)
                s3_client.list_buckets()
                resultados["conexion_s3"] = True
                resultados["mensaje_s3"] = "Conexión a S3 exitosa"
                
            except NoCredentialsError:
                resultados["errores"].append("Credenciales AWS no configuradas (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
                resultados["mensaje_s3"] = "Credenciales AWS no encontradas"
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == 'InvalidAccessKeyId':
                    resultados["errores"].append("Credenciales AWS inválidas")
                    resultados["mensaje_s3"] = f"Error de credenciales: {error_code}"
                else:
                    # Si es otro error pero las credenciales funcionan, consideramos conexión OK
                    resultados["conexion_s3"] = True
                    resultados["mensaje_s3"] = f"Conexión a S3 OK (error menor: {error_code})"
            except Exception as e:
                resultados["errores"].append(f"Error al verificar S3: {str(e)}")
                resultados["mensaje_s3"] = f"Error: {str(e)}"
                
        except ImportError:
            resultados["errores"].append("boto3 no está instalado (requerido para verificar S3)")
            resultados["mensaje_s3"] = "boto3 no disponible"
        except Exception as e:
            resultados["errores"].append(f"Error inesperado al verificar S3: {str(e)}")
        
        # Determinar estado general
        todo_ok = (
            resultados["dvc_instalado"] and
            resultados["config_existe"] and
            resultados["remotes_configurados"] and
            len(resultados["archivos_dvc_encontrados"]) > 0 and
            resultados["conexion_s3"]
        )
        
        return {
            "status": "ok" if todo_ok else "warning",
            "todo_funcional": todo_ok,
            "detalles": resultados,
            "resumen": {
                "dvc_instalado": resultados["dvc_instalado"],
                "configuracion_ok": resultados["config_existe"] and resultados["remotes_configurados"],
                "archivos_dvc": len(resultados["archivos_dvc_encontrados"]),
                "s3_conectado": resultados["conexion_s3"],
                "errores": len(resultados["errores"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error inesperado en test_dvc: {str(e)}", exc_info=True)
        resultados["errores"].append(f"Error inesperado: {str(e)}")
        return {
            "status": "error",
            "todo_funcional": False,
            "detalles": resultados,
            "error": str(e)
        }


# ========== ENDPOINTS GENERALES ==========

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "mensaje": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "endpoints": {
            "ETL": {
                "POST /procesar_facturas": "Iniciar procesamiento",
                "GET /procesar_facturas/status": "Estado del procesamiento",
                "POST /procesar_facturas/reset": "Resetear estado"
            },
            "Training": {
                "POST /train_model": "Iniciar entrenamiento",
                "GET /train_model/status": "Estado del entrenamiento",
                "POST /train_model/reset": "Resetear estado"
            },
            "DVC": {
                "GET /dvc/test": "Probar configuración de DVC"
            }
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}


# ========== EJECUTAR SERVIDOR ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT
    )
