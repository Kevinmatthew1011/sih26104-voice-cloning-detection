# Docker & Container Orchestration: SIH26104

## 1. Docker Compose Configuration (`docker-compose.yml`)

The platform includes multi-container orchestration for the FastAPI backend, Next.js frontend, and PostgreSQL database:

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://voiceguard:securepassword@db:5432/voiceguard_db
      - DETECTION_ENGINE=aasist
      - AASIST_DEVICE=cpu
    depends_on:
      - db
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=voiceguard
      - POSTGRES_PASSWORD=securepassword
      - POSTGRES_DB=voiceguard_db
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  pgdata:
```

---

## 2. Launching with Docker

```bash
# Build and start all services in detached mode
docker compose up -d --build

# View container logs
docker compose logs -f

# Stop and remove containers
docker compose down
```
