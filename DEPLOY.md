# Deploying to AWS (one EC2 server)

Everything runs on one small server with Docker Compose, exactly like on your laptop, plus Caddy in front:

```
Internet ──HTTPS──▶ Caddy ──┬─ /      → the built React app
                            └─ /api/* → api (FastAPI) ──▶ Redis ◀── stream_prices ◀── Alpaca
                                                     └─▶ Postgres ◀── match_orders
```

Only Caddy is reachable from the internet. Postgres, Redis and the API are private to the server.

**Cost:** a `t3.small` in Ireland is roughly $15–17/month including disk and IP, so the free-plan credits cover a few months.

---

## 0. Before you start

- **Push the new files to GitHub (`main`).** The server downloads your code from there.
- **Only one copy of `stream_prices` may run.** Alpaca allows one live connection per account, so when the
  server is running, stop the laptop one: `docker compose stop stream_prices` (or `docker compose down`).

## 1. Set a budget alert (2 minutes; also earns $20 of credits)

AWS console → **Billing and Cost Management → Budgets → Create budget** → use the *Monthly cost budget*
template, e.g. $20, with your email.

## 2. Launch the server

AWS console → top right, pick region **Europe (Ireland) eu-west-1** → **EC2 → Launch instance**:

| Setting | Value |
|---|---|
| Name | `trading-app` |
| Image | **Ubuntu Server 24.04 LTS** (64-bit x86) |
| Instance type | **t3.small** (t3.micro's 1 GB is too little) |
| Key pair | **Create new key pair** → RSA, `.pem` → it downloads `trading-app.pem`. Keep it safe; it's your only way in. |
| Network → Security group | Create one. Allow **SSH from My IP**, **HTTPS from anywhere**, **HTTP from anywhere** |
| Storage | **20 GiB gp3** |

Click **Launch instance**.

## 3. Give it a fixed address (Elastic IP)

Otherwise the address changes whenever the server stops, and your site name and HTTPS break.

EC2 → **Elastic IPs → Allocate Elastic IP address → Allocate**, then **Actions → Associate** → pick
the `trading-app` instance. Note the IP, e.g. `34.240.12.7`.

Your site's name will be that IP with dashes + `.sslip.io`, e.g. **`34-240-12-7.sslip.io`**
(a free service that points that name at that IP, so you don't need to buy a domain yet).

## 4. Connect to the server

In Git Bash on your laptop, from the folder with the key:

```bash
chmod 400 trading-app.pem
ssh -i trading-app.pem ubuntu@34.240.12.7
```

Type `yes` the first time. Everything below runs **on the server**.

## 5. Install Docker (once)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu        # lets you run docker without sudo
exit                                  # log out and back in for that to apply
```

Reconnect with the same `ssh` command, then add 2 GB of swap (spare memory on disk, so builds don't run out):

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 6. Get the code and add the settings

```bash
git clone https://github.com/SeanLynch1/trading-app.git
cd trading-app
```

**Your Alpaca keys**, same as on your laptop:

```bash
cp backend/.env.example backend/.env
nano backend/.env                     # fill in ALPACA_API_KEY and ALPACA_SECRET_KEY; Ctrl+O, Enter, Ctrl+X to save
```

(Its `REDIS_URL` and `DATABASE_URL` lines don't matter here; Compose overrides them.)

**The server settings:**

```bash
cp .env.prod.example .env
openssl rand -hex 24                  # copy this: your database password
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'choose-a-site-password'   # copy the hash
nano .env
```

Fill in `DOMAIN` (from step 3), `POSTGRES_PASSWORD` (the random one), `BASIC_AUTH_USER`, and
`BASIC_AUTH_HASH` (keep the single quotes around it).

## 7. Start everything

```bash
docker compose up -d --build
```

The first build takes a few minutes. Then check:

```bash
docker compose ps -a                  # all running; setup "exited (0)"
docker compose logs caddy | grep -i certificate   # "certificate obtained successfully"
docker compose logs -f stream_prices  # live trades (Ctrl+C to stop watching)
```

Open **`https://34-240-12-7.sslip.io`** (your own name), log in with the site password, and you're live.

---

## Updating the site after code changes

Push to GitHub from your laptop, then on the server:

```bash
cd trading-app
git pull
docker compose up -d --build          # rebuilds only what changed; the database is kept
```

## Useful commands (on the server, in `trading-app`)

| Command | What it does |
|---|---|
| `docker compose ps -a` | what's running |
| `docker compose logs -f api` | follow one service's logs |
| `docker compose restart stream_prices` | restart one service |
| `docker compose down` | stop everything (data is kept) |

## If something goes wrong

- **The site doesn't load / no certificate:** check the security group allows 80 and 443 from anywhere,
  and that `DOMAIN` matches the Elastic IP. Then `docker compose logs caddy`.
- **No live prices:** `docker compose logs stream_prices`. "too many connections"/"connection limit"
  means another copy is running (your laptop?).
- **A service keeps restarting:** `docker compose logs <service>` shows why.

## Stopping costs

EC2 → Instances → **Stop instance** stops the hourly server charge; the disk and the Elastic IP still cost
a little (a few dollars a month). To stop paying entirely: **Terminate** the instance, delete its volume,
and **release** the Elastic IP.
