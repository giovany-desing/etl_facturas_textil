# 🧪 Guía de Testing Local

## 📋 Tabla de Contenidos

- [Introducción](#introducción)
- [Docker Compose para AWS Local](#docker-compose-para-aws-local)
- [LocalStack para Simular AWS](#localstack-para-simular-aws)
- [Testing de DAGs de Airflow](#testing-de-dags-de-airflow)
- [Validación de Dockerfiles](#validación-de-dockerfiles)
- [Testing de Scripts de Deployment](#testing-de-scripts-de-deployment)
- [Comandos Útiles para Debugging](#comandos-útiles-para-debugging)

---

## Introducción

Antes de desplegar a AWS, es recomendable probar localmente para:

- ✅ Validar Dockerfiles
- ✅ Probar cambios en código
- ✅ Verificar integraciones
- ✅ Simular ambiente AWS con LocalStack
- ✅ Testing de DAGs de Airflow

---

## Docker Compose para AWS Local

### 1. Usar docker-compose.aws-local.yml

```bash
# Desde la raíz del proyecto
cd docker

# Levantar servicios
docker-compose -f docker-compose.aws-local.yml up -d

# Ver logs
docker-compose -f docker-compose.aws-local.yml logs -f

# Verificar servicios
docker-compose -f docker-compose.aws-local.yml ps
```

### 2. Servicios Disponibles

| Servicio | Puerto | URL |
|----------|--------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| MLflow | 5001 | http://localhost:5001 |
| MySQL | 3306 | localhost:3306 |

### 3. Verificar Health Checks

```bash
# FastAPI health
curl http://localhost:8000/health

# MLflow health
curl http://localhost:5001/health

# MySQL connection
docker exec -it facturas-mysql-local mysql -u facturas_user -p
```

### 4. Testing de Endpoints

```bash
# Test endpoint raíz
curl http://localhost:8000/

# Test status
curl http://localhost:8000/procesar_facturas/status

# Test DVC
curl http://localhost:8000/dvc/test
```

### 5. Limpiar Ambiente

```bash
# Detener servicios
docker-compose -f docker-compose.aws-local.yml down

# Eliminar volúmenes (⚠️ CUIDADO: elimina datos)
docker-compose -f docker-compose.aws-local.yml down -v
```

---

## LocalStack para Simular AWS

### 1. Instalar LocalStack

```bash
# Con Docker
docker pull localstack/localstack

# O con pip
pip install localstack
```

### 2. Iniciar LocalStack

```bash
# Con Docker
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=s3,ecs,ecr,secretsmanager,cloudwatch \
  -e DEBUG=1 \
  localstack/localstack

# Verificar que está corriendo
curl http://localhost:4566/_localstack/health
```

### 3. Configurar AWS CLI para LocalStack

```bash
# Configurar endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# O crear perfil
aws configure set endpoint_url http://localhost:4566 --profile localstack
aws configure set aws_access_key_id test --profile localstack
aws configure set aws_secret_access_key test --profile localstack
aws configure set region us-east-1 --profile localstack
```

### 4. Crear Recursos en LocalStack

```bash
# Crear bucket S3
aws --endpoint-url=http://localhost:4566 s3 mb s3://mes-en-curso

# Crear ECR repository
aws --endpoint-url=http://localhost:4566 ecr create-repository \
  --repository-name etl-facturas-fastapi

# Crear secret
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
  --name textil/mysql/credentials \
  --secret-string '{"user":"test","password":"test","host":"localhost","database":"test"}'
```

### 5. Testing con LocalStack

```bash
# Usar scripts con LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566

# Build y push a LocalStack ECR
./scripts/deployment/build-and-push-ecr.sh \
  --region us-east-1

# Migrar secrets
python3 scripts/migration/migrate-secrets.py \
  --env .env \
  --region us-east-1
```

---

## Testing de DAGs de Airflow

### 1. Airflow Local con Docker

```bash
# Usar docker-compose de Airflow
cd docker
docker-compose -f docker-compose.airflow.yml up -d

# Acceder a webserver
# URL: http://localhost:8080
# Usuario: airflow
# Password: airflow
```

### 2. Probar DAGs Localmente

```bash
# Listar DAGs
docker exec -it airflow-webserver airflow dags list

# Test DAG syntax
docker exec -it airflow-webserver airflow dags test process_invoices_etl_aws 2024-01-01

# Ejecutar DAG manualmente
docker exec -it airflow-webserver airflow dags trigger process_invoices_etl_aws
```

### 3. Validar DAGs para MWAA

```bash
# Validar sintaxis de DAGs
python3 -m py_compile airflow/dags/etl_dag_aws.py
python3 -m py_compile airflow/dags/train_dag_aws.py
python3 -m py_compile airflow/dags/drift_dag_aws.py

# Validar imports
python3 -c "from airflow import DAG; print('OK')"
```

### 4. Testing de Variables de Airflow

```bash
# Crear variables en Airflow local
docker exec -it airflow-webserver airflow variables set ECS_SUBNETS "subnet-xxx,subnet-yyy"
docker exec -it airflow-webserver airflow variables set ECS_SECURITY_GROUPS "sg-xxx"

# Verificar variables
docker exec -it airflow-webserver airflow variables list
```

---

## Validación de Dockerfiles

### 1. Build de Imágenes

```bash
# Build FastAPI
docker build -f docker/Dockerfile.fastapi -t etl-facturas-fastapi:local .

# Build Training
docker build -f docker/Dockerfile.training -t etl-facturas-training:local .

# Build MLflow
docker build -f docker/Dockerfile.mlflow -t etl-facturas-mlflow:local .
```

### 2. Verificar Tamaño de Imágenes

```bash
# Listar imágenes y tamaños
docker images | grep etl-facturas

# Analizar tamaño
docker history etl-facturas-fastapi:local
```

### 3. Testing de Imágenes

```bash
# Ejecutar contenedor FastAPI
docker run -d \
  --name fastapi-test \
  -p 8000:8000 \
  -e ENV=development \
  etl-facturas-fastapi:local

# Verificar health
curl http://localhost:8000/health

# Ver logs
docker logs fastapi-test

# Limpiar
docker stop fastapi-test
docker rm fastapi-test
```

### 4. Validar Multi-stage Builds

```bash
# Verificar que no hay herramientas de build en imagen final
docker run --rm etl-facturas-fastapi:local which gcc
# No debe retornar nada (gcc no debe estar en runtime)

docker run --rm etl-facturas-fastapi:local which python
# Debe retornar: /usr/local/bin/python
```

---

## Testing de Scripts de Deployment

### 1. Testing con Dry-run

```bash
# Migrar secretos (dry-run)
python3 scripts/migration/migrate-secrets.py \
  --env .env \
  --region us-east-1 \
  --dry-run

# Verificar que no crea secretos reales
```

### 2. Validar Scripts Bash

```bash
# Verificar sintaxis
bash -n scripts/deployment/build-and-push-ecr.sh
bash -n scripts/deployment/deploy-ecs-service.sh

# Ejecutar con modo debug
bash -x scripts/deployment/build-and-push-ecr.sh
```

### 3. Testing de Health Checks

```bash
# Simular servicio ECS
# (Requiere servicio ECS real o LocalStack)

./scripts/monitoring/check-ecs-health.sh \
  --cluster etl-facturas-cluster \
  --service fastapi-service \
  --region us-east-1 \
  --verbose
```

### 4. Testing de Rollback

```bash
# Listar revisiones (sin hacer rollback)
./scripts/deployment/rollback-deployment.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --list
```

---

## Comandos Útiles para Debugging

### Docker

```bash
# Ver logs de contenedor
docker logs <container-name> --tail 100 -f

# Ejecutar shell en contenedor
docker exec -it <container-name> /bin/bash

# Inspeccionar imagen
docker inspect <image-name>

# Ver procesos en contenedor
docker top <container-name>

# Ver uso de recursos
docker stats <container-name>
```

### Docker Compose

```bash
# Ver logs de todos los servicios
docker-compose -f docker-compose.aws-local.yml logs

# Ver logs de servicio específico
docker-compose -f docker-compose.aws-local.yml logs fastapi

# Reiniciar servicio
docker-compose -f docker-compose.aws-local.yml restart fastapi

# Rebuild y restart
docker-compose -f docker-compose.aws-local.yml up -d --build fastapi
```

### LocalStack

```bash
# Ver logs de LocalStack
docker logs localstack -f

# Listar recursos creados
aws --endpoint-url=http://localhost:4566 s3 ls
aws --endpoint-url=http://localhost:4566 ecr describe-repositories

# Limpiar todos los recursos
docker restart localstack
```

### Airflow

```bash
# Ver logs de task
docker exec -it airflow-webserver airflow tasks logs \
  process_invoices_etl_aws \
  task_id \
  2024-01-01

# Ver estado de DAG run
docker exec -it airflow-webserver airflow dags state \
  process_invoices_etl_aws \
  2024-01-01

# Limpiar DAG runs antiguos
docker exec -it airflow-webserver airflow dags delete \
  process_invoices_etl_aws
```

### Python/Debugging

```bash
# Ejecutar con debugger
python3 -m pdb app/main.py

# Verificar imports
python3 -c "from app.config_aws import aws_settings; print(aws_settings.aws_region)"

# Testing de módulos AWS
python3 -c "
import asyncio
from app.aws_integration.ecs_client import ECSClient

async def test():
    async with ECSClient() as client:
        print('ECS Client OK')

asyncio.run(test())
"
```

---

## Checklist de Testing Local

- [ ] Docker Compose funciona correctamente
- [ ] Servicios responden a health checks
- [ ] Endpoints funcionan correctamente
- [ ] LocalStack simula AWS correctamente
- [ ] DAGs de Airflow se ejecutan sin errores
- [ ] Dockerfiles construyen sin errores
- [ ] Imágenes tienen tamaño razonable
- [ ] Scripts de deployment funcionan
- [ ] Health check scripts funcionan
- [ ] Logs son claros y útiles

---

**Última actualización**: Diciembre 2024

