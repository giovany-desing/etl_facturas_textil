"""
Capa de base de datos - MySQL con SQLAlchemy
Migrado de utils/connect_sql.py (SQL Server → MySQL)

⚠️ IMPORTANTE - ARQUITECTURA DE BASES DE DATOS:
Este módulo se conecta a MySQL RDS (AWS) para datos de negocio:
- Tablas: ventas_preventivas, ventas_correctivas, tracking
- Host: textil.cof2oucystyr.us-east-1.rds.amazonaws.com
- Usuario: samaca

El proyecto usa DOS bases de datos MySQL diferentes:
1. MySQL LOCAL (Docker): Para Airflow y MLflow
   - Host: mysql (contenedor Docker)
   - Usuario: facturas_user
   - Bases: airflow, mlflow, facturas_db
   
2. MySQL RDS (AWS): Para datos de negocio ← ESTE MÓDULO
   - Host: textil.cof2oucystyr.us-east-1.rds.amazonaws.com
   - Usuario: samaca
   - Base: textil
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, DECIMAL, Boolean, TIMESTAMP, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import List, Optional, Dict, Any
import mysql.connector
import json
import subprocess
import os

from app.config import settings
from app.utils import setup_logger

logger = setup_logger(__name__)

Base = declarative_base()


# ========== MODELOS SQLALCHEMY ==========

class VentaPreventiva(Base):
    """Tabla de ventas preventivas"""
    __tablename__ = 'ventas_preventivas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    orden_compra = Column(Integer, nullable=False, index=True)
    producto = Column(String(500), nullable=True)
    fecha_creacion = Column(DateTime, nullable=True)
    cantidad = Column(Integer, nullable=True)
    total = Column(Float, nullable=True)


class VentaCorrectiva(Base):
    """Tabla de ventas correctivas"""
    __tablename__ = 'ventas_correctivas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    orden_compra = Column(Integer, nullable=False, index=True)
    producto = Column(String(500), nullable=True)
    fecha_creacion = Column(DateTime, nullable=True)
    cantidad = Column(Integer, nullable=True)
    total = Column(Float, nullable=True)


class TrackingEntrenamiento(Base):
    """Tabla de tracking de entrenamiento del modelo - Estructura real de la BD"""
    __tablename__ = 'tracking'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mlflow_run_id = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.now, server_default='CURRENT_TIMESTAMP')
    
    # Arquitectura del modelo
    filtros_conv1 = Column(Integer, nullable=True)
    filtros_conv2 = Column(Integer, nullable=True)
    filtros_conv3 = Column(Integer, nullable=True)
    neuronas_dense1 = Column(Integer, nullable=True)
    neuronas_dense2 = Column(Integer, nullable=True)
    dropout1 = Column(DECIMAL(5, 4), nullable=True)
    dropout2 = Column(DECIMAL(5, 4), nullable=True)
    
    # Hiperparámetros
    learning_rate = Column(DECIMAL(10, 8), nullable=True)
    optimizer = Column(String(50), nullable=True)
    batch_size = Column(Integer, nullable=True)
    epochs = Column(Integer, nullable=True)
    validation_split = Column(DECIMAL(5, 4), nullable=True)
    early_stopping_patience = Column(Integer, nullable=True)
    reduce_lr_patience = Column(Integer, nullable=True)
    reduce_lr_factor = Column(DECIMAL(5, 4), nullable=True)
    
    # Configuración de entrada
    input_shape = Column(String(50), nullable=True)
    
    # Optuna
    usar_optuna = Column(Boolean, nullable=True, default=False)
    n_trials_optuna = Column(Integer, nullable=True)
    
    # Loss y métricas
    loss = Column(String(100), nullable=True)
    metrics = Column(String(200), nullable=True)
    
    # Métricas de test
    test_loss = Column(DECIMAL(10, 6), nullable=True)
    test_accuracy = Column(DECIMAL(10, 6), nullable=True)
    test_precision = Column(DECIMAL(10, 6), nullable=True)
    test_recall = Column(DECIMAL(10, 6), nullable=True)
    
    # Métricas de validación finales
    val_accuracy_final = Column(DECIMAL(10, 6), nullable=True)
    val_loss_final = Column(DECIMAL(10, 6), nullable=True)
    
    # Versionado
    dvc_hash = Column(String(255), nullable=True)
    dvc_hash_short = Column(String(8), nullable=True)
    git_commit_hash = Column(String(255), nullable=True)
    git_commit_hash_short = Column(String(8), nullable=True)
    dvc_push_completed = Column(Boolean, nullable=True, default=False)
    
    # Información del modelo
    model_type = Column(String(50), nullable=True)
    task = Column(String(50), nullable=True)
    dataset = Column(String(100), nullable=True)
    training_type = Column(String(50), nullable=True)
    model_version = Column(String(50), nullable=True)
    modelo_path = Column(String(500), nullable=True)
    mlflow_artifact_path = Column(String(500), nullable=True)
    
    # Notas adicionales
    notes = Column(Text, nullable=True)


# ========== CONEXIÓN Y SESIÓN ==========

engine = create_engine(
    settings.MYSQL_URI,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Crea todas las tablas en la base de datos"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tablas MySQL creadas exitosamente")
    except Exception as e:
        logger.error(f"❌ Error creando tablas: {e}")
        raise


def get_db():
    """Obtiene una sesión de base de datos"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise


