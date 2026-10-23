# Secret scan of the Docker images

Goal: confirm that no credential is baked into any image (layers, environment, files).
Run it after `docker compose build`, whenever a Dockerfile changes, and before pushing images to ECR.

## Images

`voltiagrid/migrate-seed:local`, `voltiagrid/f3-simulator:local`, `voltiagrid/api-customer-consumption:local`,
`voltiagrid/api-network-inventory:local`, `voltiagrid/api-transformer-metering:local`,
`voltiagrid/api-control-center:local`


## How (PowerShell, Docker Desktop running)

```powershell
$images = "voltiagrid/migrate-seed:local", "voltiagrid/f3-simulator:local",
          "voltiagrid/api-customer-consumption:local", "voltiagrid/api-network-inventory:local",
          "voltiagrid/api-transformer-metering:local", "voltiagrid/api-control-center:local"

foreach ($i in $images) {
  Write-Host "===== $i"
  Write-Host "--- 1. layers"
  docker history --no-trunc --format "{{.CreatedBy}}" $i |
    Select-String -Pattern "PASSWORD|SECRET|TOKEN|AWS_|KEY=" | Select-String -NotMatch "GPG_KEY"
  Write-Host "--- 2. env"
  docker inspect --format "{{range .Config.Env}}{{println .}}{{end}}" $i
  Write-Host "--- 3. files"
  docker run --rm --entrypoint sh $i -c "find / -xdev \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' \) -not -path '/etc/ssl/*' -not -path '/usr/lib/ssl/*' -not -path '/usr/share/ca-certificates/*' -not -name 'cacert.pem' 2>/dev/null"
  Write-Host "--- 4. trivy"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.56.2 image --scanners secret --quiet $i
}
```

Expected for every image:

1. **Layers:** prints nothing. `GPG_KEY` is filtered out: it is the public fingerprint of the key that signs Python releases (set by the `python:3.12-slim` base image), not a secret.
2. **Env:** only non-secret settings: `PATH`, `LANG`, `GPG_KEY`, `PYTHON_VERSION`, `PYTHON_SHA256`, `PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED`. Credentials are given at run time by compose from `.env`, never baked in.
3. **Files:** prints nothing. Public CA certificates are excluded on purpose (`/etc/ssl`, `/usr/lib/ssl`, `/usr/share/ca-certificates` and `certifi`'s `cacert.pem`, used for HTTPS). `.env` is also kept out of the build context by `.dockerignore`.
4. **Trivy:** one known false positive, nothing else (see below).

Docker Desktop may print "What's next: Debug this container error with Gordon" after step 3: `find` exits with
permission warnings on system folders. It is not a scan failure.

### Known false positive

Trivy reports `MEDIUM: JWT (jwt-token)` in `/opt/venv/lib/python3.12/site-packages/pyjwt-<version>.dist-info/METADATA`.
It is the usage example of the PyJWT README (a sample token signed with the word `"secret"`), shipped with every public
install of the library. It is not one of our tokens and grants no access. Any other Trivy finding must be treated as real.

## Result

Scanned on: 2026-10-20, by Sharon. Trivy 0.56.2, Docker Desktop, images built from `develop` after KAN-191.

| Image | Layers | Env | Files | Trivy secrets | Clean? |
|---|---|---|---|---|---|
| migrate-seed | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |
| f3-simulator | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |
| api-customer-consumption | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |
| api-network-inventory | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |
| api-transformer-metering | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |
| api-control-center | none | no credentials | none (public CA bundle only) | 1 known false positive (PyJWT README example) | Yes |

The full output of the loop is in the PR description as evidence.