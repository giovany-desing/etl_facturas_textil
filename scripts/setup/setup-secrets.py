#!/usr/bin/env python3
"""
Script para configurar secretos en AWS Secrets Manager.

Este script lee credenciales locales (.env) y las configura
en AWS Secrets Manager para uso en producción.
"""
import argparse
import logging
import os
import sys
import json
from typing import Dict, Optional
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# ========== CONFIGURACIÓN DE LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== SECRETOS A CONFIGURAR ==========
SECRETS_CONFIG = {
    'textil/mysql/credentials': {
        'env_vars': ['MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_HOST', 'MYSQL_DATABASE'],
        'keys': ['user', 'password', 'host', 'database']
    },
    'textil/aws/credentials': {
        'env_vars': ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'],
        'keys': ['access_key_id', 'secret_access_key']
    },
    'textil/google/oauth': {
        'file': 'credentials.json',
        'key': 'credentials'
    },
    'textil/slack/webhook': {
        'env_vars': ['SLACK_WEBHOOK_URL'],
        'keys': ['webhook_url'],
        'optional': True
    }
}


def load_env_file(env_path: str) -> Dict[str, str]:
    """
    Carga variables de entorno desde un archivo .env
    
    Args:
        env_path: Ruta al archivo .env
    
    Returns:
        dict: Diccionario con variables de entorno
    """
    env_vars = {}
    
    if not os.path.exists(env_path):
        logger.warning(f"Archivo .env no encontrado: {env_path}")
        return env_vars
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Ignorar comentarios y líneas vacías
                if not line or line.startswith('#'):
                    continue
                
                # Parsear KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value
        
        logger.info(f"Cargadas {len(env_vars)} variables desde {env_path}")
        return env_vars
        
    except Exception as e:
        logger.error(f"Error leyendo archivo .env: {e}")
        raise


def read_json_file(file_path: str) -> Optional[Dict]:
    """
    Lee un archivo JSON
    
    Args:
        file_path: Ruta al archivo JSON
    
    Returns:
        dict: Contenido del archivo JSON o None si hay error
    """
    if not os.path.exists(file_path):
        logger.warning(f"Archivo no encontrado: {file_path}")
        return None
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo archivo JSON {file_path}: {e}")
        return None


def create_or_update_secret(
    secrets_client,
    secret_name: str,
    secret_value: Dict,
    region: str,
    dry_run: bool = False
) -> bool:
    """
    Crea o actualiza un secreto en AWS Secrets Manager
    
    Args:
        secrets_client: Cliente de boto3 para Secrets Manager
        secret_name: Nombre del secreto
        secret_value: Valor del secreto (dict)
        region: Región AWS
        dry_run: Si es True, solo simula sin crear/actualizar
    
    Returns:
        bool: True si fue exitoso
    """
    try:
        secret_string = json.dumps(secret_value)
        
        if dry_run:
            logger.info(f"[DRY RUN] Crear/actualizar secreto: {secret_name}")
            logger.info(f"[DRY RUN] Valor: {json.dumps(secret_value, indent=2)}")
            return True
        
        # Intentar obtener el secreto existente
        try:
            secrets_client.describe_secret(SecretId=secret_name)
            # Si existe, actualizar
            logger.info(f"Actualizando secreto existente: {secret_name}")
            secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=secret_string
            )
            logger.info(f"✅ Secreto actualizado: {secret_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Si no existe, crear
                logger.info(f"Creando nuevo secreto: {secret_name}")
                secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=secret_string,
                    Description=f"Secreto para {secret_name} - Configurado desde .env"
                )
                logger.info(f"✅ Secreto creado: {secret_name}")
            else:
                raise
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Error con secreto {secret_name}: {error_code} - {error_message}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado con secreto {secret_name}: {e}", exc_info=True)
        return False


