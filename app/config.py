"""
Configuración centralizada del proyecto
Gestiona todas las variables de entorno
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    # ========== GENERAL ==========
    PROJECT_NAME: str = "ETL Facturas MLOps"
    VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ========== API ==========
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # ========== MYSQL (AWS RDS) - BASE DE DATOS DE NEGOCIO ==========
    # ⚠️ IMPORTANTE: Esta es la base de datos REMOTA en AWS RDS para datos de negocio
    # Tablas: ventas_preventivas, ventas_correctivas, tracking
    # 
    # NOTA: El proyecto usa DOS bases de datos MySQL diferentes:
    # 1. MySQL LOCAL (Docker): Para Airflow y MLflow (facturas_user/facturas_pass)
    # 2. MySQL RDS (AWS): Para datos de negocio (samaca/Mirringa2020) ← ESTA CONFIGURACIÓN
    #
    # Ver: docker/docker-compose.airflow.yml para configuración de MySQL local
    MYSQL_HOST: str = "textil.cof2oucystyr.us-east-1.rds.amazonaws.com"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "samaca"
    MYSQL_PASSWORD: str = "Mirringa2020"
    MYSQL_DATABASE: str = "textil"

    @property
    def MYSQL_URI(self) -> str:
        """
        Genera URI de conexión MySQL para SQLAlchemy
        Conecta a AWS RDS (base de datos remota para datos de negocio)
        """
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    # ========== MLFLOW ==========
    # ⚠️ IMPORTANTE: Puerto 5001 (no 5000) - Verificado en docker-compose.airflow.yml
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"
    MLFLOW_EXPERIMENT_NAME: str = "facturas_classification"

    # ========== GOOGLE CLOUD ==========
    GCP_PROJECT_ID: Optional[str] = None
    GOOGLE_CREDENTIALS_PATH: str = "credentials.json"
    GOOGLE_TOKEN_PATH: str = "token.json"

    # ========== AWS S3 ==========
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "mes-en-curso"  # Nombre del bucket S3
    S3_PREFIX_FACTURAS: str = ""  # Prefijo/carpeta dentro del bucket (vacío si los archivos están en la raíz)

    # ========== SLACK ==========
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_NOTIFICATIONS_ENABLED: bool = False

    # ========== PATHS ==========
    BASE_DIR: str = "."
    MODELS_DIR: str = "modelos"
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"

    # ========== MODEL ==========
    MODEL_INPUT_SIZE: tuple = (224, 224, 3)
    TRAIN_BATCH_SIZE: int = 16
    TRAIN_EPOCHS: int = 50

    # ========== LOGGING ==========
    LOG_LEVEL: str = "INFO"

    class Config:
        # Pydantic Settings lee automáticamente variables de entorno del sistema
        # Docker Compose carga el .env con env_file, así que las variables estarán disponibles como env vars
        case_sensitive = True


# Instancia global
settings = Settings()

# AWS Configuration (opcional)
USE_AWS_INTEGRATION = os.getenv("USE_AWS_INTEGRATION", "false").lower() == "true"

if USE_AWS_INTEGRATION:
    try:
        from app.config_aws import aws_settings, AWSSettings
        logger.info("✅ AWS integration enabled")
        logger.info(f"   AWS Region: {aws_settings.aws_region}")
        logger.info(f"   ECS Cluster: {aws_settings.ecs_cluster_name}")
    except ImportError:
        logger.warning("⚠️  USE_AWS_INTEGRATION=True but AWS modules not available")
        logger.warning("   Install requirements/aws.txt to enable AWS integration")
        USE_AWS_INTEGRATION = False
else:
    logger.debug("AWS integration disabled (USE_AWS_INTEGRATION=false or not set)")
