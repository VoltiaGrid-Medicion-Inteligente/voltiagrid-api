output "app_secret_arn" {
  description = "JSON with jwt_secret, demo_customer_password and demo_internal_password."
  value       = aws_secretsmanager_secret.app.arn
}
