"""
Configuración AWS para arquitectura cloud-native.

Este módulo gestiona settings específicos de servicios AWS utilizados
en producción: ECS Fargate, Secrets Manager, S3, CloudWatch, MWAA.

La configuración se carga desde variables de entorno con el prefijo AWS_
y permite deployment en múltiples ambientes (dev, staging, production).
"""
from pydantic_settings import BaseSettings
from typing import Optional, List


class AWSSettings(BaseSettings):
    """Configuración de servicios AWS"""
    
    # ========== AWS GENERAL ==========
    aws_region: str = "us-east-1"
    aws_account_id: Optional[str] = None
    
    # ========== ECS (Elastic Container Service) ==========
    ecs_cluster_name: str = "etl-facturas-cluster"
    ecs_task_definition_training: str = "model-training"
    ecs_subnets: List[str] = []
    ecs_security_groups: List[str] = []
    
    # ========== SECRETS MANAGER ==========
    secrets_prefix: str = "textil/"
    mysql_secret_name: str = "textil/mysql/credentials"
    
    # ========== S3 BUCKETS ==========
    s3_bucket_facturas: str = "mes-en-curso"
    s3_bucket_modelos: str = "textil-modelos"
    s3_bucket_mlflow: str = "textil-mlflow-artifacts"
    
    # ========== CLOUDWATCH ==========
    cloudwatch_log_group: str = "/ecs/facturas-etl"
    
    # ========== MWAA (Managed Workflows for Apache Airflow) ==========
    mwaa_environment_name: str = "etl-facturas-airflow"
    
    class Config:
        env_prefix = "AWS_"
        env_file = ".env.aws"
        case_sensitive = False
        # Permitir variables de entorno con guiones bajos o guiones
        extra = "ignore"


# Instancia global
aws_settings = AWSSettings()

