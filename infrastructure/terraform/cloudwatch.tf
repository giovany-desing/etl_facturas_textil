# ========== CLOUDWATCH METRIC ALARMS ==========

# Alarma para CPU alta en servicio FastAPI
resource "aws_cloudwatch_metric_alarm" "fastapi_high_cpu" {
  alarm_name          = "${local.project_name}-fastapi-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alerta cuando CPU del servicio FastAPI excede 80%"
  alarm_actions       = [] # Agregar SNS topic para notificaciones

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.fastapi.name
  }

  tags = {
    Name = "${local.project_name}-fastapi-high-cpu-alarm"
  }
}

# Alarma para memoria alta en servicio FastAPI
resource "aws_cloudwatch_metric_alarm" "fastapi_high_memory" {
  alarm_name          = "${local.project_name}-fastapi-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Alerta cuando memoria del servicio FastAPI excede 85%"
  alarm_actions       = []

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.fastapi.name
  }

  tags = {
    Name = "${local.project_name}-fastapi-high-memory-alarm"
  }
}

# Alarma para target health del ALB
resource "aws_cloudwatch_metric_alarm" "alb_target_health" {
  alarm_name          = "${local.project_name}-alb-target-unhealthy"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = var.fastapi_desired_count
  alarm_description   = "Alerta cuando hay menos targets saludables que el desired count"
  alarm_actions       = []

  dimensions = {
    TargetGroup  = aws_lb_target_group.fastapi.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = {
    Name = "${local.project_name}-alb-target-health-alarm"
  }
}

# Alarma para errores 5xx en ALB
resource "aws_cloudwatch_metric_alarm" "alb_5xx_errors" {
  alarm_name          = "${local.project_name}-alb-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alerta cuando hay más de 10 errores 5xx en 1 minuto"
  alarm_actions       = []

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = {
    Name = "${local.project_name}-alb-5xx-errors-alarm"
  }
}

# ========== CLOUDWATCH DASHBOARD ==========

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.fastapi.name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS FastAPI - CPU y Memoria"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.main.arn_suffix],
            [".", "RequestCount", ".", "."],
            [".", "HTTPCode_Target_2XX_Count", ".", "."],
            [".", "HTTPCode_Target_4XX_Count", ".", "."],
            [".", "HTTPCode_Target_5XX_Count", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "ALB - Métricas de Tráfico"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "RunningTaskCount", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.fastapi.name],
            [".", "DesiredTaskCount", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS FastAPI - Task Count"
        }
      }
    ]
  })

  tags = {
    Name = "${local.project_name}-dashboard"
  }
}

