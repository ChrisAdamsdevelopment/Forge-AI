FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic pydantic-settings httpx sqlalchemy aiosqlite jinja2 pyyaml

COPY forge /app/forge

EXPOSE 9147

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "9147"]
