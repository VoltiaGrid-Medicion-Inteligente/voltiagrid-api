output "address" {
  description = "Private DNS name of the database."
  value       = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "master_secret_arn" {
  description = "Secrets Manager secret with the master username and password (JSON, managed by RDS)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
