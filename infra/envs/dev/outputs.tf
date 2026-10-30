output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.network.private_subnet_ids
}

output "s3_endpoint_id" {
  value = module.network.s3_endpoint_id
}

output "admin_instance_id" {
  description = "aws ssm start-session --target <this id>"
  value       = try(module.admin_instance[0].instance_id, null)
}

output "rds_address" {
  description = "Private DNS name of RDS (only resolvable to a private IP)."
  value       = module.rds.address
}

output "rds_master_secret_arn" {
  description = "Secret with the RDS master user and password, managed by RDS."
  value       = module.rds.master_secret_arn
}

output "app_secret_arn" {
  description = "Secret with the JWT secret and the demo passwords."
  value       = module.secrets.app_secret_arn
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "ecs_cluster" {
  value = module.ecs.cluster_name
}

output "app_security_group_id" {
  description = "Security Group for one-off tasks (migrate-seed)."
  value       = module.security.app_sg_id
}

output "task_definitions" {
  description = "Task definition ARN with its revision, per image."
  value       = module.ecs.task_definition_arns
}

output "alb_url" {
  description = "Base URL of the APIs: <alb_url>/consumption, /control-center, /inventory, /f5."
  value       = module.alb.url
}
