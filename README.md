# DSA-Lab4

## DSA-Lab 4: Observability with Prometheus and Grafana

### Project Structure
```
dsa-lab4/
├── grpc/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
├── rest/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── observability/
│   ├── prometheus.yml
│   └── grafana-provisioning/
└── docker-compose.yml
```

### Setup and Running

1. Build and start services:
```bash
docker compose build
docker compose up -d
```

2. Check service status:
```bash
docker compose ps
```

3. View service logs:
```bash
docker compose logs rest-service
docker compose logs grpc-service
```

### Testing the Services

1. Test REST API:
```bash
curl http://localhost:5000/items
```

## Load Testing

Generate traffic to see metrics in action:

```bash
# Generate successful requests
while true; do curl http://localhost:5000/items; sleep 0.5; done

# Generate error requests
while true; do curl http://localhost:5000/nonexistent; sleep 2; done
```

## Observability & Monitoring

This project includes a complete monitoring stack with Prometheus, Grafana, and custom metrics.

### Architecture
- **REST Service** (Flask) - Port 5000
- **gRPC Service** - Port 50051  
- **MongoDB** - Port 27017
- **Prometheus** - Port 9090
- **Grafana** - Port 3000

### Metrics Endpoints
- REST Service metrics: `http://localhost:5000/metrics`
- gRPC Service metrics: `http://localhost:9103/metrics`

### Grafana Dashboard
Access the monitoring dashboard at `http://localhost:3000`
- Username: `admin`
- Password: `admin`

**Dashboard Features:**
- **Request Rate**: Real-time request rates for both REST and gRPC services
- **Error Rate**: HTTP error percentage tracking
- **Latency Histogram**: Separate latency visualization for REST endpoints and gRPC methods
- **Service Health**: Container health monitoring

### Key Metrics Tracked
- HTTP request duration and count by endpoint
- gRPC method latency and request count
- Error rates and status codes
- Database connection health

### Cleanup
```bash
docker compose down
```

### Additional Notes
- Prometheus scrapes metrics every 15 seconds
- Grafana dashboard includes:
  - Error Rate
  - Request Latency
  - Request Rate by endpoint
- Circuit breaker implemented in REST service
- Health checks configured for all services

## Troubleshooting

### Check Service Health
```bash
docker compose ps
curl http://localhost:9090/targets  # Prometheus targets
curl http://localhost:5000/health   # REST service health
```

### View Logs
```bash
docker compose logs -f rest-service
docker compose logs -f grpc-service
```

