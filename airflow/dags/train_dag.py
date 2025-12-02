"""
DAG de Airflow para entrenamiento del modelo con CI/CD

ROL: Ejecutar la fase de entrenamiento, la CI del Modelo y el CD del Modelo (DVC Push).
     - Inicia el pipeline de entrenamiento (que incluye CI interna)
     - Monitorea el progreso hasta completar
     - Verifica si el modelo fue promovido (auditoría de CI)
     - Limpia el estado al finalizar
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.exceptions import AirflowException
import re

# ========== CONSTANTES ==========
FASTAPI_CONN_ID = 'fastapi_etl'
SLACK_CONN_ID = 'slack_webhook'
SLACK_CHANNEL = '#mlops-alerts'

# Variable global para almacenar datos de error (se usará desde el callback)
_error_data_cache = {}

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 0,  # Sin retries: el entrenamiento es costoso, mejor notificar que reintentar
    'retry_delay': timedelta(minutes=10),
}

dag = DAG(
    'train_invoice_model',
    default_args=default_args,
    description='Entrenamiento del modelo con CI/CD - Activación condicional desde Drift DAG',
    schedule_interval=None,  # Sin schedule: solo se ejecuta cuando es disparado por el DAG de Drift o manualmente
    catchup=False,
    max_active_runs=1,  # Solo una ejecución a la vez
    tags=['ml', 'training', 'facturas', 'ci-cd']
)


def verificar_activacion_entrenamiento(response):
    """
    Callback para T1: Verifica que la respuesta contenga "estado": "en_cola" (200/202)
    """
    try:
        if response.status_code in [200, 202]:
            data = response.json()
            estado = data.get('estado', '')
            if estado == 'en_cola':
                print(f"✅ Entrenamiento activado exitosamente. Estado: {estado}")
                return True
            else:
                print(f"⚠️ Estado inesperado: {estado}")
                return False
        else:
            print(f"❌ Código de respuesta inesperado: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando activación: {e}")
        return False


def verificar_entrenamiento_completado(response):
    """
    Callback para HttpSensor T2: Verifica que el estado sea "completado" o "error"
    Almacena detalles de error en caché global para que T2_capturar_error pueda acceder
    """
    global _error_data_cache
    try:
        data = response.json()
        estado = data.get('estado', '').lower()
        
        if estado == 'completado':
            print(f"✅ Entrenamiento completado exitosamente")
            return True
        elif estado == 'error':
            # Almacenar detalles del error en caché global
            error_data = {
                'estado': data.get('estado', 'desconocido'),
                'etapa_actual': data.get('etapa_actual', 'N/A'),
                'progreso': data.get('progreso', 0),
                'mensaje': data.get('mensaje', 'N/A'),
                'error': data.get('error', 'Error desconocido'),
                'inicio': data.get('inicio', 'N/A'),
                'fin': data.get('fin', 'N/A')
            }
            _error_data_cache['training_error_data'] = error_data
            
            error_msg = data.get('error', 'Error desconocido')
            print(f"❌ Entrenamiento falló: {error_msg}")
            raise AirflowException(f"El entrenamiento terminó con error: {error_msg}")
        else:
            progreso = data.get('progreso', 0)
            etapa = data.get('etapa_actual', 'desconocida')
            print(f"⏳ Estado: {estado}, Progreso: {progreso}%, Etapa: {etapa}")
            return False
    except AirflowException:
        raise
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False


def capturar_error_desde_cache(**context):
    """
    Tarea intermedia: Captura datos de error desde caché y los almacena en XComs
    Se ejecuta solo si T2 falla (error fatal)
    """
    global _error_data_cache
    ti = context['ti']
    
    # Intentar obtener datos de error desde caché
    if 'training_error_data' in _error_data_cache:
        error_data = _error_data_cache.pop('training_error_data')  # Limpiar caché después de usar
        ti.xcom_push(key='training_error_data', value=error_data)
        print(f"✅ Datos de error capturados desde caché y almacenados en XComs")
    else:
        # Fallback: intentar obtener desde la API directamente
        print(f"⚠️ No se encontraron datos de error en caché. Intentando obtener desde API...")
        try:
            from airflow.hooks.base import BaseHook
            import requests
            
            http_conn = BaseHook.get_connection(FASTAPI_CONN_ID)
            base_url = f"http://{http_conn.host}:{http_conn.port or 8000}"
            status_url = f"{base_url}/train_model/status"
            
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                error_data = {
                    'estado': data.get('estado', 'desconocido'),
                    'etapa_actual': data.get('etapa_actual', 'N/A'),
                    'progreso': data.get('progreso', 0),
                    'mensaje': data.get('mensaje', 'N/A'),
                    'error': data.get('error', data.get('mensaje', 'Error desconocido')),
                    'inicio': data.get('inicio', 'N/A'),
                    'fin': data.get('fin', 'N/A')
                }
                ti.xcom_push(key='training_error_data', value=error_data)
                print(f"✅ Datos de error obtenidos desde API y almacenados en XComs")
            else:
                print(f"⚠️ No se pudo obtener estado desde API. Código: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error al obtener datos desde API: {e}")


def formatear_mensaje_error_fatal(**context):
    """
    Tarea T2_alertar_error: Formatea mensaje de error fatal del entrenamiento
    Retorna el mensaje formateado para usar en SlackWebhookOperator
    """
    try:
        ti = context['ti']
        
        # Intentar obtener datos de error desde XComs (almacenados por T2_capturar_error)
        error_data = ti.xcom_pull(key='training_error_data', task_ids='T2_capturar_error')
        
        if error_data:
            estado = error_data.get('estado', 'desconocido')
            etapa_actual = error_data.get('etapa_actual', 'N/A')
            progreso = error_data.get('progreso', 0)
            mensaje = error_data.get('mensaje', 'N/A')
            error_details = error_data.get('error', 'Error desconocido')
        else:
            # Fallback: usar valores por defecto
            estado = 'error'
            etapa_actual = 'N/A'
            progreso = 0
            mensaje = 'Error fatal durante el entrenamiento'
            error_details = 'No se pudieron obtener detalles del error'
        
        # Formatear mensaje con Markdown para Slack
        dag_run_id = context.get('dag_run').run_id if context.get('dag_run') else 'N/A'
        task_id = context.get('task_instance').task_id if context.get('task_instance') else 'N/A'
        timestamp = datetime.now().isoformat()
        
        error_message = f"""
