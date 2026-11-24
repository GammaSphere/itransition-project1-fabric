FROM python:3.12-slim-bookworm

# Native libraries needed by the SQL Server driver bundled with mssql-python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libltdl7 libkrb5-3 libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY integrations/requirements.txt integrations/requirements.txt
RUN pip install --no-cache-dir -r integrations/requirements.txt
COPY integrations integrations

ENV PYTHONUNBUFFERED=1
