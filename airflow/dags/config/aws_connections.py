"""
Funciones helper para configuración de AWS en DAGs de Airflow

Proporciona funciones para obtener configuración de red, overrides de contenedores
y conexiones AWS desde Variables de Airflow.
"""
from airflow.models import Variable
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def get_ecs_network_config() -> Dict[str, Any]:
    """
    Obtiene la configuración de red para ECS desde Variables de Airflow
    
    Returns:
        dict: Configuración de red con subnets y security groups
            {
                'awsvpcConfiguration': {
                    'subnets': [...],
                    'securityGroups': [...],
                    'assignPublicIp': 'ENABLED'
                }
            }
    """
    try:
        # Obtener subnets desde Variables (formato: "subnet-xxx,subnet-yyy")
        subnets_str = Variable.get("ECS_SUBNETS", default_var="")
        if subnets_str:
            subnets = [s.strip() for s in subnets_str.split(",") if s.strip()]
        else:
            logger.warning("⚠️ Variable ECS_SUBNETS no configurada, usando lista vacía")
            subnets = []
        
        # Obtener security groups desde Variables (formato: "sg-xxx,sg-yyy")
        security_groups_str = Variable.get("ECS_SECURITY_GROUPS", default_var="")
        if security_groups_str:
            security_groups = [sg.strip() for sg in security_groups_str.split(",") if sg.strip()]
        else:
            logger.warning("⚠️ Variable ECS_SECURITY_GROUPS no configurada, usando lista vacía")
            security_groups = []
        
        network_config = {
            'awsvpcConfiguration': {
                'subnets': subnets,
                'securityGroups': security_groups,
                'assignPublicIp': 'ENABLED'  # Para Fargate sin NAT Gateway
            }
        }
        
        logger.info(f"Configuración de red ECS: {len(subnets)} subnets, {len(security_groups)} security groups")
        
        return network_config
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración de red ECS: {e}")
        # Retornar configuración por defecto vacía
        return {
            'awsvpcConfiguration': {
                'subnets': [],
                'securityGroups': [],
                'assignPublicIp': 'ENABLED'
            }
        }


def get_ecs_overrides(
    environment: Optional[List[Dict[str, str]]] = None,
    command: Optional[List[str]] = None,
    cpu: Optional[str] = None,
    memory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Genera container overrides para ECS tasks
    
    Args:
        environment: Lista de variables de entorno [{"name": "VAR", "value": "val"}]
        command: Comando a ejecutar en el contenedor
        cpu: CPU override (opcional)
        memory: Memory override (opcional)
    
    Returns:
        dict: Container overrides para ECS run_task
    """
    overrides = {}
    
    # Container overrides
    container_overrides = []
    container_override = {}
    
    if environment:
        container_override['environment'] = environment
    
    if command:
        container_override['command'] = command
    
    if container_override:
        container_overrides.append(container_override)
    
    if container_overrides:
        overrides['containerOverrides'] = container_overrides
    
    # Task-level overrides (CPU y Memory)
    if cpu or memory:
        overrides['cpu'] = cpu
        overrides['memory'] = memory
    
    return overrides


def get_aws_conn_id() -> str:
    """
    Obtiene el connection ID de AWS desde Variables de Airflow
    
    Returns:
        str: Connection ID de AWS (default: 'aws_default')
    """
    try:
        conn_id = Variable.get("AWS_CONN_ID", default_var="aws_default")
        logger.debug(f"Usando AWS connection ID: {conn_id}")
        return conn_id
    except Exception as e:
        logger.warning(f"Error obteniendo AWS_CONN_ID, usando default: {e}")
        return "aws_default"


def get_ecs_cluster_name() -> str:
    """
    Obtiene el nombre del cluster ECS desde Variables de Airflow
    
    Returns:
        str: Nombre del cluster (default: 'etl-facturas-cluster')
    """
    try:
        cluster_name = Variable.get("ECS_CLUSTER_NAME", default_var="etl-facturas-cluster")
        logger.debug(f"Usando ECS cluster: {cluster_name}")
        return cluster_name
    except Exception as e:
        logger.warning(f"Error obteniendo ECS_CLUSTER_NAME, usando default: {e}")
        return "etl-facturas-cluster"


def get_fastapi_alb_url() -> Optional[str]:
    """
    Obtiene la URL del ALB de FastAPI desde Variables de Airflow
    
    Returns:
        str: URL del ALB o None si no está configurado
    """
    try:
        alb_url = Variable.get("FASTAPI_ALB_URL", default_var=None)
        if alb_url:
            logger.debug(f"Usando FastAPI ALB URL: {alb_url}")
        return alb_url
    except Exception as e:
        logger.warning(f"Error obteniendo FASTAPI_ALB_URL: {e}")
        return None

