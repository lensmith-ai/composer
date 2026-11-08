# a Python 3.12 that is fine, like the python.org one; its venv templates are made group-writable (python.org's are)
FROM python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null && useradd -m -s /bin/sh tester