def setup_secrets(
    env_path: str,
    region: str,
    dry_run: bool = False,
    project_root: Optional[str] = None
) -> int:
    """
    Configura secretos desde .env en AWS Secrets Manager
    
    Args:
        env_path: Ruta al archivo .env
        region: Región AWS
        dry_run: Si es True, solo simula sin crear/actualizar
        project_root: Ruta raíz del proyecto (para buscar archivos)
    
    Returns:
        int: Número de secretos configurados exitosamente
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Cargar variables de entorno
    env_vars = load_env_file(env_path)
    
    # Crear cliente de Secrets Manager
    try:
        secrets_client = boto3.client('secretsmanager', region_name=region)
    except NoCredentialsError:
        logger.error("No se encontraron credenciales de AWS. Configura AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY")
        return 0
    except Exception as e:
        logger.error(f"Error creando cliente de Secrets Manager: {e}")
        return 0
    
    if dry_run:
        logger.info("=" * 60)
        logger.info("MODO DRY RUN - No se crearán/actualizarán secretos")
        logger.info("=" * 60)
    
    setup_count = 0
    
    # Procesar cada secreto configurado
    for secret_name, config in SECRETS_CONFIG.items():
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Procesando secreto: {secret_name}")
        logger.info(f"{'=' * 60}")
        
        secret_value = {}
        missing_vars = []
        
        # Procesar variables de entorno
        if 'env_vars' in config:
            for env_var, key in zip(config['env_vars'], config['keys']):
                if env_var in env_vars:
                    secret_value[key] = env_vars[env_var]
                else:
                    missing_vars.append(env_var)
        
        # Procesar archivos
        if 'file' in config:
            file_path = os.path.join(project_root, config['file'])
            file_content = read_json_file(file_path)
            if file_content:
                secret_value[config['key']] = json.dumps(file_content)
            else:
                missing_vars.append(config['file'])
        
        # Verificar si es opcional
        if missing_vars and not config.get('optional', False):
            logger.warning(f"⚠️ Variables/archivos faltantes para {secret_name}: {', '.join(missing_vars)}")
            logger.warning(f"   Saltando este secreto (no es opcional)")
            continue
        
        if missing_vars and config.get('optional', False):
            logger.info(f"ℹ️ Variables/archivos faltantes para {secret_name}: {', '.join(missing_vars)}")
            logger.info(f"   Saltando este secreto (es opcional)")
            continue
        
        # Crear o actualizar secreto
        if create_or_update_secret(secrets_client, secret_name, secret_value, region, dry_run):
            setup_count += 1
        else:
            logger.error(f"❌ Error configurando secreto: {secret_name}")
    
    return setup_count


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Configura secretos desde .env en AWS Secrets Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --env .env --region us-east-1
  %(prog)s --env .env --region us-east-1 --dry-run
  %(prog)s --env .env.production --region us-west-2
        """
    )
    
    parser.add_argument(
        '--env',
        type=str,
        default='.env',
        help='Ruta al archivo .env (default: .env)'
    )
    
    parser.add_argument(
        '--region',
        type=str,
        default='us-east-1',
        help='Región AWS (default: us-east-1)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular setup sin crear/actualizar secretos'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default=None,
        help='Ruta raíz del proyecto (default: auto-detect)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SETUP DE SECRETOS EN AWS SECRETS MANAGER")
    logger.info("=" * 60)
    logger.info(f"Archivo .env: {args.env}")
    logger.info(f"Región AWS: {args.region}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)
    
    # Validar que existe el archivo .env
    if not os.path.exists(args.env):
        logger.error(f"Archivo .env no encontrado: {args.env}")
        sys.exit(1)
    
    # Configurar secretos
    setup_count = setup_secrets(
        env_path=args.env,
        region=args.region,
        dry_run=args.dry_run,
        project_root=args.project_root
    )
    
    logger.info("")
    logger.info("=" * 60)
    if args.dry_run:
        logger.info(f"DRY RUN completado: {setup_count} secretos procesados")
    else:
        logger.info(f"Setup completado: {setup_count} secretos configurados exitosamente")
    logger.info("=" * 60)
    
    if setup_count == 0:
        logger.warning("No se configuró ningún secreto. Revisa los logs anteriores.")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()

