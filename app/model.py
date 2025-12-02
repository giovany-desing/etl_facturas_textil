import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import os
from typing import Dict, Any, Optional

from app.config import settings
from app.utils import setup_logger
from app.database import insertar_tracking_entrenamiento

logger = setup_logger(__name__)

# Directorio raíz del proyecto
DIRECTORIO_RAIZ = settings.BASE_DIR

def crear_modelo_simple():
    """Modelo CNN simple pero efectivo"""
    logger.debug("Creando modelo CNN simple...")
    model = models.Sequential([
        layers.Conv2D(32, (3,3), activation='relu', input_shape=(224, 224, 3)),
        layers.MaxPooling2D(2,2),
        
        layers.Conv2D(64, (3,3), activation='relu'),
        layers.MaxPooling2D(2,2),
        
        layers.Conv2D(128, (3,3), activation='relu'),
        layers.MaxPooling2D(2,2),
        
        layers.Flatten(),
        layers.Dense(256, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.3),
        layers.Dense(1, activation='sigmoid')
    ])
    
    logger.debug("✅ Modelo CNN creado exitosamente")
    return model

def crear_carpeta_modelos():
    """Crea la carpeta modelos en la raíz del proyecto"""
    carpeta_modelos = os.path.join(DIRECTORIO_RAIZ, "modelos")
    if not os.path.exists(carpeta_modelos):
        os.makedirs(carpeta_modelos)
        logger.info(f"✅ Carpeta creada: {carpeta_modelos}")
    else:
        logger.debug(f"📁 Carpeta ya existe: {carpeta_modelos}")
    return carpeta_modelos

def listar_archivos_en_directorio(directorio):
    """Lista todos los archivos en un directorio para debugging"""
    if os.path.exists(directorio):
        archivos = os.listdir(directorio)
        logger.info(f"📁 Archivos encontrados en {directorio}/:")
        for archivo in archivos:
            logger.info(f"   - {archivo}")
        return archivos
    else:
        logger.error(f"❌ El directorio {directorio} no existe")
        return []

def cargar_datos_preprocesados():
    """Carga los datos preprocesados desde train_data/ en la raíz"""
    logger.info("Cargando datos preprocesados...")
    
    # Definir rutas absolutas
    carpeta_train_data = os.path.join(DIRECTORIO_RAIZ, "train_data")
    ruta_x_train = os.path.join(carpeta_train_data, "facturas_X_entrenamiento.npy")
    ruta_y_train = os.path.join(carpeta_train_data, "facturas_y_entrenamiento.npy")
    ruta_x_test = os.path.join(carpeta_train_data, "facturas_X_prueba.npy")
    ruta_y_test = os.path.join(carpeta_train_data, "facturas_y_prueba.npy")
    ruta_mapeo = os.path.join(carpeta_train_data, "facturas_mapeo_etiquetas.npy")
    
    logger.info(f"🔍 Buscando datos en: {carpeta_train_data}")
    
    # Verificar estructura de carpetas
    logger.info("🔍 Verificando estructura de carpetas...")
    listar_archivos_en_directorio(DIRECTORIO_RAIZ)
    listar_archivos_en_directorio(carpeta_train_data)
    
    # Verificar que los archivos existan
    archivos_requeridos = [ruta_x_train, ruta_y_train, ruta_x_test, ruta_y_test]
    archivos_faltantes = []
    
    for archivo in archivos_requeridos:
        if not os.path.exists(archivo):
            archivos_faltantes.append(os.path.basename(archivo))
    
    if archivos_faltantes:
        logger.error(f"❌ Archivos faltantes: {archivos_faltantes}")
        logger.info("💡 Solución: Ejecuta primero el preprocesamiento:")
        logger.info("   python utils/preprocesamiento.py")
        return None, None, None, None, None
    
    try:
        # Cargar datos desde train_data/ (raíz del proyecto)
        X_train = np.load(ruta_x_train)
        y_train = np.load(ruta_y_train)
        X_test = np.load(ruta_x_test)
        y_test = np.load(ruta_y_test)
        
        logger.info("✅ Datos preprocesados cargados exitosamente")
        
        # Intentar cargar mapeo de etiquetas
        try:
            mapeo_etiquetas = np.load(ruta_mapeo, allow_pickle=True).item()
            logger.info(f"📊 Mapeo de etiquetas: {mapeo_etiquetas}")
        except FileNotFoundError:
            logger.warning("⚠️ No se encontró el archivo de mapeo de etiquetas")
            mapeo_etiquetas = {'0': 0, '1': 1}  # Valor por defecto
        
        return X_train, y_train, X_test, y_test, mapeo_etiquetas
        
    except Exception as e:
        logger.error(f"❌ Error cargando datos: {e}")
        return None, None, None, None, None

