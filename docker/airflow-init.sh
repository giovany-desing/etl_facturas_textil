#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Iniciando script de inicialización de Airflow"
echo "=========================================="

echo "🔧 Instalando dependencias necesarias..."
# Instalar numpy primero con versión compatible para pyarrow
pip install --no-cache-dir "numpy<2.0" 2>&1

# Instalar pyarrow con versión compatible (requerido por google.cloud.bigquery)
pip install --no-cache-dir "pyarrow>=10.0.0,<16.0.0" 2>&1

# Instalar el resto de dependencias
pip install --no-cache-dir \
    pymysql \
    scipy \
    opencv-python-headless \
    pdf2image \
    Pillow \
    pandas \
    google-api-python-client \
    google-auth-httplib2 \
    google-auth-oauthlib \
    requests \
    pydantic \
    pydantic-settings \
    fastapi \
    uvicorn \
    sqlalchemy \
    mysql-connector-python \
    2>&1

echo "✅ Verificando que pymysql se instaló correctamente..."
python3 -c "import pymysql; print('✅ pymysql importado correctamente')" || {
    echo "❌ Error: pymysql no se pudo importar"
    exit 1
}

echo "🔧 Inicializando base de datos de Airflow..."
airflow db init 2>&1

echo "🔧 Creando usuario admin (si no existe)..."
# Verificar si el usuario ya existe antes de crearlo
if airflow users list 2>&1 | grep -q "admin"; then
    echo "✅ Usuario admin ya existe"
else
    echo "🔧 Creando usuario admin..."
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com \
        --password admin \
        --use-random-password=false 2>&1 && echo "✅ Usuario admin creado exitosamente" || echo "⚠️  Error al crear usuario admin (puede que ya exista)"
fi

echo "✅ Inicialización completada. Iniciando servicios..."
echo "=========================================="

# Mantener el proceso en ejecución
airflow webserver &
WEBSERVER_PID=$!
echo "✅ Webserver iniciado (PID: $WEBSERVER_PID)"

airflow scheduler &
SCHEDULER_PID=$!
echo "✅ Scheduler iniciado (PID: $SCHEDULER_PID)"

echo "✅ Ambos servicios están corriendo. Esperando..."
# Esperar indefinidamente
wait