# ========== FUNCIONES MIGRADAS DE connect_sql.py ==========

def actualizar_orden_fecha(
    orden_compra: int,
    fecha_creacion: str,
    productos: List[str],
    cantidades: List[int],
    totales: List[float],
    carpeta: str
) -> bool:
    """
    Actualiza la orden en la tabla correspondiente
    Migrado de connect_sql.py con SQLAlchemy
    """
    if len(productos) != len(cantidades) or len(productos) != len(totales):
        logger.error("Las listas de productos, cantidades y totales no coinciden")
        return False

    # Validar carpeta
    if carpeta not in ["prev", "corr"]:
        logger.error(f"Carpeta inválida: {carpeta}")
        return False

    # Seleccionar modelo según carpeta
    VentaModel = VentaPreventiva if carpeta == "prev" else VentaCorrectiva
    nombre_tabla = "ventas_preventivas" if carpeta == "prev" else "ventas_correctivas"

    db = get_db()
    try:
        # Validar orden_compra
        if orden_compra is None:
            logger.error("orden_compra es None, no se puede insertar")
            return False
        
        # Convertir orden_compra a int si es string
        try:
            orden_compra_int = int(orden_compra)
        except (ValueError, TypeError):
            logger.error(f"orden_compra '{orden_compra}' no es un número válido")
            return False
        
        # Convertir fecha
        fecha_dt = None
        if fecha_creacion:
            try:
                fecha_dt = datetime.strptime(fecha_creacion, '%Y-%m-%d')
                logger.debug(f"Fecha convertida: {fecha_dt}")
            except ValueError:
                logger.warning(f"Formato de fecha inválido: {fecha_creacion}")
                fecha_dt = None

        # Eliminar registros existentes de la orden
        registros_eliminados = db.query(VentaModel).filter(
            VentaModel.orden_compra == orden_compra_int
        ).delete()
        if registros_eliminados > 0:
            logger.info(f"🗑️  Eliminados {registros_eliminados} registros antiguos de orden {orden_compra_int}")

        # Insertar nuevos registros (uno por cada producto)
        registros_insertados = 0
        for producto, cantidad, total in zip(productos, cantidades, totales):
            try:
                total_float = float(str(total).replace(',', ''))
            except (ValueError, AttributeError):
                logger.warning(f"No se pudo convertir total '{total}' a float")
                total_float = 0.0

            venta = VentaModel(
                orden_compra=orden_compra_int,
                producto=str(producto)[:500],  # Limitar a 500 caracteres
                fecha_creacion=fecha_dt,
                cantidad=int(cantidad),
                total=total_float
            )
            db.add(venta)
            registros_insertados += 1
            logger.debug(f"  → Producto agregado: {producto} (cantidad: {cantidad}, total: {total_float})")

        db.commit()
        logger.info(f"✅ Orden {orden_compra_int} procesada en {nombre_tabla}: {registros_insertados} productos insertados")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error procesando orden {orden_compra} en {nombre_tabla}: {e}", exc_info=True)
        return False
    finally:
        db.close()


