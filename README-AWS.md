# 🚀 ETL Facturas - Guía de Migración a AWS

## 📋 Tabla de Contenidos

- [Introducción](#introducción)
- [Arquitectura en Alto Nivel](#arquitectura-en-alto-nivel)
- [Stack Tecnológico AWS](#stack-tecnológico-aws)
- [Servicios AWS Utilizados](#servicios-aws-utilizados)
- [Costos Estimados](#costos-estimados)
- [Prerequisites](#prerequisites)
- [Quick Start Guide](#quick-start-guide)
- [Variables de Entorno](#variables-de-entorno)
- [Troubleshooting Común](#troubleshooting-común)
- [Documentación Detallada](#documentación-detallada)
- [Contacto y Soporte](#contacto-y-soporte)

---

## Introducción

Este proyecto es un sistema de **ETL (Extract, Transform, Load)** y **MLOps** para procesamiento automatizado de facturas. La migración a AWS permite:

- ✅ **Escalabilidad**: Auto-scaling según demanda
- ✅ **Alta Disponibilidad**: Multi-AZ deployment
- ✅ **Seguridad**: IAM roles, Secrets Manager, encryption
- ✅ **Monitoreo**: CloudWatch logs, metrics, alarms
- ✅ **CI/CD**: GitHub Actions + ECR + ECS
- ✅ **Costo-efectividad**: Pay-as-you-go, optimización de recursos

### ¿Por qué migrar a AWS?

- **Infraestructura como Código**: Terraform para reproducibilidad
- **Containerización**: Docker + ECS Fargate (sin gestión de servidores)
- **Orquestación**: MWAA (Managed Workflows for Apache Airflow)
- **Observabilidad**: CloudWatch integrado
- **Compliance**: Certificaciones AWS (SOC, ISO, etc.)

---

## Arquitectura en Alto Nivel

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Cloud                              │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   ALB        │    │   ECS        │    │   MWAA       │  │
│  │   (FastAPI)  │───▶│   Fargate    │    │   (Airflow)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                    │           │
│         │                   │                    │           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   RDS MySQL  │    │   S3         │    │   Secrets    │  │
│  │   (Business) │    │   Buckets    │    │   Manager    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   ECR        │    │ CloudWatch   │    │   MLflow     │  │
│  │   (Images)   │    │   (Logs)     │    │   (Tracking) │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Componentes Principales

- **Application Load Balancer (ALB)**: Enrutamiento de tráfico HTTP/HTTPS
- **ECS Fargate**: Contenedores sin gestión de servidores
- **MWAA**: Airflow managed para orquestación de workflows
- **RDS MySQL**: Base de datos para datos de negocio
- **S3**: Almacenamiento de facturas, modelos, artifacts
- **Secrets Manager**: Gestión segura de credenciales
- **CloudWatch**: Logs, métricas y alarmas

---

## Stack Tecnológico AWS

| Categoría | Tecnología | Propósito |
|-----------|-----------|-----------|
| **Compute** | ECS Fargate | Contenedores serverless |
| **Orquestación** | MWAA (Apache Airflow) | Workflow automation |
| **Base de Datos** | RDS MySQL | Datos de negocio |
| **Almacenamiento** | S3 | Facturas, modelos, artifacts |
| **Container Registry** | ECR | Docker images |
| **Load Balancing** | ALB | Distribución de tráfico |
| **Networking** | VPC, Subnets, NAT Gateway | Red privada |
| **Seguridad** | IAM, Secrets Manager | Autenticación y autorización |
| **Monitoreo** | CloudWatch | Logs, métricas, alarmas |
| **CI/CD** | GitHub Actions | Automatización de deployment |

---

## Servicios AWS Utilizados

### 🐳 **Amazon ECS (Elastic Container Service)**
- **Tipo**: Container orchestration
- **Uso**: Ejecutar contenedores FastAPI, MLflow, training tasks
- **Ventaja**: Sin gestión de servidores (Fargate)
- **Costo**: ~$0.04/vCPU-hora + ~$0.004/GB-hora

### 🔄 **Amazon MWAA (Managed Workflows for Apache Airflow)**
- **Tipo**: Workflow orchestration
- **Uso**: Ejecutar DAGs de ETL, training, drift detection
- **Ventaja**: Airflow managed, sin infraestructura
- **Costo**: ~$0.49/hora (mw1.small)

### 🗄️ **Amazon RDS MySQL**
- **Tipo**: Relational database
- **Uso**: Almacenar datos de negocio (ventas_preventivas, ventas_correctivas, tracking)
- **Ventaja**: Backup automático, multi-AZ
- **Costo**: ~$0.10/GB-mes (storage) + instancia

### 📦 **Amazon S3**
- **Tipo**: Object storage
- **Uso**: Facturas, modelos ML, MLflow artifacts, DAGs
- **Ventaja**: Durabilidad 99.999999999%, versioning
- **Costo**: ~$0.023/GB-mes (Standard)

### 🔐 **AWS Secrets Manager**
- **Tipo**: Secrets management
- **Uso**: Credenciales MySQL, AWS keys, Google OAuth
- **Ventaja**: Rotación automática, encriptación
- **Costo**: ~$0.40/secreto-mes

### 📊 **Amazon CloudWatch**
- **Tipo**: Monitoring and logging
- **Uso**: Logs de aplicaciones, métricas, alarmas
- **Ventaja**: Integración nativa con AWS
- **Costo**: ~$0.50/GB logs ingesta, $0.03/GB almacenamiento

### 🌐 **Application Load Balancer (ALB)**
- **Tipo**: Load balancing
- **Uso**: Distribuir tráfico a FastAPI
- **Ventaja**: Health checks, SSL termination
- **Costo**: ~$0.0225/ALB-hora + $0.008/GB transferencia

---

## Costos Estimados

| Servicio | Configuración | Costo Mensual Estimado |
|----------|---------------|------------------------|
| **ECS Fargate** | 2 tasks FastAPI (1 vCPU, 2GB) | ~$60 |
| **ECS Fargate** | 1 task MLflow (0.5 vCPU, 1GB) | ~$15 |
| **ECS Fargate** | Training tasks (on-demand) | ~$20 |
| **MWAA** | mw1.small (2 workers) | ~$350 |
| **RDS MySQL** | db.t3.medium (multi-AZ) | ~$150 |
| **S3** | ~100GB storage | ~$2.30 |
| **ALB** | 1 ALB + 50GB transferencia | ~$20 |
| **Secrets Manager** | 5 secretos | ~$2 |
| **CloudWatch** | Logs + métricas | ~$10 |
| **NAT Gateway** | 1 NAT Gateway | ~$32 |
| **Data Transfer** | Inter-AZ, Internet | ~$20 |
| **ECR** | Storage imágenes | ~$1 |
| **TOTAL ESTIMADO** | | **~$682/mes** |

> ⚠️ **Nota**: Costos reales varían según uso. Usa AWS Cost Explorer para monitoreo detallado.

---

## Prerequisites

Antes de comenzar el deployment, asegúrate de tener:

### 1. **Cuenta AWS**
- Cuenta AWS activa con permisos de administrador
- Acceso a AWS Console y AWS CLI

### 2. **Herramientas Locales**
```bash
# AWS CLI
aws --version  # >= 2.0

# Docker
docker --version  # >= 20.10

# Terraform
terraform --version  # >= 1.0

# Python
python3 --version  # >= 3.11

# Git
git --version
```

### 3. **Credenciales AWS**
```bash
# Configurar AWS CLI
aws configure

# Verificar credenciales
aws sts get-caller-identity
```

### 4. **Permisos IAM Requeridos**
- `ecs:*`
- `ecr:*`
- `s3:*`
- `rds:*`
- `secretsmanager:*`
- `cloudwatch:*`
- `mwaa:*`
- `iam:*` (para crear roles)
- `vpc:*`
- `elasticloadbalancing:*`

### 5. **Recursos Pre-existentes**
- RDS MySQL instance (o crear con Terraform)
- Dominio para SSL certificate (opcional)

---

## Quick Start Guide

### Paso 1: Clonar y Configurar
```bash
git clone <repository-url>
cd etl_facturas_textil

# Copiar template de variables
cp .env.aws.example .env.aws
# Editar .env.aws con tus valores
```

### Paso 2: Configurar Secrets
```bash
# Migrar secretos a Secrets Manager
python3 scripts/migration/migrate-secrets.py \
  --env .env \
  --region us-east-1
```

### Paso 3: Crear Infraestructura
```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

### Paso 4: Build y Push Imágenes
```bash
# Build y push a ECR
./scripts/deployment/build-and-push-ecr.sh \
  --region us-east-1
```

### Paso 5: Deploy Servicios
```bash
# Deploy FastAPI y MLflow
./scripts/deployment/deploy-ecs-service.sh \
  --service fastapi-service \
  --cluster etl-facturas-cluster \
  --task-def aws/ecs/task-definitions/fastapi-service.json
```

### Paso 6: Verificar Deployment
```bash
# Verificar health
./scripts/monitoring/check-ecs-health.sh \
  --cluster etl-facturas-cluster \
  --service fastapi-service

# Obtener URL del ALB
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[0].DNSName' \
  --output text
```

> 📖 **Documentación detallada**: Ver [docs/deployment/deployment-guide.md](docs/deployment/deployment-guide.md)

---

## Variables de Entorno

### Variables Críticas

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# ECS Configuration
ECS_CLUSTER_NAME=etl-facturas-cluster
ECS_SUBNETS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUPS=sg-xxx

# S3 Buckets
S3_BUCKET_FACTURAS=mes-en-curso
S3_BUCKET_MODELOS=textil-modelos
S3_BUCKET_MLFLOW=textil-mlflow-artifacts

# Database
MYSQL_HOST=textil.cof2oucystyr.us-east-1.rds.amazonaws.com
MYSQL_DATABASE=textil
MYSQL_USER=samaca

# MLflow
MLFLOW_TRACKING_URI=http://mlflow-service.facturas-namespace:5001

# Feature Flags
USE_AWS_INTEGRATION=true
USE_AWS_ECS=true
USE_SECRETS_MANAGER=true
```

> 📖 **Lista completa**: Ver [.env.aws.example](.env.aws.example)

---

## Troubleshooting Común

### ❌ **Error: "No se puede conectar a MySQL"**

**Causa**: Security group no permite tráfico desde ECS

**Solución**:
```bash
# Verificar security group de RDS
aws rds describe-db-instances \
  --query 'DBInstances[0].VpcSecurityGroups'

# Agregar regla de entrada desde ECS security group
aws ec2 authorize-security-group-ingress \
  --group-id <rds-sg-id> \
  --protocol tcp \
  --port 3306 \
  --source-group <ecs-sg-id>
```

### ❌ **Error: "Task failed to start"**

**Causa**: Imagen ECR no encontrada o permisos insuficientes

**Solución**:
```bash
# Verificar imagen existe
aws ecr describe-images \
  --repository-name etl-facturas-fastapi

# Verificar task execution role tiene permisos ECR
aws iam get-role-policy \
  --role-name etl-facturas-ecs-task-execution-role \
  --policy-name ecs-task-execution-policy
```

### ❌ **Error: "Secrets Manager access denied"**

**Causa**: Task role no tiene permisos para Secrets Manager

**Solución**:
```bash
# Verificar política IAM
aws iam list-role-policies \
  --role-name etl-facturas-ecs-task-role

# Agregar política si falta
aws iam put-role-policy \
  --role-name etl-facturas-ecs-task-role \
  --policy-name secrets-manager-policy \
  --policy-document file://aws/iam/policies/ecs-task-role.json
```

### ❌ **Error: "ALB health check failing"**

**Causa**: Endpoint `/health` no responde o servicio no está listo

**Solución**:
```bash
# Verificar logs de ECS
aws logs tail /ecs/fastapi --follow

# Verificar health endpoint manualmente
curl https://<alb-dns-name>/health

# Verificar target group health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

> 📖 **Más troubleshooting**: Ver [docs/runbooks/incident-response.md](docs/runbooks/incident-response.md)

---

## Documentación Detallada

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura AWS](docs/architecture/aws-architecture.md) | Arquitectura técnica detallada |
| [Guía de Deployment](docs/deployment/deployment-guide.md) | Paso a paso para deployment |
| [Testing Local](docs/deployment/local-testing-guide.md) | Testing antes de AWS |
| [Incident Response](docs/runbooks/incident-response.md) | Troubleshooting y runbooks |
| [Scaling Guide](docs/runbooks/scaling-guide.md) | Cómo escalar recursos |

---

## Contacto y Soporte

### 📧 **Equipo de Desarrollo**
- **Email**: mlops-team@textil.com
- **Slack**: #etl-facturas-aws

### 📚 **Recursos**
- **AWS Documentation**: https://docs.aws.amazon.com/
- **Terraform AWS Provider**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **ECS Best Practices**: https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/

### 🐛 **Reportar Issues**
- **GitHub Issues**: [Crear issue](https://github.com/your-org/etl_facturas_textil/issues)
- **Templates**: Usar templates de bug report o feature request

---

## 📝 **Notas Importantes**

> ⚠️ **Seguridad**: Nunca commitees credenciales. Usa Secrets Manager.

> 💰 **Costos**: Monitorea costos regularmente con AWS Cost Explorer.

> 🔄 **Backups**: RDS tiene backups automáticos. S3 tiene versioning habilitado.

> 📊 **Monitoreo**: Configura alarmas en CloudWatch para métricas críticas.

---

**Última actualización**: Diciembre 2024  
**Versión**: 2.0.0

