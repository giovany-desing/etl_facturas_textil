import shutil
import os
import io
from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from app.config import settings
from app.utils import setup_logger

logger = setup_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']


def autenticar_drive():
    """
    Autentica con Google Drive usando OAuth 2.0
    
    Returns:
        googleapiclient.discovery.Resource: Servicio de Google Drive autenticado
        
    Raises:
        FileNotFoundError: Si no se encuentra el archivo de credenciales
        ValueError: Si el archivo de credenciales es inválido
        Exception: Para otros errores de autenticación
    """
    creds_path = settings.GOOGLE_CREDENTIALS_PATH
    token_path = settings.GOOGLE_TOKEN_PATH
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    try:
        # Verificar que existe el archivo de credenciales
        if not os.path.exists(creds_path):
            logger.error(f"Archivo de credenciales no encontrado en: {creds_path}")
            raise FileNotFoundError(
                f"No se encontró el archivo 'credentials.json' en {creds_path}. "
                "Por favor, descarga las credenciales OAuth 2.0 desde Google Cloud Console."
            )
        
        # Verificar que es un archivo, no un directorio
        if os.path.isdir(creds_path):
            logger.error(f"La ruta {creds_path} es un directorio, no un archivo")
            raise ValueError(
                f"La ruta {creds_path} es un directorio. "
                "Por favor, asegúrate de que 'credentials.json' sea un archivo."
            )
        
        logger.info(f"Cargando credenciales desde: {creds_path}")
        
        creds = None
        
        # Cargar token si existe
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                logger.info("Token de OAuth cargado exitosamente")
            except Exception as e:
                logger.warning(f"Error al cargar token: {e}. Se generará uno nuevo.")
        
        # Si no hay credenciales válidas, autenticar
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Token expirado, refrescando...")
                try:
                    creds.refresh(Request())
                    logger.info("Token refrescado exitosamente")
                except Exception as e:
                    logger.warning(f"Error al refrescar token: {e}. Se generará uno nuevo.")
                    creds = None
            
            if not creds:
                logger.error("No hay credenciales válidas disponibles")
                raise Exception(
                    "No se encontraron credenciales válidas de OAuth 2.0. "
                    "Por favor, asegúrate de que existe un token.json válido. "
                    "Si es la primera vez, necesitas ejecutar el flujo de autenticación OAuth 2.0 "
                    "para generar el token.json inicial."
                )
        
        # Guardar token para uso futuro
        if not os.path.exists(token_path) or creds != Credentials.from_authorized_user_file(token_path, SCOPES):
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            logger.info(f"Token guardado en: {token_path}")
        
        try:
            drive_service = build('drive', 'v3', credentials=creds)
            logger.info("Servicio de Google Drive construido exitosamente")
        except HttpError as e:
            logger.error(f"Error HTTP al construir servicio de Drive: {e}")
            raise Exception(
                f"Error al conectar con Google Drive API. "
                f"Verifica que la API esté habilitada en Google Cloud Console. Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error al construir servicio de Drive: {e}")
            raise Exception(f"Error inesperado al construir servicio de Drive: {str(e)}")
        
        try:
            logger.debug("Verificando autenticación con Google Drive...")
            about = drive_service.about().get(fields="user").execute()
            user_email = about.get('user', {}).get('emailAddress', 'Desconocido')
            logger.info(f"Autenticación exitosa. Usuario: {user_email}")
        except HttpError as e:
            if e.resp.status == 403:
                logger.error("Permiso denegado. Verifica que la API de Drive esté habilitada")
                raise Exception(
                    "Acceso denegado a Google Drive API. "
                    "Asegúrate de que la API de Google Drive esté habilitada en tu proyecto de Google Cloud."
                )
            else:
                logger.warning(f"No se pudo verificar la autenticación: {e}")
        except Exception as e:
            logger.warning(f"No se pudo verificar la autenticación (no crítico): {e}")
        
        logger.info("Autenticación con Google Drive completada exitosamente")
        return drive_service
        
    except (FileNotFoundError, ValueError) as e:
        raise
    except Exception as e:
        logger.critical(f"Error crítico durante la autenticación con Google Drive: {e}")
        raise Exception(f"Fallo en autenticación con Google Drive: {str(e)}")


