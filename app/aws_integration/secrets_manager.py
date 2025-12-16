"""
Cliente para interactuar con AWS Secrets Manager

Proporciona funcionalidad para:
- Obtener secretos con caché en memoria
- Actualizar secretos
"""
import aioboto3
import logging
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError, BotoCoreError
import json
from datetime import datetime, timedelta

from app.config_aws import aws_settings

logger = logging.getLogger(__name__)


class SecretsManagerClient:
    """
    Cliente para interactuar con AWS Secrets Manager usando aioboto3
    Incluye caché en memoria para reducir llamadas a la API
    """
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        cache_ttl_seconds: int = 300
    ):
        """
        Inicializa el cliente Secrets Manager
        
        Args:
            region_name: Región AWS (default: aws_settings.aws_region)
            aws_access_key_id: AWS Access Key ID (opcional)
            aws_secret_access_key: AWS Secret Access Key (opcional)
            cache_ttl_seconds: TTL del caché en segundos (default: 300 = 5 minutos)
        """
        self.region_name = region_name or aws_settings.aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.cache_ttl_seconds = cache_ttl_seconds
        
        # Caché en memoria: {secret_name: {"value": ..., "expires_at": ...}}
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"SecretsManagerClient inicializado para región: {self.region_name}")
        logger.info(f"Cache TTL: {cache_ttl_seconds} segundos")
    
    def _is_cache_valid(self, secret_name: str) -> bool:
        """
        Verifica si el caché para un secreto es válido
        
        Args:
            secret_name: Nombre del secreto
        
        Returns:
            bool: True si el caché es válido, False en caso contrario
        """
        if secret_name not in self._cache:
            return False
        
        cache_entry = self._cache[secret_name]
        expires_at = cache_entry.get("expires_at")
        
        if not expires_at:
            return False
        
        return datetime.utcnow() < expires_at
    
    def _get_from_cache(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un secreto del caché si es válido
        
        Args:
            secret_name: Nombre del secreto
        
        Returns:
            dict: Valor del secreto o None si no está en caché o expiró
        """
        if self._is_cache_valid(secret_name):
            logger.debug(f"Secreto {secret_name} obtenido del caché")
            return self._cache[secret_name]["value"]
        else:
            # Limpiar entrada expirada
            if secret_name in self._cache:
                del self._cache[secret_name]
            return None
    
    def _set_cache(self, secret_name: str, value: Dict[str, Any]) -> None:
        """
        Almacena un secreto en el caché
        
        Args:
            secret_name: Nombre del secreto
            value: Valor del secreto
        """
        expires_at = datetime.utcnow() + timedelta(seconds=self.cache_ttl_seconds)
        self._cache[secret_name] = {
            "value": value,
            "expires_at": expires_at
        }
        logger.debug(f"Secreto {secret_name} almacenado en caché hasta {expires_at}")
    
    async def get_secret(
        self,
        secret_name: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Obtiene un secreto de AWS Secrets Manager
        
        Args:
            secret_name: Nombre del secreto (puede incluir el prefijo)
            use_cache: Si usar caché (default: True)
        
        Returns:
            dict: Contenido del secreto parseado como JSON
        
        Raises:
            ClientError: Si hay un error al obtener el secreto
            ValueError: Si el secreto no es JSON válido
        """
        # Construir nombre completo del secreto si tiene prefijo
        if not secret_name.startswith(aws_settings.secrets_prefix):
            full_secret_name = f"{aws_settings.secrets_prefix}{secret_name}"
        else:
            full_secret_name = secret_name
        
        # Intentar obtener del caché
        if use_cache:
            cached_value = self._get_from_cache(full_secret_name)
            if cached_value is not None:
                return cached_value
        
        logger.info(f"Obteniendo secreto: {full_secret_name}")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                'secretsmanager',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as secrets_client:
                response = await secrets_client.get_secret_value(
                    SecretId=full_secret_name
                )
                
                # Parsear el secreto (puede ser JSON string o plain text)
                secret_string = response.get("SecretString", "")
                
                if not secret_string:
                    raise ValueError(f"Secreto {full_secret_name} está vacío")
                
                # Intentar parsear como JSON
                try:
                    secret_value = json.loads(secret_string)
                except json.JSONDecodeError:
                    # Si no es JSON, retornar como texto plano
                    logger.warning(f"Secreto {full_secret_name} no es JSON válido, retornando como texto")
                    secret_value = {"value": secret_string}
                
                # Almacenar en caché
                if use_cache:
                    self._set_cache(full_secret_name, secret_value)
                
                logger.info(f"Secreto {full_secret_name} obtenido exitosamente")
                
                return secret_value
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al obtener secreto: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al obtener secreto: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al obtener secreto: {e}", exc_info=True)
            raise
    
    async def update_secret(
        self,
        secret_name: str,
        secret_value: Dict[str, Any],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza un secreto en AWS Secrets Manager
        
        Args:
            secret_name: Nombre del secreto
            secret_value: Nuevo valor del secreto (será convertido a JSON)
            description: Descripción opcional del secreto
        
        Returns:
            dict: Información de la actualización con keys:
                - arn: ARN del secreto
                - name: Nombre del secreto
                - version_id: ID de la versión
        
        Raises:
            ClientError: Si hay un error al actualizar el secreto
        """
        # Construir nombre completo del secreto si tiene prefijo
        if not secret_name.startswith(aws_settings.secrets_prefix):
            full_secret_name = f"{aws_settings.secrets_prefix}{secret_name}"
        else:
            full_secret_name = secret_name
        
        logger.info(f"Actualizando secreto: {full_secret_name}")
        
        try:
            # Convertir valor a JSON string
            secret_string = json.dumps(secret_value)
            
            session = aioboto3.Session()
            async with session.client(
                'secretsmanager',
                region_name=self.region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            ) as secrets_client:
                update_params = {
                    "SecretId": full_secret_name,
                    "SecretString": secret_string
                }
                
                if description:
                    update_params["Description"] = description
                
                response = await secrets_client.update_secret(**update_params)
                
                # Invalidar caché
                if full_secret_name in self._cache:
                    del self._cache[full_secret_name]
                    logger.debug(f"Caché invalidado para {full_secret_name}")
                
                result = {
                    "arn": response.get("ARN", ""),
                    "name": response.get("Name", full_secret_name),
                    "version_id": response.get("VersionId", "")
                }
                
                logger.info(f"Secreto {full_secret_name} actualizado exitosamente")
                
                return result
                
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Error de AWS al actualizar secreto: {error_code} - {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Error de boto3 al actualizar secreto: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al actualizar secreto: {e}", exc_info=True)
            raise

