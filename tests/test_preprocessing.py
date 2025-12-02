"""
Tests Unitarios - Preprocessing

Verifica que preprocessing.ejecutar_preprocesamiento_completo() 
siempre devuelve los arrays esperados.
"""
import pytest
import numpy as np
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Importar el módulo a testear
from app import preprocessing
from app.config import settings


class TestEjecutarPreprocesamientoCompleto:
    """Tests para ejecutar_preprocesamiento_completo()"""
    
    def test_retorna_arrays_esperados_cuando_hay_datos(self, test_data_dir, mock_env_vars):
        """
        Verifica que la función retorna 4 arrays (X_train, y_train, X_test, y_test)
        cuando hay datos disponibles
        """
        # Crear estructura de carpetas de test
        train_dir = test_data_dir / "invoices_train"
        test_dir = test_data_dir / "invoices_test"
        
        # Crear subcarpetas 0 y 1
        train_0 = train_dir / "0"
        train_1 = train_dir / "1"
        test_0 = test_dir / "0"
        test_1 = test_dir / "1"
        
        for dir_path in [train_0, train_1, test_0, test_1]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Mock de la función que procesa imágenes
        with patch.object(preprocessing, 'preprocesar_conjunto_datos_preprocesamiento') as mock_preprocess:
            # Simular arrays de retorno
            mock_X_train = np.array([[1, 2, 3], [4, 5, 6]])
            mock_y_train = np.array([0, 1])
            mock_X_test = np.array([[7, 8, 9]])
            mock_y_test = np.array([0])
            
            mock_preprocess.side_effect = [
                (mock_X_train, mock_y_train),  # Para entrenamiento
                (mock_X_test, mock_y_test)     # Para prueba
            ]
            
            # Mock de funciones auxiliares
            with patch.object(preprocessing, 'verificar_estructura_proyecto_preprocesamiento', return_value=True), \
                 patch.object(preprocessing, 'crear_carpetas_preprocesamiento'), \
                 patch.object(preprocessing, 'verificar_poppler_preprocesamiento', return_value=True), \
                 patch.object(preprocessing, 'verificar_calidad_preprocesamiento_preprocesamiento', return_value=True), \
                 patch.object(preprocessing, 'mostrar_estadisticas_imagenes_preprocesamiento'), \
                 patch('app.preprocessing.CARPETA_ENTRENAMIENTO', str(train_dir), create=True), \
                 patch('app.preprocessing.CARPETA_PRUEBA', str(test_dir), create=True):
                
                # Ejecutar función
                resultado = preprocessing.ejecutar_preprocesamiento_completo()
                
                # Verificar que retorna 4 elementos
                assert resultado is not None, "La función debe retornar un resultado"
                assert len(resultado) == 4, f"Debe retornar 4 arrays, pero retornó {len(resultado)}"
                
                X_train, y_train, X_test, y_test = resultado
                
                # Verificar tipos
                assert isinstance(X_train, np.ndarray), "X_train debe ser un numpy array"
                assert isinstance(y_train, np.ndarray), "y_train debe ser un numpy array"
                assert isinstance(X_test, np.ndarray), "X_test debe ser un numpy array"
                assert isinstance(y_test, np.ndarray), "y_test debe ser un numpy array"
                
                # Verificar que los arrays tienen la forma esperada
                assert X_train.shape[0] == len(y_train), "X_train y y_train deben tener la misma longitud"
                assert X_test.shape[0] == len(y_test), "X_test y y_test deben tener la misma longitud"


