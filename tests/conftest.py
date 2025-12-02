"""
Configuración compartida para tests
"""
import pytest
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Configurar variables de entorno para tests
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")  # Reducir logs en tests

@pytest.fixture
def test_data_dir(tmp_path):
    """Crea un directorio temporal para datos de test"""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock de variables de entorno para tests"""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test_access_key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_secret_key")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TEXTIL_MYSQL_HOST", "localhost")
    monkeypatch.setenv("TEXTIL_MYSQL_PORT", "3306")
    monkeypatch.setenv("TEXTIL_MYSQL_USER", "test_user")
    monkeypatch.setenv("TEXTIL_MYSQL_PASSWORD", "test_password")
    monkeypatch.setenv("TEXTIL_MYSQL_DATABASE", "test_db")
    # Variables MySQL local
    monkeypatch.setenv("MYSQL_HOST", "localhost")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "")
    monkeypatch.setenv("MYSQL_DATABASE", "facturas_db")

@pytest.fixture
def mysql_env_vars(monkeypatch):
    """Fixture específico para tests de MySQL"""
    monkeypatch.setenv("TEXTIL_MYSQL_HOST", "localhost")
    monkeypatch.setenv("TEXTIL_MYSQL_PORT", "3306")
    monkeypatch.setenv("TEXTIL_MYSQL_USER", "test_user")
    monkeypatch.setenv("TEXTIL_MYSQL_PASSWORD", "test_password")
    monkeypatch.setenv("TEXTIL_MYSQL_DATABASE", "test_db")


