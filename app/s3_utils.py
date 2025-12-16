"""
Utilidades para trabajar con AWS S3
- Descargar facturas desde S3
- Eliminar archivos procesados de S3
"""
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Tuple
from pathlib import Path

from app.config import settings
from app.utils import setup_logger

logger = setup_logger(__name__)


def is_running_in_ecs() -> bool:
    """
    Detecta si está corriendo en ECS usando Instance Metadata Service (IMDS)
    
    Returns:
        bool: True si está corriendo en ECS, False en caso contrario
    """
    # ECS inyecta esta variable de entorno cuando el contenedor está corriendo
    return os.getenv("ECS_CONTAINER_METADATA_URI") is not None


def obtener_cliente_s3():
    """
    Obtiene un cliente de S3 configurado
    - Si está en ECS, usa IAM role (no requiere access keys)
    - Si no está en ECS, intenta usar credenciales de settings o variables de entorno
    
    Returns:
        boto3.client: Cliente de S3 o None si hay error
    """
    try:
        # Verificar nombre del bucket
        if not settings.S3_BUCKET_NAME:
            logger.error(" Nombre del bucket S3 no configurado (S3_BUCKET_NAME)")
            return None
        
        # Detectar si está corriendo en ECS
        running_in_ecs = is_running_in_ecs()
        
        if running_in_ecs:
            # En ECS, usar IAM role (boto3 lo detecta automáticamente)
            logger.info("🚀 Detectado: Ejecutándose en ECS - Usando IAM role para S3")
            try:
                s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
                logger.info("✅ Cliente S3 creado usando IAM role de ECS")
                return s3_client
            except Exception as e:
                logger.error(f" Error creando cliente S3 con IAM role: {e}")
                return None
        else:
            # No está en ECS, usar credenciales explícitas
            logger.info("💻 Ejecutándose fuera de ECS - Usando credenciales explícitas")
            
            # Verificar credenciales disponibles (prioridad: env vars > settings)
            aws_key = os.getenv('AWS_ACCESS_KEY_ID') or settings.AWS_ACCESS_KEY_ID
            aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY') or settings.AWS_SECRET_ACCESS_KEY
            
            logger.debug(f" Verificando credenciales AWS:")
            logger.debug(f"   env AWS_ACCESS_KEY_ID: {' Configurado' if os.getenv('AWS_ACCESS_KEY_ID') else ' No configurado'}")
            logger.debug(f"   settings.AWS_ACCESS_KEY_ID: {' Configurado' if settings.AWS_ACCESS_KEY_ID else ' No configurado'}")
            logger.debug(f"   env AWS_SECRET_ACCESS_KEY: {' Configurado' if os.getenv('AWS_SECRET_ACCESS_KEY') else ' No configurado'}")
            logger.debug(f"   settings.AWS_SECRET_ACCESS_KEY: {' Configurado' if settings.AWS_SECRET_ACCESS_KEY else ' No configurado'}")
            logger.debug(f"   Bucket: {settings.S3_BUCKET_NAME}")
            
            # Intentar usar credenciales de variables de entorno o settings
            if aws_key and aws_secret:
                logger.info(" Usando credenciales explícitas de AWS")
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_key,
                    aws_secret_access_key=aws_secret,
                    region_name=settings.AWS_REGION
                )
            else:
                # Intentar usar credenciales por defecto de boto3 (variables de entorno, ~/.aws/credentials, etc.)
                logger.warning("  No se encontraron credenciales explícitas, intentando usar credenciales por defecto de boto3...")
                try:
                    s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
                    logger.info(" Cliente S3 creado con credenciales por defecto de boto3")
                except NoCredentialsError as e:
                    logger.error(" No se encontraron credenciales de AWS")
                    logger.error("   Configura AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY en:")
                    logger.error("   - Archivo .env en la raíz del proyecto (y reinicia el contenedor)")
                    logger.error("   - Variables de entorno del sistema")
                    logger.error("   - Archivo ~/.aws/credentials")
                    logger.error("   - O agrega env_file: - ../.env en docker-compose.yml")
                    return None
        
        logger.debug(" Cliente S3 creado exitosamente")
        return s3_client
        
    except Exception as e:
        logger.error(f" Error creando cliente S3: {e}", exc_info=True)
        return None


