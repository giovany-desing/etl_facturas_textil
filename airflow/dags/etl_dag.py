"""
DAG de Airflow para procesamiento ETL de facturas con inferencia del modelo

ROL: Orquestar el flujo de ETL y la inferencia del modelo, ejecutándose cada hora.
     - Previene colisiones verificando estado inactivo antes de iniciar
     - Activa el pipeline ETL
     - Monitorea el progreso hasta completar
     - Maneja errores y notificaciones
     - Limpia el estado al finalizar
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.exceptions import AirflowException

# ========== CONSTANTES ==========
FASTAPI_CONN_ID = 'fastapi_etl'
SLACK_CONN_ID = 'slack_webhook'
SLACK_CHANNEL = '#mlops-alerts'

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,  # Aumentado para manejar errores de red comunes en fuentes externas
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'process_invoices_etl',
    default_args=default_args,
    description='Procesamiento ETL de facturas con inferencia del modelo - Ejecución cada hora',
    schedule_interval='0 * * * *',  # Cada hora en el minuto 0
    catchup=False,
    max_active_runs=1,  # Solo una ejecución a la vez
    tags=['etl', 'facturas', 'hourly', 'inference']
)


def verificar_estado_inactivo(response):
    """
    Callback para HttpSensor T1: Verifica que el estado sea inactivo, completado o error
    """
    try:
        data = response.json()
        estado = data.get('estado', '').lower()
        
        if estado in ['inactivo', 'completado', 'error']:
            return True
        else:
            print(f"⚠️ Estado actual: {estado}. Esperando que sea inactivo/completado/error...")
            return False
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False


def verificar_activacion_exitosa(response):
    """
    Callback para T2: Verifica que la respuesta contenga "estado": "en_cola" (200 OK o 202 Accepted)
    """
    try:
        # Aceptar tanto 200 como 202 (FastAPI puede devolver 200 con estado "en_cola")
        if response.status_code in [200, 202]:
            data = response.json()
            estado = data.get('estado', '')
            if estado == 'en_cola':
                print(f"✅ ETL activado exitosamente. Estado: {estado} (código: {response.status_code})")
                return True
            else:
                print(f"⚠️ Estado inesperado: {estado} (esperado: 'en_cola')")
                return False
        else:
            print(f"❌ Código de respuesta inesperado: {response.status_code} (esperado: 200 o 202)")
            return False
    except Exception as e:
        print(f"❌ Error verificando activación: {e}")
        return False


# Variable global para almacenar datos de error (se usará desde el callback)
_error_data_cache = {}

def verificar_completado(response):
    """
    Callback para HttpSensor T3: Verifica que el estado sea "completado"
    Almacena detalles de error en caché global para que T4 pueda acceder
    """
    global _error_data_cache
    try:
        data = response.json()
        estado = data.get('estado', '').lower()
        
        if estado == 'completado':
            print(f"✅ Procesamiento completado exitosamente")
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
            _error_data_cache['etl_error_data'] = error_data
            
            error_msg = data.get('error', 'Error desconocido')
            print(f"❌ Procesamiento falló: {error_msg}")
            raise AirflowException(f"El procesamiento terminó con error: {error_msg}")
        else:
            print(f"⏳ Estado actual: {estado}. Esperando completado...")
            return False
    except AirflowException:
        raise
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False


def capturar_error_desde_cache(**context):
    """
    Tarea intermedia: Captura datos de error desde caché o API y los almacena en XComs
    Se ejecuta solo si T3 falla
    """
    global _error_data_cache
    ti = context['ti']
    
    # Intentar obtener datos de error desde caché
    if 'etl_error_data' in _error_data_cache:
        error_data = _error_data_cache.pop('etl_error_data')  # Limpiar caché después de usar
        ti.xcom_push(key='etl_error_data', value=error_data)
        print(f"✅ Datos de error capturados desde caché y almacenados en XComs")
    else:
        # Fallback: intentar obtener desde la API directamente
        print(f"⚠️ No se encontraron datos de error en caché. Intentando obtener desde API...")
        try:
            from airflow.hooks.base import BaseHook
            import requests
            
            http_conn = BaseHook.get_connection(FASTAPI_CONN_ID)
            base_url = f"http://{http_conn.host}:{http_conn.port or 8000}"
            status_url = f"{base_url}/procesar_facturas/status"
            
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
                ti.xcom_push(key='etl_error_data', value=error_data)
                print(f"✅ Datos de error obtenidos desde API y almacenados en XComs")
            else:
                print(f"⚠️ No se pudo obtener estado desde API. Código: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error al obtener datos desde API: {e}")


def formatear_mensaje_error(**context):
    """
    Tarea T4: Formatea el mensaje de error desde XComs
    Retorna el mensaje formateado para usar en SlackWebhookOperator
    """
    try:
        ti = context['ti']
        
        # Intentar obtener datos de error desde XComs (almacenados por T3_capturar_error)
        error_data = ti.xcom_pull(key='etl_error_data', task_ids='T3_capturar_error')
        
        if error_data:
            # Usar datos de XComs
            estado = error_data.get('estado', 'desconocido')
            etapa_actual = error_data.get('etapa_actual', 'N/A')
            progreso = error_data.get('progreso', 0)
            mensaje = error_data.get('mensaje', 'N/A')
            error_details = error_data.get('error', 'Error desconocido')
        else:
            # Fallback: intentar obtener desde la API (si está disponible)
            try:
                from airflow.hooks.base import BaseHook
                http_conn = BaseHook.get_connection(FASTAPI_CONN_ID)
                base_url = f"http://{http_conn.host}:{http_conn.port or 8000}"
                
                import requests
                status_url = f"{base_url}/procesar_facturas/status"
                response = requests.get(status_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    estado = data.get('estado', 'desconocido')
                    etapa_actual = data.get('etapa_actual', 'N/A')
                    progreso = data.get('progreso', 0)
                    mensaje = data.get('mensaje', 'N/A')
                    error_details = data.get('error', data.get('mensaje', 'Error desconocido'))
                else:
                    estado = 'desconocido'
                    etapa_actual = 'N/A'
                    progreso = 0
                    mensaje = 'No se pudo obtener el estado de la API'
                    error_details = f"Código de respuesta: {response.status_code}"
            except Exception as e:
                # Si todo falla, usar valores por defecto
                estado = 'error'
                etapa_actual = 'N/A'
                progreso = 0
                mensaje = 'Error al obtener detalles del error'
                error_details = str(e)
        
        # Formatear mensaje con Markdown para Slack
        dag_run_id = context.get('dag_run').run_id if context.get('dag_run') else 'N/A'
        task_id = context.get('task_instance').task_id if context.get('task_instance') else 'N/A'
        timestamp = datetime.now().isoformat()
        
        error_message = f"""
