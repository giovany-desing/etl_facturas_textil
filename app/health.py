"""
Health checks para Application Load Balancer (ALB) de AWS.

Endpoints diseñados para health checks, readiness y liveness probes
en ECS Fargate. Verifican conectividad a dependencias (DB, modelo).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime
import os
import logging

from app.config import settings
from app.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthCheckResponse(BaseModel):
    """Respuesta de health check"""
    status: str
    timestamp: str
    checks: Dict[str, Dict[str, str]]


class ReadinessResponse(BaseModel):
    """Respuesta de readiness check"""
    status: str
    timestamp: str


class LivenessResponse(BaseModel):
    """Respuesta de liveness check"""
    status: str
    timestamp: str


def check_database() -> Dict[str, str]:
    """
    Verifica la conexión a MySQL
    
    Returns:
        dict: Estado de la verificación de base de datos
    """
    try:
        db = get_db()
        try:
            # Ejecutar query simple para verificar conexión
            db.execute(text("SELECT 1"))
            db.close()
            return {
                "status": "healthy",
                "message": "Database connection successful"
            }
        except Exception as e:
            db.close()
            logger.error(f"Database check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Database check error: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database check error: {str(e)}"
        }


def check_model() -> Dict[str, str]:
    """
    Verifica que el modelo existe en la ruta configurada
    
    Returns:
        dict: Estado de la verificación del modelo
    """
    try:
        # Construir ruta del modelo
        model_path = os.path.join(settings.BASE_DIR, settings.MODELS_DIR)
        
        if not os.path.exists(model_path):
            return {
                "status": "unhealthy",
                "message": f"Models directory does not exist: {model_path}"
            }
        
        # Buscar modelos .h5
        modelos_disponibles = [f for f in os.listdir(model_path) if f.endswith('.h5')]
        
        if not modelos_disponibles:
            return {
                "status": "unhealthy",
                "message": f"No .h5 models found in {model_path}"
            }
        
        # Verificar modelo preferido
        modelos_preferidos = [
            'modelo_facturas_final.h5',
            'mejor_modelo.h5',
            'modelo_entrenado.h5'
        ]
        
        modelo_encontrado = None
        for modelo_preferido in modelos_preferidos:
            if modelo_preferido in modelos_disponibles:
                modelo_encontrado = modelo_preferido
                break
        
        if modelo_encontrado:
            return {
                "status": "healthy",
                "message": f"Model found: {modelo_encontrado}"
            }
        else:
            return {
                "status": "healthy",
                "message": f"Model found: {modelos_disponibles[0]}"
            }
            
    except Exception as e:
        logger.error(f"Model check error: {e}")
        return {
            "status": "unhealthy",
            "message": f"Model check error: {str(e)}"
        }


@router.get("", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check completo para ALB
    
    Verifica:
    - Conexión a base de datos MySQL
    - Existencia del modelo
    
    Returns:
        HealthCheckResponse: Estado completo de la aplicación
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Ejecutar checks
    db_check = check_database()
    model_check = check_model()
    
    # Determinar estado general
    all_healthy = (
        db_check["status"] == "healthy" and
        model_check["status"] == "healthy"
    )
    
    status = "healthy" if all_healthy else "unhealthy"
    
    # Si algún check falla, retornar 503
    if not all_healthy:
        raise HTTPException(
            status_code=503,
            detail={
                "status": status,
                "timestamp": timestamp,
                "checks": {
                    "database": db_check,
                    "model": model_check
                }
            }
        )
    
    return HealthCheckResponse(
        status=status,
        timestamp=timestamp,
        checks={
            "database": db_check,
            "model": model_check
        }
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check - Verifica que la aplicación está lista para recibir tráfico
    
    La aplicación está lista si:
    - La base de datos está accesible
    - El modelo está disponible
    
    Returns:
        ReadinessResponse: Estado de readiness
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Verificar readiness (menos estricto que health)
    db_check = check_database()
    
    if db_check["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "timestamp": timestamp,
                "message": "Application is not ready to receive traffic"
            }
        )
    
    return ReadinessResponse(
        status="ready",
        timestamp=timestamp
    )


@router.get("/live", response_model=LivenessResponse)
async def liveness_check():
    """
    Liveness check - Verifica que la aplicación está viva
    
    Este check es simple y solo verifica que la aplicación responde.
    No verifica dependencias externas.
    
    Returns:
        LivenessResponse: Estado de liveness
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return LivenessResponse(
        status="alive",
        timestamp=timestamp
    )

