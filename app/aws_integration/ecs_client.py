"""
Cliente para interactuar con AWS ECS (Elastic Container Service)

Proporciona funcionalidad para:
- Ejecutar tareas ECS Fargate
- Consultar estado de tareas
"""
import aioboto3
import logging
from typing import Dict, Optional, List, Any
from botocore.exceptions import ClientError, BotoCoreError

from app.config_aws import aws_settings

logger = logging.getLogger(__name__)


class ECSClient:
    """
    Cliente para interactuar con AWS ECS usando aioboto3
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Inicializa el cliente ECS
        
        Args:
            region_name: Región AWS (default: aws_settings.aws_region)
            aws_access_key_id: AWS Access Key ID (opcional, usa credenciales por defecto si no se proporciona)
            aws_secret_access_key: AWS Secret Access Key (opcional)
        """
        self.region_name = region_name or aws_settings.aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        
        # Configuración desde settings
        self.cluster_name = aws_settings.ecs_cluster_name
        self.task_definition = aws_settings.ecs_task_definition_training
        self.subnets = aws_settings.ecs_subnets
        self.security_groups = aws_settings.ecs_security_groups
        
        logger.info(f"ECSClient inicializado para región: {self.region_name}")
        logger.info(f"Cluster: {self.cluster_name}, Task Definition: {self.task_definition}")
    
    async def run_task(
        self,
        task_definition: Optional[str] = None,
        cluster_name: Optional[str] = None,
        launch_type: str = "FARGATE",
        subnets: Optional[List[str]] = None,
        security_groups: Optional[List[str]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        command: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ejecuta una tarea ECS Fargate
        
        Args:
            task_definition: Nombre de la task definition (default: aws_settings.ecs_task_definition_training)
            cluster_name: Nombre del cluster ECS (default: aws_settings.ecs_cluster_name)
            launch_type: Tipo de lanzamiento (default: "FARGATE")
            subnets: Lista de subnet IDs (default: aws_settings.ecs_subnets)
            security_groups: Lista de security group IDs (default: aws_settings.ecs_security_groups)
            environment_variables: Variables de entorno para la tarea
            command: Comando a ejecutar en el contenedor
            **kwargs: Argumentos adicionales para run_task
        
        Returns:
            dict: Información de la tarea ejecutada con keys:
                - task_arn: ARN de la tarea
                - task_id: ID de la tarea
                - cluster: Nombre del cluster
                - desired_status: Estado deseado
                - last_status: Último estado conocido
        
        Raises:
            ClientError: Si hay un error al ejecutar la tarea
        """
        task_definition = task_definition or self.task_definition
        cluster_name = cluster_name or self.cluster_name
        subnets = subnets or self.subnets
        security_groups = security_groups or self.security_groups
        
        if not subnets:
            raise ValueError("subnets es requerido para ejecutar tareas Fargate")
        
        # Preparar configuración de red
        network_configuration = {
            "awsvpcConfiguration": {
                "subnets": subnets,
                "assignPublicIp": "ENABLED"  # Para Fargate sin NAT Gateway
            }
        }
        
        if security_groups:
            network_configuration["awsvpcConfiguration"]["securityGroups"] = security_groups
        
        # Preparar overrides del contenedor
        container_overrides = []
        if environment_variables or command:
            container_override = {}
            
            if environment_variables:
                container_override["environment"] = [
                    {"name": k, "value": v}
                    for k, v in environment_variables.items()
                ]
            
            if command:
                container_override["command"] = command
            
            container_overrides.append(container_override)
        
        # Preparar parámetros para run_task
        run_task_params = {
            "cluster": cluster_name,
            "taskDefinition": task_definition,
            "launchType": launch_type,
            "networkConfiguration": network_configuration,
            **kwargs
        }
        
        if container_overrides:
            run_task_params["overrides"] = {
                "containerOverrides": container_overrides
            }
        
        logger.info(f"Ejecutando tarea ECS: {task_definition} en cluster {cluster_name}")
        logger.debug(f"Parámetros: {run_task_params}")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                'ecs',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as ecs_client:
                response = await ecs_client.run_task(**run_task_params)
                
                if not response.get("tasks"):
                    raise ValueError("No se recibieron tareas en la respuesta")
                
                task = response["tasks"][0]
                task_arn = task["taskArn"]
                
                # Extraer task ID del ARN
                task_id = task_arn.split("/")[-1]
                
                result = {
                    "task_arn": task_arn,
                    "task_id": task_id,
                    "cluster": task.get("clusterArn", "").split("/")[-1],
                    "desired_status": task.get("desiredStatus", "UNKNOWN"),
                    "last_status": task.get("lastStatus", "UNKNOWN"),
                    "created_at": task.get("createdAt").isoformat() if task.get("createdAt") else None
                }
                
                logger.info(f"Tarea ejecutada exitosamente: {task_id}")
                logger.info(f"ARN: {task_arn}")
                
                return result
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al ejecutar tarea: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al ejecutar tarea: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al ejecutar tarea: {e}", exc_info=True)
            raise
    
    async def get_task_status(
        self,
        task_arn: str,
        cluster_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene el estado actual de una tarea ECS
        
        Args:
            task_arn: ARN completo de la tarea
            cluster_name: Nombre del cluster (default: aws_settings.ecs_cluster_name)
        
        Returns:
            dict: Información del estado de la tarea con keys:
                - task_arn: ARN de la tarea
                - task_id: ID de la tarea
                - last_status: Último estado (PENDING, RUNNING, STOPPED, etc.)
                - desired_status: Estado deseado
                - stopped_reason: Razón de detención (si aplica)
                - exit_code: Código de salida del contenedor (si aplica)
                - stopped_at: Fecha de detención (si aplica)
        
        Raises:
            ClientError: Si hay un error al consultar la tarea
        """
        cluster_name = cluster_name or self.cluster_name
        
        logger.debug(f"Consultando estado de tarea: {task_arn}")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                'ecs',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as ecs_client:
                response = await ecs_client.describe_tasks(
                    cluster=cluster_name,
                    tasks=[task_arn]
                )
                
                if not response.get("tasks"):
                    raise ValueError(f"Tarea no encontrada: {task_arn}")
                
                task = response["tasks"][0]
                task_id = task_arn.split("/")[-1]
                
                # Obtener información del contenedor
                containers = task.get("containers", [])
                container_info = {}
                if containers:
                    container = containers[0]
                    container_info = {
                        "exit_code": container.get("exitCode"),
                        "reason": container.get("reason"),
                        "last_status": container.get("lastStatus")
                    }
                
                result = {
                    "task_arn": task_arn,
                    "task_id": task_id,
                    "last_status": task.get("lastStatus", "UNKNOWN"),
                    "desired_status": task.get("desiredStatus", "UNKNOWN"),
                    "stopped_reason": task.get("stoppedReason"),
                    "stopped_at": task.get("stoppedAt").isoformat() if task.get("stoppedAt") else None,
                    "started_at": task.get("startedAt").isoformat() if task.get("startedAt") else None,
                    "created_at": task.get("createdAt").isoformat() if task.get("createdAt") else None,
                    **container_info
                }
                
                logger.debug(f"Estado de tarea {task_id}: {result['last_status']}")
                
                return result
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al consultar tarea: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al consultar tarea: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al consultar tarea: {e}", exc_info=True)
            raise

