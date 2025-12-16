# ========== SECRETS MANAGER ==========
# NOTA: Los valores de los secretos se populan usando el script:
# scripts/setup/setup-secrets.py
# Estos recursos solo crean la estructura en Secrets Manager

# Secreto para credenciales MySQL
resource "aws_secretsmanager_secret" "mysql_credentials" {
  name        = "${local.secrets_prefix}/mysql/credentials"
  description = "Credenciales de MySQL RDS para el proyecto ETL Facturas"

  recovery_window_in_days = 7 # Permite recuperación por 7 días si se elimina

  tags = {
    Name = "${local.project_name}-mysql-credentials"
  }
}

# Secreto para credenciales AWS
resource "aws_secretsmanager_secret" "aws_credentials" {
  name        = "${local.secrets_prefix}/aws/credentials"
  description = "Credenciales AWS (Access Key ID y Secret Access Key)"

  recovery_window_in_days = 7

  tags = {
    Name = "${local.project_name}-aws-credentials"
  }
}

# Secreto para OAuth de Google
resource "aws_secretsmanager_secret" "google_oauth" {
  name        = "${local.secrets_prefix}/google/oauth"
  description = "Credenciales OAuth de Google (credentials.json)"

  recovery_window_in_days = 7

  tags = {
    Name = "${local.project_name}-google-oauth"
  }
}

# Secreto para Slack Webhook (opcional)
resource "aws_secretsmanager_secret" "slack_webhook" {
  count = 1 # Cambiar a 0 si no se usa Slack

  name        = "${local.secrets_prefix}/slack/webhook"
  description = "Webhook URL de Slack para notificaciones"

  recovery_window_in_days = 7

  tags = {
    Name = "${local.project_name}-slack-webhook"
  }
}

# ========== SECRET VERSIONS (OPCIONAL) ==========
# Descomentar y configurar si quieres poblar los secretos desde Terraform
# En producción, es mejor usar el script setup-secrets.py

# resource "aws_secretsmanager_secret_version" "mysql_credentials" {
#   secret_id = aws_secretsmanager_secret.mysql_credentials.id
#   secret_string = jsonencode({
#     user     = var.mysql_username
#     password = "CHANGE_ME"  # Usar setup-secrets.py para poblar
#     host     = var.mysql_host
#     database = var.mysql_database
#     port     = var.mysql_port
#   })
# }

# resource "aws_secretsmanager_secret_version" "aws_credentials" {
#   secret_id = aws_secretsmanager_secret.aws_credentials.id
#   secret_string = jsonencode({
#     access_key_id     = "CHANGE_ME"
#     secret_access_key = "CHANGE_ME"
#   })
# }