def _buscar_carpeta_por_nombre(drive, nombre_carpeta, parent_id='root'):
    """
    Busca una carpeta por nombre en Drive (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        nombre_carpeta: Nombre de la carpeta a buscar
        parent_id: ID de la carpeta padre (si es 'root', busca en todas partes)
        
    Returns:
        str: ID de la carpeta encontrada o None
    """
    try:
        # Si parent_id es 'root', buscar en todas las carpetas compartidas
        if parent_id == 'root':
            query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            logger.debug(f"Buscando carpeta '{nombre_carpeta}' en todas las ubicaciones")
        else:
            query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            logger.debug(f"Buscando carpeta '{nombre_carpeta}' dentro de parent_id: {parent_id}")
        
        logger.debug(f"Query: {query}")
        
        results = drive.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, parents)',
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        if not folders:
            logger.warning(f"No se encontró la carpeta '{nombre_carpeta}'")
            logger.info("💡 Asegúrate de compartir la carpeta con el email de la Service Account")
            return None
        
        if len(folders) > 1:
            logger.warning(f"Se encontraron {len(folders)} carpetas con nombre '{nombre_carpeta}', usando la primera")
            for i, folder in enumerate(folders):
                logger.debug(f"  Carpeta {i+1}: ID={folder['id']}, Parents={folder.get('parents', 'N/A')}")
        
        folder_id = folders[0]['id']
        logger.info(f"Carpeta '{nombre_carpeta}' encontrada con ID: {folder_id}")
        return folder_id
        
    except HttpError as e:
        logger.error(f"Error HTTP al buscar carpeta '{nombre_carpeta}': {e}")
        if e.resp.status == 403:
            logger.error(" Acceso denegado. Verifica que la carpeta esté compartida con la Service Account")
        return None
    except Exception as e:
        logger.error(f"Error al buscar carpeta '{nombre_carpeta}': {e}")
        return None


def _listar_archivos_en_carpeta(drive, folder_id, incluir_carpetas=False):
    """
    Lista archivos en una carpeta (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        folder_id: ID de la carpeta
        incluir_carpetas: Si True, incluye subcarpetas en el resultado
        
    Returns:
        list: Lista de archivos/carpetas con metadatos
    """
    try:
        if incluir_carpetas:
            query = f"'{folder_id}' in parents and trashed=false"
        else:
            query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        
        logger.debug(f"Listando archivos en carpeta ID: {folder_id}")
        
        all_files = []
        page_token = None
        
        while True:
            results = drive.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime)',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            files = results.get('files', [])
            all_files.extend(files)
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        logger.debug(f"Se encontraron {len(all_files)} elementos en la carpeta")
        return all_files
        
    except Exception as e:
        logger.error(f"Error al listar archivos: {e}")
        return []