def actualizar_orden_total(
    orden_compra: int,
    total: float,
    carpeta: str
) -> bool:
    """
    Esta función ya no es necesaria porque el total se guarda en cada registro de producto.
    Se mantiene por compatibilidad pero no hace nada.
    """
    logger.debug(f"actualizar_orden_total llamado para orden {orden_compra} en {carpeta}, pero el total ya se guarda en cada producto")
    return True


def obtener_git_commit_hash() -> tuple[Optional[str], Optional[str]]:
    """
    Obtiene el hash del commit actual de Git
    
    Returns:
        tuple: (hash_completo, hash_corto) o (None, None) si hay error
    """
    try:
        resultado = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=5
        )
        if resultado.returncode == 0:
            hash_completo = resultado.stdout.strip()
            hash_corto = hash_completo[:8] if len(hash_completo) >= 8 else hash_completo
            return hash_completo, hash_corto
    except Exception as e:
        logger.debug(f"No se pudo obtener git commit hash: {e}")
    return None, None


def obtener_dvc_hash(ruta_modelo: str) -> tuple[Optional[str], Optional[str]]:
    """
    Obtiene el hash DVC del modelo
    
    Args:
        ruta_modelo: Ruta al archivo del modelo
    
    Returns:
        tuple: (hash_completo, hash_corto) o (None, None) si hay error
    """
    try:
        # Buscar el archivo .dvc correspondiente
        ruta_dvc = ruta_modelo + '.dvc'
        if os.path.exists(ruta_dvc):
            with open(ruta_dvc, 'r') as f:
                contenido = f.read()
                # Buscar el hash md5 en el archivo .dvc
                import re
                match = re.search(r'md5:\s*([a-f0-9]{32})', contenido)
                if match:
                    hash_completo = match.group(1)
                    hash_corto = hash_completo[:8] if len(hash_completo) >= 8 else hash_completo
                    return hash_completo, hash_corto
    except Exception as e:
        logger.debug(f"No se pudo obtener DVC hash: {e}")
    return None, None


def extraer_arquitectura_modelo(model) -> Dict[str, Optional[int]]:
    """
    Extrae la arquitectura del modelo Keras
    
    Args:
        model: Modelo de Keras
    
    Returns:
        dict: Diccionario con filtros_conv1, filtros_conv2, etc.
    """
    arquitectura = {
        'filtros_conv1': None,
        'filtros_conv2': None,
        'filtros_conv3': None,
        'neuronas_dense1': None,
        'neuronas_dense2': None,
        'dropout1': None,
        'dropout2': None
    }
    
    try:
        layer_idx = 0
        conv_count = 0
        dense_count = 0
        dropout_count = 0
        
        for layer in model.layers:
            layer_type = type(layer).__name__
            
            if 'Conv2D' in layer_type:
                conv_count += 1
                if conv_count == 1:
                    arquitectura['filtros_conv1'] = layer.filters if hasattr(layer, 'filters') else None
                elif conv_count == 2:
                    arquitectura['filtros_conv2'] = layer.filters if hasattr(layer, 'filters') else None
                elif conv_count == 3:
                    arquitectura['filtros_conv3'] = layer.filters if hasattr(layer, 'filters') else None
            
            elif 'Dense' in layer_type:
                dense_count += 1
                if dense_count == 1:
                    arquitectura['neuronas_dense1'] = layer.units if hasattr(layer, 'units') else None
                elif dense_count == 2:
                    arquitectura['neuronas_dense2'] = layer.units if hasattr(layer, 'units') else None
            
            elif 'Dropout' in layer_type:
                dropout_count += 1
                if dropout_count == 1:
                    arquitectura['dropout1'] = float(layer.rate) if hasattr(layer, 'rate') else None
                elif dropout_count == 2:
                    arquitectura['dropout2'] = float(layer.rate) if hasattr(layer, 'rate') else None
    
    except Exception as e:
        logger.debug(f"Error extrayendo arquitectura del modelo: {e}")
    
    return arquitectura


