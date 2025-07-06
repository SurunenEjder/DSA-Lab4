from flask import Flask, request, jsonify
import grpc
import items_pb2
import items_pb2_grpc
import os
import time
import logging
from pybreaker import CircuitBreaker, CircuitBreakerError
from functools import wraps
import json as pyjson
import threading
from prometheus_client import Counter, Histogram, generate_latest
#from prometheus_flask_exporter import PrometheusMetrics



# Prometheus metrics
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"])

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"])



app = Flask(__name__)
#metrics = PrometheusMetrics(app)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['JSON_SORT_KEYS'] = False

@app.before_request
def before_request():
    request.start_time = time.time()

# def start_timer():
#     # returns a stop-function bound to the request
#     request._timer = REQUEST_LATENCY.labels(
#         request.method, request.path).time()
    
@app.after_request
def after_request(response):
    # Calculate request duration
    request_latency = time.time() - request.start_time
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path
    ).observe(request_latency)
    
    # Count the request
    REQUEST_COUNTER.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code
    ).inc()
    
    return response

@app.route("/metrics")
def metrics():
    # Standard text format understood by Prometheus
    return generate_latest(), 200, {"Content-Type": "text/plain; version=0.0.4"}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# gRPC Configuration
GRPC_HOST = os.getenv("GRPC_HOST", "localhost")
GRPC_PORT = os.getenv("GRPC_PORT", "50051")

# Enhanced gRPC channel with reliability options
channel = grpc.insecure_channel(
    f"{GRPC_HOST}:{GRPC_PORT}",
    options=[
        ('grpc.connect_timeout_ms', 5000),
        ('grpc.enable_retries', 1),
        ('grpc.keepalive_timeout_ms', 10000),
        ('grpc.max_receive_message_length', 100 * 1024 * 1024),
        ('grpc.max_send_message_length', 100 * 1024 * 1024)
    ]
)

# Circuit Breaker Configuration
class CircuitBreakerMonitor:
    def state_change(self, cb, old_state, new_state):
        logger.info(f"CircuitBreaker state changed from {old_state} to {new_state}")
        print(f"CircuitBreaker state changed from {old_state} to {new_state}")

    def before_call(self, cb, func, *args, **kwargs):
        pass

    def failure(self, cb, exc):
        pass

    def success(self, cb):
        pass

breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    exclude=[
        grpc.StatusCode.NOT_FOUND,
        grpc.StatusCode.INVALID_ARGUMENT
    ],
    listeners=[CircuitBreakerMonitor()],
    name="gRPC_Circuit_Breaker"
)

stub = items_pb2_grpc.ItemServiceStub(channel)


# This decorator retries gRPC calls with exponential backoff
def retry_grpc(max_retries=3, initial_delay=0.1):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except grpc.RpcError as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                except Exception as e:
                    logger.error(f"Unexpected error: {str(e)}")
                    raise
        return wrapper
    return decorator

# Connection verification
# This function checks if the gRPC connection is active
def verify_grpc_connection():
    try:
        list(stub.ListAllItems(items_pb2.Empty(), timeout=1))
        return True
    except grpc.RpcError as e:
        logger.error(f"gRPC connection failed: {e.code().name}")
        return False

# Health Check Endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        channel_ready = grpc.channel_ready_future(channel).result(timeout=1)
        try:
            list(stub.ListAllItems(items_pb2.Empty(), timeout=1))
            grpc_status = "connected"
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                grpc_status = "connected"
            else:
                grpc_status = f"disconnected ({e.code().name})"
        
        return jsonify({
            "status": "healthy",
            "grpc": grpc_status,
            "breaker": breaker.current_state,
            "breaker_failures": breaker.fail_counter,
            "services": {
                "grpc": f"{GRPC_HOST}:{GRPC_PORT}",
                "mongo": os.getenv("MONGO_HOST", "mymongo")
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

# Reset Circuit Breaker
@app.route('/reset-breaker', methods=['POST'])
def reset_breaker():
    try:
        logger.info("Resetting circuit breaker...")
        breaker.close()
        logger.info("Circuit breaker closed")
        logger.info("Circuit breaker fully reset")
        return jsonify({
            "status": "success",
            "breaker_state": "closed",
            "fail_count": 0
        }), 200
    except Exception as e:
        logger.error(f"Reset failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

# CRUD Endpoints with Retry and Circuit Breaker
@app.route('/items', methods=['POST'])
def create_item():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Name is required'}), 400

        response = breaker.call(
            stub.AddItem,
            items_pb2.ItemRequest(
                id=data.get('id', 0),
                name=data['name']
            ),
            timeout=3
        )
        return jsonify({'id': response.id, 'name': response.name}), 201

    except pyjson.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 400
    except grpc.RpcError as e:
        logger.error(f"GRPC error: {e.code().name}")
        return jsonify({'error': f'Service error: {e.details()}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/items', methods=['GET'])
@retry_grpc()
def get_all_items():
    try:
        items = list(stub.ListAllItems(items_pb2.Empty(), timeout=1))
        return jsonify([{"id": item.id, "name": item.name} for item in items]), 200
    except grpc.RpcError as e:
        logger.error(f"gRPC error: {e.code().name}")
        return jsonify({'error': 'Service error'}), 500

@app.route('/items/<int:item_id>', methods=['GET'])
@retry_grpc()
def get_item(item_id):
    try:
        item = stub.GetItemById(items_pb2.ItemRequest(id=item_id), timeout=1)
        if item.id == 0:
            return jsonify({'error': 'Item not found'}), 404
        return jsonify({"id": item.id, "name": item.name}), 200
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({'error': 'Item not found'}), 404
        logger.error(f"gRPC error: {e.code().name}")
        return jsonify({'error': 'Service error'}), 500


# Background thread to monitor gRPC connection
# This function runs in a separate thread to monitor the gRPC connection
def monitor_grpc_connection():
    while True:
        time.sleep(10)  # Check every 10 seconds
        if not verify_grpc_connection():
            logger.warning("gRPC connection lost, attempting to reconnect...")
            # Re-establish the gRPC channel
            global channel
            channel = grpc.insecure_channel(
                f"{GRPC_HOST}:{GRPC_PORT}",
                options=[
                    ('grpc.connect_timeout_ms', 5000),
                    ('grpc.enable_retries', 1),
                    ('grpc.keepalive_timeout_ms', 10000),
                    ('grpc.max_receive_message_length', 100 * 1024 * 1024),
                    ('grpc.max_send_message_length', 100 * 1024 * 1024)
                ]
            )
            global stub
            stub = items_pb2_grpc.ItemServiceStub(channel)

if __name__ == '__main__':
    # Verify connection at startup
    if not verify_grpc_connection():
        logger.error("Initial gRPC connection failed")
    
    logger.info(f"Starting REST service on port 5000, connecting to gRPC at {GRPC_HOST}:{GRPC_PORT}")
    
    # Start the background thread for monitoring gRPC connection
    threading.Thread(target=monitor_grpc_connection, daemon=True).start()
    
    app.run(host="0.0.0.0", port=5000)