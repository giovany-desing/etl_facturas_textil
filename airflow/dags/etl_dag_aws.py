"""
DAG de Airflow para procesamiento ETL de facturas con inferencia del modelo - Versión AWS

ROL: Orquestar el flujo de ETL usando AWS ECS Fargate o ALB.
     - Opción 1: Lanzar task ECS Fargate para procesamiento
     - Opción 2: Llamar endpoint POST /procesar_facturas al ALB
     - Monitorea el progreso hasta completar
     - Maneja errores y notificaciones
     - Limpia el estado al finalizar
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python import PythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.exceptions import AirflowException
from airflow.models import Variable

import sys
import os
# Agregar path para imports locales
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.aws_connections import (
    get_ecs_network_config,
    get_aws_conn_id,
    get_ecs_cluster_name,
    get_fastapi_alb_url
)

# ========== CONSTANTES ==========
SLACK_CONN_ID = 'slack_webhook'
SLACK_CHANNEL = '#mlops-alerts'

# Determinar si usar ECS o ALB (desde Variable de Airflow)
USE_ECS_TASK = Variable.get("ETL_USE_ECS_TASK", default_var="false").lower() == "true"

default_args = {
    'owner': 'mlops',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'process_invoices_etl_aws',
    default_args=default_args,
    description='Procesamiento ETL de facturas con inferencia del modelo - AWS ECS/MWAA',
    schedule_interval='0 * * * *',  # Cada hora en el minuto 0
    catchup=False,
    max_active_runs=1,
    tags=['aws', 'etl', 'facturas', 'hourly', 'inference', 'ecs']
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
    Callback para T2: Verifica que la respuesta contenga "estado": "en_cola"
    """
    try:
        if response.status_code in [200, 202]:
            data = response.json()
            estado = data.get('estado', '')
            if estado == 'en_cola':
                print(f"✅ ETL activado exitosamente. Estado: {estado}")
                return True
            else:
                print(f"⚠️ Estado inesperado: {estado} (esperado: 'en_cola')")
                return False
        else:
            print(f"❌ Código de respuesta inesperado: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verificando activación: {e}")
        return False


_error_data_cache = {}


