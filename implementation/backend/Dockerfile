FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY forge /app/forge

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

EXPOSE 9147

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "9147"]
