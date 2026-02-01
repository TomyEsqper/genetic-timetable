# Etapa 1: Builder (Compilación)
FROM python:3.10-slim as builder

WORKDIR /app

# Instalar dependencias de compilación (pesadas)
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Etapa 2: Final (Ejecución - Ligera)
FROM python:3.10-slim

WORKDIR /app

# Instalar solo librerías de sistema necesarias para correr (runtime)
# libmysqlclient-dev es necesario para mysqlclient, aunque trae headers, es seguro.
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    libjpeg62-turbo \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Copiar entorno virtual desde el builder
COPY --from=builder /opt/venv /opt/venv

# Configurar variables de entorno
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copiar código del proyecto
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["gunicorn", "colegio.wsgi:application", "--bind", "0.0.0.0:8000"]
