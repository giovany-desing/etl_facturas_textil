"""
DAG de Airflow para detección de Data Drift

ROL: Detectar cambios en la distribución de datos (drift) y activar reentrenamiento si es necesario.
     - Extrae facturas de Drive (preventivos y correctivos)
     - Compara distribuciones con datos de referencia
     - Decide si activar reentrenamiento basado en drift detectado
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable
import os

# ========== CONSTANTES ==========
TRAIN_DAG_ID = 'train_invoice_model'  # ID del DAG de entrenamiento a disparar

# IDs de conexiones (configurar en Airflow UI)
GOOGLE_DRIVE_CONN_ID = 'google_drive'  # Connection para Google Drive (opcional, si se usa Google Provider)

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,  # Aumentado para manejar errores de red comunes
    'retry_delay': timedelta(minutes=10),
}

dag = DAG(
    'detect_data_drift',
    default_args=default_args,
    description='Detección de Data Drift y activación condicional de reentrenamiento',
    schedule_interval='0 3 * * 0',  # Domingos a las 3 AM (después del entrenamiento semanal)
    catchup=False,
    max_active_runs=1,
    tags=['ml', 'drift', 'monitoring', 'retraining']
)


def preparar_datos(**context):
    """
    T1: Extracción de facturas de Drive (preventivos y correctivos)
    Recicla las funciones de descarga usadas por el endpoint de procesar facturas
    """
    try:
        from app.drive import autenticar_drive, _buscar_carpeta_por_nombre, descargar_carpeta_recursiva
        from app.utils import setup_logger
        
        logger = setup_logger(__name__)
        logger.info("📥 Iniciando descarga de facturas para análisis de drift")
        
        # Obtener directorio raíz del proyecto
        # En producción, esto debería venir de una Variable de Airflow o configuración
        # Usar /opt/airflow/drift_data si está disponible, sino /tmp/drift_data
        directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/opt/airflow/drift_data')
        
        # Verificar que el directorio sea escribible, si no, usar /tmp
        if not os.access(os.path.dirname(directorio_raiz) if os.path.dirname(directorio_raiz) else '/', os.W_OK):
            logger.warning(f"⚠️ Directorio {directorio_raiz} no es escribible, usando /tmp/drift_data")
            directorio_raiz = '/tmp/drift_data'
        
        # Crear directorio raíz si no existe
        os.makedirs(directorio_raiz, exist_ok=True)
        logger.info(f"📁 Directorio raíz para datos de drift: {directorio_raiz}")
        
        # Carpetas a descargar desde Drive (dentro de 'facturas')
        carpetas_descargar = ['preventivos', 'correctivos']
        
        resultados = {}
        
        # Autenticar Drive (usa credenciales del sistema, no hardcodeadas)
        drive = autenticar_drive()
        
        # Buscar carpeta principal 'facturas'
        logger.info("🔍 Buscando carpeta principal 'facturas' en Drive...")
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        if not carpeta_principal_id:
            error_msg = "No se encontró la carpeta principal 'facturas' en Drive. Asegúrate de que existe y está compartida con el usuario de OAuth."
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"✅ Carpeta principal 'facturas' encontrada. ID: {carpeta_principal_id}")
        
        for carpeta_nombre in carpetas_descargar:
            try:
                logger.info(f"📂 Procesando carpeta: {carpeta_nombre}")
                
                ruta_destino = os.path.join(directorio_raiz, f"drift_data_{carpeta_nombre}")
                logger.info(f"   Ruta destino: {ruta_destino}")
                
                # Buscar carpeta específica dentro de 'facturas'
                logger.info(f"   Buscando carpeta '{carpeta_nombre}' dentro de 'facturas'...")
                carpeta_id = _buscar_carpeta_por_nombre(drive, carpeta_nombre, carpeta_principal_id)
                if not carpeta_id:
                    logger.warning(f"⚠️ No se encontró la carpeta '{carpeta_nombre}' dentro de 'facturas' en Drive")
                    logger.warning(f"   Verifica que la carpeta '{carpeta_nombre}' existe dentro de 'facturas' y está compartida correctamente")
                    resultados[carpeta_nombre] = False
                    continue
                
                logger.info(f"   ✅ Carpeta '{carpeta_nombre}' encontrada. ID: {carpeta_id}")
                
                # Crear directorio de destino
                os.makedirs(ruta_destino, exist_ok=True)
                logger.info(f"   📁 Directorio de destino creado: {ruta_destino}")
                
                # Descargar recursivamente
                logger.info(f"   ⬇️ Iniciando descarga recursiva...")
                if descargar_carpeta_recursiva(drive, carpeta_id, ruta_destino):
                    logger.info(f"✅ Carpeta '{carpeta_nombre}' descargada exitosamente en: {ruta_destino}")
                    resultados[carpeta_nombre] = ruta_destino
                else:
                    logger.error(f"❌ Error al descargar carpeta '{carpeta_nombre}' (descargar_carpeta_recursiva retornó False)")
                    resultados[carpeta_nombre] = False
                    
            except Exception as e:
                logger.error(f"❌ Error descargando '{carpeta_nombre}': {e}", exc_info=True)
                resultados[carpeta_nombre] = False
        
        # Almacenar rutas en XCom para la siguiente tarea
        context['ti'].xcom_push(key='rutas_datos', value=resultados)
        
        # Verificar que al menos una carpeta se descargó
        descargas_exitosas = sum(1 for v in resultados.values() if v is not False)
        
        if descargas_exitosas == 0:
            raise Exception("No se pudo descargar ninguna carpeta de facturas")
        
        logger.info(f"✅ Preparación de datos completada. Carpetas descargadas: {descargas_exitosas}/{len(carpetas_descargar)}")
        return resultados
        
    except Exception as e:
        logger.error(f"❌ Error en preparar_datos: {e}", exc_info=True)
        raise


def ejecutar_deteccion_drift(**context):
    """
    T2: Análisis de drift - Compara distribuciones de características
    Almacena el resultado (True/False) en XComs
    """
    try:
        from app.drift_analyzer import run_drift_detection
        from app.utils import setup_logger
        from airflow.models import Variable
        
        logger = setup_logger(__name__)
        logger.info("🔍 Iniciando detección de drift")
        
        # Obtener rutas de datos desde XCom
        ti = context.get('ti')
        rutas_datos = None
        
        if ti:
            rutas_datos = ti.xcom_pull(key='rutas_datos', task_ids='T1_preparar_datos')
        
        # Si no hay datos en XCom (modo test o primera ejecución), intentar usar rutas por defecto
        if not rutas_datos:
            logger.warning("⚠️ No se encontraron rutas de datos en XCom. Intentando usar rutas por defecto...")
            
            # Obtener directorio raíz
            directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/opt/airflow/drift_data')
            
            # Verificar si existen las carpetas por defecto
            import os
            rutas_por_defecto = {
                'preventivos': os.path.join(directorio_raiz, 'drift_data_preventivos'),
                'correctivos': os.path.join(directorio_raiz, 'drift_data_correctivos')
            }
            
            # Filtrar solo las rutas que existen
            rutas_datos = {}
            for nombre, ruta in rutas_por_defecto.items():
                if os.path.exists(ruta) and os.path.isdir(ruta):
                    archivos = [f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))]
                    if archivos:
                        rutas_datos[nombre] = ruta
                        logger.info(f"✅ Usando ruta por defecto para {nombre}: {ruta} ({len(archivos)} archivos)")
                    else:
                        logger.warning(f"⚠️ Carpeta {ruta} existe pero está vacía")
                else:
                    logger.warning(f"⚠️ Carpeta {ruta} no existe")
        
        if not rutas_datos:
            raise Exception("No se encontraron rutas de datos en XCom ni en ubicaciones por defecto. Ejecuta T1_preparar_datos primero o asegúrate de que las carpetas de datos existan.")
        
        # Obtener configuración desde Variables de Airflow
        directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/opt/airflow/drift_data')
        
        # Verificar que el directorio sea válido
        if not os.access(os.path.dirname(directorio_raiz) if os.path.dirname(directorio_raiz) else '/', os.W_OK):
            directorio_raiz = '/tmp/drift_data'
        
        ruta_baseline = Variable.get(
            'DRIFT_BASELINE_PATH',
            default_var=os.path.join('/app', 'modelos', 'baseline_caracteristicas.npy')
        )
        
        # Umbrales configurables desde Variables de Airflow
        umbral_p_value = float(Variable.get('DRIFT_UMBRAL_P_VALUE', default_var='0.05'))
        umbral_statistic = float(Variable.get('DRIFT_UMBRAL_STATISTIC', default_var='0.3'))
        
        logger.info(f"📊 Configuración de drift:")
        logger.info(f"   Baseline: {ruta_baseline}")
        logger.info(f"   Umbral p-value: {umbral_p_value}")
        logger.info(f"   Umbral statistic: {umbral_statistic}")
        
        # Ejecutar detección de drift
        drift_detectado, resultados_drift = run_drift_detection(
            rutas_datos=rutas_datos,
            ruta_baseline=ruta_baseline,
            umbral_p_value=umbral_p_value,
            umbral_statistic=umbral_statistic
        )
        
        # Almacenar resultado en XCom
        ti.xcom_push(key='drift_detectado', value=drift_detectado)
        ti.xcom_push(key='resultados_drift', value=resultados_drift)
        
        logger.info(f"🔍 Detección de drift completada. Drift detectado: {drift_detectado}")
        
        return drift_detectado
        
    except Exception as e:
        logger.error(f"❌ Error en ejecutar_deteccion_drift: {e}", exc_info=True)
        # Relanzar excepción - Airflow manejará el fallo con trigger_rule
        raise


def decision_reentreno(**context):
    """
    T3: Lógica de Decisión - Lee el valor XCom de T2
    Retorna el ID de la tarea siguiente según el resultado
    """
    try:
        from app.utils import setup_logger
        
        logger = setup_logger(__name__)
        ti = context['ti']
        
        # Leer resultado de T2 desde XCom
        drift_detectado = ti.xcom_pull(key='drift_detectado', task_ids='T2_detectar_drift')
        resultados_drift = ti.xcom_pull(key='resultados_drift', task_ids='T2_detectar_drift')
        
        if drift_detectado is None:
            logger.warning("⚠️ No se pudo obtener resultado de detección de drift. Asumiendo drift detectado.")
            drift_detectado = True
        
        logger.info(f"🎯 Decisión de reentrenamiento. Drift detectado: {drift_detectado}")
        
        if drift_detectado:
            logger.info("✅ DRIFT DETECTADO → Activando reentrenamiento")
            return 'T4_activar_reentreno'
        else:
            logger.info("✅ NO HAY DRIFT → Finalizando sin reentrenamiento")
            return 'T5_fin'
            
    except Exception as e:
        logger.error(f"❌ Error en decision_reentreno: {e}", exc_info=True)
        # En caso de error, activar reentrenamiento para ser conservador
        return 'T4_activar_reentreno'


# ========== TAREAS DEL DAG ==========

# T1: Preparar datos (descargar facturas de Drive)
T1_preparar_datos = PythonOperator(
    task_id='T1_preparar_datos',
    python_callable=preparar_datos,
    dag=dag
)

# T2: Detectar drift
T2_detectar_drift = PythonOperator(
    task_id='T2_detectar_drift',
    python_callable=ejecutar_deteccion_drift,
    dag=dag
)

# T3: Decisión de reentrenamiento (branch)
T3_decision_reentreno = BranchPythonOperator(
    task_id='T3_decision_reentreno',
    python_callable=decision_reentreno,
    dag=dag
)

# T4: Activar reentrenamiento (disparar DAG de entrenamiento)
T4_activar_reentreno = TriggerDagRunOperator(
    task_id='T4_activar_reentreno',
    trigger_dag_id=TRAIN_DAG_ID,  # Usar constante definida
    wait_for_completion=False,  # No esperar a que termine (ejecución asíncrona)
    reset_dag_run=True,  # Resetear el DAG run si ya existe
    dag=dag
)

# T5: Finalización (sin reentrenamiento) - Usando EmptyOperator (estándar Airflow 2.x)
T5_fin = EmptyOperator(
    task_id='T5_fin',
    dag=dag
)

# ========== DEPENDENCIAS ==========
# Flujo: T1 -> T2 -> T3 -> (T4 o T5)
T1_preparar_datos >> T2_detectar_drift >> T3_decision_reentreno
T3_decision_reentreno >> [T4_activar_reentreno, T5_fin]
