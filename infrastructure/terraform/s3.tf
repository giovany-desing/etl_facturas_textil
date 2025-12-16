# ========== S3 BUCKET PARA FACTURAS ==========

resource "aws_s3_bucket" "facturas" {
  bucket = var.s3_bucket_facturas

  tags = {
    Name = "${local.project_name}-facturas"
  }
}

resource "aws_s3_bucket_versioning" "facturas" {
  bucket = aws_s3_bucket.facturas.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "facturas" {
  bucket = aws_s3_bucket.facturas.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "facturas" {
  bucket = aws_s3_bucket.facturas.id

  rule {
    id     = "delete-old-facturas"
    status = "Enabled"

    expiration {
      days = 90 # Mantener facturas por 90 días
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_public_access_block" "facturas" {
  bucket = aws_s3_bucket.facturas.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========== S3 BUCKET PARA MODELOS ==========

resource "aws_s3_bucket" "modelos" {
  bucket = local.s3_buckets.modelos

  tags = {
    Name = "${local.project_name}-modelos"
  }
}

resource "aws_s3_bucket_versioning" "modelos" {
  bucket = aws_s3_bucket.modelos.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "modelos" {
  bucket = aws_s3_bucket.modelos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "modelos" {
  bucket = aws_s3_bucket.modelos.id

  rule {
    id     = "keep-latest-models"
    status = "Enabled"

    # Mantener versiones no actuales por 90 días
    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    # Mantener modelos actuales indefinidamente
  }
}

resource "aws_s3_bucket_public_access_block" "modelos" {
  bucket = aws_s3_bucket.modelos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========== S3 BUCKET PARA MLFLOW ARTIFACTS ==========

resource "aws_s3_bucket" "mlflow" {
  bucket = local.s3_buckets.mlflow

  tags = {
    Name = "${local.project_name}-mlflow"
  }
}

resource "aws_s3_bucket_versioning" "mlflow" {
  bucket = aws_s3_bucket.mlflow.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow" {
  bucket = aws_s3_bucket.mlflow.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "mlflow" {
  bucket = aws_s3_bucket.mlflow.id

  rule {
    id     = "delete-old-mlflow-artifacts"
    status = "Enabled"

    expiration {
      days = 180 # Mantener artifacts por 180 días
    }

    noncurrent_version_expiration {
      noncurrent_days = 60
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mlflow" {
  bucket = aws_s3_bucket.mlflow.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========== S3 BUCKET PARA AIRFLOW DAGS ==========

resource "aws_s3_bucket" "airflow_dags" {
  bucket = local.s3_buckets.airflow_dags

  tags = {
    Name = "${local.project_name}-airflow-dags"
  }
}

resource "aws_s3_bucket_versioning" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Política para permitir que MWAA acceda al bucket de DAGs
resource "aws_s3_bucket_policy" "airflow_dags" {
  bucket = aws_s3_bucket.airflow_dags.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "airflow.amazonaws.com"
        }
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.airflow_dags.arn}/*",
          aws_s3_bucket.airflow_dags.arn
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })
}

