-- Crear base de datos para Airflow si no existe
CREATE DATABASE IF NOT EXISTS airflow;

-- Crear base de datos para la aplicación si no existe
CREATE DATABASE IF NOT EXISTS facturas_db;

-- Crear base de datos para MLflow si no existe
CREATE DATABASE IF NOT EXISTS mlflow;

-- Otorgar permisos al usuario facturas_user
GRANT ALL PRIVILEGES ON airflow.* TO 'facturas_user'@'%';
GRANT ALL PRIVILEGES ON facturas_db.* TO 'facturas_user'@'%';
GRANT ALL PRIVILEGES ON mlflow.* TO 'facturas_user'@'%';

FLUSH PRIVILEGES;

