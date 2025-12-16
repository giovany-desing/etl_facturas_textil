# 🏗️ Arquitectura del Sistema - ETL Facturas Textiles

## 📋 Tabla de Contenidos

- [Introducción](#introducción)
- [Decisiones de Arquitectura](#decisiones-de-arquitectura)
- [Diagrama de Arquitectura](#diagrama-de-arquitectura)
- [Componentes Principales](#componentes-principales)
- [Flujo de Datos](#flujo-de-datos)
- [Networking](#networking)
- [Seguridad](#seguridad)
- [Escalabilidad](#escalabilidad)
- [Alta Disponibilidad](#alta-disponibilidad)
- [Monitoreo](#monitoreo)

---

## Introducción

Este documento describe la arquitectura cloud-native del sistema ETL de facturas, diseñada y construida sobre AWS desde el inicio.

La arquitectura aprovecha servicios managed de AWS para minimizar overhead operacional mientras mantiene escalabilidad, seguridad y observabilidad.

---

## Decisiones de Arquitectura

### Principios de Diseño

1. **Serverless First**: Evitar gestión de servidores (ECS Fargate, MWAA, RDS)
2. **Managed Services**: Preferir servicios AWS managed sobre self-hosted
3. **Infrastructure as Code**: Todo definido en Terraform
4. **Security by Design**: Secrets Manager, IAM roles, encryption
5. **Observability**: CloudWatch para logs, métricas y alertas
6. **Cost Optimization**: Auto-scaling, lifecycle policies, spot instances

### Alternativas Consideradas

**¿Por qué ECS Fargate sobre Kubernetes (EKS)?**

- Menor complejidad operacional
- No requiere gestión de nodos
- Integración nativa con ALB y CloudWatch
- Costo más predecible para este workload
- Tiempo de setup más rápido

**¿Por qué MWAA sobre Airflow self-hosted?**

- AWS gestiona upgrades, patches, scaling
- Alta disponibilidad out-of-the-box
- Integración con IAM roles y Secrets Manager
- Reduce trabajo operacional en ~70%

**¿Por qué RDS MySQL sobre DynamoDB?**

- Datos relacionales (facturas, productos)
- Queries complejas con JOINs
- Compatibilidad con herramientas SQL existentes
- Transactions ACID requeridas

**¿Por qué Terraform sobre CloudFormation?**

- Multi-cloud capability (no vendor lock-in)
- Sintaxis HCL más legible que JSON/YAML
- Ecosistema de providers más amplio
- State management superior

---

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud (us-east-1)                       │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                         VPC (10.0.0.0/16)                          │ │
│  │                                                                     │ │
│  │  ┌──────────────────┐         ┌──────────────────┐                │ │
│  │  │  Public Subnets  │         │  Private Subnets │                │ │
│  │  │  (10.0.0.0/24)   │         │  (10.0.10.0/24)  │                │ │
│  │  │  (10.0.1.0/24)   │         │  (10.0.11.0/24)  │                │ │
│  │  │                  │         │                  │                │ │
│  │  │  ┌────────────┐  │         │  ┌────────────┐  │                │ │
│  │  │  │    ALB    │  │         │  │   ECS     │  │                │ │
│  │  │  │  (FastAPI)│  │────────▶│  │  Fargate  │  │                │ │
│  │  │  └────────────┘  │         │  │  FastAPI │  │                │ │
│  │  │                  │         │  └────────────┘  │                │ │
│  │  │  ┌────────────┐  │         │                  │                │ │
│  │  │  │  NAT GW    │  │         │  ┌────────────┐  │                │ │
│  │  │  │            │  │◀────────│  │   ECS     │  │                │ │
│  │  │  └────────────┘  │         │  │  MLflow   │  │                │ │
│  │  │                  │         │  └────────────┘  │                │ │
│  │  │  ┌────────────┐  │         │                  │                │ │
│  │  │  │  Internet  │  │         │  ┌────────────┐  │                │ │
│  │  │  │  Gateway   │  │         │  │   MWAA    │  │                │ │
│  │  │  └────────────┘  │         │  │  (Airflow)│  │                │ │
│  │  └──────────────────┘         │  └────────────┘  │                │ │
│  │                                └──────────────────┘                │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   RDS MySQL      │  │   S3 Buckets     │  │   Secrets        │     │
│  │   (Multi-AZ)     │  │   - Facturas     │  │   Manager        │     │
│  │   - textil DB    │  │   - Modelos      │  │   - MySQL creds   │     │
│  │                  │  │   - MLflow       │  │   - AWS keys     │     │
│  └──────────────────┘  │   - DAGs         │  │   - Google OAuth │     │
│                        └──────────────────┘  └──────────────────┘     │
│                                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   ECR            │  │   CloudWatch     │  │   VPC Endpoints  │     │
│  │   - fastapi      │  │   - Logs         │  │   - S3          │     │
│  │   - training     │  │   - Metrics      │  │   - ECR         │     │
│  │   - mlflow       │  │   - Alarms       │  │   - CloudWatch  │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Componentes Principales

### 1. **Application Load Balancer (ALB)**

**Propósito**: Distribuir tráfico HTTP/HTTPS a servicios FastAPI

**Configuración**:
- **Tipo**: Application Load Balancer
- **Scheme**: Internet-facing
- **Subnets**: Public subnets (2 AZs)
- **Security Groups**: Permite 80/443 desde Internet
- **Target Group**: FastAPI service (port 8000)
- **Health Check**: `/health` endpoint

**Características**:
- SSL/TLS termination
- Health checks automáticos
- Auto-scaling basado en tráfico

### 2. **Amazon ECS Fargate**

**Propósito**: Ejecutar contenedores sin gestión de servidores

**Servicios**:

#### **FastAPI Service**
- **CPU**: 1024 (1 vCPU)
- **Memory**: 2048 MB
- **Desired Count**: 2 (mínimo)
- **Auto-scaling**: 2-10 tasks
- **Health Check**: `/health` cada 30s

#### **MLflow Service**
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB
- **Desired Count**: 1
- **Backend Store**: MySQL RDS
- **Artifact Store**: S3

#### **Training Task** (On-demand)
- **CPU**: 8192 (8 vCPU)
- **Memory**: 32768 MB
- **Launch Type**: Fargate (spot opcional para ahorro)
- **Trigger**: Desde MWAA o API

### 3. **Amazon MWAA (Managed Workflows for Apache Airflow)**

**Propósito**: Orquestar workflows de ETL, training y drift detection

**Configuración**:
- **Environment Class**: mw1.small
- **Max Workers**: 2
- **Airflow Version**: 2.8.1
- **Network**: Private subnets
- **DAGs Location**: S3 bucket (`etl-facturas-airflow-dags`)

**DAGs Principales**:
- `process_invoices_etl_aws`: ETL horario
- `train_invoice_model_aws`: Training bajo demanda
- `detect_data_drift_aws`: Drift detection semanal

### 4. **Amazon RDS MySQL**

**Propósito**: Almacenar datos de negocio

**Configuración**:
- **Engine**: MySQL 8.0
- **Instance Class**: db.t3.medium
- **Multi-AZ**: Enabled (alta disponibilidad)
- **Storage**: 100GB gp3
- **Backup**: Automated (7 días retention)

**Bases de Datos**:
- `textil`: Datos de negocio (ventas_preventivas, ventas_correctivas, tracking)
- `mlflow`: MLflow tracking (opcional, puede usar RDS separado)

### 5. **Amazon S3**

**Buckets**:

| Bucket | Propósito | Lifecycle |
|--------|-----------|-----------|
| `mes-en-curso` | Facturas pendientes | 90 días |
| `textil-modelos` | Modelos ML versionados | Sin expiración |
| `textil-mlflow-artifacts` | MLflow artifacts | 180 días |
| `etl-facturas-airflow-dags` | DAGs de Airflow | Sin expiración |
| `textil-drift-data` | Datos de drift detection | 30 días |

**Características**:
- Versioning habilitado
- Encryption: AES256
- Public access: Bloqueado

### 6. **AWS Secrets Manager**

**Secretos**:

| Secreto | Contenido |
|---------|-----------|
| `textil/mysql/credentials` | user, password, host, database |
| `textil/aws/credentials` | access_key_id, secret_access_key |
| `textil/google/oauth` | credentials.json |
| `textil/slack/webhook` | webhook_url |

**Características**:
- Rotación automática (opcional)
- Encriptación en reposo
- Integración con ECS (inyección automática)

---

## Flujo de Datos

### 🔄 **ETL Pipeline (Horario - cada hora)**

```
1. MWAA DAG: process_invoices_etl_aws
   │
   ├─▶ 2. ECS Task (FastAPI) o HTTP POST a ALB
   │   │
   │   ├─▶ 3. Descargar facturas desde S3
   │   │   │   S3: mes-en-curso/ → Local: "mes en curso/"
   │   │   │
   │   ├─▶ 4. Clasificar facturas (modelo ML)
   │   │   │   Modelo: modelos/modelo_facturas_final.h5
   │   │   │   Output: correctivas → "corr/", preventivas → "prev/"
   │   │   │
   │   ├─▶ 5. Procesar OCR y extraer datos
   │   │   │   OCR: Tesseract
   │   │   │   Output: Datos estructurados
   │   │   │
   │   ├─▶ 6. Insertar en MySQL RDS
   │   │   │   Tablas: ventas_preventivas, ventas_correctivas
   │   │   │
   │   ├─▶ 7. Subir a Google Drive
   │   │   │   Carpetas: histórico, correctivos, preventivos
   │   │   │
   │   └─▶ 8. Limpiar S3 y local
   │       │   Eliminar facturas procesadas de S3
   │       │   Eliminar carpetas temporales locales
   │
   └─▶ 9. Notificar resultado (Slack opcional)
```

### 🎓 **Training Pipeline (Bajo Demanda)**

```
1. Trigger: POST /train_model o MWAA DAG
   │
   ├─▶ Opción A: ECS Task (si USE_AWS_ECS=true)
   │   │
   │   ├─▶ 2. ECS RunTask (model-training)
   │   │   │   CPU: 8192, Memory: 32768
   │   │   │
   │   ├─▶ 3. Descargar datos desde Google Drive
   │   │   │   Carpetas: invoices_train, invoices_test
   │   │   │
   │   ├─▶ 4. Preprocesamiento
   │   │   │   Output: train_data/*.npy
   │   │   │
   │   ├─▶ 5. Entrenar modelo
   │   │   │   Framework: TensorFlow/Keras
   │   │   │   Output: modelos/modelo_facturas_final.h5
   │   │   │
   │   ├─▶ 6. Evaluar y guardar tracking
   │   │   │   MySQL: tabla tracking
   │   │   │   MLflow: experiment tracking
   │   │   │
   │   ├─▶ 7. Subir modelo a S3 (DVC)
   │   │   │   S3: textil-modelos/
   │   │   │
   │   └─▶ 8. Enviar métricas a CloudWatch
   │
   └─▶ Opción B: Entrenamiento Local (fallback)
       │ (Misma lógica pero en contenedor local)
```

### 📊 **Drift Detection Pipeline (Semanal - Domingos 3 AM)**

```
1. MWAA DAG: detect_data_drift_aws
   │
   ├─▶ 2. Obtener datos de referencia
   │   │   Baseline: modelos/baseline_caracteristicas.npy
   │   │
   ├─▶ 3. Obtener datos actuales
   │   │   Fuente: MySQL RDS o S3
   │   │
   ├─▶ 4. Calcular estadísticas
   │   │   Test: Kolmogorov-Smirnov
   │   │   Threshold: p-value < 0.05
   │   │
   ├─▶ 5. Evaluar drift
   │   │
   ├─▶ 6. Si drift detectado:
   │   │   ├─▶ Guardar datos en S3 (textil-drift-data)
   │   │   ├─▶ Notificar (Slack)
   │   │   └─▶ Trigger DAG de training
   │   │       └─▶ train_invoice_model_aws
   │   │
   └─▶ 7. Si no hay drift:
       └─▶ Log resultado y continuar
```

---

## Networking

### **VPC (Virtual Private Cloud)**

**CIDR**: `10.0.0.0/16`

**Subnets**:

| Tipo | CIDR | AZ | Uso |
|------|------|----|-----|
| Public | `10.0.0.0/24` | us-east-1a | ALB, NAT Gateway |
| Public | `10.0.1.0/24` | us-east-1b | ALB (redundancia) |
| Private | `10.0.10.0/24` | us-east-1a | ECS, MWAA, RDS |
| Private | `10.0.11.0/24` | us-east-1b | ECS, MWAA, RDS |

### **Internet Gateway**

- Permite tráfico saliente/incoming desde Internet
- Conectado a public subnets

### **NAT Gateway**

- Permite tráfico saliente desde private subnets
- Ubicado en public subnet
- Elastic IP asociado

### **VPC Endpoints**

Para reducir costos de data transfer:

- **S3 Gateway Endpoint**: Acceso a S3 sin NAT Gateway
- **ECR Interface Endpoints**: Pull de imágenes desde ECR
- **CloudWatch Logs Interface Endpoint**: Envío de logs

### **Security Groups**

| SG | Inbound | Outbound | Uso |
|----|---------|----------|-----|
| **ALB** | 80, 443 desde 0.0.0.0/0 | All | Load Balancer |
| **ECS** | 8000 desde ALB SG | All | FastAPI, MLflow |
| **MWAA** | All desde ECS SG | All | Airflow |
| **RDS** | 3306 desde ECS SG | All | MySQL |

---

## Seguridad

### **IAM Roles**

#### **ECS Task Execution Role**
- **Permisos**:
  - ECR: Pull images
  - CloudWatch Logs: Write logs
  - Secrets Manager: Get secret values
- **Uso**: ECS necesita esto para iniciar tasks

#### **ECS Task Role**
- **Permisos**:
  - S3: Read/Write buckets
  - Secrets Manager: Get secrets
  - CloudWatch: Put metrics
  - RDS: Describe (metadata)
- **Uso**: Aplicación necesita esto para acceder a recursos

#### **MWAA Execution Role**
- **Permisos**:
  - ECS: RunTask, DescribeTasks
  - S3: Read/Write DAGs bucket
  - CloudWatch: Write logs
  - Secrets Manager: Get secrets
- **Uso**: Airflow necesita esto para ejecutar workflows

### **Secrets Manager**

- **Encriptación**: AES256
- **Rotación**: Opcional (configurable)
- **Acceso**: Solo desde IAM roles autorizados
- **Integración**: ECS inyecta secrets como env vars

### **Encriptación**

- **S3**: AES256 (server-side encryption)
- **RDS**: Encryption at rest (habilitado)
- **Secrets Manager**: Encryption at rest (automático)
- **In-transit**: TLS/SSL para todas las conexiones

---

## Escalabilidad

### **Auto-Scaling ECS**

**FastAPI Service**:

```yaml
Min Capacity: 2
Max Capacity: 10
Target CPU: 70%
Target Memory: 80%
Scale Out Cooldown: 60s
Scale In Cooldown: 300s
```

**Políticas**:
- CPU-based scaling
- Memory-based scaling
- Target tracking (no step scaling)

### **MWAA Scaling**

- **Environment Class**: mw1.small (2 workers)
- **Max Workers**: Configurable (2-10)
- **Auto-scaling**: Basado en queue depth

### **RDS Scaling**

- **Vertical**: Cambiar instance class (manual)
- **Storage**: Auto-scaling habilitado (hasta 1TB)
- **Read Replicas**: Opcional para read scaling

---

## Alta Disponibilidad

### **Multi-AZ Deployment**

- **ECS**: Tasks distribuidos en 2 AZs
- **RDS**: Multi-AZ habilitado (failover automático)
- **ALB**: Distribución en 2 AZs
- **MWAA**: Redundancia interna (managed)

### **Health Checks**

- **ALB**: `/health` cada 30s
- **ECS**: Health check en contenedor
- **RDS**: Automated backups + monitoring

### **Backup y Recovery**

- **RDS**: Automated backups (7 días retention)
- **S3**: Versioning habilitado
- **Terraform State**: Backend S3 con versioning

---

## Monitoreo

### **CloudWatch Logs**

| Log Group | Retención | Uso |
|-----------|-----------|-----|
| `/ecs/fastapi` | 30 días | Logs de FastAPI |
| `/ecs/model-training` | 7 días | Logs de entrenamiento |
| `/ecs/mlflow` | 30 días | Logs de MLflow |
| `/aws/mwaa/etl-facturas-airflow` | 30 días | Logs de Airflow |

### **CloudWatch Metrics**

**Métricas Personalizadas**:
- `TrainingAccuracy`: Accuracy del modelo
- `TrainingLoss`: Loss del modelo
- `ETLProcessingTime`: Tiempo de procesamiento ETL

**Métricas de AWS**:
- ECS: CPU, Memory, Task count
- ALB: Request count, Response time, Error rate
- RDS: CPU, Memory, Connections

### **CloudWatch Alarms**

| Alarma | Métrica | Threshold | Acción |
|--------|---------|-----------|--------|
| FastAPI High CPU | CPUUtilization | > 80% | SNS notification |
| FastAPI High Memory | MemoryUtilization | > 85% | SNS notification |
| ALB 5xx Errors | HTTPCode_Target_5XX_Count | > 10/min | SNS notification |
| Target Unhealthy | HealthyHostCount | < desired | SNS notification |

---

**Última actualización**: Diciembre 2024

