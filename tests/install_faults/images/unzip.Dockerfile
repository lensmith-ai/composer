# bare plus unzip (so uv can be unpacked from PyPI's wheel)
FROM debian@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends curl ca-certificates unzip >/dev/null && useradd -m -s /bin/sh tester
