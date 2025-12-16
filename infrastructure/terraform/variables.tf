# ========== VARIABLES GENERALES ==========

variable "aws_region" {
  description = "Región AWS donde se desplegarán los recursos"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Ambiente de despliegue (production, staging, development)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Nombre del proyecto (usado para naming de recursos)"
  type        = string
  default     = "etl-facturas"
}

# ========== VARIABLES DE RED ==========

variable "vpc_cidr" {
  description = "CIDR block para la VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Lista de Availability Zones a usar"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ========== VARIABLES DE ECS ==========

variable "ecs_cluster_name" {
  description = "Nombre del cluster ECS"
  type        = string
  default     = "etl-facturas-cluster"
}

variable "fastapi_cpu" {
  description = "CPU units para servicio FastAPI (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "fastapi_memory" {
  description = "Memoria en MB para servicio FastAPI"
  type        = number
  default     = 2048
}

variable "fastapi_desired_count" {
  description = "Número deseado de tasks para servicio FastAPI"
  type        = number
  default     = 2
}

variable "training_cpu" {
  description = "CPU units para task de entrenamiento (8192 = 8 vCPU)"
  type        = number
  default     = 8192
}

variable "training_memory" {
  description = "Memoria en MB para task de entrenamiento"
  type        = number
  default     = 32768
}

variable "mlflow_cpu" {
  description = "CPU units para servicio MLflow"
  type        = number
  default     = 512
}

variable "mlflow_memory" {
  description = "Memoria en MB para servicio MLflow"
  type        = number
  default     = 1024
}

variable "mlflow_desired_count" {
  description = "Número deseado de tasks para servicio MLflow"
  type        = number
  default     = 1
}

# ========== VARIABLES DE BASE DE DATOS ==========

variable "mysql_host" {
  description = "Host de MySQL RDS (ya existente)"
  type        = string
  default     = "textil.cof2oucystyr.us-east-1.rds.amazonaws.com"
}

variable "mysql_database" {
  description = "Nombre de la base de datos MySQL"
  type        = string
  default     = "textil"
}

variable "mysql_username" {
  description = "Usuario de MySQL (el password está en Secrets Manager)"
  type        = string
  default     = "samaca"
}

variable "mysql_port" {
  description = "Puerto de MySQL"
  type        = number
  default     = 3306
}

# ========== VARIABLES DE S3 ==========

variable "s3_bucket_facturas" {
  description = "Nombre del bucket S3 para facturas"
  type        = string
  default     = "mes-en-curso"
}

# ========== VARIABLES DE MWAA ==========

variable "mwaa_environment_name" {
  description = "Nombre del ambiente MWAA"
  type        = string
  default     = "etl-facturas-airflow"
}

variable "mwaa_environment_class" {
  description = "Clase del ambiente MWAA (mw1.small, mw1.medium, mw1.large)"
  type        = string
  default     = "mw1.small"
}

variable "mwaa_max_workers" {
  description = "Número máximo de workers para MWAA"
  type        = number
  default     = 2
}

# ========== VARIABLES DE ALB ==========

variable "alb_certificate_arn" {
  description = "ARN del certificado ACM para HTTPS (opcional, dejar vacío para HTTP)"
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Habilitar HTTPS en el ALB (requiere certificate_arn)"
  type        = bool
  default     = false
}

# ========== VARIABLES DE TAGS ==========

variable "tags" {
  description = "Tags comunes para todos los recursos"
  type        = map(string)
  default = {
    Project     = "ETL-Facturas"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

# ========== VARIABLES DE AUTO-SCALING ==========

variable "fastapi_min_capacity" {
  description = "Capacidad mínima para auto-scaling de FastAPI"
  type        = number
  default     = 2
}

variable "fastapi_max_capacity" {
  description = "Capacidad máxima para auto-scaling de FastAPI"
  type        = number
  default     = 10
}

variable "fastapi_target_cpu_utilization" {
  description = "Target CPU utilization para auto-scaling de FastAPI"
  type        = number
  default     = 70.0
}

variable "fastapi_target_memory_utilization" {
  description = "Target memory utilization para auto-scaling de FastAPI"
  type        = number
  default     = 80.0
}

