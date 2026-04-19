# Route53 dynamic DNS

Service that keeps **Route53 A records** aligned with your current **public IPv4**, using `https://checkip.amazonaws.com`. It runs a background poll loop, **UPSERTs** a **companion TXT record** with the **update time** (ISO-8601 UTC) whenever the A record changes, and exposes a **small status website** (no authentication—see [Security](#security)) plus a **JSON status API** at `GET /api/status`.

Behavior and requirements follow [DESIGN.md](DESIGN.md).

## Configuration (YAML file)

Application settings (poll interval, public-IP URL, Route53 records, optional [Apprise](https://github.com/caronc/apprise) notification URLs) live in a **YAML** file. Set **`CONFIG_FILE`** to the path of that file (or rely on defaults below).

- **Local development:** default is **`config.yaml`** in the **current working directory** (run the app from the repository root, or set `CONFIG_FILE` explicitly).
- **Docker:** the image sets **`CONFIG_FILE=/config.yaml`** by default; mount your file at that path or override `CONFIG_FILE`.

Copy the sample and edit:

```bash
cp examples/config.example.yaml config.yaml
# edit config.yaml: zones, record names, optional notifications.apprise_urls
```

Top-level keys:

- `poll_interval_seconds` — seconds between poll cycles (default `14400`, 4 hours).
- `checkip_url` — URL that returns the public IPv4 as plain text (default `https://checkip.amazonaws.com`).
- `records` — list of objects, each with:
  - `hosted_zone_id` — Route53 hosted zone ID (e.g. `Z123...`)
  - `record_name` — FQDN for the A record (trailing dot recommended, e.g. `dyn.example.com.`)
  - `ttl` — optional (default `300`)
  - `txt_record_name` — optional; defaults to `_ddns-last-update.<your-A-record-name>` so existing TXT on the A name is not overwritten
- `notifications` — optional:
  - `apprise_urls` — list of [Apprise URLs](https://github.com/caronc/apprise/wiki) (empty list disables notifications). When the **background poller** updates at least one record or encounters an error in a single run, **one** aggregated notification is sent.

**Migrating from JSON:** if you previously used a JSON array file (`ROUTE53_RECORDS_FILE`), move that array under `records:` in YAML and add `poll_interval_seconds` / `checkip_url` as needed.

## Quick start (local)

Python **3.12+**, virtualenv recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` if you want, place **`config.yaml`** in the project root (or set `CONFIG_FILE`), and configure AWS credentials (environment variables or `AWS_SHARED_CREDENTIALS_FILE`).

```bash
export CONFIG_FILE="$PWD/config.yaml"
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# or use AWS_PROFILE / shared credentials file — see below
route53-ddns
```

Or with Uvicorn directly (use `--factory` so settings load when the process starts, not at import time):

```bash
uvicorn route53_ddns.main:create_app --factory --host 0.0.0.0 --port 8080
```

## Status API

`GET /api/status` returns JSON:

- `lastUpdated` — ISO-8601 UTC time of the most recent successful DNS update among configured records, or `null` if none yet.
- `records` — array of `{ "host": "<hostname>", "lastUpdated": "<ISO-8601 UTC or null>" }`. The `host` field uses the configured `record_name` with a trailing dot removed.

## Docker

Build:

```bash
docker build -t route53-ddns .
```

Run with a **bind-mounted** config file and AWS credentials file (paths on the host → paths in the container):

```bash
docker run --rm \
  -e AWS_SHARED_CREDENTIALS_FILE=/run/secrets/aws_credentials \
  -v "$PWD/config.yaml:/config.yaml:ro" \
  -v "$PWD/aws_credentials.ini:/run/secrets/aws_credentials:ro" \
  -p 8080:8080 \
  route53-ddns
```

- The image defaults **`CONFIG_FILE=/config.yaml`**; mount your YAML at **`/config.yaml`** or set `CONFIG_FILE` to match your mount.
- Mount the config **read-only** (`:ro`) if the container does not need to modify it.

### Docker Compose

An example stack is in **[docker-compose.example.yml](docker-compose.example.yml)**. Copy `examples/config.example.yaml` to `config.yaml`, add an `aws_credentials.ini` beside it (shared-credentials format), then:

```bash
docker compose -f docker-compose.example.yml up --build
```

The example declares a **Compose secret** (`secrets.aws_credentials.file`) and attaches it to the service; Docker Compose mounts it at **`/run/secrets/aws_credentials`**, which matches `AWS_SHARED_CREDENTIALS_FILE`. Adjust paths and environment as needed.

### AWS credentials file as a Docker secret

Create a standard **shared credentials** INI file, for example:

```ini
[default]
aws_access_key_id = YOUR_KEY_ID
aws_secret_access_key = YOUR_SECRET
```

With **plain `docker run`**, bind-mount that file to `/run/secrets/aws_credentials` (or another path) and set `AWS_SHARED_CREDENTIALS_FILE` accordingly.

With **Docker Compose**, define a **secret** pointing at the file (see [docker-compose.example.yml](docker-compose.example.yml)) and list it under the service’s `secrets:`; set:

```yaml
environment:
  AWS_SHARED_CREDENTIALS_FILE: /run/secrets/aws_credentials
```

Do **not** bake credentials into the image. Restrict file permissions on the host; Compose secrets are mounted read-only inside the container.

You can also use environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or an IAM role on AWS (ECS/EC2), as supported by **boto3**.

## IAM

Grant least privilege on the hosted zones you manage, for example:

- `route53:ListResourceRecordSets`
- `route53:ChangeResourceRecordSets`

Scope `Resource` to `arn:aws:route53:::hostedzone/Z...` for each zone.

## Companion TXT record

On every A record update (automatic or manual), the service writes a **TXT** record whose **name** defaults to `_ddns-last-update.<A-record-labels>` in the same zone, and whose **value** is the update time (e.g. `2026-04-18T12:00:00Z`, quoted for Route53). Override with `txt_record_name` per record if needed.

## Environment variables

See [`.env.example`](.env.example) for **`HOST`**, **`PORT`**, **`CONFIG_FILE`**, and AWS-related variables.

| Variable | Notes |
| -------- | ----- |
| `HOST` / `PORT` | Bind address for the web UI (defaults `0.0.0.0` / `8080`). |
| `CONFIG_FILE` | Path to YAML config. Default: `config.yaml` (local dev). Docker image defaults to `/config.yaml`. |

`poll_interval_seconds`, `checkip_url`, Route53 `records`, and Apprise URLs are **not** environment variables; use the YAML file.

## Security

The web UI has **no authentication**. Anyone who can reach the port can read IPs and trigger Route53 updates. Run only on **trusted networks**, bind to localhost when appropriate, or place a reverse proxy with auth in front. 

## Development

```bash
pytest
```

## License

Add your license as needed.
