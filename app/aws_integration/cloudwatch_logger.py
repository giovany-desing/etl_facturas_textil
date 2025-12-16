"""
Cliente para interactuar con AWS CloudWatch

Proporciona funcionalidad para:
- Enviar métricas custom a CloudWatch
- Enviar eventos de log a CloudWatch Logs
"""
import aioboto3
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
from botocore.exceptions import ClientError, BotoCoreError

from app.config_aws import aws_settings

logger = logging.getLogger(__name__)


class CloudWatchLogger:
    """
    Cliente para interactuar con AWS CloudWatch usando aioboto3
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        namespace: str = "ETLFacturas",
        log_group: Optional[str] = None
    ):
        """
        Inicializa el cliente CloudWatch
        
        Args:
            region_name: Región AWS (default: aws_settings.aws_region)
            aws_access_key_id: AWS Access Key ID (opcional)
            aws_secret_access_key: AWS Secret Access Key (opcional)
            namespace: Namespace para métricas CloudWatch (default: "ETLFacturas")
            log_group: Nombre del log group para CloudWatch Logs (default: aws_settings.cloudwatch_log_group)
        """
        self.region_name = region_name or aws_settings.aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.namespace = namespace
        self.log_group = log_group or aws_settings.cloudwatch_log_group
        
        logger.info(f"CloudWatchLogger inicializado para región: {self.region_name}")
        logger.info(f"Namespace: {self.namespace}, Log Group: {self.log_group}")
    
    async def log_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Envía una métrica custom a CloudWatch
        
        Args:
            metric_name: Nombre de la métrica
            value: Valor de la métrica
            unit: Unidad de la métrica (Count, Bytes, Seconds, etc.) (default: "Count")
            dimensions: Dimensiones opcionales para la métrica
            timestamp: Timestamp de la métrica (default: ahora)
        
        Returns:
            dict: Información de la métrica enviada con keys:
                - metric_name: Nombre de la métrica
                - value: Valor
                - unit: Unidad
                - timestamp: Timestamp
        
        Raises:
            ClientError: Si hay un error al enviar la métrica
        """
        timestamp = timestamp or datetime.utcnow()
        
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": timestamp
        }
        
        if dimensions:
            metric_data["Dimensions"] = dimensions
        
        logger.debug(f"Enviando métrica: {metric_name} = {value} {unit}")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                'cloudwatch',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as cloudwatch_client:
                response = await cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=[metric_data]
                )
                
                result = {
                    "metric_name": metric_name,
                    "value": value,
                    "unit": unit,
                    "timestamp": timestamp.isoformat(),
                    "response_metadata": response.get("ResponseMetadata", {})
                }
                
                logger.debug(f"Métrica {metric_name} enviada exitosamente")
                
                return result
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al enviar métrica: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al enviar métrica: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al enviar métrica: {e}", exc_info=True)
            raise
    
    async def log_event(
        self,
        message: str,
        log_stream: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Envía un evento de log a CloudWatch Logs
        
        Args:
            message: Mensaje del log
            log_stream: Nombre del log stream (default: genera uno basado en timestamp)
            timestamp: Timestamp del evento (default: ahora)
            **kwargs: Campos adicionales para incluir en el log
        
        Returns:
            dict: Información del evento enviado con keys:
                - log_group: Nombre del log group
                - log_stream: Nombre del log stream
                - message: Mensaje
                - timestamp: Timestamp
        
        Raises:
            ClientError: Si hay un error al enviar el log
        """
        timestamp = timestamp or datetime.utcnow()
        
        # Generar log stream si no se proporciona
        if not log_stream:
            log_stream = f"etl-{timestamp.strftime('%Y-%m-%d')}"
        
        # Construir mensaje completo con campos adicionales
        log_message = message
        if kwargs:
            import json
            log_message = json.dumps({
                "message": message,
                **kwargs
            })
        
        logger.debug(f"Enviando log a {self.log_group}/{log_stream}")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                'logs',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as logs_client:
                # Verificar/crear log group si no existe
                try:
                    await logs_client.describe_log_groups(
                        logGroupNamePrefix=self.log_group
                    )
                except ClientError:
                    # Crear log group si no existe
                    logger.info(f"Creando log group: {self.log_group}")
                    await logs_client.create_log_group(logGroupName=self.log_group)
                
                # Verificar/crear log stream si no existe
                try:
                    await logs_client.describe_log_streams(
                        logGroupName=self.log_group,
                        logStreamNamePrefix=log_stream
                    )
                except ClientError:
                    # Crear log stream si no existe
                    logger.debug(f"Creando log stream: {log_stream}")
                    await logs_client.create_log_stream(
                        logGroupName=self.log_group,
                        logStreamName=log_stream
                    )
                
                # Enviar evento de log
                timestamp_ms = int(timestamp.timestamp() * 1000)
                
                response = await logs_client.put_log_events(
                    logGroupName=self.log_group,
                    logStreamName=log_stream,
                    logEvents=[
                        {
                            "timestamp": timestamp_ms,
                            "message": log_message
                        }
                    ]
                )
                
                result = {
                    "log_group": self.log_group,
                    "log_stream": log_stream,
                    "message": message,
                    "timestamp": timestamp.isoformat(),
                    "next_sequence_token": response.get("nextSequenceToken")
                }
                
                logger.debug(f"Log enviado exitosamente a {self.log_group}/{log_stream}")
                
                return result
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al enviar log: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al enviar log: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al enviar log: {e}", exc_info=True)
            raise