def verificar_calidad_datos(X_train, y_train, X_test, y_test):
    """Verifica la calidad de los datos cargados"""
    logger.info("🔍 Verificando calidad de datos...")
    
    if X_train is None or y_train is None or X_test is None or y_test is None:
        logger.error("❌ Datos incompletos o nulos")
        return False
    
    # Verificar formas
    logger.info(f"📐 Forma X_train: {X_train.shape}")
    logger.info(f"📐 Forma y_train: {y_train.shape}")
    logger.info(f"📐 Forma X_test: {X_test.shape}")
    logger.info(f"📐 Forma y_test: {y_test.shape}")
    
    # Verificar que las formas sean consistentes
    if len(X_train) != len(y_train):
        logger.error(f"❌ Inconsistencia en datos de entrenamiento: {len(X_train)} vs {len(y_train)}")
        return False
        
    if len(X_test) != len(y_test):
        logger.error(f"❌ Inconsistencia en datos de prueba: {len(X_test)} vs {len(y_test)}")
        return False
    
    # Verificar rango de valores de las imágenes
    logger.info(f"📊 Rango X_train: [{X_train.min():.3f}, {X_train.max():.3f}]")
    logger.info(f"📊 Rango X_test: [{X_test.min():.3f}, {X_test.max():.3f}]")
    
    # Verificar distribución de etiquetas
    train_unique, train_counts = np.unique(y_train, return_counts=True)
    test_unique, test_counts = np.unique(y_test, return_counts=True)
    
    logger.info(f"📈 Distribución entrenamiento: {dict(zip(train_unique, train_counts))}")
    logger.info(f"📈 Distribución prueba: {dict(zip(test_unique, test_counts))}")
    
    logger.info("✅ Calidad de datos verificada exitosamente")
    return True

