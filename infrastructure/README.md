# 🏗️ Infrastructure as Code - Terraform

## 📋 Overview

Este directorio contiene toda la configuración de **Infrastructure as Code (IaC)** usando Terraform para provisionar la infraestructura AWS completa del proyecto.

**Total:** ~2,317 líneas de Terraform | **Recursos:** 75+ recursos AWS automatizados

---

## 🎯 ¿Por qué Terraform?

### Ventajas sobre CloudFormation

1. **Multi-cloud capability** - No vendor lock-in, puede usarse con otros clouds
2. **Sintaxis HCL** - Más legible que JSON/YAML de CloudFormation
3. **Ecosistema amplio** - Más providers y módulos disponibles
4. **State management superior** - Mejor control de estado y locking
5. **Plan antes de aplicar** - Preview de cambios antes de ejecutar

### Decisiones de Diseño

- **Modularización** - Archivos separados por servicio (vpc.tf, ecs.tf, alb.tf, etc.)
- **Variables centralizadas** - `variables.tf` para configuración reutilizable
- **Outputs estructurados** - `outputs.tf` para valores importantes
- **Tags consistentes** - Tags en todos los recursos para organización
- **Backend remoto** - S3 backend para state compartido y DynamoDB para locking

---

## 📁 Estructura de Archivos

```
infrastructure/terraform/
├── main.tf              # Configuración principal (terraform block, providers)
├── variables.tf          # Variables de entrada (región, environment, etc.)
├── outputs.tf            # Valores de salida (ARNs, URLs, IDs)
├── vpc.tf                # VPC, subnets, Internet Gateway, NAT Gateway
├── ecs.tf                # ECS Cluster, Task Definitions, Services, Auto-scaling
├── alb.tf                # Application Load Balancer, Target Groups, Listeners
├── iam.tf                # IAM Roles y Policies (ECS, MWAA, etc.)
├── s3.tf                 # S3 Buckets (facturas, modelos, mlflow, airflow dags)
├── mwaa.tf               # Managed Workflows for Apache Airflow
├── cloudwatch.tf         # CloudWatch Log Groups, Alarms, Dashboards
├── ecr.tf                # ECR Repositories (FastAPI, Training, MLflow)
└── secrets.tf            # Secrets Manager (estructura, valores se populan con scripts)
```

---

## 🏗️ Recursos Principales

### Networking (vpc.tf)
- **VPC** - 10.0.0.0/16 con DNS habilitado
- **Subnets** - 2 públicas + 2 privadas (Multi-AZ)
- **Internet Gateway** - Acceso público
- **NAT Gateway** - Acceso saliente desde subnets privadas
- **Route Tables** - Routing apropiado para público/privado
- **VPC Endpoints** - S3 y ECR (reduce costos de data transfer)
- **Security Groups** - Reglas de firewall

### Compute (ecs.tf)
- **ECS Cluster** - `etl-facturas-cluster` con Container Insights
- **Task Definitions** - FastAPI, Training, MLflow
- **ECS Services** - FastAPI (2-10 tasks), MLflow (1 task)
- **Auto-scaling** - Target tracking policies (CPU/Memory)
- **CloudWatch Log Groups** - `/ecs/fastapi`, `/ecs/training`, `/ecs/mlflow`

### Load Balancing (alb.tf)
- **Application Load Balancer** - Multi-AZ, HTTPS/HTTP
- **Target Groups** - Health checks en `/health`
- **Listeners** - Puerto 443 (HTTPS) y 80 (redirect)
- **Security Group** - Reglas para ALB

### Orchestration (mwaa.tf)
- **MWAA Environment** - `etl-facturas-airflow`
- **Environment Class** - mw1.small (configurable)
- **Network** - Private subnets con security group
- **DAGs Location** - S3 bucket para DAGs
- **Logging** - CloudWatch logs habilitados

### Storage (s3.tf)
- **Buckets:**
  - `mes-en-curso` - Facturas a procesar
  - `textil-modelos` - Modelos entrenados
  - `textil-mlflow-artifacts` - MLflow artifacts
  - `etl-facturas-airflow-dags` - Airflow DAGs
  - `terraform-state` - Terraform state (backend)
- **Features:**
  - Versioning habilitado
  - Encryption (AES256)
  - Lifecycle policies
  - Public access bloqueado

### Security (iam.tf, secrets.tf)
- **IAM Roles:**
  - `ecsTaskExecutionRole` - Para ECS tasks (ECR pull, CloudWatch logs)
  - `ecsTaskRole` - Para aplicación (S3, Secrets Manager, CloudWatch)
  - `mwaaExecutionRole` - Para MWAA (ECS, S3, CloudWatch)
