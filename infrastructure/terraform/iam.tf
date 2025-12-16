# ========== IAM ROLE PARA ECS TASK EXECUTION ==========
# Este rol permite a ECS ejecutar tasks (pull imágenes, escribir logs, etc.)

resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.project_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.project_name}-ecs-task-execution-role"
  }
}

# Attach managed policy para ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ========== IAM ROLE PARA ECS TASKS ==========
# Este rol permite a las tasks acceder a otros servicios AWS

resource "aws_iam_role" "ecs_task" {
  name = "${local.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.project_name}-ecs-task-role"
  }
}

# Política para acceso a S3
resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${local.project_name}-ecs-task-s3-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.facturas.arn}/*",
          "${aws_s3_bucket.facturas.arn}",
          "${aws_s3_bucket.modelos.arn}/*",
          "${aws_s3_bucket.modelos.arn}",
          "${aws_s3_bucket.mlflow.arn}/*",
          "${aws_s3_bucket.mlflow.arn}"
        ]
      }
    ]
  })
}

# Política para acceso a Secrets Manager
resource "aws_iam_role_policy" "ecs_task_secrets" {
  name = "${local.project_name}-ecs-task-secrets-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.mysql_credentials.arn,
          aws_secretsmanager_secret.aws_credentials.arn,
          aws_secretsmanager_secret.google_oauth.arn,
          "${aws_secretsmanager_secret.mysql_credentials.arn}*",
          "${aws_secretsmanager_secret.aws_credentials.arn}*",
          "${aws_secretsmanager_secret.google_oauth.arn}*"
        ]
      }
    ]
  })
}

# Política para CloudWatch Logs y Metrics
resource "aws_iam_role_policy" "ecs_task_cloudwatch" {
  name = "${local.project_name}-ecs-task-cloudwatch-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.fastapi.arn}:*",
          "${aws_cloudwatch_log_group.training.arn}:*",
          "${aws_cloudwatch_log_group.mlflow.arn}:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "ETLFacturas"
          }
        }
      }
    ]
  })
}

# Política para ECS (para ejecutar tasks desde MWAA)
resource "aws_iam_role_policy" "ecs_task_ecs" {
  name = "${local.project_name}-ecs-task-ecs-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition"
        ]
        Resource = [
          "${aws_ecs_cluster.main.arn}/*",
          aws_ecs_task_definition.training.arn,
          aws_ecs_task_definition.fastapi.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      }
    ]
  })
}

# ========== IAM ROLE PARA MWAA EXECUTION ==========

resource "aws_iam_role" "mwaa_execution" {
  name = "${local.project_name}-mwaa-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "airflow.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })

  tags = {
    Name = "${local.project_name}-mwaa-execution-role"
  }
}

# Política para MWAA - ECS
resource "aws_iam_role_policy" "mwaa_ecs" {
  name = "${local.project_name}-mwaa-ecs-policy"
  role = aws_iam_role.mwaa_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:ListTasks"
        ]
        Resource = [
          "${aws_ecs_cluster.main.arn}/*",
          aws_ecs_task_definition.training.arn,
          aws_ecs_task_definition.fastapi.arn,
          aws_ecs_task_definition.mlflow.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      }
    ]
  })
}

# Política para MWAA - S3
resource "aws_iam_role_policy" "mwaa_s3" {
  name = "${local.project_name}-mwaa-s3-policy"
  role = aws_iam_role.mwaa_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.airflow_dags.arn}/*",
          aws_s3_bucket.airflow_dags.arn,
          "${aws_s3_bucket.facturas.arn}/*",
          "${aws_s3_bucket.modelos.arn}/*",
          "${aws_s3_bucket.mlflow.arn}/*"
        ]
      }
    ]
  })
}

# Política para MWAA - CloudWatch
resource "aws_iam_role_policy" "mwaa_cloudwatch" {
  name = "${local.project_name}-mwaa-cloudwatch-policy"
  role = aws_iam_role.mwaa_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.mwaa.arn}:*"
        ]
      }
    ]
  })
}

# Política para MWAA - Secrets Manager
resource "aws_iam_role_policy" "mwaa_secrets" {
  name = "${local.project_name}-mwaa-secrets-policy"
  role = aws_iam_role.mwaa_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.mysql_credentials.arn,
          aws_secretsmanager_secret.aws_credentials.arn,
          aws_secretsmanager_secret.google_oauth.arn,
          "${aws_secretsmanager_secret.mysql_credentials.arn}*",
          "${aws_secretsmanager_secret.aws_credentials.arn}*",
          "${aws_secretsmanager_secret.google_oauth.arn}*"
        ]
      }
    ]
  })
}

# Política para MWAA - HTTP (para llamar APIs)
resource "aws_iam_role_policy" "mwaa_http" {
  name = "${local.project_name}-mwaa-http-policy"
  role = aws_iam_role.mwaa_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "airflow:PublishMetrics"
        ]
        Resource = "*"
      }
    ]
  })
}

# ========== IAM ROLE PARA AUTO-SCALING ==========

resource "aws_iam_role" "ecs_autoscaling" {
  name = "${local.project_name}-ecs-autoscaling-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "application-autoscaling.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.project_name}-ecs-autoscaling-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_autoscaling" {
  role       = aws_iam_role.ecs_autoscaling.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceAutoscalingRole"
}