def entrenar_modelo():
    """Entrenamiento principal del modelo"""
    logger.info("=== INICIANDO ENTRENAMIENTO DEL MODELO ===")
    
    # Cargar datos
    X_train, y_train, X_test, y_test, mapeo_etiquetas = cargar_datos_preprocesados()
    
    if X_train is None:
        logger.error("❌ No se pudieron cargar los datos. Deteniendo entrenamiento.")
        return None, None, 0
    
    # Verificar calidad de datos
    if not verificar_calidad_datos(X_train, y_train, X_test, y_test):
        logger.error("❌ Problemas con la calidad de los datos. Deteniendo entrenamiento.")
        return None, None, 0
    
    # Split validation
    logger.info("Dividiendo datos en entrenamiento y validación...")
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.2, stratify=y_train, random_state=42
    )
    logger.info(f"📊 Conjuntos creados - Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
    
    # Crear y compilar modelo
    logger.info("Creando y compilando modelo...")
    model = crear_modelo_simple()
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy', 'precision', 'recall']
    )
    
    logger.info("✅ Modelo compilado exitosamente")
    
    # Crear carpeta modelos (en raíz del proyecto)
    carpeta_modelos = crear_carpeta_modelos()
    
    # MODIFICACIÓN: Solo un callback para guardar el mejor modelo como modelo_facturas_final.h5
    logger.info("Configurando callbacks de entrenamiento...")
    callbacks = [
        keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(patience=5, factor=0.5, verbose=1),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(carpeta_modelos, 'modelo_facturas_final.h5'),
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1
        )
    ]
    
    # Entrenar
    logger.info("🚀 Iniciando entrenamiento del modelo...")
    try:
        history = model.fit(
            X_train, y_train,
            batch_size=16,
            epochs=50,
            validation_data=(X_val, y_val),
            callbacks=callbacks,
            verbose=1
        )
        logger.info("✅ Entrenamiento completado")
    except KeyboardInterrupt:
        logger.warning("⚠️ Entrenamiento interrumpido por el usuario")
        raise
    except Exception as e:
        logger.error(f"❌ Error durante el entrenamiento: {e}", exc_info=True)
        raise
    
    # Evaluar
    logger.info("Evaluando modelo en datos de prueba...")
    test_loss, test_accuracy, test_precision, test_recall = model.evaluate(X_test, y_test, verbose=0)
    
    logger.info("=== RESULTADOS FINALES ===")
    logger.info(f"📈 Test Loss: {test_loss:.4f}")
    logger.info(f"🎯 Test Accuracy: {test_accuracy:.4f}")
    logger.info(f"🎯 Test Precision: {test_precision:.4f}")
    logger.info(f"🎯 Test Recall: {test_recall:.4f}")
    
    # Predicciones y reportes
    logger.info("Generando predicciones...")
    y_pred = (model.predict(X_test) > 0.5).astype(int).flatten()
    
    # Classification report
    report = classification_report(y_test, y_pred)
    logger.info("📋 Classification Report:\n" + report)
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"📊 Matriz de Confusión:\n{cm}")
    
    # MODIFICACIÓN: Información sobre el modelo guardado
    ruta_modelo_final = os.path.join(carpeta_modelos, 'modelo_facturas_final.h5')
    logger.info("💾 Modelo guardado:")
    logger.info(f"   📁 Ruta: {ruta_modelo_final}")
    logger.info(f"   🎯 Accuracy: {test_accuracy:.4f}")
    logger.info(f"   📊 El modelo con mejor val_accuracy fue guardado automáticamente")
    
    # Guardar historial en modelos/
    ruta_historial = os.path.join(carpeta_modelos, 'historial_entrenamiento.npy')
    np.save(ruta_historial, history.history)
    logger.info(f"✅ Historial de entrenamiento guardado en: {ruta_historial}")
    
    # Guardar mapeo de etiquetas en modelos/ para referencia futura
    ruta_mapeo = os.path.join(carpeta_modelos, 'mapeo_etiquetas.npy')
    np.save(ruta_mapeo, mapeo_etiquetas)
    logger.info(f"✅ Mapeo de etiquetas guardado en: {ruta_mapeo}")
    
    # Guardar tracking en base de datos
    logger.info("💾 Guardando tracking de entrenamiento en base de datos...")
    try:
        # Preparar métricas de test
        test_metrics = {
            'loss': test_loss,
            'accuracy': test_accuracy,
            'precision': test_precision,
            'recall': test_recall
        }
        
        # Obtener mejor época y mejor val_accuracy
        mejor_epoch = None
        mejor_val_accuracy = None
        if 'val_accuracy' in history.history and len(history.history['val_accuracy']) > 0:
            mejor_epoch = int(np.argmax(history.history['val_accuracy']))
            mejor_val_accuracy = float(history.history['val_accuracy'][mejor_epoch])
        
        # Verificar si el DVC push se completó (esto se actualizará después del push)
        dvc_push_completed = False  # Se actualizará después si el push es exitoso
        
        # Guardar en base de datos
        tracking_ok = insertar_tracking_entrenamiento(
            model=model,
            history=history.history,
            test_metrics=test_metrics,
            confusion_matrix=cm,
            classification_report=report,
            epochs=len(history.history.get('loss', [])),
            batch_size=16,
            total_samples_train=len(X_train),
            total_samples_val=len(X_val),
            total_samples_test=len(X_test),
            modelo_guardado=ruta_modelo_final,
            mejor_epoch=mejor_epoch,
            mejor_val_accuracy=mejor_val_accuracy,
            dvc_push_completed=dvc_push_completed
        )
        
        if tracking_ok:
            logger.info("✅ Tracking guardado exitosamente en la base de datos 'textil', tabla 'tracking'")
        else:
            logger.warning("⚠️  No se pudo guardar el tracking en la base de datos, pero el entrenamiento fue exitoso")
    except Exception as e:
        logger.error(f"❌ Error al guardar tracking en base de datos: {e}", exc_info=True)
        logger.warning("⚠️  El entrenamiento fue exitoso, pero no se pudo guardar el tracking")
    
    logger.info("✅ Proceso de entrenamiento y evaluación completado")
    return model, history, test_accuracy

