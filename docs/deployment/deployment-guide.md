# 🚀 Guía de Deployment - Infraestructura desde Cero

Esta guía describe el proceso completo para desplegar la infraestructura y aplicación en AWS desde cero.

**Tiempo estimado:** 45-60 minutos  
**Nivel:** Intermedio-Avanzado  
**Costo:** ~$500-1000/mes (environment de producción)

## 📋 Tabla de Contenidos

- [Sección 1: Prerequisites](#sección-1-prerequisites)
- [Sección 2: Setup Inicial](#sección-2-setup-inicial)
- [Sección 3: Infraestructura (Terraform)](#sección-3-infraestructura-terraform)
- [Sección 4: Deployment de Aplicación](#sección-4-deployment-de-aplicación)
- [Sección 5: Post-deployment](#sección-5-post-deployment)
- [Sección 6: Rollback](#sección-6-rollback)

---

## Sección 1: Prerequisites

### 1.1 AWS CLI Configurado

```bash
# Instalar AWS CLI (si no está instalado)
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verificar instalación
aws --version
# Debe mostrar: aws-cli/2.x.x
```

### 1.2 Configurar Credenciales AWS

```bash
# Configurar AWS CLI
aws configure

# Ingresar:
# AWS Access Key ID: [tu-access-key]
# AWS Secret Access Key: [tu-secret-key]
# Default region name: us-east-1
# Default output format: json

# Verificar credenciales
aws sts get-caller-identity
# Debe mostrar tu Account ID y User ARN
```

### 1.3 Docker Instalado

```bash
# Verificar Docker
docker --version
# Debe mostrar: Docker version 20.x.x o superior

# Verificar que Docker está corriendo
docker ps
```

### 1.4 Terraform Instalado

```bash
# Instalar Terraform
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verificar instalación
terraform --version
# Debe mostrar: Terraform v1.6.0 o superior
```

### 1.5 Python 3.11+

```bash
# Verificar Python
python3 --version
# Debe mostrar: Python 3.11.x o superior

# Instalar dependencias del proyecto
pip install -r requirements/base.txt
pip install -r requirements/aws.txt
```

### 1.6 Validación de Prerequisites

```bash
# Ejecutar script de validación
./scripts/deployment/validate-prerequisites.sh

# O validar manualmente
echo "=== Validando Prerequisites ==="
aws --version && echo "✅ AWS CLI OK" || echo "❌ AWS CLI missing"
docker --version && echo "✅ Docker OK" || echo "❌ Docker missing"
terraform --version && echo "✅ Terraform OK" || echo "❌ Terraform missing"
python3 --version && echo "✅ Python OK" || echo "❌ Python missing"
```

---

## Sección 2: Setup Inicial

### 2.1 Configurar Variables de Entorno

```bash
# Copiar template
cp .env.aws.example .env.aws

# Editar con tus valores
nano .env.aws  # o vim, code, etc.
```

**Variables críticas a configurar**:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012  # Obtener con: aws sts get-caller-identity --query Account --output text

# ECS Configuration
ECS_CLUSTER_NAME=etl-facturas-cluster
ECS_SUBNETS=subnet-xxx,subnet-yyy  # Se obtendrán después de Terraform
ECS_SECURITY_GROUPS=sg-xxx  # Se obtendrán después de Terraform

# S3 Buckets (deben ser únicos globalmente)
S3_BUCKET_FACTURAS=mes-en-curso
S3_BUCKET_MODELOS=textil-modelos
S3_BUCKET_MLFLOW=textil-mlflow-artifacts
S3_BUCKET_AIRFLOW_DAGS=etl-facturas-airflow-dags

# Database
MYSQL_HOST=textil.cof2oucystyr.us-east-1.rds.amazonaws.com
MYSQL_DATABASE=textil
MYSQL_USER=samaca
```

### 2.2 Crear Secrets en Secrets Manager

```bash
# Configurar secretos desde .env
python3 scripts/setup/setup-secrets.py \
  --env .env \
  --region us-east-1

# O crear manualmente
aws secretsmanager create-secret \
  --name textil/mysql/credentials \
  --secret-string '{"user":"samaca","password":"Mirringa2020","host":"textil.cof2oucystyr.us-east-1.rds.amazonaws.com","database":"textil","port":3306}' \
  --region us-east-1
```

**Secretos a crear**:
- `textil/mysql/credentials`
- `textil/aws/credentials`
- `textil/google/oauth`
- `textil/slack/webhook` (opcional)

### 2.3 Crear Buckets S3 (si no existen)

```bash
# Los buckets se crearán automáticamente con Terraform
# Pero si necesitas crearlos manualmente:

aws s3 mb s3://mes-en-curso --region us-east-1
aws s3 mb s3://textil-modelos --region us-east-1
aws s3 mb s3://textil-mlflow-artifacts --region us-east-1
aws s3 mb s3://etl-facturas-airflow-dags --region us-east-1

# Habilitar versioning
aws s3api put-bucket-versioning \
  --bucket mes-en-curso \
  --versioning-configuration Status=Enabled
```

---

## Sección 3: Infraestructura (Terraform)

### 3.1 Configurar Backend S3 (Opcional pero Recomendado)

```bash
# Crear bucket para Terraform state
aws s3 mb s3://tu-empresa-terraform-state --region us-east-1

# Habilitar versioning
aws s3api put-bucket-versioning \
  --bucket tu-empresa-terraform-state \
  --versioning-configuration Status=Enabled

# Crear DynamoDB table para state locking (opcional)
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 3.2 Inicializar Terraform

```bash
cd infrastructure/terraform

# Inicializar Terraform
terraform init

# Si usas backend S3, actualiza backend.tf primero
# Luego ejecuta:
terraform init -migrate-state
```

### 3.3 Revisar Plan

```bash
# Generar plan
terraform plan -out=tfplan

# Revisar cambios
terraform show tfplan

# Si todo se ve bien, continuar
```

### 3.4 Aplicar Infraestructura

```bash
# Aplicar cambios
terraform apply tfplan

# O aplicar directamente (sin plan previo)
terraform apply

# Confirmar cuando se solicite
# Esto puede tardar 10-15 minutos
```

### 3.5 Validar Recursos Creados

```bash
# Obtener outputs importantes
terraform output

# Verificar VPC
aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=etl-facturas-vpc" \
  --query 'Vpcs[0].VpcId' \
  --output text

# Verificar ECS Cluster
aws ecs describe-clusters \
  --clusters etl-facturas-cluster \
  --query 'clusters[0].status' \
  --output text
# Debe mostrar: ACTIVE

# Verificar ECR Repositories
aws ecr describe-repositories \
  --query 'repositories[*].repositoryName' \
  --output table

# Guardar outputs importantes
terraform output -json > terraform-outputs.json
```

---

## Sección 4: Deployment de Aplicación

### 4.1 Build y Push de Imágenes Docker a ECR

```bash
# Desde la raíz del proyecto
./scripts/deployment/build-and-push-ecr.sh \
  --region us-east-1

# Esto construirá y subirá:
# - etl-facturas-fastapi:latest
# - etl-facturas-training:latest
# - etl-facturas-mlflow:latest
```

**Verificar imágenes**:

```bash
# Listar imágenes en ECR
aws ecr list-images \
  --repository-name etl-facturas-fastapi \
  --region us-east-1
```

### 4.2 Deploy de Servicios ECS

#### **Deploy FastAPI**

```bash
./scripts/deployment/deploy-ecs-service.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --task-def aws/ecs/task-definitions/fastapi-service.json \
  --region us-east-1 \
  --wait

# Esto:
# 1. Registra nueva task definition
# 2. Actualiza servicio ECS
# 3. Espera a que esté estable
```

#### **Deploy MLflow**

```bash
./scripts/deployment/deploy-ecs-service.sh \
  --service mlflow-service \
  --cluster etl-facturas-cluster \
  --task-def aws/ecs/task-definitions/mlflow-server.json \
  --region us-east-1 \
  --wait
```

### 4.3 Sync de DAGs de Airflow a S3

```bash
# Obtener bucket de MWAA
MWAA_BUCKET=$(aws mwaa get-environment \
  --name etl-facturas-airflow \
  --region us-east-1 \
  --query 'Environment.SourceBucketArn' \
  --output text | awk -F':::' '{print $NF}' | awk -F'/' '{print $NF}')

# Sync DAGs
aws s3 sync airflow/dags/ \
  s3://$MWAA_BUCKET/dags/ \
  --delete \
  --region us-east-1

# Sync requirements
aws s3 cp aws/mwaa/requirements.txt \
  s3://$MWAA_BUCKET/requirements.txt \
  --region us-east-1
```

### 4.4 Validación de Deployments

```bash
# Verificar servicios ECS
./scripts/monitoring/check-ecs-health.sh \
  --cluster etl-facturas-cluster \
  --service fastapi-service \
  --region us-east-1 \
  --verbose

./scripts/monitoring/check-ecs-health.sh \
  --cluster etl-facturas-cluster \
  --service mlflow-service \
  --region us-east-1 \
  --verbose

# Verificar MWAA
aws mwaa get-environment \
  --name etl-facturas-airflow \
  --region us-east-1 \
  --query 'Environment.Status' \
  --output text
# Debe mostrar: AVAILABLE
```

---

## Sección 5: Post-deployment

### 5.1 Verificación de Health Checks

```bash
# Obtener DNS del ALB
ALB_DNS=$(terraform output -raw alb_dns_name)

# Verificar health endpoint
curl https://$ALB_DNS/health
# Debe retornar: {"status": "healthy", ...}

# Verificar ready endpoint
curl https://$ALB_DNS/ready
# Debe retornar: {"status": "ready", ...}

# Verificar live endpoint
curl https://$ALB_DNS/live
# Debe retornar: {"status": "live", ...}
```

### 5.2 Pruebas de Endpoints

```bash
# Test endpoint raíz
curl https://$ALB_DNS/

# Test status de procesamiento
curl https://$ALB_DNS/procesar_facturas/status

# Test status de entrenamiento
curl https://$ALB_DNS/train_model/status
```

### 5.3 Configuración de Monitoreo

```bash
# Verificar CloudWatch Log Groups
aws logs describe-log-groups \
  --log-group-name-prefix /ecs \
  --query 'logGroups[*].logGroupName' \
  --output table

# Verificar CloudWatch Alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix etl-facturas \
  --query 'MetricAlarms[*].[AlarmName,StateValue]' \
  --output table

# Verificar Dashboard
aws cloudwatch get-dashboard \
  --dashboard-name etl-facturas-dashboard \
  --region us-east-1
```

### 5.4 Configuración de Alarmas (Opcional)

```bash
# Crear SNS Topic para notificaciones
aws sns create-topic \
  --name etl-facturas-alerts \
  --region us-east-1

# Suscribirse al topic (email)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:etl-facturas-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Actualizar alarmas para usar SNS (editar terraform o manual)
```

---

## Sección 6: Rollback

### 6.1 Rollback de Servicios ECS

```bash
# Listar revisiones disponibles
./scripts/deployment/rollback-deployment.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --list

# Hacer rollback a revisión específica
./scripts/deployment/rollback-deployment.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --revision 5
```

### 6.2 Revertir Cambios de Terraform

```bash
cd infrastructure/terraform

# Ver historial de estados
terraform state list

# Revertir a estado anterior
terraform state pull > current-state.json
terraform state push previous-state.json

# O destruir y recrear (⚠️ CUIDADO)
terraform destroy
terraform apply
```

### 6.3 Recovery Procedures

#### **Si ECS Service está Unhealthy**

```bash
# 1. Ver logs
aws logs tail /ecs/fastapi --follow

# 2. Ver eventos del servicio
aws ecs describe-services \
  --cluster etl-facturas-cluster \
  --services fastapi-service \
  --query 'services[0].events[:5]' \
  --output table

# 3. Verificar task definition
aws ecs describe-task-definition \
  --task-definition fastapi-service \
  --query 'taskDefinition.containerDefinitions[0]' \
  --output json

# 4. Rollback a versión anterior
./scripts/deployment/rollback-deployment.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --revision <previous-revision>
```

#### **Si MWAA está Down**

```bash
# 1. Verificar estado
aws mwaa get-environment \
  --name etl-facturas-airflow \
  --query 'Environment.Status' \
  --output text

# 2. Ver logs
aws logs tail /aws/mwaa/etl-facturas-airflow --follow

# 3. Verificar DAGs en S3
aws s3 ls s3://etl-facturas-airflow-dags/dags/

# 4. Re-sync DAGs si es necesario
aws s3 sync airflow/dags/ \
  s3://etl-facturas-airflow-dags/dags/ \
  --delete
```

#### **Si RDS está Inaccesible**

```bash
# 1. Verificar estado
aws rds describe-db-instances \
  --db-instance-identifier textil-db \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text

# 2. Verificar security groups
aws rds describe-db-instances \
  --db-instance-identifier textil-db \
  --query 'DBInstances[0].VpcSecurityGroups' \
  --output table

# 3. Verificar connectivity desde ECS
aws ecs run-task \
  --cluster etl-facturas-cluster \
  --task-definition fastapi-service \
  --overrides '{
    "containerOverrides": [{
      "name": "fastapi",
      "command": ["python", "-c", "import mysql.connector; print(\"OK\")"]
    }]
  }'
```

---

## ✅ Checklist de Deployment

- [ ] Prerequisites instalados y verificados
- [ ] Variables de entorno configuradas (.env.aws)
- [ ] Secrets creados en Secrets Manager
- [ ] Buckets S3 creados (o creados por Terraform)
- [ ] Terraform inicializado
- [ ] Terraform plan revisado
- [ ] Terraform apply ejecutado exitosamente
- [ ] Imágenes Docker construidas y subidas a ECR
- [ ] Servicios ECS desplegados
- [ ] DAGs de Airflow sincronizados a S3
- [ ] Health checks verificados
- [ ] Endpoints probados
- [ ] Monitoreo configurado
- [ ] Alarmas configuradas (opcional)

---

**Última actualización**: Diciembre 2024

