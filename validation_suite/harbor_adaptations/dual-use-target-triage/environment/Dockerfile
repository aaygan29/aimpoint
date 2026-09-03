FROM --platform=linux/amd64 python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir rdkit==2024.3.5 pandas==2.2.2

WORKDIR /workdir

# Base-task inputs (shipped identically to drug-target-selection so the underlying
# capability computation is unchanged).
COPY fragments.json profile_alpha.json profile_bravo.json assemble.py vocab.json /workdir/
