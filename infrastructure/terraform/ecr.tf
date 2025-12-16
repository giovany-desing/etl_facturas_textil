# ========== ECR REPOSITORIES ==========

# Repositorio para FastAPI
resource "aws_ecr_repository" "fastapi" {
  name                 = local.ecr_repositories.fastapi
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.project_name}-fastapi-ecr"
  }
}

# Repositorio para Training
resource "aws_ecr_repository" "training" {
  name                 = local.ecr_repositories.training
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.project_name}-training-ecr"
  }
}

# Repositorio para MLflow
resource "aws_ecr_repository" "mlflow" {
  name                 = local.ecr_repositories.mlflow
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.project_name}-mlflow-ecr"
  }
}

# ========== ECR LIFECYCLE POLICIES ==========

# Lifecycle policy para FastAPI - Mantener últimas 10 imágenes
resource "aws_ecr_lifecycle_policy" "fastapi" {
  repository = aws_ecr_repository.fastapi.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Mantener últimas 10 imágenes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Lifecycle policy para Training - Mantener últimas 5 imágenes (son más grandes)
resource "aws_ecr_lifecycle_policy" "training" {
  repository = aws_ecr_repository.training.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Mantener últimas 5 imágenes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Lifecycle policy para MLflow - Mantener últimas 10 imágenes
resource "aws_ecr_lifecycle_policy" "mlflow" {
  repository = aws_ecr_repository.mlflow.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Mantener últimas 10 imágenes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ========== ECR REPOSITORY POLICIES ==========
# Permitir que ECS pueda hacer pull de las imágenes

resource "aws_ecr_repository_policy" "fastapi" {
  repository = aws_ecr_repository.fastapi.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSPull"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_execution.arn
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

resource "aws_ecr_repository_policy" "training" {
  repository = aws_ecr_repository.training.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSPull"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_execution.arn
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

resource "aws_ecr_repository_policy" "mlflow" {
  repository = aws_ecr_repository.mlflow.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSPull"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_execution.arn
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

