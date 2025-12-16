# ========== OUTPUTS DE RED ==========

output "vpc_id" {
  description = "ID de la VPC creada"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block de la VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs de las subnets públicas"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs de las subnets privadas"
  value       = aws_subnet.private[*].id
}

output "nat_gateway_id" {
  description = "ID del NAT Gateway"
  value       = aws_nat_gateway.main.id
}

# ========== OUTPUTS DE ECS ==========

output "ecs_cluster_id" {
  description = "ID del cluster ECS"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_arn" {
  description = "ARN del cluster ECS"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_cluster_name" {
  description = "Nombre del cluster ECS"
  value       = aws_ecs_cluster.main.name
}

output "fastapi_service_name" {
  description = "Nombre del servicio FastAPI"
  value       = aws_ecs_service.fastapi.name
}

output "mlflow_service_name" {
  description = "Nombre del servicio MLflow"
  value       = aws_ecs_service.mlflow.name
}

# ========== OUTPUTS DE ALB ==========

output "alb_dns_name" {
  description = "DNS name del Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "ARN del Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_zone_id" {
  description = "Zone ID del Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "fastapi_target_group_arn" {
  description = "ARN del target group de FastAPI"
  value       = aws_lb_target_group.fastapi.arn
}

# ========== OUTPUTS DE ECR ==========

output "ecr_repository_urls" {
  description = "URLs de los repositorios ECR"
  value = {
    fastapi  = aws_ecr_repository.fastapi.repository_url
    training = aws_ecr_repository.training.repository_url
    mlflow   = aws_ecr_repository.mlflow.repository_url
  }
}

output "ecr_repository_arns" {
  description = "ARNs de los repositorios ECR"
  value = {
    fastapi  = aws_ecr_repository.fastapi.arn
    training = aws_ecr_repository.training.arn
    mlflow   = aws_ecr_repository.mlflow.arn
  }
}

# ========== OUTPUTS DE MWAA ==========

output "mwaa_environment_name" {
  description = "Nombre del ambiente MWAA"
  value       = aws_mwaa_environment.main.name
}

output "mwaa_webserver_url" {
  description = "URL del webserver de MWAA"
  value       = aws_mwaa_environment.main.webserver_url
}

output "mwaa_arn" {
  description = "ARN del ambiente MWAA"
  value       = aws_mwaa_environment.main.arn
}

# ========== OUTPUTS DE S3 ==========

output "s3_bucket_ids" {
  description = "IDs de los buckets S3 creados"
  value = {
    facturas     = aws_s3_bucket.facturas.id
    modelos      = aws_s3_bucket.modelos.id
    mlflow       = aws_s3_bucket.mlflow.id
    airflow_dags = aws_s3_bucket.airflow_dags.id
  }
}

output "s3_bucket_arns" {
  description = "ARNs de los buckets S3"
  value = {
    facturas     = aws_s3_bucket.facturas.arn
    modelos      = aws_s3_bucket.modelos.arn
    mlflow       = aws_s3_bucket.mlflow.arn
    airflow_dags = aws_s3_bucket.airflow_dags.arn
  }
}

# ========== OUTPUTS DE CLOUDWATCH ==========

output "cloudwatch_log_groups" {
  description = "Nombres de los log groups de CloudWatch"
  value = {
    fastapi  = aws_cloudwatch_log_group.fastapi.name
    training = aws_cloudwatch_log_group.training.name
    mlflow   = aws_cloudwatch_log_group.mlflow.name
    mwaa     = aws_cloudwatch_log_group.mwaa.name
  }
}

# ========== OUTPUTS DE IAM ==========

output "ecs_task_execution_role_arn" {
  description = "ARN del rol de ejecución de tasks ECS"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN del rol de tasks ECS"
  value       = aws_iam_role.ecs_task.arn
}

output "mwaa_execution_role_arn" {
  description = "ARN del rol de ejecución de MWAA"
  value       = aws_iam_role.mwaa_execution.arn
}

# ========== OUTPUTS DE SECRETS MANAGER ==========

output "secrets_manager_arns" {
  description = "ARNs de los secretos en Secrets Manager"
  value = {
    mysql_credentials = aws_secretsmanager_secret.mysql_credentials.arn
    aws_credentials   = aws_secretsmanager_secret.aws_credentials.arn
    google_oauth      = aws_secretsmanager_secret.google_oauth.arn
    slack_webhook     = try(aws_secretsmanager_secret.slack_webhook[0].arn, null)
  }
}

# ========== OUTPUTS DE SECURITY GROUPS ==========

output "security_group_ids" {
  description = "IDs de los security groups"
  value = {
    alb  = aws_security_group.alb.id
    ecs  = aws_security_group.ecs.id
    mwaa = aws_security_group.mwaa.id
  }
}

