# Route53 dynamic DNS

Service that keeps **Route53 A records** aligned with your current **public IPv4**, using `https://checkip.amazonaws.com`. It runs a background poll loop, **UPSERTs** a **companion TXT record** with the **update time** (ISO-8601 UTC) whenever the A record changes, and exposes a **small status website** (no authentication—see [Security](#security)).

Behavior and requirements follow [DESIGN.md](DESIGN.md).

## Record configuration (JSON file)

Route53 are configured in a JSON document mounted into the container. Set the **`ROUTE53_RECORDS_FILE`** environment variable to the **path of a JSON file on disk**. The file must contain a **JSON array** of objects, each with:

- `hosted_zone_id` — Route53 hosted zone ID (e.g. `Z123...`)
- `record_name` — FQDN for the A record (trailing dot recommended, e.g. `dyn.example.com.`)
- `ttl` — optional (default `300`)
- `txt_record_name` — optional; defaults to `_ddns-last-update.<your-A-record-name>` so existing TXT on the A name is not overwritten

Copy the sample file and edit it:

```bash
cp examples/records.example.json records.json
# edit records.json with your zone and names
export ROUTE53_RECORDS_FILE="$PWD/records.json"
```

In **Docker**, mount the file as a **volume** and set `ROUTE53_RECORDS_FILE` to the path **inside the container** (see [Docker](#docker) and [docker-compose.example.yml](docker-compose.example.yml)).

## Quick start (local)

Python **3.12+**, virtualenv recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env`, set `ROUTE53_RECORDS_FILE` to your `records.json` path, and configure AWS credentials (environment variables or `AWS_SHARED_CREDENTIALS_FILE`). By default the poller runs every **4 hours** (`POLL_INTERVAL_SECONDS=14400`); override if you need a different interval.

```bash
export ROUTE53_RECORDS_FILE="$PWD/records.json"
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# or use AWS_PROFILE / shared credentials file — see below
route53-ddns
```

Or with Uvicorn directly (use `--factory` so settings load when the process starts, not at import time):

```bash
uvicorn route53_ddns.main:create_app --factory --host 0.0.0.0 --port 8080
```

## Docker

Build:

```bash
docker build -t route53-ddns .
```

Run with a **bind-mounted** records file and AWS credentials file (paths on the host → paths in the container):

```bash
docker run --rm \
  -e ROUTE53_RECORDS_FILE=/config/records.json \
  -e AWS_SHARED_CREDENTIALS_FILE=/run/secrets/aws_credentials \
  -v "$PWD/records.json:/config/records.json:ro" \
  -v "$PWD/aws_credentials.ini:/run/secrets/aws_credentials:ro" \
  -p 8080:8080 \
  route53-ddns
```

- **`ROUTE53_RECORDS_FILE`** must match the in-container path you choose on the right side of the records volume (`/config/records.json` in this example).
- Mount the JSON file **read-only** (`:ro`) if you do not need the container to modify it.
- **`POLL_INTERVAL_SECONDS`** is optional; if omitted, the default is **4 hours** (`14400` seconds).

### Docker Compose

An example stack is in **[docker-compose.example.yml](docker-compose.example.yml)**. Copy `examples/records.example.json` to `records.json`, add an `aws_credentials.ini` beside it (shared-credentials format), then:

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

See [`.env.example`](.env.example) for `HOST`, `PORT`, `POLL_INTERVAL_SECONDS`, `CHECKIP_URL`, **`ROUTE53_RECORDS_FILE`** (required), and AWS-related variables.

| Variable | Notes |
| -------- | ----- |
| `POLL_INTERVAL_SECONDS` | Seconds between poll cycles. **Default: `14400` (4 hours).** |

All other defaults match `.env.example` and [`config.py`](src/route53_ddns/config.py) (`DEFAULT_POLL_INTERVAL_SECONDS`).

## Security

The web UI has **no authentication**. Anyone who can reach the port can read IPs and trigger Route53 updates. Run only on **trusted networks**, bind to localhost when appropriate, or place a reverse proxy with auth in front. 

## Development

```bash
pytest
```

## License

Add your license as needed.
