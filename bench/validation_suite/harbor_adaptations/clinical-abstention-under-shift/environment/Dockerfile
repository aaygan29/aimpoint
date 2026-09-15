FROM --platform=linux/amd64 python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir numpy==1.26.4 pandas==2.2.2 scipy==1.13.1
WORKDIR /workdir
COPY cohort.csv patient_in_dist.json patient_ood.json threshold.json reason_vocab.json /workdir/
