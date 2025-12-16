"""
Utilidades generales - logging y helpers
Reciclado de utils/log_utils.py
"""
import logging
import sys
from app.config import settings


def setup_logger(name: str = "etl_facturas") -> logging.Logger:
    """
    Configura y retorna un logger
    Reciclado de utils/log_utils.py
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Función auxiliar para compatibilidad
def logs():
    """Función para compatibilidad con código original"""
    return setup_logger()
