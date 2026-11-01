#!/usr/bin/env bash
# The always-on proof (test-plan section 10, the parts this branch can run): build the image, start compose.yaml
# with Caddy on a local CA (`tls internal`), reach the app over HTTPS through Caddy with the login, show the app
# port is not reachable any other way, then back the data volume up, destroy it, restore it and compare.
#
#   tests/deploy/proof.sh            needs Docker Engine with Compose v2, curl and python3
#
# It uses its own Compose project (composer-proof), ports 18080/18443 and subnet 172.30.66.0/24, so it does not
# touch a real install on the same machine, and removes everything it made when it ends.
# Until phase P1 adds `composer up`, it layers tests/deploy/compose.serve-0.1.yaml over compose.yaml.
# Prints one PASS / FAIL / SKIP line per check and exits 1 if any check failed.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d)
PROJECT=composer-proof
DOMAIN=composer.localhost
HTTP_PORT=${PROOF_HTTP_PORT:-18080}
HTTPS_PORT=${PROOF_HTTPS_PORT:-18443}
URL="https://$DOMAIN:$HTTPS_PORT"
passed=0
failed=0

ok() { echo "PASS $*"; passed=$((passed + 1)); }
bad() { echo "FAIL $*"; failed=$((failed + 1)); }
skip() { echo "SKIP $*"; }
dc() {
  docker compose -p "$PROJECT" --env-file "$WORK/env" \
    -f "$ROOT/compose.yaml" -f "$ROOT/tests/deploy/compose.serve-0.1.yaml" "$@"
}
cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf -- "$WORK"
}
trap cleanup EXIT
secret() { python3 -c 'import secrets; print(secrets.token_urlsafe(24))'; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 --cacert "$WORK/root.crt" \
  --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" "$@"; }
manifest() {  # sha256 and path of every file in the data volume, sorted
  dc exec -T composer python -c 'import hashlib, os
rows = []
for d, _, files in os.walk("/data"):
    for f in files:
        p = os.path.join(d, f)
        rows.append(hashlib.sha256(open(p, "rb").read()).hexdigest() + "  " + p)
print("\n".join(sorted(rows)))'
}

PASSWORD=$(secret)
cat > "$WORK/env" <<PROOF_ENV_END
COMPOSER_DOMAIN=$DOMAIN
COMPOSER_TLS=internal
COMPOSER_LOGIN_USER=proof
COMPOSER_LOGIN_HASH='not set yet'
COMPOSER_HTTP_PORT=$HTTP_PORT
COMPOSER_HTTPS_PORT=$HTTPS_PORT
COMPOSER_FRONT_SUBNET=172.30.66.0/24
COMPOSER_SERVER_PASS=$(secret)
PROOF_ENV_END

echo "== build"
dc build composer
ok "image built: $(docker image inspect lensmith-composer:proof --format '{{.Id}} {{.Size}} bytes')"

echo "== login hash (caddy hash-password, password on stdin, never on a command line)"
HASH=$(printf '%s\n' "$PASSWORD" | dc run --rm --no-deps -T caddy caddy hash-password)
case "$HASH" in '$2a$'*) ok "bcrypt hash made" ;; *) bad "unexpected hash output: ${HASH:0:12}"; exit 1 ;; esac
python3 - "$WORK/env" "$HASH" <<'PROOF_PY_END'
import sys
path, value = sys.argv[1], sys.argv[2]
text = open(path).read().replace("COMPOSER_LOGIN_HASH='not set yet'", f"COMPOSER_LOGIN_HASH='{value}'")
open(path, "w").write(text)
PROOF_PY_END

echo "== up"
dc up -d --wait
ok "compose up: $(dc ps --format '{{.Service}}={{.State}}/{{.Health}}' | tr '\n' ' ')"

for _ in $(seq 1 30); do
  dc exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > "$WORK/root.crt" 2>/dev/null && \
    [ -s "$WORK/root.crt" ] && break
  sleep 1
done
[ -s "$WORK/root.crt" ] && ok "Caddy's local CA root exported" || bad "no local CA root"

