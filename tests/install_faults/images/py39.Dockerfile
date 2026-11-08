# python 3.9 only (the official image: 3.9 with venv and pip, but too old for Composer, like macOS's python3 3.9.6)
FROM python@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null && useradd -m -s /bin/sh tester