- **Secrets Manager:**
  - `textil/mysql/credentials`
  - `textil/aws/credentials`
  - `textil/google/oauth`
  - `textil/slack/webhook` (opcional)

### Monitoring (cloudwatch.tf)
- **Log Groups** - 5 grupos de logs con retención configurada
- **Metric Alarms** - 8 alarmas (CPU, Memory, Errors, Health)
- **Dashboard** - Dashboard centralizado con métricas principales

### Container Registry (ecr.tf)
- **ECR Repositories:**
  - `fastapi`
  - `model-training`
  - `mlflow`
- **Features:**
  - Image scanning on push
  - Lifecycle policies (mantener últimas 10 imágenes)

---

## 🚀 Uso

### Prerequisites

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
```

### Configuración Inicial

1. **Configurar backend S3** (en `main.tf`):
   ```hcl
   backend "s3" {
     bucket         = "tu-empresa-terraform-state"
     key            = "etl-facturas/terraform.tfstate"
     region         = "us-east-1"
     encrypt        = true
     dynamodb_table = "terraform-state-lock"
   }
   ```

2. **Configurar variables** (crear `terraform.tfvars`):
   ```hcl
   aws_region      = "us-east-1"
   environment     = "production"
   project_name    = "etl-facturas"
   vpc_cidr        = "10.0.0.0/16"
   ```

### Comandos Principales

```bash
cd infrastructure/terraform

# 1. Inicializar Terraform
terraform init

# 2. Validar configuración
terraform validate

# 3. Formatear código
terraform fmt

# 4. Plan (preview de cambios)
terraform plan -out=tfplan

# 5. Aplicar cambios
terraform apply tfplan

# 6. Ver outputs
terraform output

# 7. Destruir infraestructura (¡cuidado!)
terraform destroy
```

### Workflow Recomendado

```bash
# 1. Inicializar (solo primera vez)
terraform init

# 2. Plan y revisar cambios
terraform plan -out=tfplan

# 3. Revisar el plan generado
terraform show tfplan

# 4. Aplicar si todo está correcto
terraform apply tfplan

# 5. Verificar outputs importantes
terraform output alb_dns_name
terraform output ecs_cluster_arn
```

---

## 🔒 Seguridad

### State Management

- **Backend remoto** - State guardado en S3 (encriptado)
- **State locking** - DynamoDB table previene modificaciones simultáneas
- **Versioning** - S3 bucket con versioning habilitado

### Secrets

- **NO** guardar secrets en Terraform
- Usar **AWS Secrets Manager** (estructura en `secrets.tf`)
- Poblar valores con `scripts/setup/setup-secrets.py`

### Variables Sensibles

- Usar `*.tfvars` files (en `.gitignore`)
- No commitear archivos con credenciales
- Usar `terraform.tfvars.example` como template

---

## 📊 Outputs Importantes

Después de `terraform apply`, estos outputs están disponibles:

```bash
# DNS del ALB
terraform output alb_dns_name

# ARN del cluster ECS
terraform output ecs_cluster_arn

# URLs de ECR repositories
terraform output ecr_repository_urls

# URL de MWAA
terraform output mwaa_webserver_url

# IDs de subnets privadas
terraform output private_subnet_ids
```

---

## 🛠️ Mantenimiento

### Actualizar Recursos

1. Modificar archivo `.tf` correspondiente
2. `terraform plan` para ver cambios
3. `terraform apply` para aplicar

### Agregar Nuevos Recursos

1. Crear o modificar archivo `.tf` apropiado
2. Agregar variables en `variables.tf` si es necesario
3. Agregar outputs en `outputs.tf` si es relevante
4. `terraform plan` y `terraform apply`

### Rollback

Si algo sale mal:

```bash
# Ver historial de state
terraform state list

# Ver configuración anterior
terraform show

# Si es necesario, destruir y recrear
terraform destroy
terraform apply
```

---

## 📚 Recursos Adicionales

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

---

## ⚠️ Notas Importantes

1. **Costo estimado:** ~$500-1000/mes (production environment)
2. **Tiempo de deployment:** ~15-20 minutos para toda la infraestructura
3. **Dependencias:** Algunos recursos dependen de otros (usar `depends_on` cuando sea necesario)
4. **Multi-AZ:** Todos los servicios están desplegados en múltiples zonas para alta disponibilidad

---

**Última actualización:** Diciembre 2024  
**Terraform version:** >= 1.0  
**AWS Provider:** ~> 5.0

