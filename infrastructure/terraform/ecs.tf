# ========== ECS CLUSTER ==========

resource "aws_ecs_cluster" "main" {
  name = local.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = local.ecs_cluster_name
  }
}

# ========== CLOUDWATCH LOG GROUPS PARA ECS ==========

resource "aws_cloudwatch_log_group" "fastapi" {
  name              = local.log_groups.fastapi
  retention_in_days = 30

  tags = {
    Name = "${local.project_name}-fastapi-logs"
  }
}

resource "aws_cloudwatch_log_group" "training" {
  name              = local.log_groups.training
  retention_in_days = 7 # Logs de entrenamiento se mantienen menos tiempo

  tags = {
    Name = "${local.project_name}-training-logs"
  }
}

resource "aws_cloudwatch_log_group" "mlflow" {
  name              = local.log_groups.mlflow
  retention_in_days = 30

  tags = {
    Name = "${local.project_name}-mlflow-logs"
  }
}

# ========== TASK DEFINITIONS ==========

# Task Definition para FastAPI
resource "aws_ecs_task_definition" "fastapi" {
  family                   = "fastapi-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.fastapi_cpu
  memory                   = var.fastapi_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode(
    jsondecode(
      replace(
        file("${path.module}/../../aws/ecs/task-definitions/fastapi-service.json"),
        "ACCOUNT_ID",
        local.account_id
      )
    ).containerDefinitions
  )

  tags = {
    Name = "${local.project_name}-fastapi-task"
  }
}

# Task Definition para Training
resource "aws_ecs_task_definition" "training" {
  family                   = "model-training"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.training_cpu
  memory                   = var.training_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode(
    jsondecode(
      replace(
        file("${path.module}/../../aws/ecs/task-definitions/model-training.json"),
        "ACCOUNT_ID",
        local.account_id
      )
    ).containerDefinitions
  )

  tags = {
    Name = "${local.project_name}-training-task"
  }
}

# Task Definition para MLflow
resource "aws_ecs_task_definition" "mlflow" {
  family                   = "mlflow-server"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.mlflow_cpu
  memory                   = var.mlflow_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode(
    jsondecode(
      replace(
        file("${path.module}/../../aws/ecs/task-definitions/mlflow-server.json"),
        "ACCOUNT_ID",
        local.account_id
      )
    ).containerDefinitions
  )

  tags = {
    Name = "${local.project_name}-mlflow-task"
  }
}

# ========== ECS SERVICES ==========

# Servicio FastAPI
resource "aws_ecs_service" "fastapi" {
  name            = "fastapi-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.fastapi.arn
  desired_count   = var.fastapi_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false # Usar NAT Gateway para acceso a internet
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.fastapi.arn
    container_name   = "fastapi"
    container_port   = 8000
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }

  health_check_grace_period_seconds = 60

  depends_on = [
    aws_lb_listener.fastapi_https,
    aws_lb_listener.fastapi_http
  ]

  tags = {
    Name = "${local.project_name}-fastapi-service"
  }
}

# Servicio MLflow
resource "aws_ecs_service" "mlflow" {
  name            = "mlflow-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = var.mlflow_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 50
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }

  tags = {
    Name = "${local.project_name}-mlflow-service"
  }
}

# ========== AUTO-SCALING PARA FASTAPI ==========

resource "aws_appautoscaling_target" "fastapi" {
  max_capacity       = var.fastapi_max_capacity
  min_capacity       = var.fastapi_min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.fastapi.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Auto-scaling policy basado en CPU
resource "aws_appautoscaling_policy" "fastapi_cpu" {
  name               = "${local.project_name}-fastapi-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.fastapi.resource_id
  scalable_dimension = aws_appautoscaling_target.fastapi.scalable_dimension
  service_namespace  = aws_appautoscaling_target.fastapi.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = var.fastapi_target_cpu_utilization
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Auto-scaling policy basado en Memory
resource "aws_appautoscaling_policy" "fastapi_memory" {
  name               = "${local.project_name}-fastapi-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.fastapi.resource_id
  scalable_dimension = aws_appautoscaling_target.fastapi.scalable_dimension
  service_namespace  = aws_appautoscaling_target.fastapi.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = var.fastapi_target_memory_utilization
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

