# Run Composer always on: a server, Docker Compose and Caddy

This guide puts Composer on a server you rent (any provider that gives you a Linux machine with a public address),
behind [Caddy](https://caddyserver.com/) for HTTPS and a login, so you can open your briefs from any device.
The same files run on your own computer first, with a local certificate authority instead of a public one:
[try it on your own computer](#try-it-on-your-own-computer-first) before you rent anything.

**How to read the commands.** Every command below was run as written on a Linux machine with Docker Engine 29 and
Compose v5, unless its block says **runs on your server** (it needs your server, your domain or your DNS provider,
so we could not run it for you). Lines that start with `#` are notes, not commands.

**What works.** This guide is written for Composer 0.2. Each part below is proved, and the one thing that depends on the release is the published image.

| part | status |
|---|---|
| The image, Compose, Caddy, HTTPS, the login, the app reachable only through Caddy | works; proved by `tests/deploy/proof.sh` |
| `composer up` (the command the image runs), your key in the data volume, the daily brief, `composer backup` / `composer restore` | works (steps 7 to 9) |
| Copying your whole data volume out and restoring it | works (step 9) |
| Optional narration, as a separate image | works (see [Narration](#narration-optional-not-in-the-default-image)) |
| A published image to pull, and its attestation | works from 0.2.0 (you can also build the image on the server) |

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

**Or use the published image:** set `COMPOSER_VERSION=0.2.1` in `.env` and pull the published image instead,
with `docker compose pull`. You can check where it came from before you run it, with the
[GitHub CLI](https://cli.github.com/):

```sh
gh attestation verify oci://ghcr.io/lensmith-ai/composer:0.2.1 --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
```

## 7. Start it

```sh
docker compose up -d
docker compose ps
```

Both services should say `running`, and `composer` should become `healthy` within a minute (its health check asks
the app's own `/health`). Open `https://brief.example.com/` in a browser: it asks for your login, then opens the
Composer app (at `/app/`). The first visit can take a
few seconds while Caddy gets the certificate.

To check from the command line that the login is required (`401`) and works (`200`):

```sh
# runs on your server
curl -s -o /dev/null -w '%{http_code}\n' https://brief.example.com/
curl -s -o /dev/null -w '%{http_code}\n' -u me https://brief.example.com/
```

## 8. Your model key and a daily brief

Composer stores your key inside the data volume, in `/data/secrets.env` (mode 0600, readable only by the app's
user). It is never a container environment variable, because `docker inspect` shows those to anyone who can run
Docker on the server. Set the key, your sources and an optional daily brief with the same questions a laptop
install asks (the key is typed without being shown):

```sh
docker compose run --rm --no-deps composer setup --data-only
docker compose restart composer
```

Run it again later with `--reconfigure provider`, `--reconfigure sources` or `--reconfigure schedule` to change one
part; everything else is kept. The daily brief runs inside the app (the same on a laptop and a server): `restart:
unless-stopped` brings it back after a reboot, a missed run happens late if it is within 6 hours of its time, and is
skipped (and logged) otherwise. Each scheduled brief is saved to your shelf. `docker compose exec composer composer
doctor` checks it all, one line per check; add `--online` to make one tiny model call and read every source.

## 9. Backups

Two layers:

1. **`composer backup`.** The app writes a dated archive of your current data (your briefs, settings and sources;
   never your key unless you add `--include-secrets`) to `/data/backups` once a week, keeping the last 8. Make one
   now and copy it out of the container:

```sh
docker compose exec composer composer backup
docker compose exec composer ls /data/backups
docker compose cp composer:/data/backups/composer-backup-20261101T120000Z.tar.gz .
```

   (the file name is the one `ls` printed). To bring one back, stop the app, restore, start it again. Restore checks
   the archive first (every file's SHA-256, no unsafe paths or links), backs up what is there now, and keeps the
   replaced data under `/data/recovery/replaced`:

```sh
docker compose stop composer
docker compose run --rm --no-deps -v "$PWD:/in:ro" composer restore /in/composer-backup-20261101T120000Z.tar.gz
docker compose start composer
```

2. **Copy the whole volume out of Docker.** A backup that only lives inside the volume is gone when the volume is.
   Copy it out before every update, and regularly:

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

An update is a transaction: when a new version needs a newer data schema, it copies your current data, migrates
the copy, and only then switches the pointer inside the volume; the old data is kept untouched. **After the first
release**, to update: set the new `COMPOSER_VERSION` in `.env`, then `docker compose pull` and `docker compose up -d`.
To roll back:

```sh
docker compose stop composer
docker compose run --rm --no-deps composer rollback --data-only
```

It exports any briefs made since the update to `/data/recovery/exports` first. Then set the previous
`COMPOSER_VERSION` and run `docker compose up -d`. An old image refuses to start on data a newer version has
migrated, and says which command to run.

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
| `composer` keeps restarting | `docker compose logs composer`; then `docker compose run --rm --no-deps composer doctor` |
| the app answers `403` through Caddy | `COMPOSER_PUBLIC_ORIGIN` does not match the address you opened (set it in `.env` when you use a port other than 443), or you changed `COMPOSER_FRONT_SUBNET` without setting `COMPOSER_CADDY_IP` to an address inside it |

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
[Kokoro](https://github.com/thewh1teagle/kokoro-onnx), and it brings parts under other licences: kokoro-onnx (MIT);
espeakng-loader, which bundles the eSpeak NG library (**GPL-3.0-or-later**); phonemizer-fork, which kokoro-onnx uses
(**GPL-3.0-or-later**); and the Kokoro model and voices (Apache-2.0, about 354 MB).
[THIRD-PARTY.md](../THIRD-PARTY.md) lists every package and what the GPL means if you pass a copy on. So narration
is opt-in, in two ways:

- the narration runtime is a separate image (`--target narration`, published as `<version>-narration`), never the
  default. It ships eSpeak NG's GPL-3.0 licence text and a source offer in `/usr/share/doc/composer-narration/`, and
  the release that publishes it attaches the exact eSpeak NG source. Every release's SBOM lists these parts;
- the model and voices are downloaded into your data volume only when you turn narration on, never baked into an image.

To turn it on, add `COMPOSER_TARGET=narration` to `.env`, rebuild, answer the narration question, and restart:

```sh
docker compose build composer
docker compose run --rm --no-deps composer setup --data-only --reconfigure narration
docker compose up -d
```

The question shows the size and the licences before anything is downloaded. Each brief is narrated after its text
is ready, from the brief's own narration script (the same words the page's transcript sheet shows), one brief at a
time and capped in length and time. If narration fails for a brief, that brief stays text-only and says why. To turn
it off, answer no to the same question: the page then shows no player and no voice picker.

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
COMPOSER_PUBLIC_ORIGIN=https://composer.localhost:8443
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
