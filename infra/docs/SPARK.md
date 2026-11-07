# Spark jobs on ECS Fargate (US-40)

The Spark jobs of `voltiagrid-data` run as ECS Fargate tasks that read and write the S3 lake (ADR-002, ADR-014).
`infra/modules/spark_task` creates, in the dev stack:

| Resource | Name | Why |
|---|---|---|
| ECR repository | `voltiagrid/spark-jobs` | Image built from `voltiagrid-data/docker/spark/Dockerfile`; immutable tags, last 5 kept |
| Task definition | `voltiagrid-dev-spark-jobs` | 2 vCPU, 8 GB, 21 GB of disk for Spark's scratch files; the command is the job |
| Task role | `voltiagrid-dev-spark-task` | Only the data lake **process** policy: read raw, read and write clean and curated |
| Log group | `/ecs/voltiagrid-dev/spark-jobs` | One stream per task, 7 days |

The container gets `AWS_REGION`, `SPARK_DRIVER_MEMORY` (75% of the task memory) and the three buckets as
`LAKE_RAW`, `LAKE_CLEAN` and `LAKE_CURATED` (`s3a://` URIs). Credentials come from the task role, never from a variable.

**The data stack must exist** (`infra/envs/data`, applied once and never destroyed with dev): the dev stack looks up
its policy `voltiagrid-dev-datalake-process` and its bucket names. If it is missing, `apply` stops with
`no matching IAM Policy found`.

## 1. Publish the image (from voltiagrid-data)

The tag is the short commit of `voltiagrid-data`, so every run can be traced to its code.

```powershell
aws sso login --profile voltia-admin
$env:AWS_PROFILE = "voltia-admin"
terraform -chdir=infra/envs/dev apply -var desired_count=0          # first time in the window: creates the repository
$repo = terraform -chdir=infra/envs/dev output -raw spark_repository_url
cd ..\voltiagrid-data
$tag = (git rev-parse --short HEAD).Trim()
docker build -f docker/spark/Dockerfile -t "${repo}:$tag" .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $repo.Split("/")[0]
docker push "${repo}:$tag"
cd ..\voltiagrid-api
```

The image is about 1.5 GB (the AWS SDK of the S3A connector): the first push takes a few minutes.

## 2. Point the task definition at it

```powershell
terraform -chdir=infra/envs/dev apply -var image_tag=<APIs tag> -var spark_image_tag=$tag
```

Every new `spark_image_tag` is a new revision of `voltiagrid-dev-spark-jobs`.

## 3. Run a job

```powershell
.\infra\scripts\run-spark.ps1 -Job clean_readings -JobArgs "--source f1 --mode dev --ingest-date <date of the F1 upload>"
.\infra\scripts\run-spark.ps1 -Job estimate_gaps -JobArgs "--run f1-dev-<same date>"
```

The script starts the task with `python -m jobs.<Job> <JobArgs> --raw $LAKE_RAW --clean $LAKE_CLEAN --curated
$LAKE_CURATED`, waits until it stops, and prints the job's log, the exit code, how long it ran and its cost:

```
Ran 214 s on 2 vCPU / 8 GB (FARGATE): about 0.0069 USD
```

Cost = seconds from the image pull to the stop (1 minute minimum) × (vCPU × price per vCPU-hour + GB × price per
GB-hour), with the Fargate prices of us-east-1 (Linux/x86, on-demand 0.04048 and 0.004445; Spot about 0.0127 and
0.0014, which change with demand: check https://aws.amazon.com/fargate/pricing/ before reporting a cost).
`-Spot` uses Fargate Spot (only for the history load, ADR-014); `-Cpu 4096 -Memory 16384` asks for a bigger task.

The task runs in the public subnets with a public IP and the app Security Group (no inbound traffic), like
`migrate-seed`; S3 traffic goes through the VPC gateway endpoint.