def _descargar_archivo(drive, file_id, destination_path):
    """
    Descarga un archivo desde Drive (función auxiliar interna)
    
    Args:
        drive: Servicio de Google Drive autenticado
        file_id: ID del archivo a descargar
        destination_path: Ruta local donde guardar el archivo
        
    Returns:
        bool: True si la descarga fue exitosa
    """
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        request = drive.files().get_media(fileId=file_id)
        
        with io.FileIO(destination_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.debug(f"Descarga {progress}%: {os.path.basename(destination_path)}")
        
        logger.debug(f"Archivo descargado: {os.path.basename(destination_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Error al descargar archivo {file_id}: {e}")
        return False


def descargar_carpeta_recursiva(drive, folder_id, ruta_local):
    """Descarga recursivamente el contenido de una carpeta de Google Drive"""
    try:
        # Listar todos los elementos (archivos y carpetas)
        elementos = _listar_archivos_en_carpeta(drive, folder_id, incluir_carpetas=True)
        
        if not elementos:
            logger.debug(f"Carpeta vacía: {ruta_local}")
            return True
        
        # Separar archivos y carpetas
        archivos = [e for e in elementos if e.get('mimeType') != 'application/vnd.google-apps.folder']
        carpetas = [e for e in elementos if e.get('mimeType') == 'application/vnd.google-apps.folder']
        
        # Descargar archivos
        for archivo in archivos:
            try:
                ruta_archivo = os.path.join(ruta_local, archivo['name'])
                logger.debug(f"Descargando archivo: {archivo['name']}")
                _descargar_archivo(drive, archivo['id'], ruta_archivo)
            except Exception as e:
                logger.error(f"Error descargando archivo {archivo['name']}: {e}")
        
        # Procesar subcarpetas recursivamente
        for carpeta in carpetas:
            ruta_subcarpeta = os.path.join(ruta_local, carpeta['name'])
            os.makedirs(ruta_subcarpeta, exist_ok=True)
            descargar_carpeta_recursiva(drive, carpeta['id'], ruta_subcarpeta)
        
        return True
        
    except Exception as e:
        logger.error(f"Error en descarga recursiva: {e}")
        return False


def descargar_carpeta(nombre_carpeta):
    """Descarga una carpeta específica de Google Drive a la raíz del proyecto"""
    try:
        logger.info(f"Iniciando descarga de carpeta: {nombre_carpeta}")
        drive = autenticar_drive()
        
        # Buscar carpeta principal de facturas
        FOLDER_NAME = 'facturas'
        
        logger.info(f"Buscando carpeta principal: {FOLDER_NAME}")
        folder_id = _buscar_carpeta_por_nombre(drive, FOLDER_NAME)

        if not folder_id:
            logger.error(f"No se encontró la carpeta principal '{FOLDER_NAME}'")
            return False

        ID_CARPETA_PRINCIPAL = folder_id
        logger.info(f"Carpeta principal '{FOLDER_NAME}' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        logger.info(f"Descargando documentos ...")
        
        # Buscar carpeta específica
        logger.info(f"Buscando carpeta: {nombre_carpeta}")
        carpeta_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, ID_CARPETA_PRINCIPAL)
        
        if not carpeta_id:
            logger.error(f"No se encontró la carpeta '{nombre_carpeta}'")
            return False
            
        logger.info(f"Carpeta '{nombre_carpeta}' encontrada. ID: {carpeta_id}")
        
        # Crear directorio en la raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        ruta_destino = os.path.join(directorio_raiz, nombre_carpeta)
        
        # Crear directorio si no existe
        os.makedirs(ruta_destino, exist_ok=True)
        
        # Descargar contenido recursivo de la carpeta
        if descargar_carpeta_recursiva(drive, carpeta_id, ruta_destino):
            logger.info(f"✓ Carpeta '{nombre_carpeta}' descargada exitosamente en: {ruta_destino}")
            return True
        else:
            logger.error(f"✗ Error al descargar carpeta '{nombre_carpeta}'")
            return False

    except Exception as e:
        logger.error(f"Error descargando carpeta '{nombre_carpeta}': {e}", exc_info=True)
        return False


def eliminar_archivos_drive(nombre_carpeta="mes en curso", horas_limite=1, eliminar_permanentemente=False):
    """
    Versión más flexible para eliminar archivos por antigüedad
    
    Args:
        nombre_carpeta (str): Nombre de la carpeta dentro de 'facturas'
        horas_limite (int): Eliminar archivos más recientes que X horas
        eliminar_permanentemente (bool): Si es True, elimina permanentemente en lugar de enviar a papelera
    """
    try:
        logger.info(f" Eliminando archivos de '{nombre_carpeta}' con menos de {horas_limite} hora(s)")
        drive = autenticar_drive()
        
        # Buscar carpeta principal
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        if not carpeta_principal_id:
            logger.error("No se encontró la carpeta principal 'facturas'")
            return False
        
        # Buscar carpeta target
        carpeta_target_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, carpeta_principal_id)
        if not carpeta_target_id:
            logger.error(f"No se encontró la carpeta '{nombre_carpeta}'")
            return False
        
        # Listar archivos
        archivos = _listar_archivos_en_carpeta(drive, carpeta_target_id)
        
        if not archivos:
            logger.info(f"No hay archivos en la carpeta '{nombre_carpeta}'")
            return True
        
        archivos_eliminados = 0
        
        # Si horas_limite es 0, eliminar todos los archivos sin importar la fecha
        if horas_limite == 0:
            logger.info("  Eliminando TODOS los archivos de la carpeta (sin filtro de tiempo)")
            for archivo in archivos:
                try:
                    if eliminar_permanentemente:
                        # Eliminar permanentemente
                        drive.files().delete(fileId=archivo['id']).execute()
                        logger.info(f"  ELIMINADO PERMANENTEMENTE: {archivo['name']}")
                    else:
                        # Enviar a papelera (actualizar con trashed=true)
                        drive.files().update(
                            fileId=archivo['id'],
                            body={'trashed': True}
                        ).execute()
                        logger.info(f"  ENVIADO A PAPELERA: {archivo['name']}")
                    
                    archivos_eliminados += 1
                except Exception as e:
                    logger.error(f"Error eliminando archivo {archivo.get('name', 'desconocido')}: {e}")
                    continue
        else:
            # Calcular límite de tiempo
            hora_limite = datetime.now(timezone.utc) - timedelta(hours=horas_limite)
            logger.info(f"⏰ Límite temporal: {hora_limite.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Procesar archivos
            for archivo in archivos:
                try:
                    # Parsear fecha de creación
                    fecha_creacion_str = archivo.get('createdTime')
                    if not fecha_creacion_str:
                        logger.warning(f"Archivo sin fecha de creación: {archivo['name']}")
                        continue
                    
                    fecha_creacion = datetime.fromisoformat(fecha_creacion_str.replace('Z', '+00:00'))
                    
                    if fecha_creacion > hora_limite:
                        if eliminar_permanentemente:
                            # Eliminar permanentemente
                            drive.files().delete(fileId=archivo['id']).execute()
                            logger.info(f"  ELIMINADO PERMANENTEMENTE: {archivo['name']}")
                        else:
                            # Enviar a papelera (actualizar con trashed=true)
                            drive.files().update(
                                fileId=archivo['id'],
                                body={'trashed': True}
                            ).execute()
                            logger.info(f"  ENVIADO A PAPELERA: {archivo['name']}")
                        
                        archivos_eliminados += 1
                    
                except Exception as e:
                    logger.error(f"Error procesando archivo {archivo.get('name', 'desconocido')}: {e}")
                    continue
        
        logger.info(f" Total archivos eliminados: {archivos_eliminados}")
        return True
        
    except Exception as e:
        logger.error(f"Error en eliminar_archivos_drive: {e}", exc_info=True)
        return False


def buscar_o_crear_carpeta(drive, carpeta_padre_id, nombre_carpeta):
    """
    Busca una carpeta en Drive y si no existe, la crea
    """
    try:
        # Buscar carpeta existente
        carpeta_id = _buscar_carpeta_por_nombre(drive, nombre_carpeta, carpeta_padre_id)
        
        if carpeta_id:
            logger.debug(f" Carpeta '{nombre_carpeta}' encontrada en Drive")
            return {'id': carpeta_id}
        else:
            # Crear nueva carpeta
            logger.info(f" Creando nueva carpeta: '{nombre_carpeta}'")
            
            file_metadata = {
                'name': nombre_carpeta,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [carpeta_padre_id]
            }
            
            folder = drive.files().create(
                body=file_metadata,
                fields='id, name'
            ).execute()
            
            logger.info(f" Carpeta '{nombre_carpeta}' creada exitosamente. ID: {folder['id']}")
            return folder
            
    except Exception as e:
        logger.error(f" Error buscando/creando carpeta '{nombre_carpeta}': {e}")
        return None


def subir_archivos_a_drive_segun_clasificacion(
    archivos_correctivos: list,
    archivos_preventivos: list,
    carpeta_local_base: str = None
):
    """
    Sube archivos a Google Drive según su clasificación:
    - Todos los archivos → 'historico'
    - Archivos correctivos → 'correctivos'
    - Archivos preventivos → 'preventivos'
    
    Args:
        archivos_correctivos: Lista de nombres de archivos clasificados como correctivos
        archivos_preventivos: Lista de nombres de archivos clasificados como preventivos
        carpeta_local_base: Ruta base donde están los archivos (default: "mes en curso")
    
    Returns:
        bool: True si la subida fue exitosa
    """
    try:
        logger.info(" Subiendo archivos a Google Drive según clasificación...")
        drive = autenticar_drive()
        
        # Obtener ruta raíz del proyecto
        if carpeta_local_base is None:
            directorio_raiz = os.path.dirname(os.path.dirname(__file__))
            carpeta_local_base = os.path.join(directorio_raiz, "mes en curso")
        
        # Buscar carpeta principal 'facturas' en Drive
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        if not carpeta_principal_id:
            logger.error(" No se encontró la carpeta principal 'facturas' en Drive")
            return False
        
        logger.info(f" Carpeta principal 'facturas' encontrada. ID: {carpeta_principal_id}")
        
        # Obtener todos los archivos procesados
        todos_los_archivos = archivos_correctivos + archivos_preventivos
        
        if not todos_los_archivos:
            logger.warning("  No hay archivos para subir a Google Drive")
            return True
        
        # Buscar o crear carpetas en Drive
        carpeta_historico = buscar_o_crear_carpeta(drive, carpeta_principal_id, 'historico')
        carpeta_correctivos = buscar_o_crear_carpeta(drive, carpeta_principal_id, 'correctivos')
        carpeta_preventivos = buscar_o_crear_carpeta(drive, carpeta_principal_id, 'preventivos')
        
        if not carpeta_historico or not carpeta_correctivos or not carpeta_preventivos:
            logger.error(" No se pudieron obtener/crear las carpetas en Drive")
            return False
        
        archivos_subidos_historico = 0
        archivos_subidos_correctivos = 0
        archivos_subidos_preventivos = 0
        
        # Obtener directorio raíz para buscar en carpetas prev y corr
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        carpeta_prev = os.path.join(directorio_raiz, "prev")
        carpeta_corr = os.path.join(directorio_raiz, "corr")
        
        # Subir todos los archivos a histórico (buscar en prev y corr)
        for nombre_archivo in todos_los_archivos:
            # Buscar archivo en prev o corr
            ruta_archivo = None
            if nombre_archivo in archivos_correctivos:
                ruta_archivo = os.path.join(carpeta_corr, nombre_archivo)
            elif nombre_archivo in archivos_preventivos:
                ruta_archivo = os.path.join(carpeta_prev, nombre_archivo)
            
            # Si no se encuentra, intentar en carpeta_local_base (mes en curso)
            if not ruta_archivo or not os.path.exists(ruta_archivo):
                ruta_archivo = os.path.join(carpeta_local_base, nombre_archivo)
            
            if os.path.exists(ruta_archivo):
                try:
                    file_metadata = {
                        'name': nombre_archivo,
                        'parents': [carpeta_historico['id']]
                    }
                    media = MediaFileUpload(ruta_archivo, resumable=True)
                    drive.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name'
                    ).execute()
                    archivos_subidos_historico += 1
                    logger.debug(f"   Subido a histórico: {nombre_archivo}")
                except Exception as e:
                    logger.error(f"   Error subiendo {nombre_archivo} a histórico: {e}")
        
        # Subir correctivos a carpeta correctivos
        for nombre_archivo in archivos_correctivos:
            ruta_archivo = os.path.join(carpeta_corr, nombre_archivo)
            if not os.path.exists(ruta_archivo):
                ruta_archivo = os.path.join(carpeta_local_base, nombre_archivo)
            
            if os.path.exists(ruta_archivo):
                try:
                    file_metadata = {
                        'name': nombre_archivo,
                        'parents': [carpeta_correctivos['id']]
                    }
                    media = MediaFileUpload(ruta_archivo, resumable=True)
                    drive.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name'
                    ).execute()
                    archivos_subidos_correctivos += 1
                    logger.debug(f"   Subido a correctivos: {nombre_archivo}")
                except Exception as e:
                    logger.error(f"   Error subiendo {nombre_archivo} a correctivos: {e}")
        
        # Subir preventivos a carpeta preventivos
        for nombre_archivo in archivos_preventivos:
            ruta_archivo = os.path.join(carpeta_prev, nombre_archivo)
            if not os.path.exists(ruta_archivo):
                ruta_archivo = os.path.join(carpeta_local_base, nombre_archivo)
            
            if os.path.exists(ruta_archivo):
                try:
                    file_metadata = {
                        'name': nombre_archivo,
                        'parents': [carpeta_preventivos['id']]
                    }
                    media = MediaFileUpload(ruta_archivo, resumable=True)
                    drive.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name'
                    ).execute()
                    archivos_subidos_preventivos += 1
                    logger.debug(f"   Subido a preventivos: {nombre_archivo}")
                except Exception as e:
                    logger.error(f"   Error subiendo {nombre_archivo} a preventivos: {e}")
        
        logger.info(f" Resumen de subida a Google Drive:")
        logger.info(f"    Histórico: {archivos_subidos_historico} archivos")
        logger.info(f"    Correctivos: {archivos_subidos_correctivos} archivos")
        logger.info(f"    Preventivos: {archivos_subidos_preventivos} archivos")
        
        return True
        
    except Exception as e:
        logger.error(f" Error subiendo archivos a Google Drive: {e}", exc_info=True)
        return False


