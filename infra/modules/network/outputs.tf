output "vpc_id" {
  value = aws_vpc.this.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_id" {
  value = aws_route_table.private.id
}

output "s3_endpoint_id" {
  value = aws_vpc_endpoint.s3.id
}

output "s3_prefix_list_id" {
  description = "Prefix list of S3 in the region, for Security Group rules."
  value       = aws_vpc_endpoint.s3.prefix_list_id
}