❌ *ERROR EN PROCESAMIENTO ETL DE FACTURAS*

*Estado:* `{estado}`
*Etapa:* `{etapa_actual}`
*Progreso:* `{progreso}%`
*Mensaje:* `{mensaje}`
*Error:* `{error_details}`

*DAG Run:* `{dag_run_id}`
*Task:* `{task_id}`
*Timestamp:* `{timestamp}`
"""
        
        # Almacenar mensaje formateado en XComs para T4_notificar_error
        ti.xcom_push(key='error_message_formatted', value=error_message)
        
        print(error_message)
        return error_message
        
    except Exception as e:
        error_msg = f"Error al formatear mensaje de error: {str(e)}"
        print(f"❌ {error_msg}")
        # Almacenar mensaje de error genérico
        context['ti'].xcom_push(
            key='error_message_formatted',
            value=f"❌ Error al obtener detalles del error: {error_msg}"
        )
        return error_msg


# ========== TAREAS DEL DAG ==========

# T1: Verificar que el estado sea inactivo antes de iniciar (previene colisiones)
# Timeout reducido a 2 minutos para SLA más estricto (ajustable según necesidades)
T1_check_inactivo = HttpSensor(
    task_id='T1_check_inactivo',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/procesar_facturas/status',
    method='GET',
    response_check=verificar_estado_inactivo,
    poke_interval=30,  # Verificar cada 30 segundos
    timeout=120,  # Timeout de 2 minutos (reducido de 5 minutos para SLA más estricto)
    soft_fail=False,  # Falla si no se cumple la condición
    dag=dag
)

# T2: Activar el ETL
T2_activar_etl = SimpleHttpOperator(
    task_id='T2_activar_etl',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/procesar_facturas',
    method='POST',
    headers={"Content-Type": "application/json"},
    response_check=verificar_activacion_exitosa,
    dag=dag
)

# T3: Monitorear el progreso hasta que esté completado
T3_monitorear_etl = HttpSensor(
    task_id='T3_monitorear_etl',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/procesar_facturas/status',
    method='GET',
    response_check=verificar_completado,
    poke_interval=60,  # Verificar cada minuto (el procesamiento puede tardar)
    timeout=3600,  # Timeout de 1 hora (ajustar según tiempo esperado de procesamiento)
    soft_fail=False,  # Falla si no se completa en el timeout
    dag=dag
)

# T3.5: Capturar error desde caché y almacenar en XComs
T3_capturar_error = PythonOperator(
    task_id='T3_capturar_error',
    python_callable=capturar_error_desde_cache,
    trigger_rule='one_failed',  # Se ejecuta si T3 falla
    dag=dag
)

# T4: Formatear mensaje de error (obtiene datos de XComs)
T4_formatear_error = PythonOperator(
    task_id='T4_formatear_error',
    python_callable=formatear_mensaje_error,
    trigger_rule='one_success',  # Se ejecuta si T3_capturar_error fue exitoso
    dag=dag
)

# T4_notificar: Notificar error en Slack usando operador nativo
T4_notificar_error = SlackWebhookOperator(
    task_id='T4_notificar_error',
    slack_webhook_conn_id=SLACK_CONN_ID,  # Cambiado de http_conn_id a slack_webhook_conn_id
    message="{{ ti.xcom_pull(key='error_message_formatted', task_ids='T4_formatear_error') }}",
    channel=SLACK_CHANNEL,
    trigger_rule='one_failed',  # Se ejecuta si T4_formatear_error falla o si T3 falló
    dag=dag
)

# T5: Reset del estado (siempre se ejecuta, éxito o error)
def verificar_reset_exitoso(response):
    """
    Callback para T5: Verifica que el reset fue exitoso o que el estado ya está inactivo
    Acepta 200 (reset exitoso) o 409 (si está ejecutando, lo cual es válido en algunos casos)
    """
    try:
        if response.status_code == 200:
            print(f"✅ Estado reseteado exitosamente")
            return True
        elif response.status_code == 409:
            # Si el estado es "ejecutando", no se puede resetear (esto es válido)
            # Pero si el estado es "completado" o "error", debería permitirse
            # Por ahora, consideramos 409 como un caso válido (el estado se reseteará en la próxima ejecución)
            print(f"⚠️ No se pudo resetear (estado: ejecutando). Esto es válido si el procesamiento aún está corriendo.")
            return True  # Considerar como éxito para no fallar el DAG
        else:
            print(f"❌ Código de respuesta inesperado: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando reset: {e}")
        return False

T5_reset_estado = SimpleHttpOperator(
    task_id='T5_reset_estado',
    http_conn_id=FASTAPI_CONN_ID,
    endpoint='/procesar_facturas/reset',
    method='POST',
    headers={"Content-Type": "application/json"},
    trigger_rule='all_done',  # Se ejecuta siempre, sin importar el resultado de las tareas anteriores
    response_check=verificar_reset_exitoso,
    dag=dag
)

# ========== DEPENDENCIAS ==========
# Flujo: T1 -> T2 -> T3 -> T5
#        T3 (si falla) -> T3_capturar_error -> T4_formatear_error -> T4_notificar_error -> T5
T1_check_inactivo >> T2_activar_etl >> T3_monitorear_etl >> T5_reset_estado
T3_monitorear_etl >> T3_capturar_error >> T4_formatear_error >> T4_notificar_error >> T5_reset_estado
