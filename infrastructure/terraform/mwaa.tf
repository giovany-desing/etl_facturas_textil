# ========== CLOUDWATCH LOG GROUP PARA MWAA ==========

resource "aws_cloudwatch_log_group" "mwaa" {
  name              = local.log_groups.mwaa
  retention_in_days = 30

  tags = {
    Name = "${local.project_name}-mwaa-logs"
  }
}

# ========== MWAA ENVIRONMENT ==========

resource "aws_mwaa_environment" "main" {
  name              = local.mwaa_environment_name
  airflow_version   = "2.8.1"
  environment_class = var.mwaa_environment_class
  max_workers       = var.mwaa_max_workers

  # Source bucket para DAGs
  source_bucket_arn = aws_s3_bucket.airflow_dags.arn
  dag_s3_path       = "dags"

  # Execution role
  execution_role_arn = aws_iam_role.mwaa_execution.arn

  # Network configuration
  network_configuration {
    security_group_ids = [aws_security_group.mwaa.id]
    subnet_ids         = aws_subnet.private[*].id
  }

  # Logging configuration
  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }

    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }

    task_logs {
      enabled   = true
      log_level = "INFO"
    }

    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }

    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  # Airflow configuration options
  airflow_configuration_options = {
    "secrets.backend" = "airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend"
    "secrets.backend_kwargs" = jsonencode({
      connections_prefix = "${local.secrets_prefix}/airflow/connections"
      variables_prefix   = "${local.secrets_prefix}/airflow/variables"
    })
    "core.default_timezone"     = "America/Bogota"
    "core.parallelism"          = "10"
    "core.dag_concurrency"      = "5"
    "webserver.dag_orientation" = "LR"
  }

  # Requirements file desde S3
  requirements_s3_path = "requirements.txt"

  # Tags
  tags = {
    Name = local.mwaa_environment_name
  }

  depends_on = [
    aws_s3_bucket.airflow_dags,
    aws_iam_role.mwaa_execution,
    aws_cloudwatch_log_group.mwaa
  ]
}

# ========== S3 OBJECT PARA REQUIREMENTS.TXT ==========
# Subir el archivo requirements/mwaa.txt al bucket de DAGs

resource "aws_s3_object" "mwaa_requirements" {
  bucket = aws_s3_bucket.airflow_dags.id
  key    = "requirements.txt"
  source = "${path.module}/../../aws/mwaa/requirements.txt"
  etag   = filemd5("${path.module}/../../aws/mwaa/requirements.txt")

  tags = {
    Name = "${local.project_name}-mwaa-requirements"
  }
}