def descargar_carpeta_s3(carpeta_s3: str = None, ruta_local: str = None) -> Tuple[bool, List[str]]:
    """
    Descarga todos los archivos del bucket S3 a una ruta local
    
    Args:
        carpeta_s3: Prefijo/carpeta dentro del bucket (opcional, usa S3_PREFIX_FACTURAS si es None)
        ruta_local: Ruta local donde descargar los archivos
    
    Returns:
        tuple[bool, List[str]]: (éxito, lista de archivos descargados)
    """
    try:
        # Usar prefijo de configuración si no se especifica
        if carpeta_s3 is None:
            carpeta_s3 = settings.S3_PREFIX_FACTURAS
        
        logger.info(f" Descargando archivos desde S3 bucket '{settings.S3_BUCKET_NAME}' (prefijo: '{carpeta_s3 or 'raíz'}')...")
        
        s3_client = obtener_cliente_s3()
        if not s3_client:
            return False, []
        
        # Crear directorio local si no existe
        if ruta_local:
            os.makedirs(ruta_local, exist_ok=True)
        else:
            ruta_local = os.path.join(settings.BASE_DIR, "mes en curso")
            os.makedirs(ruta_local, exist_ok=True)
        
        # Listar objetos en el bucket (con prefijo si se especifica)
        prefix = f"{carpeta_s3}/" if carpeta_s3 and not carpeta_s3.endswith('/') else (carpeta_s3 or "")
        archivos_descargados = []
        
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    logger.warning(f"  No se encontraron archivos en S3 con prefijo '{prefix}'")
                    continue
                
                for obj in page['Contents']:
                    # Obtener nombre del archivo (sin el prefijo de carpeta)
                    key = obj['Key']
                    nombre_archivo = os.path.basename(key)
                    
                    # Saltar si es una carpeta (termina en /)
                    if nombre_archivo == '' or key.endswith('/'):
                        continue
                    
                    # Ruta local completa
                    ruta_archivo_local = os.path.join(ruta_local, nombre_archivo)
                    
                    # Descargar archivo
                    try:
                        s3_client.download_file(settings.S3_BUCKET_NAME, key, ruta_archivo_local)
                        archivos_descargados.append(nombre_archivo)
                        logger.debug(f"   Descargado: {nombre_archivo}")
                    except Exception as e:
                        logger.error(f"   Error descargando {nombre_archivo}: {e}")
                        continue
            
            logger.info(f" Total archivos descargados desde S3: {len(archivos_descargados)}")
            return True, archivos_descargados
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchBucket':
                logger.error(f" El bucket '{settings.S3_BUCKET_NAME}' no existe")
            else:
                logger.error(f" Error de AWS S3: {e}")
            return False, []
        
    except Exception as e:
        logger.error(f" Error inesperado descargando desde S3: {e}", exc_info=True)
        return False, []


def eliminar_archivos_s3(archivos: List[str], carpeta_s3: str = None) -> Tuple[bool, int]:
    """
    Elimina archivos del bucket S3
    
    Args:
        archivos: Lista de nombres de archivos a eliminar
        carpeta_s3: Prefijo/carpeta dentro del bucket (opcional, usa S3_PREFIX_FACTURAS si es None)
    
    Returns:
        tuple[bool, int]: (éxito, cantidad de archivos eliminados)
    """
    try:
        if not archivos:
            logger.info("📭 No hay archivos para eliminar de S3")
            return True, 0
        
        # Usar prefijo de configuración si no se especifica
        if carpeta_s3 is None:
            carpeta_s3 = settings.S3_PREFIX_FACTURAS
        
        logger.info(f"  Eliminando {len(archivos)} archivos del bucket S3 '{settings.S3_BUCKET_NAME}'...")
        
        s3_client = obtener_cliente_s3()
        if not s3_client:
            return False, 0
        
        prefix = f"{carpeta_s3}/" if carpeta_s3 and not carpeta_s3.endswith('/') else (carpeta_s3 or "")
        archivos_eliminados = 0
        
        # Eliminar archivos en lotes (máximo 1000 por request)
        for i in range(0, len(archivos), 1000):
            lote = archivos[i:i+1000]
            
            # Construir lista de objetos a eliminar
            objects_to_delete = [
                {'Key': f"{prefix}{archivo}"} for archivo in lote
            ]
            
            try:
                response = s3_client.delete_objects(
                    Bucket=settings.S3_BUCKET_NAME,
                    Delete={'Objects': objects_to_delete}
                )
                
                # Contar eliminados exitosamente
                eliminados = len(response.get('Deleted', []))
                archivos_eliminados += eliminados
                
                # Verificar errores
                if 'Errors' in response and response['Errors']:
                    for error in response['Errors']:
                        logger.error(f"   Error eliminando {error.get('Key', 'desconocido')}: {error.get('Message', 'Unknown error')}")
                
                logger.debug(f"   Lote eliminado: {eliminados}/{len(lote)} archivos")
                
            except ClientError as e:
                logger.error(f" Error eliminando lote de archivos: {e}")
                continue
        
        logger.info(f" Total archivos eliminados de S3: {archivos_eliminados}/{len(archivos)}")
        return True, archivos_eliminados
        
    except Exception as e:
        logger.error(f" Error inesperado eliminando archivos de S3: {e}", exc_info=True)
        return False, 0

