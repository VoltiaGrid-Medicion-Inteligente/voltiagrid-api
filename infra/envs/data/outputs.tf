output "raw_bucket" {
  value = module.data_lake.bucket_names["raw"]
}

output "clean_bucket" {
  value = module.data_lake.bucket_names["clean"]
}

output "curated_bucket" {
  value = module.data_lake.bucket_names["curated"]
}

output "read_policy_arn" {
  value = module.data_lake.read_policy_arn
}

output "ingest_policy_arn" {
  value = module.data_lake.ingest_policy_arn
}

output "process_policy_arn" {
  value = module.data_lake.process_policy_arn
}
