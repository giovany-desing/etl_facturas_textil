"""
DAG de Airflow para detección de Data Drift - Versión AWS

ROL: Detectar cambios en la distribución de datos (drift) y activar reentrenamiento si es necesario.
     - Extrae facturas de Drive (preventivos y correctivos)
     - Compara distribuciones con datos de referencia
     - Decide si activar reentrenamiento basado en drift detectado
     - Dispara train_invoice_model_aws si se detecta drift
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable
import os

# ========== CONSTANTES ==========
TRAIN_DAG_ID = 'train_invoice_model_aws'  # ID del DAG de entrenamiento AWS a disparar

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
}

dag = DAG(
    'detect_data_drift_aws',
    default_args=default_args,
    description='Detección de Data Drift y activación condicional de reentrenamiento - AWS',
    schedule_interval='0 3 * * 0',  # Domingos a las 3 AM
    catchup=False,
    max_active_runs=1,
    tags=['aws', 'ml', 'drift', 'monitoring', 'retraining']
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
        logger.info("📥 Iniciando descarga de facturas para análisis de drift (AWS)")
        
        # Obtener directorio raíz del proyecto
        directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/tmp/drift_data')
        
        # Verificar que el directorio sea escribible
        if not os.access(os.path.dirname(directorio_raiz) if os.path.dirname(directorio_raiz) else '/', os.W_OK):
            logger.warning(f"⚠️ Directorio {directorio_raiz} no es escribible, usando /tmp/drift_data")
            directorio_raiz = '/tmp/drift_data'
        
        # Crear directorio raíz si no existe
        os.makedirs(directorio_raiz, exist_ok=True)
        logger.info(f"📁 Directorio raíz para datos de drift: {directorio_raiz}")
        
        # Carpetas a descargar desde Drive
        carpetas_descargar = ['preventivos', 'correctivos']
        resultados = {}
        
        # Autenticar Drive
        drive = autenticar_drive()
        
        # Buscar carpeta principal 'facturas'
        logger.info("🔍 Buscando carpeta principal 'facturas' en Drive...")
        carpeta_principal_id = _buscar_carpeta_por_nombre(drive, 'facturas')
        if not carpeta_principal_id:
            error_msg = "No se encontró la carpeta principal 'facturas' en Drive."
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        logger.info(f"✅ Carpeta principal 'facturas' encontrada. ID: {carpeta_principal_id}")
        
        for carpeta_nombre in carpetas_descargar:
            try:
                logger.info(f"📂 Procesando carpeta: {carpeta_nombre}")
                
                ruta_destino = os.path.join(directorio_raiz, f"drift_data_{carpeta_nombre}")
                
                # Buscar carpeta específica dentro de 'facturas'
                carpeta_id = _buscar_carpeta_por_nombre(drive, carpeta_nombre, carpeta_principal_id)
                if not carpeta_id:
                    logger.warning(f"⚠️ No se encontró la carpeta '{carpeta_nombre}'")
                    resultados[carpeta_nombre] = False
                    continue
                
                logger.info(f"   ✅ Carpeta '{carpeta_nombre}' encontrada. ID: {carpeta_id}")
                
                # Crear directorio de destino
                os.makedirs(ruta_destino, exist_ok=True)
                
                # Descargar recursivamente
                if descargar_carpeta_recursiva(drive, carpeta_id, ruta_destino):
                    logger.info(f"✅ Carpeta '{carpeta_nombre}' descargada exitosamente")
                    resultados[carpeta_nombre] = ruta_destino
                else:
                    logger.error(f"❌ Error al descargar carpeta '{carpeta_nombre}'")
                    resultados[carpeta_nombre] = False
                    
            except Exception as e:
                logger.error(f"❌ Error descargando '{carpeta_nombre}': {e}", exc_info=True)
                resultados[carpeta_nombre] = False
        
        # Almacenar rutas en XCom
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
        logger.info("🔍 Iniciando detección de drift (AWS)")
        
        # Obtener rutas de datos desde XCom
        ti = context.get('ti')
        rutas_datos = ti.xcom_pull(key='rutas_datos', task_ids='T1_preparar_datos') if ti else None
        
        # Si no hay datos en XCom, intentar usar rutas por defecto
        if not rutas_datos:
            logger.warning("⚠️ No se encontraron rutas de datos en XCom. Intentando usar rutas por defecto...")
            
            directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/tmp/drift_data')
            rutas_por_defecto = {
                'preventivos': os.path.join(directorio_raiz, 'drift_data_preventivos'),
                'correctivos': os.path.join(directorio_raiz, 'drift_data_correctivos')
            }
            
            rutas_datos = {}
            for nombre, ruta in rutas_por_defecto.items():
                if os.path.exists(ruta) and os.path.isdir(ruta):
                    archivos = [f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))]
                    if archivos:
                        rutas_datos[nombre] = ruta
                        logger.info(f"✅ Usando ruta por defecto para {nombre}: {ruta} ({len(archivos)} archivos)")
        
        if not rutas_datos:
            raise Exception("No se encontraron rutas de datos. Ejecuta T1_preparar_datos primero.")
        
        # Obtener configuración desde Variables de Airflow
        directorio_raiz = Variable.get('DRIFT_DATA_ROOT', default_var='/tmp/drift_data')
        ruta_baseline = Variable.get(
            'DRIFT_BASELINE_PATH',
            default_var=os.path.join('/app', 'modelos', 'baseline_caracteristicas.npy')
        )
        
        # Umbrales configurables
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
            logger.info("✅ DRIFT DETECTADO → Activando reentrenamiento en AWS ECS")
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

# T4: Activar reentrenamiento (disparar DAG de entrenamiento AWS)
T4_activar_reentreno = TriggerDagRunOperator(
    task_id='T4_activar_reentreno',
    trigger_dag_id=TRAIN_DAG_ID,
    wait_for_completion=False,  # No esperar a que termine (ejecución asíncrona)
    reset_dag_run=True,
    dag=dag
)

# T5: Finalización (sin reentrenamiento)
T5_fin = EmptyOperator(
    task_id='T5_fin',
    dag=dag
)

# ========== DEPENDENCIAS ==========
T1_preparar_datos >> T2_detectar_drift >> T3_decision_reentreno
T3_decision_reentreno >> [T4_activar_reentreno, T5_fin]

