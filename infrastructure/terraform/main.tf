# ========== TERRAFORM CONFIGURATION ==========
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend S3 para guardar state remoto
  backend "s3" {
    bucket         = "tu-empresa-terraform-state"
    key            = "etl-facturas/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock" # Opcional: usar DynamoDB para locking
  }
}

# ========== PROVIDERS ==========
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      var.tags,
      {
        ManagedBy = "Terraform"
        Project   = var.project_name
      }
    )
  }
}

# ========== DATA SOURCES ==========
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

# ========== LOCALS ==========
locals {
  # Nombres de recursos
  project_name = var.project_name
  environment  = var.environment

  # Account ID y Region
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Availability Zones (usar las especificadas o las disponibles)
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : slice(data.aws_availability_zones.available.names, 0, 2)

  # Nombres de recursos comunes
  vpc_name              = "${local.project_name}-vpc"
  ecs_cluster_name      = var.ecs_cluster_name
  alb_name              = "${local.project_name}-alb"
  mwaa_environment_name = var.mwaa_environment_name

  # ECR Repository names
  ecr_repositories = {
    fastapi  = "${local.project_name}-fastapi"
    training = "${local.project_name}-training"
    mlflow   = "${local.project_name}-mlflow"
  }

  # S3 Bucket names
  s3_buckets = {
    facturas        = var.s3_bucket_facturas
    modelos         = "${local.project_name}-modelos"
    mlflow          = "${local.project_name}-mlflow-artifacts"
    airflow_dags    = "${local.project_name}-airflow-dags"
    terraform_state = "tu-empresa-terraform-state"
  }

  # CloudWatch Log Groups
  log_groups = {
    fastapi  = "/ecs/fastapi"
    training = "/ecs/model-training"
    mlflow   = "/ecs/mlflow"
    mwaa     = "/aws/mwaa/${local.mwaa_environment_name}"
  }

  # Secrets Manager paths
  secrets_prefix = "textil"
}

