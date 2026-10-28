# Data lake (US-23)

Terraform: `infra/modules/data_lake`, applied by the persistent stack `infra/envs/data` (ADR-012).
Layers and formats: ADR-003. Paths and partitions: *Data lake layout* in `voltiagrid-docs` (T-23.4).

## Buckets

| Layer | Bucket | Versioning | Why |
|---|---|---|---|
| raw | `voltiagrid-dev-raw-<account id>` | Enabled | The only copy of what the sources sent; protects it from a delete or overwrite by mistake |
| clean | `voltiagrid-dev-clean-<account id>` | Off | Rebuilt from raw by Spark |
| curated | `voltiagrid-dev-curated-<account id>` | Off | Rebuilt from clean by Spark |

The account id makes the global names unique without writing it in the repo.
`terraform -chdir=infra/envs/data output` prints the real names.

## Security (T-23.1)

| Control | How | Check |
|---|---|---|
| No public access | Block Public Access with the four settings on; ACLs disabled (`BucketOwnerEnforced`) | `aws s3api get-public-access-block --bucket <bucket>` → four `true` |
| Anonymous requests fail | Same as above | `curl.exe -s -o NUL -w "%{http_code}" https://<bucket>.s3.amazonaws.com/` → `403` |
| Encrypted at rest | Default encryption SSE-S3 (`AES256`) | `aws s3api get-bucket-encryption --bucket <bucket>` |
| Encrypted in transit | Bucket policy denies requests without HTTPS (`aws:SecureTransport`) | `aws s3api get-bucket-policy --bucket <bucket>` |
| Only roles of this account | Bucket policy denies any principal that is not an IAM role (`aws:PrincipalType = AssumedRole`) or not from this account | same policy; team members sign in as roles (IAM Identity Center) |

Services do not get access by bucket policy. They get it by attaching one of these managed policies to their IAM role:

| Policy | Allows | For |
|---|---|---|
| `voltiagrid-dev-datalake-read` | List and read every layer | Analysts, exports for Power BI |
| `voltiagrid-dev-datalake-ingest` | List and write new objects in raw; no delete | Ingestion consumers (US-29), initial load (T-23.3) |
| `voltiagrid-dev-datalake-process` | Read raw; read, write and delete in clean and curated | Spark jobs (US-30 onward) |

## Apply (once)

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
$bucket = terraform -chdir=infra/bootstrap output -raw state_bucket
terraform -chdir=infra/envs/data init -backend-config="bucket=$bucket"
terraform -chdir=infra/envs/data plan -out data.tfplan
terraform -chdir=infra/envs/data apply data.tfplan
```

This stack is not destroyed at the end of a test window. Empty buckets cost nothing; data costs per GB stored.