def subir_documentos_preventivos_correctivos():
    """
    Sube documentos desde carpetas locales 'prev' y 'corr' a Google Drive
    - 'prev' → 'preventivos' en Drive  
    - 'corr' → 'correctivos' en Drive
    """
    try:
        logger.info(" Iniciando subida de documentos preventivos y correctivos")
        drive = autenticar_drive()
        
        # Obtener ruta raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        
        # Buscar carpeta principal 'facturas' en Drive
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error(" No se encontró la carpeta principal 'facturas' en Drive")
            return False

        ID_CARPETA_PRINCIPAL = carpeta_principal_id
        logger.info(f" Carpeta principal 'facturas' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        
        # Configuración de carpetas a procesar
        carpetas_procesar = [
            {
                'local': 'prev',
                'drive': 'preventivos', 
                'tipo': 'PREVENTIVOS'
            },
            {
                'local': 'corr', 
                'drive': 'correctivos',
                'tipo': 'CORRECTIVOS'
            }
        ]
        
        resultados = []
        
        for config in carpetas_procesar:
            carpeta_local = os.path.join(directorio_raiz, config['local'])
            nombre_carpeta_drive = config['drive']
            tipo = config['tipo']
            
            logger.info(f" Procesando {tipo}...")
            
            # Verificar que existe la carpeta local
            if not os.path.exists(carpeta_local):
                logger.error(f" No existe la carpeta local: {carpeta_local}")
                resultados.append(False)
                continue
            
            # Buscar o crear carpeta en Drive
            carpeta_drive = buscar_o_crear_carpeta(drive, ID_CARPETA_PRINCIPAL, nombre_carpeta_drive)
            if not carpeta_drive:
                logger.error(f" No se pudo obtener/crear carpeta '{nombre_carpeta_drive}' en Drive")
                resultados.append(False)
                continue
            
            # Obtener lista de archivos en carpeta local
            archivos_local = []
            extensiones_validas = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx', '.xls', '.xlsx']
            
            try:
                for archivo in os.listdir(carpeta_local):
                    ruta_completa = os.path.join(carpeta_local, archivo)
                    if os.path.isfile(ruta_completa):
                        _, extension = os.path.splitext(archivo)
                        if extension.lower() in extensiones_validas:
                            archivos_local.append(ruta_completa)
                        else:
                            logger.debug(f"  Archivo omitido (extensión no válida): {archivo}")
            except Exception as e:
                logger.error(f" Error obteniendo archivos de {carpeta_local}: {e}")
                resultados.append(False)
                continue
            
            if not archivos_local:
                logger.info(f"📭 No hay archivos para subir en {carpeta_local}")
                resultados.append(True)
                continue
            
            logger.info(f"📄 Encontrados {len(archivos_local)} archivos en {carpeta_local}")
            
            # Subir cada archivo
            archivos_subidos = 0
            for archivo_path in archivos_local:
                try:
                    nombre_archivo = os.path.basename(archivo_path)
                    
                    # Crear metadata del archivo en Drive
                    file_metadata = {
                        'name': nombre_archivo,
                        'parents': [carpeta_drive['id']]
                    }
                    
                    media = MediaFileUpload(archivo_path, resumable=True)
                    
                    file = drive.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name'
                    ).execute()
                    
                    archivos_subidos += 1
                    logger.debug(f" Subido: {nombre_archivo}")
                    
                except Exception as e:
                    logger.error(f" Error subiendo {os.path.basename(archivo_path)}: {e}")
                    continue
            
            logger.info(f"🎯 {tipo}: {archivos_subidos}/{len(archivos_local)} archivos subidos exitosamente")
            resultados.append(archivos_subidos > 0)
        
        # Resumen final
        exitos = sum(1 for r in resultados if r)
        total = len(resultados)
        
        logger.info(" RESUMEN FINAL:")
        logger.info(f"    Carpetas procesadas exitosamente: {exitos}/{total}")
        
        for i, config in enumerate(carpetas_procesar):
            estado = " ÉXITO" if resultados[i] else " FALLO"
            logger.info(f"   {estado} - {config['tipo']} ({config['local']} → {config['drive']})")
        
        return exitos > 0

    except Exception as e:
        logger.error(f" Error crítico en subida de documentos: {e}", exc_info=True)
        return False


