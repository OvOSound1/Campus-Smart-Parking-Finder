# Campus Smart Parking Finder

A distributed parking management system implementing multithreaded server architecture, RPC communication, asynchronous messaging, and publish/subscribe event delivery.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup Instructions](#setup-instructions)
- [Running the System](#running-the-system)
- [Configuration](#configuration)
- [RPC Protocol Specification](#rpc-protocol-specification)
- [Thread Model](#thread-model)
- [Pub/Sub Design](#pubsub-design)
- [Back-Pressure Policy](#back-pressure-policy)
- [Testing](#testing)

## Features

- **Multithreaded TCP Server**: Concurrent client handling with thread-per-connection model
- **Text Protocol**: Simple newline-delimited command interface
- **RPC Layer**: Type-safe remote procedure calls with length-prefixed framing
- **Async Updates**: Non-blocking sensor data processing
- **Pub/Sub System**: Real-time event notifications for lot occupancy changes
- **Reservation Management**: Time-based spot reservations with automatic expiry
- **Thread-Safe State**: Protected shared data structures with proper synchronization

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Parking Server (parking_server.py)        │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Text      │  │    RPC      │  │   Sensor    │         │
│  │  Protocol   │  │   Server    │  │   Server    │         │
│  │  Port 5000  │  │  Port 5001  │  │  Port 5002  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                  │
│         └────────────────┴────────────────┘                  │
│                          │                                    │
│                 ┌────────▼────────┐                          │
│                 │   Parking Lots  │                          │
│                 │  (Thread-Safe)  │                          │
│                 └────────┬────────┘                          │
│                          │                                    │
│         ┌────────────────┴────────────────┐                  │
│         │                                  │                  │
│  ┌──────▼──────┐              ┌───────────▼──────┐          │
│  │   Update    │              │    Pub/Sub       │          │
│  │   Workers   │              │    Notifier      │          │
│  │  (Threads)  │              │   Port 5003      │          │
│  └─────────────┘              └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘
         ▲            ▲                    ▲
         │            │                    │
   ┌─────┴──┐   ┌────┴─────┐      ┌──────┴────────┐
   │  Text  │   │   RPC    │      │   Pub/Sub     │
   │ Client │   │  Client  │      │    Client     │
   └────────┘   └──────────┘      └───────────────┘
```

### Component Roles

- **Text Protocol Server**: Handles simple text commands (LOTS, AVAIL, RESERVE, CANCEL, PING)
- **RPC Server**: Processes structured RPC requests with framing and marshalling
- **Sensor Server**: Receives asynchronous occupancy updates from sensors
- **Pub/Sub Server**: Manages subscriptions and delivers real-time events
- **Update Workers**: Background threads processing sensor updates
- **Parking Lots**: Thread-safe state containers with locks and reservation management

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- Standard library only (no external dependencies required)

### Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: This project uses Python standard library only. The `requirements.txt` is present but may be empty.

## Running the System

### 1. Start the Server

```bash
python parking_server.py
```

The server will start four TCP servers:
- Text Protocol: port 5000
- RPC: port 5001
- Sensor Updates: port 5002
- Pub/Sub: port 5003

### 2. Run RPC Client (Interactive)

```bash
python rpc_client.py
```

Interactive menu allows you to:
- List all parking lots
- Check availability
- Reserve spots
- Cancel reservations

### 3. Run Sensor Simulator

```bash
# Continuous simulation (60 seconds, 1 update/sec/lot)
python sensor_simulator.py --duration 60 --rate 1.0

# Burst mode (10 updates to LOT-A)
python sensor_simulator.py --mode burst --burst-lot LOT-A --burst-count 10

# High-load simulation (10 updates/sec/lot for 30 seconds)
python sensor_simulator.py --duration 30 --rate 10.0
```

### 4. Run Pub/Sub Subscriber

```bash
# Subscribe to LOT-A updates
python pubsub_client.py --lot LOT-A

# Subscribe for specific duration
python pubsub_client.py --lot LOT-B --duration 60
```

### 5. Run Load Tests

```bash
# Single test (4 workers, 30 seconds)
python load_test.py --workers 4 --duration 30 --operation avail

# Full baseline test suite
python load_test.py --baseline
```

## Configuration

Edit `config.json` to customize:

```json
{
  "server": {
    "host": "127.0.0.1",
    "text_protocol_port": 5000,
    "rpc_port": 5001,
    "sensor_port": 5002,
    "pubsub_port": 5003,
    "thread_pool_size": 10,
    "backlog": 5,
    "reservation_timeout_seconds": 300
  },
  "lots": [
    {"id": "LOT-A", "capacity": 100, "occupied": 50},
    {"id": "LOT-B", "capacity": 150, "occupied": 75}
  ],
  "pubsub": {
    "max_queue_size": 100,
    "back_pressure_policy": "drop_oldest"
  }
}
```

## RPC Protocol Specification

### Framing

All RPC messages use **length-prefixed framing** to prevent message fragmentation:

```
┌────────────────┬─────────────────────┐
│  Length (4B)   │   JSON Payload      │
│  Big-Endian    │                     │
│  uint32        │                     │
└────────────────┴─────────────────────┘
```

### Wire Format

**Request**:
```json
{
  "rpcId": 123,
  "method": "getAvailability",
  "args": ["LOT-A"]
}
```

**Response**:
```json
{
  "rpcId": 123,
  "result": 42,
  "error": null
}
```

### Parameter Passing

- **Serialization**: JSON (UTF-8 encoding)
- **Endianness**: Big-endian for length prefix (network byte order)
- **Types**: 
  - Integers: JSON numbers
  - Strings: JSON strings
  - Booleans: JSON true/false
  - Objects: JSON objects/arrays

### Timeout Policy

- **Client-side timeout**: 5 seconds (configurable)
- **Enforcement**: Socket-level timeout on receive operations
- **Error**: Raises `TimeoutError` exception to caller
- **Cleanup**: Client closes connection on timeout

### RPC Call Path

```
Caller
  ↓
Client Stub (rpc_client.py)
  ↓ serialize request
  ↓ frame with length prefix
TCP Connection
  ↓
Server Skeleton (parking_server.py)
  ↓ receive length prefix
  ↓ receive payload
  ↓ deserialize request
Server Method (getLots, reserve, etc.)
  ↓ execute logic
  ↓ return result
Server Skeleton
  ↓ serialize response
  ↓ frame with length prefix
TCP Connection
  ↓
Client Stub
  ↓ receive and deserialize
  ↓ check for errors
Caller (receives result)
```

## Thread Model

### Server Organization: Thread-Per-Connection

**Choice Rationale**:
- **Simplicity**: Each connection has dedicated thread with isolated state
- **Blocking I/O**: Python's socket operations naturally block; threads prevent starvation
- **Connection Lifetime**: Parking operations are short-lived; thread overhead acceptable
- **Alternative Considered**: Thread pool with work queue would reduce thread count but add complexity

### Thread Types

1. **Listener Threads** (4):
   - Text Protocol listener
   - RPC listener
   - Sensor listener
   - Pub/Sub listener
   - Accept connections and spawn handler threads

2. **Connection Handler Threads** (dynamic):
   - One per active client connection
   - Process requests until client disconnects
   - Automatically cleaned up on connection close

3. **Update Worker Threads** (3):
   - Consume from shared update queue
   - Apply sensor updates to parking lots
   - Publish events to subscribers

4. **Pub/Sub Notifier Thread** (1):
   - Monitors subscriber queues
   - Currently minimal (event delivery handled per-subscriber)

### Synchronization

- **Parking Lot State**: Protected by `threading.RLock()`
- **Subscriber Registry**: Protected by `threading.Lock()`
- **Update Queue**: Thread-safe `queue.Queue`
- **Subscriber Queues**: Thread-safe `queue.Queue` per subscriber

### Configuration Parameters

- `thread_pool_size`: 10 (controls update workers)
- `backlog`: 5 (listen queue depth)
- No hard limit on connection threads (relies on OS limits)

## Pub/Sub Design

### Architecture Choice: Separate TCP Connection for Events

**Selected Approach**: Dedicated connection for event stream

**Rationale**:
- **Simplicity**: Clear separation of request/response vs. events
- **No Multiplexing Complexity**: Avoids custom framing for bidirectional messages
- **Blocking Safety**: Event delivery doesn't interfere with RPC calls
- **Standard Sockets**: No custom protocol required

**Alternative Considered**: Multiplexed stream with request IDs
- More efficient (single connection)
- Requires complex message routing
- Python's Global Interpreter Lock (GIL) reduces concurrency benefits

### Event Flow

```
Sensor Update
  ↓
Update Worker applies change to ParkingLot
  ↓
Detects free spot count changed
  ↓
Calls _publish_event(lot_id, new_free)
  ↓
Iterates over subscribers for this lot_id
  ↓
Enqueues event to each subscriber's queue
  ↓
Per-subscriber handler thread
  ↓
Dequeues event and sends over TCP
  ↓
Client receives EVENT message
```

### Event Format

```
EVENT <lot_id> <free> <timestamp>
```

Example:
```
EVENT LOT-A 42 2026-02-19T10:30:45.123456
```

### API

**Subscribe** (RPC on pub/sub connection):
```json
Request: {"rpcId": 1, "method": "subscribe", "args": ["LOT-A"]}
Response: {"rpcId": 1, "result": 123, "error": null}
```

**Unsubscribe** (RPC):
```json
Request: {"rpcId": 2, "method": "unsubscribe", "args": [123]}
Response: {"rpcId": 2, "result": true, "error": null}
```

After successful subscription, the connection transitions to event delivery mode.

## Back-Pressure Policy

### Problem

When subscribers cannot keep up with event rate, queues fill up. Need policy to prevent:
- Unbounded memory growth
- Server slowdown
- Head-of-line blocking

### Policy: Drop Oldest (Configured)

**Default**: `"back_pressure_policy": "drop_oldest"`

**Behavior**:
1. Each subscriber has bounded queue (`max_queue_size`: 100)
2. On queue full:
   - Remove oldest event from queue
   - Insert new event
   - Log warning
3. Subscriber continues receiving newest events

**Rationale**:
- **Recency Priority**: Latest parking status more valuable than stale data
- **Continuous Service**: Slow subscribers stay connected
- **Bounded Memory**: Fixed per-subscriber overhead

### Alternative Policies (Not Implemented)

- **Drop Newest**: Keep old events (less useful for real-time data)
- **Disconnect**: Harsh but ensures fast subscribers only
- **Block Publisher**: Could slow entire system (not acceptable)

### Configuration

```json
"pubsub": {
  "max_queue_size": 100,
  "back_pressure_policy": "drop_oldest"
}
```

### Monitoring

Server logs warnings when dropping events:
```
WARNING - Dropped oldest event for subscriber 5
```

## Testing

### Unit Testing

Run individual components:

```bash
# Test text protocol
python rpc_client.py  # Use interactive mode

# Test sensor updates
python sensor_simulator.py --duration 10

# Test pub/sub
python pubsub_client.py --lot LOT-A --duration 10
```

### Load Testing

See [load_test.py](load_test.py) for:
- Throughput measurement (req/s)
- Latency distribution (median, P95, P99)
- Concurrent worker scaling (1, 4, 8, 16 workers)
- Operation types (AVAIL, RESERVE, mixed)

Results saved to `load_test_results.json`

### Integration Testing

1. Start server: `python parking_server.py`
2. In separate terminals:
   ```bash
   # Terminal 2: Start subscriber
   python pubsub_client.py --lot LOT-A
   
   # Terminal 3: Send sensor updates
   python sensor_simulator.py --rate 2.0
   
   # Terminal 4: Run load test
   python load_test.py --workers 4
   ```
3. Observe events in subscriber terminal
4. Check server logs for errors

## Project Structure

```
Campus-Smart-Parking-Finder/
├── config.json                 # Server configuration
├── requirements.txt            # Python dependencies
├── parking_server.py          # Main server implementation
├── rpc_client.py              # RPC client stub
├── sensor_simulator.py        # Sensor data simulator
├── pubsub_client.py           # Pub/sub subscriber client
├── load_test.py               # Load testing script
├── README.md                  # This file
├── API.md                     # Detailed API reference
└── REPORT_TEMPLATE.md         # Report template for assignment
```

## Design Decisions Summary

### Multithreading
- **Thread-per-connection** for simplicity and blocking I/O compatibility
- **3 update workers** for sensor processing parallelism
- **RLock per lot** to allow reentrant access during cleanup

### RPC
- **JSON marshalling** for human readability and debugging
- **Length-prefix framing** to handle arbitrary message sizes
- **Client-side timeout** for failure detection

### Async Messaging
- **Separate port** for sensor updates to isolate traffic
- **Update queue** decouples reception from processing
- **Worker pool** provides backpressure and parallelism

### Pub/Sub
- **Separate connection** for events (vs. multiplexing)
- **Per-subscriber queue** for independent flow control
- **Drop oldest** policy for back-pressure

## Troubleshooting

### Connection Refused
- Ensure server is running: `python parking_server.py`
- Check ports aren't already in use: `lsof -i :5000-5003` (macOS/Linux)

### High Latency
- Reduce concurrent workers in load tests
- Check system load and available threads
- Ensure no other processes saturating CPU

### Dropped Events
- Increase `max_queue_size` in config.json
- Reduce sensor update rate
- Check subscriber processing speed

### Reservation Timeout
- Default is 300 seconds (5 minutes)
- Adjust `reservation_timeout_seconds` in config.json

## License

Academic project for CSULB Distributed Systems course.

## Authors

[Add team member names here]

## Acknowledgments

Based on Assignment 2 requirements for Campus Smart Parking Finder.
