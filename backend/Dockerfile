# Lightweight Lambda image — FastF1/Pandas/Scipy are pipeline-only now.
# Image goes from ~2GB → ~200MB, cold starts drop from ~10s → ~1s.
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["app.main.handler"]