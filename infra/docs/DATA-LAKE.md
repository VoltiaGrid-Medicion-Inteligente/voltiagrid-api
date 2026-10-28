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

## Lifecycle (T-23.2)

Days count from the moment the object is written. Every object expires after **1,095 days (3 years)**.
Incomplete multipart uploads are deleted after 7 days.

| Layer | Day 0 | Day 30 | Day 90 | Day 180 | Day 365 | Day 1,095 |
|---|---|---|---|---|---|---|
| raw | Standard | Standard-IA | Glacier Instant Retrieval | — | Glacier Deep Archive | deleted |
| clean | Standard | Standard-IA | — | Glacier Instant Retrieval | — | deleted |
| curated | Standard | — | Standard-IA | — | — | deleted |

Raw keeps old versions for 30 days after they are replaced or deleted.

### Why these classes

| Class | Price (USD per GB-month, us-east-1) | Minimum stay | Retrieval | Used for |
|---|---|---|---|---|
| S3 Standard | 0.023 | — | immediate, free | the first month, read by the daily close |
| S3 Standard-IA | 0.0125 | 30 days | immediate, 0.01 per GB | data read a few times a month |
| S3 Glacier Instant Retrieval | 0.004 | 90 days | milliseconds, 0.03 per GB | old months that billing or Power BI may still query |
| S3 Glacier Deep Archive | 0.00099 | 180 days | 12 hours, restore first | raw older than a year: only for a full reprocess |

- **Raw** is only read again to reprocess, so it can go to Deep Archive after a year. That is 23 times cheaper than Standard.
- **Clean** feeds monthly billing and the analytics. Old months must still answer in milliseconds, so it stops at Glacier Instant Retrieval.
- **Curated** is small (aggregates) and Power BI reads it, so it only moves to Standard-IA after a quarter.
- Every transition is later than the minimum stay of the previous class, so no early-deletion fee is charged.
- Objects under 128 KB are not moved (S3 default), because the per-object cost of IA would be higher than the saving.

Note for the historical load (T-23.3): F1 and F2 are from 2011–2014, but the days count from the upload, not
from the reading date. The historical files stay three years in the lake from the day they are loaded.

Check it:

```powershell
$raw = terraform -chdir=infra/envs/data output -raw raw_bucket
aws s3api get-bucket-lifecycle-configuration --bucket $raw
```

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