def verificar_completado(response):
    """
    Callback para HttpSensor T3: Verifica que el estado sea "completado"
    """
    global _error_data_cache
    try:
        data = response.json()
        estado = data.get('estado', '').lower()
        
        if estado == 'completado':
            print(f"✅ Procesamiento completado exitosamente")
            return True
        elif estado == 'error':
            error_data = {
                'estado': data.get('estado', 'desconocido'),
                'etapa_actual': data.get('etapa_actual', 'N/A'),
                'progreso': data.get('progreso', 0),
                'mensaje': data.get('mensaje', 'N/A'),
                'error': data.get('error', 'Error desconocido'),
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
    """Captura datos de error desde caché y los almacena en XComs"""
    global _error_data_cache
    ti = context['ti']
    
    if 'etl_error_data' in _error_data_cache:
        error_data = _error_data_cache.pop('etl_error_data')
        ti.xcom_push(key='etl_error_data', value=error_data)
        print(f"✅ Datos de error capturados desde caché")
    else:
        print(f"⚠️ No se encontraron datos de error en caché")


def formatear_mensaje_error(**context):
    """Formatea el mensaje de error desde XComs"""
    try:
        ti = context['ti']
        error_data = ti.xcom_pull(key='etl_error_data', task_ids='T3_capturar_error')
        
        if error_data:
            estado = error_data.get('estado', 'desconocido')
            etapa_actual = error_data.get('etapa_actual', 'N/A')
            progreso = error_data.get('progreso', 0)
            mensaje = error_data.get('mensaje', 'N/A')
            error_details = error_data.get('error', 'Error desconocido')
        else:
            estado = 'error'
            etapa_actual = 'N/A'
            progreso = 0
            mensaje = 'Error al obtener detalles del error'
            error_details = 'No se pudieron obtener detalles'
        
        dag_run_id = context.get('dag_run').run_id if context.get('dag_run') else 'N/A'
        timestamp = datetime.now().isoformat()
        
        error_message = f"""
❌ *ERROR EN PROCESAMIENTO ETL DE FACTURAS (AWS)*

*Estado:* `{estado}`
*Etapa:* `{etapa_actual}`
*Progreso:* `{progreso}%`
*Mensaje:* `{mensaje}`
*Error:* `{error_details}`

*DAG Run:* `{dag_run_id}`
*Timestamp:* `{timestamp}`
"""
        
        ti.xcom_push(key='error_message_formatted', value=error_message)
        return error_message
        
    except Exception as e:
        error_msg = f"Error al formatear mensaje de error: {str(e)}"
        context['ti'].xcom_push(key='error_message_formatted', value=error_msg)
        return error_msg


# ========== TAREAS DEL DAG ==========

# T1: Verificar que el estado sea inactivo antes de iniciar
# Usar ALB URL si está disponible, sino usar connection
alb_url = get_fastapi_alb_url()
if alb_url:
    status_url = f"{alb_url}/procesar_facturas/status"
    T1_check_inactivo = HttpSensor(
        task_id='T1_check_inactivo',
        http_conn_id=None,
        endpoint=status_url,
        method='GET',
        response_check=verificar_estado_inactivo,
        poke_interval=30,
        timeout=120,
        soft_fail=False,
        dag=dag
    )
else:
    # Fallback: usar connection (requiere configuración en Airflow)
    T1_check_inactivo = HttpSensor(
        task_id='T1_check_inactivo',
        http_conn_id='fastapi_etl',
        endpoint='/procesar_facturas/status',
        method='GET',
        response_check=verificar_estado_inactivo,
        poke_interval=30,
        timeout=120,
        soft_fail=False,
        dag=dag
    )

# T2: Activar el ETL
if USE_ECS_TASK:
    # Opción 1: Lanzar task ECS Fargate
    network_config = get_ecs_network_config()
    
    T2_activar_etl = EcsRunTaskOperator(
        task_id='T2_activar_etl',
        aws_conn_id=get_aws_conn_id(),
        cluster=get_ecs_cluster_name(),
        task_definition='fastapi-service',
        launch_type='FARGATE',
        network_configuration=network_config,
        overrides={
            'containerOverrides': [
                {
                    'name': 'fastapi',
                    'command': ['python', '-c', 'from app.main import ejecutar_procesamiento_completo; ejecutar_procesamiento_completo()']
                }
            ]
        },
        awslogs_group='/ecs/fastapi',
        awslogs_stream_prefix='etl',
        awslogs_region='us-east-1',
        dag=dag
    )
else:
    # Opción 2: Llamar endpoint ALB
    if alb_url:
        activate_url = f"{alb_url}/procesar_facturas"
        T2_activar_etl = SimpleHttpOperator(
            task_id='T2_activar_etl',
            http_conn_id=None,
            endpoint=activate_url,
            method='POST',
            headers={"Content-Type": "application/json"},
            response_check=verificar_activacion_exitosa,
            dag=dag
        )
    else:
        T2_activar_etl = SimpleHttpOperator(
            task_id='T2_activar_etl',
            http_conn_id='fastapi_etl',
            endpoint='/procesar_facturas',
            method='POST',
            headers={"Content-Type": "application/json"},
            response_check=verificar_activacion_exitosa,
            dag=dag
        )

# T3: Monitorear el progreso hasta que esté completado
if alb_url:
    T3_monitorear_etl = HttpSensor(
        task_id='T3_monitorear_etl',
        http_conn_id=None,
        endpoint=status_url,
        method='GET',
        response_check=verificar_completado,
        poke_interval=60,
        timeout=3600,
        soft_fail=False,
        dag=dag
    )
else:
    T3_monitorear_etl = HttpSensor(
        task_id='T3_monitorear_etl',
        http_conn_id='fastapi_etl',
        endpoint='/procesar_facturas/status',
        method='GET',
        response_check=verificar_completado,
        poke_interval=60,
        timeout=3600,
        soft_fail=False,
        dag=dag
    )

# T3.5: Capturar error
T3_capturar_error = PythonOperator(
    task_id='T3_capturar_error',
    python_callable=capturar_error_desde_cache,
    trigger_rule='one_failed',
    dag=dag
)

# T4: Formatear mensaje de error
T4_formatear_error = PythonOperator(
    task_id='T4_formatear_error',
    python_callable=formatear_mensaje_error,
    trigger_rule='one_success',
    dag=dag
)

# T4_notificar: Notificar error en Slack
T4_notificar_error = SlackWebhookOperator(
    task_id='T4_notificar_error',
    slack_webhook_conn_id=SLACK_CONN_ID,
    message="{{ ti.xcom_pull(key='error_message_formatted', task_ids='T4_formatear_error') }}",
    channel=SLACK_CHANNEL,
    trigger_rule='one_failed',
    dag=dag
)

# T5: Reset del estado (siempre se ejecuta)
if alb_url:
    reset_url = f"{alb_url}/procesar_facturas/reset"
    T5_reset_estado = SimpleHttpOperator(
        task_id='T5_reset_estado',
        http_conn_id=None,
        endpoint=reset_url,
        method='POST',
        headers={"Content-Type": "application/json"},
        trigger_rule='all_done',
        response_check=lambda response: response.status_code in [200, 202, 409],
        dag=dag
    )
else:
    T5_reset_estado = SimpleHttpOperator(
        task_id='T5_reset_estado',
        http_conn_id='fastapi_etl',
        endpoint='/procesar_facturas/reset',
        method='POST',
        headers={"Content-Type": "application/json"},
        trigger_rule='all_done',
        response_check=lambda response: response.status_code in [200, 202, 409],
        dag=dag
    )

# ========== DEPENDENCIAS ==========
T1_check_inactivo >> T2_activar_etl >> T3_monitorear_etl >> T5_reset_estado
T3_monitorear_etl >> T3_capturar_error >> T4_formatear_error >> T4_notificar_error >> T5_reset_estado

