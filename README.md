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

2. Load Testing:
```bash
# Success requests
while true; do curl http://localhost:5000/items; sleep 0.5; done

# Error requests
while true; do curl http://localhost:5000/nonexistent; sleep 2; done
```

### Monitoring

1. Prometheus UI:
- Access: http://localhost:9090
- Check targets: http://localhost:9090/targets

2. Grafana Dashboard:
- Access: http://localhost:3000
- Default credentials:
  - Username: admin
  - Password: admin

### Metrics Endpoints
```bash
# REST service metrics
curl http://localhost:5000/metrics

# gRPC service metrics
curl http://localhost:9103/metrics
```

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

### Troubleshooting
If services fail to start:
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

Check container logs:
```bash
docker compose logs -f
```
