"""
Módulo de integración con servicios AWS

Proporciona clientes para interactuar con:
- ECS (Elastic Container Service)
- Secrets Manager
- CloudWatch
"""
from app.aws_integration.ecs_client import ECSClient
from app.aws_integration.secrets_manager import SecretsManagerClient
from app.aws_integration.cloudwatch_logger import CloudWatchLogger

__all__ = [
    "ECSClient",
    "SecretsManagerClient",
    "CloudWatchLogger",
]