def subir_mes_curso_a_historico():
    """
    Sube el contenido de la carpeta local 'mes en curso' a Google Drive
    en la carpeta 'historico' dentro de 'facturas'
    """
    try:
        logger.info("📅 Iniciando subida de 'mes en curso' a 'historico'")
        drive = autenticar_drive()
        
        # Obtener ruta raíz del proyecto
        directorio_raiz = os.path.dirname(os.path.dirname(__file__))
        
        # Buscar carpeta principal 'facturas' en Drive
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error(" No se encontró la carpeta principal 'facturas' en Drive")
            return False

        ID_CARPETA_PRINCIPAL = carpeta_principal_id
        logger.info(f" Carpeta principal 'facturas' encontrada. ID: {ID_CARPETA_PRINCIPAL}")
        
        # Buscar carpeta local 'mes en curso'
        carpeta_mes_curso_local = os.path.join(directorio_raiz, 'mes en curso')
        
        if not os.path.exists(carpeta_mes_curso_local):
            logger.error(f" No existe la carpeta local: {carpeta_mes_curso_local}")
            return False
        
        # Buscar o crear carpeta 'historico' en Drive
        carpeta_historico_drive = buscar_o_crear_carpeta(drive, ID_CARPETA_PRINCIPAL, 'historico')
        if not carpeta_historico_drive:
            logger.error(" No se pudo obtener/crear carpeta 'historico' en Drive")
            return False
        
        # Obtener lista de archivos en carpeta local 'mes en curso'
        archivos_local = []
        extensiones_validas = ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx', '.xls', '.xlsx']
        
        try:
            for archivo in os.listdir(carpeta_mes_curso_local):
                ruta_completa = os.path.join(carpeta_mes_curso_local, archivo)
                if os.path.isfile(ruta_completa):
                    _, extension = os.path.splitext(archivo)
                    if extension.lower() in extensiones_validas:
                        archivos_local.append(ruta_completa)
                    else:
                        logger.debug(f"  Archivo omitido (extensión no válida): {archivo}")
        except Exception as e:
            logger.error(f" Error obteniendo archivos de {carpeta_mes_curso_local}: {e}")
            return False
        
        if not archivos_local:
            logger.info(f"📭 No hay archivos para subir en {carpeta_mes_curso_local}")
            return True
        
        logger.info(f"📄 Encontrados {len(archivos_local)} archivos en 'mes en curso'")
        
        # Subir cada archivo
        archivos_subidos = 0
        for archivo_path in archivos_local:
            try:
                nombre_archivo = os.path.basename(archivo_path)
                
                # Crear metadata del archivo en Drive
                file_metadata = {
                    'name': nombre_archivo,
                    'parents': [carpeta_historico_drive['id']]
                }
                
                media = MediaFileUpload(archivo_path, resumable=True)
                
                file = drive.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name'
                ).execute()
                
                archivos_subidos += 1
                logger.info(f" Subido a histórico: {nombre_archivo}")
                
            except Exception as e:
                logger.error(f" Error subiendo {os.path.basename(archivo_path)}: {e}")
                continue
        
        logger.info(f"🎯 HISTÓRICO: {archivos_subidos}/{len(archivos_local)} archivos subidos exitosamente")
        return archivos_subidos > 0

    except Exception as e:
        logger.error(f" Error crítico en subida a histórico: {e}", exc_info=True)
        return False

