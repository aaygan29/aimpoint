FROM --platform=linux/amd64 python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir numpy==1.26.4 pandas==2.2.2 scikit-learn==1.5.1
WORKDIR /workdir
COPY dataset_a.csv dataset_b.csv marker_rule.json vocab.json /workdir/
