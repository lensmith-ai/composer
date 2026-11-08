# the same, with group-writable venv templates, as on a Mac with python.org's Python
FROM lc-fault-py312
RUN find /usr/local/lib/python3.12/venv/scripts -type f -exec chmod g+w {} +