def verificar_acceso_carpetas():
    """Función para verificar acceso a las carpetas necesarias"""
    try:
        logger.info(" Verificando acceso a carpetas en Google Drive...")
        drive = autenticar_drive()
        
        # Buscar carpeta principal
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        
        if not carpeta_principal_id:
            logger.error(" No se encontró la carpeta 'facturas'")
            logger.info("💡 Asegúrate de:")
            logger.info("   1. Crear una carpeta llamada 'facturas' en tu Google Drive")
            logger.info("   2. Compartirla con el email de la Service Account")
            logger.info("   3. Dar permisos de 'Editor'")
            return False
        
        logger.info(" Carpeta 'facturas' encontrada y accesible")
        
        # Verificar subcarpetas
        subcarpetas = ['invoices_train', 'invoices_test', 'mes en curso', 'preventivos', 'correctivos', 'historico']
        
        for carpeta in subcarpetas:
            carpeta_id = _buscar_carpeta_por_nombre(drive, carpeta, carpeta_principal_id)
            if carpeta_id:
                logger.info(f"    {carpeta}: ENCONTRADA")
            else:
                logger.warning(f"     {carpeta}: NO ENCONTRADA (puedes crearla después)")
        
        return True
        
    except Exception as e:
        logger.error(f" Error verificando acceso: {e}")
        return False

# Ejemplos de uso
if __name__ == "__main__":
    
    #Descargar una carpeta invoices_train
    descargar_carpeta('invoices_train')
    
    #Descargar otra carpeta invoices_test
    descargar_carpeta('invoices_test')
    
    #  Descargar mes en curso
    #descargar_carpeta('mes en curso')
    
    # Descargar múltiples carpetas
    #descargar_varias_carpetas(['invoices_train', 'invoices_test'])

    #Descargar una carpeta invoices_train
    #eliminar_carpeta_local('invoices_train')

    #Descargar una carpeta invoices_test
    #eliminar_carpeta_local('invoices_test')

    #eliminar_archivos_drive(nombre_carpeta="mes en curso", horas_limite=1, eliminar_permanentemente=False)
    #subir_documentos_preventivos_correctivos()
    #subir_mes_curso_a_historico()