❌ *ERROR FATAL EN ENTRENAMIENTO DEL MODELO*

*Estado:* `{estado}`
*Etapa:* `{etapa_actual}`
*Progreso:* `{progreso}%`
*Mensaje:* `{mensaje}`
*Error:* `{error_details}`

*DAG Run:* `{dag_run_id}`
*Task:* `{task_id}`
*Timestamp:* `{timestamp}`

*ACCIÓN REQUERIDA:* Revisar logs del entrenamiento y corregir el error antes de reintentar.
"""
        
        # Almacenar mensaje formateado en XComs para T2_notificar_error
        ti.xcom_push(key='error_message_formatted', value=error_message)
        
        print(error_message)
        return error_message
        
    except Exception as e:
        error_msg = f"Error al formatear mensaje de error fatal: {str(e)}"
        print(f"❌ {error_msg}")
        context['ti'].xcom_push(
            key='error_message_formatted',
            value=f"❌ Error al obtener detalles del error fatal: {error_msg}"
        )
        return error_msg


def obtener_status_entrenamiento(**context):
    """
    Tarea T3_obtener_status: Obtiene el status del entrenamiento y lo almacena en XComs
    Se ejecuta solo si T2 fue exitoso
    """
    try:
        from airflow.hooks.base import BaseHook
        import requests
        
        ti = context['ti']
        
        http_conn = BaseHook.get_connection(FASTAPI_CONN_ID)
        base_url = f"http://{http_conn.host}:{http_conn.port or 8000}"
        status_url = f"{base_url}/train_model/status"
        
        response = requests.get(status_url, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"No se pudo obtener el estado. Código: {response.status_code}")
        
        data = response.json()
        
        # Almacenar datos completos en XComs
        ti.xcom_push(key='training_status_data', value=data)
        
        print(f"✅ Status del entrenamiento obtenido y almacenado en XComs")
        return data
        
    except Exception as e:
        error_msg = f"Error al obtener status del entrenamiento: {str(e)}"
        print(f"❌ {error_msg}")
        raise


def verificar_promocion_modelo(**context):
    """
    Tarea T3_verificar_promocion: Auditoría de CI - Verifica si el modelo fue promovido
    Lee los datos desde XComs (almacenados por T3_obtener_status)
    """
    try:
        ti = context['ti']
        
        # Leer datos de status desde XComs
        data = ti.xcom_pull(key='training_status_data', task_ids='T3_obtener_status')
        
        if not data:
            raise Exception("No se encontraron datos de status en XComs")
        
        mensaje = data.get('mensaje', '').lower()
        estado = data.get('estado', '').lower()
        error = data.get('error', '').strip()  # Campo error (señal más fuerte)
        
        # Señal más fuerte: si hay un error no vacío, el modelo NO fue promovido
        modelo_rechazado = bool(error)
        
        # Si no hay error explícito, buscar indicadores en el mensaje
        if not modelo_rechazado:
            # Palabras clave que indican que el modelo NO fue promovido
            indicadores_rechazo = [
                r'\bno\s+apto\b',
                r'\brechazado\b',
                r'\bfall[óo]\s+validaci[óo]n\b',
                r'\bci\s+fall[óo]\b',
                r'\bno\s+promovido\b',
                r'\bno\s+supera\s+baseline\b',
                r'\bm[eé]tricas\s+insuficientes\b',
                r'\bf1\s+insuficiente\b',
                r'\bbaseline\s+no\s+superado\b',
                r'\bvalidaci[óo]n\s+fallida\b',
                r'\bmodelo\s+no\s+apto\b',
                r'\bno\s+cumple\s+criterios\b',
                r'\bcd\s+detenido\b',
                r'\bci\s+validation\s+failed\b'
            ]
            
            # Usar expresiones regulares para búsqueda más robusta
            for patron in indicadores_rechazo:
                if re.search(patron, mensaje, re.IGNORECASE):
                    modelo_rechazado = True
                    break
        
        # Construir mensaje de alerta
        if modelo_rechazado:
            alerta = f"""
