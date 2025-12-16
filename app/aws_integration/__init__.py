"""
Módulo de integración con servicios AWS.

Clientes async para interactuar con:
- ECS (lanzar tasks de training)
- Secrets Manager (credenciales seguras)
- CloudWatch (métricas y logs)
- S3 (storage mejorado)
"""
from app.aws_integration.ecs_client import ECSClient
from app.aws_integration.secrets_manager import SecretsManagerClient
from app.aws_integration.cloudwatch_logger import CloudWatchLogger

__all__ = [
    "ECSClient",
    "SecretsManagerClient",
    "CloudWatchLogger",
]