def graficar_resultados(history, carpeta_modelos):
    """Grafica los resultados del entrenamiento y guarda en modelos/"""
    logger.info("Generando gráficas de métricas...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Accuracy
    axes[0, 0].plot(history.history['accuracy'], label='Train Accuracy')
    axes[0, 0].plot(history.history['val_accuracy'], label='Val Accuracy')
    axes[0, 0].set_title('Accuracy durante el entrenamiento')
    axes[0, 0].set_xlabel('Época')
    axes[0, 0].set_ylabel('Accuracy')
    axes[0, 0].legend()
    
    # Loss
    axes[0, 1].plot(history.history['loss'], label='Train Loss')
    axes[0, 1].plot(history.history['val_loss'], label='Val Loss')
    axes[0, 1].set_title('Loss durante el entrenamiento')
    axes[0, 1].set_xlabel('Época')
    axes[0, 1].set_ylabel('Loss')
    axes[0, 1].legend()
    
    # Precision
    if 'precision' in history.history:
        axes[1, 0].plot(history.history['precision'], label='Train Precision')
        axes[1, 0].plot(history.history['val_precision'], label='Val Precision')
        axes[1, 0].set_title('Precision durante el entrenamiento')
        axes[1, 0].set_xlabel('Época')
        axes[1, 0].set_ylabel('Precision')
        axes[1, 0].legend()
    
    # Recall
    if 'recall' in history.history:
        axes[1, 1].plot(history.history['recall'], label='Train Recall')
        axes[1, 1].plot(history.history['val_recall'], label='Val Recall')
        axes[1, 1].set_title('Recall durante el entrenamiento')
        axes[1, 1].set_xlabel('Época')
        axes[1, 1].set_ylabel('Recall')
        axes[1, 1].legend()
    
    plt.tight_layout()
    
    # Guardar gráfico en modelos/
    ruta_grafico = os.path.join(carpeta_modelos, 'metricas_entrenamiento.png')
    plt.savefig(ruta_grafico, dpi=300, bbox_inches='tight')
    logger.info(f"🖼️ Gráfico de métricas guardado en: {ruta_grafico}")
    plt.show()
    
    logger.info("✅ Gráficas generadas exitosamente")

if __name__ == "__main__":
    try:
        logger.info("=== INICIALIZANDO SISTEMA DE ENTRENAMIENTO ===")
        logger.info(f"📁 Directorio raíz: {DIRECTORIO_RAIZ}")
        logger.info("📁 Estructura del proyecto:")
        logger.info(f"   {DIRECTORIO_RAIZ}/")
        logger.info("   ├── train_data/          # Datos preprocesados") 
        logger.info("   ├── utils/               # Scripts (este archivo)")
        logger.info("   │   ├── preprocessing_data.py")
        logger.info("   │   └── entrenamiento_modelo.py (este script)")
        logger.info("   └── modelos/             # Modelos guardados (se creará)")
        
        # Crear carpeta modelos (en raíz)
        carpeta_modelos = crear_carpeta_modelos()
        
        # Entrenar modelo
        model, history, accuracy = entrenar_modelo()
        
        if model is not None:
            # Graficar resultados (opcional - descomentado)
            graficar_resultados(history, carpeta_modelos)
            
            if accuracy > 0.7:
                logger.info("🎉 ¡Entrenamiento exitoso! Modelo con buena accuracy")
            else:
                logger.warning("⚠️ Accuracy por debajo del 70%. Considera:")
                logger.warning("   - Revisar el preprocesamiento de datos")
                logger.warning("   - Aumentar el tamaño del dataset")
                logger.warning("   - Probar diferentes arquitecturas de modelo")
            
            logger.info(f"📁 Todos los archivos guardados en: {carpeta_modelos}")
            logger.info("📋 Archivos generados:")
            logger.info("   ✅ modelo_facturas_final.h5 (mejor modelo)")
            logger.info("   ✅ historial_entrenamiento.npy")
            logger.info("   ✅ mapeo_etiquetas.npy")
            logger.info("   ✅ metricas_entrenamiento.png")
            logger.info("✅ Proceso de entrenamiento COMPLETADO")
        else:
            logger.error("❌ El entrenamiento falló. Revisa los logs anteriores")
            
    except Exception as e:
        logger.error(f"❌ Error durante la ejecución principal: {e}")
        raise