⚠️ *ALERTA: MODELO NO PROMOVIDO - CI FALLÓ*

El entrenamiento completó, pero el modelo *NO* fue promovido a producción.

*Estado:* `{data.get('estado', 'desconocido')}`
*Mensaje:* `{data.get('mensaje', 'N/A')}`
*Error:* `{error if error else 'N/A'}`
*Etapa:* `{data.get('etapa_actual', 'N/A')}`
*Progreso:* `{data.get('progreso', 0)}%`

*Razón:* El modelo no pasó la validación CI (métricas insuficientes o no supera baseline)

*DAG Run:* `{context.get('dag_run').run_id if context.get('dag_run') else 'N/A'}`
*Task:* `{context.get('task_instance').task_id if context.get('task_instance') else 'N/A'}`
*Timestamp:* `{datetime.now().isoformat()}`

*ACCIÓN REQUERIDA:* Revisar métricas del modelo y criterios de CI
"""
            # Almacenar mensaje en XComs para T3_notificar_no_promocion
            ti.xcom_push(key='no_promocion_message', value=alerta)
            print(alerta)
            return alerta
        else:
            mensaje_exito = f"""
✅ *MODELO PROMOVIDO EXITOSAMENTE*

El entrenamiento completó y el modelo fue promovido a producción.

*Estado:* `{data.get('estado', 'desconocido')}`
*Mensaje:* `{data.get('mensaje', 'N/A')}`
*Etapa:* `{data.get('etapa_actual', 'N/A')}`
*Progreso:* `{data.get('progreso', 0)}%`

