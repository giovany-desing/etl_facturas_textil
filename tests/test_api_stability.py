"""
Tests de Estabilidad de la API

Verifica que los endpoints (/train_model, /procesar_facturas) 
responden con un 200/202.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import time

# Importar la aplicación FastAPI
from app.main import app


@pytest.fixture
def client(mock_env_vars):
    """Cliente de test para la API"""
    # Mock del startup event para evitar carga de modelo durante tests
    with patch('app.predict.inicializar_modelo', return_value=True), \
         patch('app.predict.cargar_modelo', return_value=None):
        return TestClient(app)


class TestTrainModelEndpoint:
    """Tests para el endpoint /train_model"""
    
    def test_endpoint_responde_200_o_202(self, client, mock_env_vars):
        """
        Verifica que el endpoint /train_model responde con 200 o 202
        """
        # Mock de las verificaciones de prerrequisitos para evitar conexiones reales
        with patch('app.main.verificar_prerequisitos_entrenamiento', return_value=(True, "Prerrequisitos OK")), \
             patch('app.main.verificar_conexion_drive', return_value=(True, "Drive OK")), \
             patch('app.main.verificar_conexion_mysql', return_value=(True, "MySQL OK")), \
             patch('app.main.ejecutar_entrenamiento_completo') as mock_train:
            # Hacer request
            response = client.post("/train_model")
            
            # Verificar código de estado
            assert response.status_code in [200, 202], \
                f"El endpoint debe responder con 200 o 202, pero respondió con {response.status_code}"
            
            # Verificar que la respuesta tiene el formato esperado
            data = response.json()
            assert "mensaje" in data, "La respuesta debe contener 'mensaje'"
            assert "estado" in data, "La respuesta debe contener 'estado'"


class TestProcesarFacturasEndpoint:
    """Tests para el endpoint /procesar_facturas"""
    
    def test_endpoint_responde_200_o_202(self, client, mock_env_vars):
        """
        Verifica que el endpoint /procesar_facturas responde con 200 o 202
        """
        # Mock de las verificaciones de prerrequisitos para evitar conexiones reales
        with patch('app.main.verificar_prerequisitos_etl', return_value=(True, "Prerrequisitos OK")), \
             patch('app.main.verificar_conexion_drive', return_value=(True, "Drive OK")), \
             patch('app.main.verificar_conexion_mysql', return_value=(True, "MySQL OK")), \
             patch('app.main.verificar_conexion_s3', return_value=(True, "S3 OK")), \
             patch('app.main.verificar_modelo_h5', return_value=(True, "Modelo OK", "/fake/path/model.h5")), \
             patch('app.main.ejecutar_procesamiento_completo') as mock_proc:
            # Hacer request
            response = client.post("/procesar_facturas")
            
            # Verificar código de estado
            assert response.status_code in [200, 202], \
                f"El endpoint debe responder con 200 o 202, pero respondió con {response.status_code}"
            
            # Verificar que la respuesta tiene el formato esperado
            data = response.json()
            assert "mensaje" in data, "La respuesta debe contener 'mensaje'"
            assert "estado" in data, "La respuesta debe contener 'estado'"