echo "== through Caddy, over HTTPS"
for _ in $(seq 1 20); do [ "$(code "$URL/")" != "000" ] && break; sleep 1; done
c=$(code "$URL/"); [ "$c" = 401 ] && ok "no login: $c" || bad "no login: expected 401, got $c"
c=$(code -u "proof:wrong-$PASSWORD" "$URL/"); [ "$c" = 401 ] && ok "wrong password: $c" || bad "wrong password: $c"
c=$(code -u "proof:$PASSWORD" "$URL/"); [ "$c" = 200 ] && ok "with login: $c" || bad "with login: expected 200, got $c"
verify=$(curl -s -o "$WORK/page.html" -w '%{ssl_verify_result} %{http_version}' --max-time 10 \
  --cacert "$WORK/root.crt" --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" -u "proof:$PASSWORD" "$URL/")
[ "${verify%% *}" = 0 ] && ok "certificate verified against the local CA (ssl_verify_result=0, HTTP ${verify#* })" \
  || bad "certificate did not verify: $verify"
grep -q 'Composer' "$WORK/page.html" && ok "the page is Composer's ($(wc -c < "$WORK/page.html") bytes)" \
  || bad "page body is not Composer's"
c=$(code -u "proof:$PASSWORD" "$URL/api/latest")
[ "$c" = 200 ] && ok "the app's data route through Caddy: $c" || bad "/api/latest: $c"
hdr=$(curl -s -D - -o /dev/null --max-time 10 --cacert "$WORK/root.crt" --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" \
  -u "proof:$PASSWORD" "$URL/" | tr -d '\r')
echo "$hdr" | grep -qi '^strict-transport-security:' && ok "HSTS header set" || bad "no HSTS header"
echo "$hdr" | grep -qi '^server:' && bad "Server header leaked" || ok "no Server header"
c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 --resolve "$DOMAIN:$HTTP_PORT:127.0.0.1" "http://$DOMAIN:$HTTP_PORT/")
case "$c" in 30[178]) ok "plain HTTP redirects to HTTPS: $c" ;; *) bad "plain HTTP: $c" ;; esac

echo "== the app port is not reachable directly"
APP=$(dc ps -q composer)
published=$(docker port "$APP" || true)
[ -z "$published" ] && ok "composer publishes no port (docker port is empty)" || bad "composer publishes: $published"
if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:8765/"; then bad "something answers on host 127.0.0.1:8765"
else ok "host 127.0.0.1:8765 refuses (nothing listens there)"; fi
APP_IP=$(docker inspect "$APP" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
probe() {  # probe NETWORK: can a throwaway container on NETWORK fetch the app by its address?
  docker run --rm --network "$1" --entrypoint python lensmith-composer:proof -c \
    "import urllib.request; urllib.request.urlopen('http://$APP_IP:8765/api/latest', timeout=4)" >/dev/null 2>&1
}
if probe "${PROJECT}_front"; then ok "control: the same probe on the front network reaches $APP_IP:8765"
else bad "control probe on the front network failed, so the next check would prove nothing"; fi
if probe bridge; then bad "a container on another Docker network reached $APP_IP:8765"
else ok "a container on another Docker network cannot reach $APP_IP:8765"; fi
dc exec -T caddy wget -q -O /dev/null "http://composer:8765/api/latest" && \
  ok "Caddy reaches composer:8765 on the front network (the only way in)" || bad "Caddy cannot reach the app"
ro=$(docker inspect "$APP" --format '{{.HostConfig.ReadonlyRootfs}} {{.Config.User}}')
[ "$ro" = "true composer" ] && ok "app root filesystem read-only, user composer" || bad "app hardening: $ro"
echo "INFO app memory at idle: $(docker stats --no-stream --format '{{.MemUsage}}' "$APP")"

echo "== backup and restore of the data volume"
dc exec -T composer composer demo --page /data/demo-brief.html
manifest > "$WORK/before.txt"
[ -s "$WORK/before.txt" ] && ok "data in the volume: $(wc -l < "$WORK/before.txt") file(s)" || bad "volume empty"
if dc exec -T composer composer backup --help >/dev/null 2>&1; then
  bad "composer backup exists now: extend this proof to use it (docs/deploy-vps.md step 9)"
else
  skip "composer backup: pending phase P1 (data generations) and P3; the volume copy below works today"
fi
dc stop composer
dc run --rm --no-deps -T --entrypoint tar composer -C /data -czf - . > "$WORK/composer-data.tar.gz"
[ -s "$WORK/composer-data.tar.gz" ] && ok "volume copied out: $(wc -c < "$WORK/composer-data.tar.gz") bytes" \
  || bad "empty backup"
dc down
docker volume rm "${PROJECT}_composer-data" >/dev/null
docker volume inspect "${PROJECT}_composer-data" >/dev/null 2>&1 && bad "volume still there" || ok "volume destroyed"
dc run --rm --no-deps -T --entrypoint tar composer -C /data -xzf - < "$WORK/composer-data.tar.gz"
dc up -d --wait
manifest > "$WORK/after.txt"
if cmp -s "$WORK/before.txt" "$WORK/after.txt"; then ok "restored volume matches, file for file (sha256)"
else bad "restored volume differs"; diff "$WORK/before.txt" "$WORK/after.txt" || true; fi
for _ in $(seq 1 20); do [ "$(code -u "proof:$PASSWORD" "$URL/")" = 200 ] && break; sleep 1; done
c=$(code -u "proof:$PASSWORD" "$URL/"); [ "$c" = 200 ] && ok "app serves again after restore: $c" || bad "after restore: $c"

echo "proof: $passed passed, $failed failed"
[ "$failed" = 0 ]
