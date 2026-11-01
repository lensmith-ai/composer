# Run Composer always on: a server, Docker Compose and Caddy

This guide puts Composer on a server you rent (any provider that gives you a Linux machine with a public address),
behind [Caddy](https://caddyserver.com/) for HTTPS and a login, so you can open your briefs from any device.
The same files run on your own computer first, with a local certificate authority instead of a public one:
[try it on your own computer](#try-it-on-your-own-computer-first) before you rent anything.

**How to read the commands.** Every command below was run as written on a Linux machine with Docker Engine 29 and
Compose v5, unless its block says **runs on your server** (it needs your server, your domain or your DNS provider,
so we could not run it for you). Lines that start with `#` are notes, not commands.

**What works today, and what is pending.** This guide is written for Composer 0.2, which is being built in phases.

| part | status |
|---|---|
| The image, Compose, Caddy, HTTPS, the login, the app reachable only through Caddy | works; proved by `tests/deploy/proof.sh` |
| Copying your data volume out and restoring it | works today (step 9) |
| `composer up`, the command the image runs | **pending phase P1**. Until then, run every `docker compose` command with `COMPOSE_FILE=compose.yaml:tests/deploy/compose.serve-0.1.yaml` set, which runs the 0.1 `composer serve` instead (see [Today, on 0.1](#today-on-01)) |
| Your model key, the daily brief, `composer backup`, `composer restore`, updates and rollback | **pending phases P1 and P3**; marked where they appear |
| A published image to pull, and its attestation | **pending the first release** (phase P5); until then you build the image on the server |

## What you get

```
  you ──https──▶ Caddy (ports 80, 443) ──private network──▶ composer (port 8765, not published)
                  certificates, login                        your briefs: the composer-data volume
```

- **One login for one person.** Composer has no accounts of its own, so Caddy asks for a name and password on every
  page and every request before anything reaches Composer, and it never passes the login on.
- **The app is not on the internet.** Its container publishes no port. Only Caddy does (80 and 443). The app runs as
  an unprivileged user on a read-only filesystem.
- **Your data in one place.** Everything Composer keeps is in one Docker volume, `composer-data`, mounted at `/data`.
  Updates switch a pointer file *inside* that volume and never rename it, so your backups and recovery records stay put.
- **No telemetry.** Composer sends nothing about you anywhere: no analytics, no crash reports, no update checks.
  The server talks to the feeds you chose, the model provider you chose (with your key), and Caddy's certificate
  authority.

## What you need

- A Linux server with a public IPv4 address (IPv6 too, if you like) and SSH access. A small one is enough for text
  briefs: on our test machine the app used 20 to 32 MB of memory at rest and Caddy 14 MB, and Docker reported the
  image as 47 MB. These numbers are for 0.1 with no brief running; we will measure them again for 0.2, including
  while a brief is composed, and narration needs more.
- A domain name, or a subdomain of one you have, such as `brief.example.com`.
- About 20 minutes.

**What it costs.** Two separate bills:

1. **The model, per brief.** Measured on 2026-11-01: one brief with the default model (Claude Sonnet 5.5) made
   7 calls and cost **$0.0755** at Anthropic's published prices (the README's [What a brief costs](../README.md#what-a-brief-costs)
   shows the token counts and the pricing page). One brief a day is about **$2.30 a month**, plus any you compose by hand.
2. **The server, per month.** Set by your provider; check their price list. We do not quote provider prices here.

## 1. Install Docker on the server

**Runs on your server.** Follow Docker's own instructions for your Linux distribution,
[Install Docker Engine](https://docs.docker.com/engine/install/) (it includes the Compose plugin), then check:

```sh
docker compose version
```

## 2. Point your domain at the server

**Runs at your DNS provider.** Add an `A` record for `brief.example.com` with your server's IPv4 address (and an
`AAAA` record for IPv6, if your server has one). Then, on the server, check it answers with the server's address:

```sh
# runs on your server
getent hosts brief.example.com
```

## 3. Open the firewall: 22, 80 and 443 only

**Runs on your server.** With `ufw` (Ubuntu and Debian):

```sh
# runs on your server
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

Docker opens the ports it publishes by itself, past `ufw`. That is why the app's container publishes none: the only
published ports are Caddy's.

## 4. Get Composer

**Runs on your server.**

```sh
# runs on your server
git clone https://github.com/lensmith-ai/composer.git
cd composer
```

All the commands below run in this `composer` folder.

## 5. Your settings and your login

Copy the example settings:

```sh
cp .env.example .env
```

Open `.env` in an editor (`nano .env`) and set:

- `COMPOSER_DOMAIN`: your domain, such as `brief.example.com`;
- `COMPOSER_TLS`: your email address (for the certificate authority's account), or `internal` for a local trial;
- `COMPOSER_LOGIN_USER`: the login name you want.

Then make the password's hash. Caddy asks for the password twice and prints a hash that starts with `$2a$`; the
password itself is not stored anywhere:

```sh
docker compose run --rm --no-deps caddy caddy hash-password
```

Put the hash in `.env` **inside single quotes** (the hash contains `$` signs, which Compose would otherwise read
as variables):

```
COMPOSER_LOGIN_HASH='$2a$14$...the whole hash...'
```

Keep `.env` private: it is ignored by git and not copied into the image.

## 6. Build the image

Until the first release is published, build the image on the server from the files you cloned (a minute or two):

```sh
docker compose build composer
```

**Pending the first release (P5):** set `COMPOSER_VERSION=0.2.0` in `.env` and pull the published image instead,
with `docker compose pull`. You can check where it came from before you run it, with the
[GitHub CLI](https://cli.github.com/):

```sh
# pending the first release
gh attestation verify oci://ghcr.io/lensmith-ai/composer:0.2.0 --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
```

## 7. Start it

```sh
docker compose up -d
docker compose ps
```

Both services should say `running`, and `composer` should become `healthy` within a minute. Open
`https://brief.example.com/` in a browser: it asks for your login, then shows Composer. The first visit can take a
few seconds while Caddy gets the certificate.

To check from the command line that the login is required (`401`) and works (`200`):

```sh
# runs on your server
curl -s -o /dev/null -w '%{http_code}\n' https://brief.example.com/
curl -s -o /dev/null -w '%{http_code}\n' -u me https://brief.example.com/
```

## 8. Your model key and a daily brief

**Pending phases P1 and P3.** Composer 0.2 stores your key inside the data volume (a file only the app can read,
mode 0600). It is never a container environment variable, because `docker inspect` shows those to anyone who can
run Docker on the server. You will set the key and the daily schedule once, in the app's settings page, or with
`composer setup` inside the container. The schedule runs inside the app (the same on a laptop and a server):
`restart: unless-stopped` brings it back after a reboot, and a missed run happens late if it is within 6 hours of
its time, and is skipped (and logged) otherwise. This section gets its exact commands when those phases land.

## 9. Backups

Two layers:

1. **Pending phases P1 and P3: `composer backup`.** It will write a dated archive of your current data (never your
   key, unless you ask) to `/data/backups` inside the volume, weekly by default, keeping the last 8, and
   `composer restore <file>` will bring one back.
2. **Works today: copy the whole volume out of Docker.** A backup that only lives inside the volume is gone when the
   volume is. Copy it out before every update, and regularly:

```sh
docker compose stop composer
docker compose run --rm --no-deps -T --entrypoint tar composer -C /data -czf - . > composer-data-$(date +%F).tar.gz
docker compose start composer
```

Then copy that file off the server. For example, with `rsync` to another machine you control (an example only;
any copy works):

```sh
# runs on your server
rsync -av composer-data-*.tar.gz you@backup.example.com:composer-backups/
```

**Restore** a copy into a fresh volume (this replaces everything in the volume with the copy; the date in the file
name is the one you are restoring):

```sh
docker compose down
docker volume rm composer_composer-data
docker compose run --rm --no-deps -T --entrypoint tar composer -C /data -xzf - < composer-data-2026-11-01.tar.gz
docker compose up -d
```

## 10. Updates and rollback

Before any update, take a copy as in step 9.

**Today (built from source):**

```sh
# runs on your server
git pull
```

```sh
docker compose build composer
docker compose up -d
```

**Pending phases P1, P3 and the first release.** An update will be a transaction: the new version copies your
current data, migrates the copy, checks it, and only then switches the pointer inside the volume; the old data is
kept untouched. To update, set the new `COMPOSER_VERSION` in `.env`, then `docker compose pull` and
`docker compose up -d`. To roll back: `docker compose exec composer composer rollback --data-only` (it exports any
briefs made since the update first), then set the previous `COMPOSER_VERSION` and `docker compose up -d`. An old
image refuses to start on data a newer version has migrated, and says which command to run.

## 11. Logs and problems

```sh
docker compose logs --tail 50 caddy
docker compose logs --tail 50 composer
```

| you see | likely cause |
|---|---|
| the browser cannot reach the site | DNS not pointing at the server yet (step 2), or ports 80/443 closed (step 3) |
| a certificate error on a public domain | Caddy could not reach its certificate authority, or DNS was wrong when it tried; fix that, then `docker compose restart caddy` |
| the login is asked for again and again | the hash in `.env` lost its `$` signs: put it in single quotes (step 5), then `docker compose up -d` |
| `composer` keeps restarting | `docker compose logs composer`; on this version, see [Today, on 0.1](#today-on-01) |

## 12. Stop, or remove everything

Stop it (your data stays in the volume):

```sh
docker compose down
```

Remove everything, including your data and Caddy's certificates. **Copy your data out first (step 9).**

```sh
docker compose down
docker volume rm composer_composer-data composer_caddy-data composer_caddy-config
```

## Narration (optional, not in the default image)

The default image has no narration. Narration reads a brief aloud with
[Kokoro](https://github.com/thewh1teagle/kokoro-onnx), and it brings parts under other licences: kokoro-onnx (MIT),
espeakng-loader (MIT), which bundles the eSpeak NG library (**GPL-3.0**), and the Kokoro model and voices
(Apache-2.0, about 354 MB). So narration is opt-in, in two ways, both **pending phase P3**:

- the model and voices are downloaded into your data volume only when you turn narration on, never baked into an image;
- the narration runtime will come as a separate image tag (`<version>-narration`), never the default. Any image we
  publish that includes eSpeak NG ships its GPL-3.0 licence text and a source offer, and the release note links the
  exact eSpeak NG source next to the image. Every release's SBOM lists all of these parts with their licences.

## Try it on your own computer first

The same files work on a laptop with Docker Desktop or Docker Engine. Caddy uses its own local certificate authority
instead of a public one (`COMPOSER_TLS=internal`), and the ports move to 8080 and 8443 so they do not need
administrator rights. Names ending in `.localhost` point at your own computer.

In `.env` (step 5), set:

```
COMPOSER_DOMAIN=composer.localhost
COMPOSER_TLS=internal
COMPOSER_HTTP_PORT=8080
COMPOSER_HTTPS_PORT=8443
```

Make the login hash as in step 5, then build and start (steps 6 and 7). Copy Caddy's local certificate authority out,
so your tools can check the certificate instead of skipping the check:

```sh
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt caddy-local-root.crt
curl -s -o /dev/null -w '%{http_code}\n' --cacert caddy-local-root.crt https://composer.localhost:8443/
```

The first `curl` says `401` (the login is needed). With `-u me` added, it asks for your password and says `200`.
In a browser, `https://composer.localhost:8443/` warns about the certificate until you add `caddy-local-root.crt`
to your system's trusted certificates; for a quick look, accept the warning once.

When you are done:

```sh
docker compose down
docker volume rm composer_composer-data composer_caddy-data composer_caddy-config
```

## Today, on 0.1

Until phase P1 adds `composer up`, the image's command does not exist yet in this branch's code, and the app
container would restart in a loop. Set this in the shell before the `docker compose` commands above, to run the 0.1
`composer serve` behind the same Caddy:

```sh
export COMPOSE_FILE=compose.yaml:tests/deploy/compose.serve-0.1.yaml
```

and add a long random phrase to `.env` (0.1 requires it to listen beyond loopback):

```
COMPOSER_SERVER_PASS=a-long-random-phrase
```

The 0.1 page shows the recorded brief; composing needs a key, which on 0.1 can only come from an environment
variable, which this guide does not use (step 8). Everything else in this guide (HTTPS, the login, the closed app port,
step 9's copies) works the same.