*DAG Run:* `{context.get('dag_run').run_id if context.get('dag_run') else 'N/A'}`
*Timestamp:* `{datetime.now().isoformat()}`
"""
            print(mensaje_exito)
            return mensaje_exito
        
    except Exception as e:
        error_msg = f"Error al verificar promoción del modelo: {str(e)}"
        print(f"❌ {error_msg}")
        raise


# ========== TAREAS DEL DAG ==========

# T1: Iniciar el entrenamiento
T1_iniciar_entrenamiento = SimpleHttpOperator(
    task_id='T1_iniciar_entrenamiento',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/train_model',
    method='POST',
    headers={"Content-Type": "application/json"},
    response_check=verificar_activacion_entrenamiento,
    dag=dag
)

# T2: Monitorear el progreso hasta completar (timeout largo para entrenamiento)
T2_monitorear_cd = HttpSensor(
    task_id='T2_monitorear_cd',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/train_model/status',
    method='GET',
    response_check=verificar_entrenamiento_completado,
    poke_interval=120,  # Verificar cada 2 minutos (el entrenamiento puede tardar mucho)
    timeout=7200,  # Timeout de 2 horas (ajustar según tiempo esperado de entrenamiento)
    soft_fail=False,  # Falla si no se completa en el timeout
    dag=dag
)

# T2_capturar_error: Capturar error desde caché y almacenar en XComs (si T2 falla)
T2_capturar_error = PythonOperator(
    task_id='T2_capturar_error',
    python_callable=capturar_error_desde_cache,
    trigger_rule='one_failed',  # Se ejecuta si T2 falla
    dag=dag
)

# T2_formatear_error: Formatear mensaje de error fatal
T2_formatear_error = PythonOperator(
    task_id='T2_formatear_error',
    python_callable=formatear_mensaje_error_fatal,
    trigger_rule='one_success',  # Se ejecuta si T2_capturar_error fue exitoso
    dag=dag
)

# T2_notificar_error: Notificar error fatal en Slack usando operador nativo
T2_notificar_error = SlackWebhookOperator(
    task_id='T2_notificar_error',
    slack_webhook_conn_id=SLACK_CONN_ID,  # Cambiado de http_conn_id a slack_webhook_conn_id
    message="{{ ti.xcom_pull(key='error_message_formatted', task_ids='T2_formatear_error') }}",
    channel=SLACK_CHANNEL,
    trigger_rule='one_success',  # Se ejecuta si T2_formatear_error fue exitoso
    dag=dag
)

# T3_obtener_status: Obtener status del entrenamiento y almacenar en XComs (si T2 exitoso)
T3_obtener_status = PythonOperator(
    task_id='T3_obtener_status',
    python_callable=obtener_status_entrenamiento,
    trigger_rule='all_success',  # Se ejecuta solo si T2 fue exitoso
    dag=dag
)

# T3_verificar_promocion: Verificar si el modelo fue promovido (auditoría de CI)
T3_verificar_promocion = PythonOperator(
    task_id='T3_verificar_promocion',
    python_callable=verificar_promocion_modelo,
    trigger_rule='all_success',  # Se ejecuta solo si T3_obtener_status fue exitoso
    dag=dag
)

# T3_notificar_no_promocion: Notificar si el modelo NO fue promovido (usando operador nativo)
T3_notificar_no_promocion = SlackWebhookOperator(
    task_id='T3_notificar_no_promocion',
    slack_webhook_conn_id=SLACK_CONN_ID,  # Cambiado de http_conn_id a slack_webhook_conn_id
    message="{{ ti.xcom_pull(key='no_promocion_message', task_ids='T3_verificar_promocion') }}",
    channel=SLACK_CHANNEL,
    trigger_rule='all_success',  # Se ejecuta solo si T3_verificar_promocion fue exitoso
    dag=dag
)

# T4: Reset del estado (siempre se ejecuta, éxito o error)
T4_reset_estado = SimpleHttpOperator(
    task_id='T4_reset_estado',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/train_model/reset',
    method='POST',
    headers={"Content-Type": "application/json"},
    trigger_rule='all_done',  # Se ejecuta siempre, sin importar el resultado de las tareas anteriores
    response_check=lambda response: response.status_code in [200, 202],
    dag=dag
)

# ========== DEPENDENCIAS ==========
# Flujo principal: T1 -> T2 -> T3_obtener_status -> T3_verificar_promocion -> T3_notificar_no_promocion -> T4
# Flujo de error: T2 (si falla) -> T2_capturar_error -> T2_formatear_error -> T2_notificar_error -> T4
T1_iniciar_entrenamiento >> T2_monitorear_cd
T2_monitorear_cd >> T3_obtener_status >> T3_verificar_promocion >> T3_notificar_no_promocion >> T4_reset_estado
T2_monitorear_cd >> T2_capturar_error >> T2_formatear_error >> T2_notificar_error >> T4_reset_estado