def insertar_tracking_entrenamiento(
    model: Any,
    history: Dict[str, List[float]],
    test_metrics: Dict[str, float],
    confusion_matrix: Any,
    classification_report: str,
    epochs: int,
    batch_size: int,
    total_samples_train: int,
    total_samples_val: int,
    total_samples_test: int,
    modelo_guardado: str,
    mejor_epoch: Optional[int] = None,
    mejor_val_accuracy: Optional[float] = None,
    dvc_push_completed: bool = False,
    mlflow_run_id: Optional[str] = None
) -> bool:
    """
    Guarda el tracking completo del entrenamiento en la tabla tracking
    
    Args:
        model: Modelo de Keras entrenado
        history: Diccionario con el historial de entrenamiento (history.history de Keras)
        test_metrics: Diccionario con métricas de test (loss, accuracy, precision, recall)
        confusion_matrix: Matriz de confusión (array de numpy o lista)
        classification_report: Reporte de clasificación como string
        epochs: Número de épocas entrenadas
        batch_size: Tamaño del batch
        total_samples_train: Total de muestras de entrenamiento
        total_samples_val: Total de muestras de validación
        total_samples_test: Total de muestras de test
        modelo_guardado: Ruta del modelo guardado
        mejor_epoch: Época con mejor val_accuracy (opcional)
        mejor_val_accuracy: Mejor val_accuracy alcanzada (opcional)
        dvc_push_completed: Si el push a DVC se completó exitosamente
        mlflow_run_id: ID del run de MLflow (opcional)
    
    Returns:
        bool: True si se guardó exitosamente, False en caso contrario
    """
    db = get_db()
    try:
        # Obtener métricas finales de validación
        val_loss_final = history.get('val_loss', [None])[-1] if history.get('val_loss') else None
        val_accuracy_final = history.get('val_accuracy', [None])[-1] if history.get('val_accuracy') else None
        
        # Si no se proporcionó mejor_epoch, buscar la época con mejor val_accuracy
        if mejor_epoch is None and val_accuracy_final is not None and history.get('val_accuracy'):
            mejor_epoch = int(max(range(len(history['val_accuracy'])), key=lambda i: history['val_accuracy'][i]))
            mejor_val_accuracy = history['val_accuracy'][mejor_epoch]
        
        # Extraer arquitectura del modelo
        arquitectura = extraer_arquitectura_modelo(model) if model else {}
        
        # Obtener información del optimizador y learning rate
        optimizer_name = None
        learning_rate = None
        if model and hasattr(model, 'optimizer'):
            optimizer = model.optimizer
            optimizer_name = type(optimizer).__name__
            if hasattr(optimizer, 'learning_rate'):
                lr = optimizer.learning_rate
                if hasattr(lr, 'numpy'):
                    learning_rate = float(lr.numpy())
                elif isinstance(lr, (int, float)):
                    learning_rate = float(lr)
        
        # Obtener loss y metrics
        loss_name = None
        metrics_names = None
        if model and hasattr(model, 'loss'):
            loss_name = str(model.loss) if isinstance(model.loss, str) else type(model.loss).__name__
        if model and hasattr(model, 'metrics'):
            metrics_list = [str(m) if isinstance(m, str) else type(m).__name__ for m in model.metrics]
            metrics_names = ', '.join(metrics_list) if metrics_list else None
        
        # Obtener git commit hash
        git_hash, git_hash_short = obtener_git_commit_hash()
        
        # Obtener DVC hash
        dvc_hash, dvc_hash_short = obtener_dvc_hash(modelo_guardado)
        
        # Calcular validation_split (aproximado)
        validation_split = None
        if total_samples_train and total_samples_val:
            total = total_samples_train + total_samples_val
            if total > 0:
                validation_split = float(total_samples_val) / float(total)
        
        # Obtener input_shape
        input_shape = None
        if model and hasattr(model, 'input_shape'):
            input_shape = str(model.input_shape[1:]) if model.input_shape else None
        
        # Crear registro de tracking
        tracking = TrackingEntrenamiento(
            mlflow_run_id=mlflow_run_id,
            created_at=datetime.now(),
            # Arquitectura
            filtros_conv1=arquitectura.get('filtros_conv1'),
            filtros_conv2=arquitectura.get('filtros_conv2'),
            filtros_conv3=arquitectura.get('filtros_conv3'),
            neuronas_dense1=arquitectura.get('neuronas_dense1'),
            neuronas_dense2=arquitectura.get('neuronas_dense2'),
            dropout1=float(arquitectura.get('dropout1')) if arquitectura.get('dropout1') is not None else None,
            dropout2=float(arquitectura.get('dropout2')) if arquitectura.get('dropout2') is not None else None,
            # Hiperparámetros
            learning_rate=float(learning_rate) if learning_rate is not None else None,
            optimizer=optimizer_name,
            batch_size=batch_size,
            epochs=epochs,
            validation_split=float(validation_split) if validation_split is not None else None,
            early_stopping_patience=10,  # Valor por defecto del callback
            reduce_lr_patience=5,  # Valor por defecto del callback
            reduce_lr_factor=0.5,  # Valor por defecto del callback
            # Configuración
            input_shape=input_shape,
            usar_optuna=False,  # No se usa Optuna actualmente
            n_trials_optuna=None,
            loss=loss_name,
            metrics=metrics_names,
            # Métricas de test
            test_loss=float(test_metrics.get('loss')) if test_metrics.get('loss') is not None else None,
            test_accuracy=float(test_metrics.get('accuracy')) if test_metrics.get('accuracy') is not None else None,
            test_precision=float(test_metrics.get('precision')) if test_metrics.get('precision') is not None else None,
            test_recall=float(test_metrics.get('recall')) if test_metrics.get('recall') is not None else None,
            # Métricas de validación finales
            val_accuracy_final=float(val_accuracy_final) if val_accuracy_final is not None else None,
            val_loss_final=float(val_loss_final) if val_loss_final is not None else None,
            # Versionado
            dvc_hash=dvc_hash,
            dvc_hash_short=dvc_hash_short,
            git_commit_hash=git_hash,
            git_commit_hash_short=git_hash_short,
            dvc_push_completed=dvc_push_completed,
            # Información del modelo
            model_type='CNN',
            task='binary_classification',
            dataset='facturas',
            training_type='supervised',
            model_version='1.0',
            modelo_path=modelo_guardado,
            mlflow_artifact_path=None,  # Se puede llenar si se usa MLflow
            notes=classification_report[:1000] if classification_report else None  # Primeros 1000 caracteres del reporte
        )
        
        db.add(tracking)
        db.commit()
        
        logger.info("✅ Tracking de entrenamiento guardado exitosamente en la tabla 'tracking'")
        logger.info(f"   📊 ID: {tracking.id}")
        logger.info(f"   📅 Fecha: {tracking.created_at}")
        logger.info(f"   🎯 Test Accuracy: {tracking.test_accuracy:.6f}" if tracking.test_accuracy else "   🎯 Test Accuracy: N/A")
        logger.info(f"   📈 Val Accuracy Final: {tracking.val_accuracy_final:.6f}" if tracking.val_accuracy_final else "   📈 Val Accuracy Final: N/A")
        logger.info(f"   🔗 Git Hash: {tracking.git_commit_hash_short}" if tracking.git_commit_hash_short else "   🔗 Git Hash: N/A")
        logger.info(f"   📦 DVC Hash: {tracking.dvc_hash_short}" if tracking.dvc_hash_short else "   📦 DVC Hash: N/A")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error guardando tracking de entrenamiento: {e}", exc_info=True)
        return False
    finally:
        db.close()
