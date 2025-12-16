# ========== APPLICATION LOAD BALANCER ==========

resource "aws_lb" "main" {
  name               = local.alb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection       = false # Cambiar a true en producción
  enable_http2                     = true
  enable_cross_zone_load_balancing = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    enabled = true
  }

  tags = {
    Name = local.alb_name
  }
}

# ========== TARGET GROUP PARA FASTAPI ==========

resource "aws_lb_target_group" "fastapi" {
  name        = "${local.project_name}-fastapi-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${local.project_name}-fastapi-tg"
  }
}

# ========== LISTENER HTTPS (si está habilitado) ==========

resource "aws_lb_listener" "fastapi_https" {
  count = var.enable_https ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi.arn
  }

  tags = {
    Name = "${local.project_name}-alb-listener-https"
  }
}

# ========== LISTENER HTTP ==========

resource "aws_lb_listener" "fastapi_http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = var.enable_https ? "redirect" : "forward"

    dynamic "redirect" {
      for_each = var.enable_https ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.enable_https ? [] : [1]
      content {
        target_group {
          arn = aws_lb_target_group.fastapi.arn
        }
      }
    }
  }

  tags = {
    Name = "${local.project_name}-alb-listener-http"
  }
}

# ========== S3 BUCKET PARA ALB LOGS ==========

resource "aws_s3_bucket" "alb_logs" {
  bucket = "${local.project_name}-alb-logs-${local.account_id}"

  tags = {
    Name = "${local.project_name}-alb-logs"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    expiration {
      days = 7 # Mantener logs por 7 días
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========== CERTIFICADO ACM (OPCIONAL - COMENTADO) ==========

# Descomentar y configurar si quieres usar HTTPS
# resource "aws_acm_certificate" "main" {
#   domain_name       = "api.tu-dominio.com"
#   validation_method = "DNS"
#
#   subject_alternative_names = [
#     "*.tu-dominio.com"
#   ]
#
#   lifecycle {
#     create_before_destroy = true
#   }
#
#   tags = {
#     Name = "${local.project_name}-certificate"
#   }
# }

