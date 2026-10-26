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
