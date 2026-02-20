# API Reference - Campus Smart Parking Finder

Complete API documentation for all server interfaces.

## Table of Contents

1. [Text Protocol API](#text-protocol-api)
2. [RPC API](#rpc-api)
3. [Sensor Update API](#sensor-update-api)
4. [Pub/Sub API](#pubsub-api)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)

---

## Text Protocol API

**Transport**: TCP on port 5000  
**Format**: Newline-delimited UTF-8 text  
**Pattern**: Request-response (one command per line)

### Commands

#### PING

Health check command.

**Request**:
```
PING
```

**Response**:
```
PONG
```

**Example**:
```python
conn.send(b"PING\n")
response = conn.recv(1024)  # b"PONG\n"
```

---

#### LOTS

Retrieve all parking lot information.

**Request**:
```
LOTS
```

**Response**: JSON array of lot objects
```json
[
  {"id": "LOT-A", "capacity": 100, "occupied": 50, "free": 48},
  {"id": "LOT-B", "capacity": 150, "occupied": 75, "free": 73}
]
```

**Notes**:
- `free` = capacity - occupied - active_reservations
- Response is single-line JSON (no newlines in JSON)

---

#### AVAIL

Get available spots for a specific lot.

**Request**:
```
AVAIL <lot_id>
```

**Response**: Integer (number of free spots)
```
42
```

**Errors**:
```
ERROR: AVAIL requires lot_id
ERROR: Unknown lot
```

**Example**:
```
Request:  AVAIL LOT-A
Response: 42
```

---

#### RESERVE

Reserve a parking spot.

**Request**:
```
RESERVE <lot_id> <plate>
```

**Parameters**:
- `lot_id`: Parking lot identifier
- `plate`: License plate number (no spaces)

**Response**:
```
OK           # Reservation successful
FULL         # No spots available
EXISTS       # Plate already has reservation in this lot
ERROR: ...   # Invalid parameters or unknown lot
```

**Example**:
```
Request:  RESERVE LOT-A ABC123
Response: OK
```

**Notes**:
- Reservations expire after 5 minutes (configurable)
- Each plate can have at most one reservation per lot
- Reservations reduce available spot count

---

#### CANCEL

Cancel a parking reservation.

**Request**:
```
CANCEL <lot_id> <plate>
```

**Response**:
```
OK          # Cancellation successful
NOT_FOUND   # No reservation for this plate
ERROR: ...  # Invalid parameters
```

**Example**:
```
Request:  CANCEL LOT-A ABC123
Response: OK
```

---

## RPC API

**Transport**: TCP on port 5001  
**Format**: Length-prefixed JSON  
**Framing**: 4-byte big-endian uint32 length + JSON payload

### Message Format

**Request**:
```json
{
  "rpcId": 123,
  "method": "methodName",
  "args": [arg1, arg2, ...]
}
```

**Response**:
```json
{
  "rpcId": 123,
  "result": <value>,
  "error": null
}
```

**Error Response**:
```json
{
  "rpcId": 123,
  "result": null,
  "error": "Error message"
}
```

### Methods

#### getLots()

Get all parking lot information.

**Request**:
```json
{
  "rpcId": 1,
  "method": "getLots",
  "args": []
}
```

**Response**:
```json
{
  "rpcId": 1,
  "result": [
    {"id": "LOT-A", "capacity": 100, "occupied": 50, "free": 48},
    {"id": "LOT-B", "capacity": 150, "occupied": 75, "free": 73}
  ],
  "error": null
}
```

**Python Example**:
```python
client = RPCClient()
client.connect()
lots = client.get_lots()
# lots = [{'id': 'LOT-A', ...}, ...]
```

---

#### getAvailability(lot_id)

Get available spot count for a lot.

**Request**:
```json
{
  "rpcId": 2,
  "method": "getAvailability",
  "args": ["LOT-A"]
}
```

**Response**:
```json
{
  "rpcId": 2,
  "result": 42,
  "error": null
}
```

**Error**:
```json
{
  "rpcId": 2,
  "result": null,
  "error": "Unknown lot: LOT-X"
}
```

**Python Example**:
```python
free = client.get_availability("LOT-A")
# free = 42
```

---

#### reserve(lot_id, plate)

Reserve a parking spot.

**Request**:
```json
{
  "rpcId": 3,
  "method": "reserve",
  "args": ["LOT-A", "ABC123"]
}
```

**Response**:
```json
{
  "rpcId": 3,
  "result": true,    // Success
  "error": null
}
```

**Failure**:
```json
{
  "rpcId": 3,
  "result": false,   // Lot full or plate already reserved
  "error": null
}
```

**Python Example**:
```python
success = client.reserve("LOT-A", "ABC123")
if success:
    print("Reserved!")
else:
    print("Failed (lot full or already reserved)")
```

**Notes**:
- Returns `true` only if reservation created
- Returns `false` if lot full or plate already reserved
- Throws error for invalid lot_id

---

#### cancel(lot_id, plate)

Cancel a reservation.

**Request**:
```json
{
  "rpcId": 4,
  "method": "cancel",
  "args": ["LOT-A", "ABC123"]
}
```

**Response**:
```json
{
  "rpcId": 4,
  "result": true,    // Cancellation successful
  "error": null
}
```

**Failure**:
```json
{
  "rpcId": 4,
  "result": false,   // Reservation not found
  "error": null
}
```

**Python Example**:
```python
success = client.cancel("LOT-A", "ABC123")
```

---

## Sensor Update API

**Transport**: TCP on port 5002  
**Format**: Newline-delimited text  
**Pattern**: Command + ACK

### Command

#### UPDATE

Report occupancy change.

**Request**:
```
UPDATE <lot_id> <delta>
```

**Parameters**:
- `lot_id`: Parking lot identifier
- `delta`: Change in occupancy (+1 = car enters, -1 = car exits)

**Response**:
```
ACK
```

**Example**:
```
Request:  UPDATE LOT-A +1
Response: ACK

Request:  UPDATE LOT-B -1
Response: ACK
```

**Notes**:
- Updates are processed asynchronously by worker threads
- Invalid lot_id is logged but still ACKed (idempotent)
- Occupancy is clamped to [0, capacity]
- Changes trigger pub/sub events if free count changes

---

## Pub/Sub API

**Transport**: TCP on port 5003  
**Format**: Length-prefixed JSON (same as RPC)  
**Pattern**: Subscribe via RPC, then receive events on same connection

### Workflow

1. Client connects to port 5003
2. Client sends `subscribe` RPC request
3. Server responds with subscription ID
4. Connection transitions to event stream mode
5. Server sends events as length-prefixed messages
6. Client reads events until disconnect or unsubscribe

### Methods

#### subscribe(lot_id)

Subscribe to updates for a parking lot.

**Request**:
```json
{
  "rpcId": 1,
  "method": "subscribe",
  "args": ["LOT-A"]
}
```

**Response**:
```json
{
  "rpcId": 1,
  "result": 123,    // Subscription ID
  "error": null
}
```

**Error**:
```json
{
  "rpcId": 1,
  "result": null,
  "error": "Unknown lot: LOT-X"
}
```

**Python Example**:
```python
client = PubSubClient()
client.connect()
sub_id = client.subscribe("LOT-A")
# sub_id = 123
```

**Notes**:
- After successful subscription, connection stays open for events
- Client should not send further requests on this connection
- One subscription per connection

---

#### unsubscribe(sub_id)

Unsubscribe from updates.

**Request**:
```json
{
  "rpcId": 2,
  "method": "unsubscribe",
  "args": [123]
}
```

**Response**:
```json
{
  "rpcId": 2,
  "result": true,
  "error": null
}
```

**Notes**:
- Currently requires separate connection (not typical usage)
- Closing connection also removes subscription

---

### Event Format

**Transport**: Length-prefixed text (4-byte length + UTF-8 string)

**Format**:
```
EVENT <lot_id> <free> <timestamp>
```

**Example**:
```
EVENT LOT-A 42 2026-02-19T10:30:45.123456
```

**Fields**:
- `lot_id`: Which lot changed
- `free`: New count of free spots
- `timestamp`: ISO 8601 timestamp

**Python Example**:
```python
client.subscribe("LOT-A")
client.receive_events()  # Blocks and prints events

# Output:
# [EVENT #1] LOT-A: 42 spots free at 2026-02-19T10:30:45.123456
# [EVENT #2] LOT-A: 41 spots free at 2026-02-19T10:30:50.234567
```

**When Events Are Published**:
- Sensor UPDATE changes occupancy
- RESERVE reduces free count
- CANCEL increases free count
- Reservation expires (automatically increases free count)

**Back-Pressure**:
- Each subscriber has bounded queue (default: 100 events)
- If queue full, oldest event dropped (configurable policy)
- Slow subscribers receive newest events

---

## Data Models

### ParkingLot

```json
{
  "id": "LOT-A",
  "capacity": 100,
  "occupied": 50,
  "free": 48
}
```

**Fields**:
- `id` (string): Unique lot identifier
- `capacity` (int): Total parking spots
- `occupied` (int): Currently occupied spots (from sensors)
- `free` (int): Available spots = capacity - occupied - active_reservations

### Reservation (Internal)

```python
{
  "lot_id": "LOT-A",
  "plate": "ABC123",
  "created_at": "2026-02-19T10:30:00",
  "expires_at": "2026-02-19T10:35:00"
}
```

**Notes**:
- Not directly exposed via API
- Managed internally by server
- Automatically removed on expiry

---

## Error Handling

### Text Protocol Errors

**Format**: `ERROR: <message>`

**Examples**:
```
ERROR: Empty command
ERROR: AVAIL requires lot_id
ERROR: Unknown lot
ERROR: Unknown command: FOO
```

### RPC Errors

**Format**: Error in response object

```json
{
  "rpcId": 123,
  "result": null,
  "error": "Error message here"
}
```

**Common Errors**:
- `"Missing lot_id argument"`
- `"Unknown lot: LOT-X"`
- `"Missing arguments"`
- `"Unknown method: foo"`

### Client Timeouts

**Python Exception**: `TimeoutError`

**Example**:
```python
try:
    result = client.get_availability("LOT-A")
except TimeoutError:
    print("RPC timed out after 5 seconds")
```

**Default Timeout**: 5 seconds (configurable in client)

### Connection Errors

**Scenarios**:
- Server not running: `ConnectionRefusedError`
- Server shutdown during request: `ConnectionError`
- Network issues: `socket.timeout` or `OSError`

**Handling**:
```python
try:
    client.connect()
except ConnectionRefusedError:
    print("Server not running on port 5001")
```

---

## Wire Protocol Examples

### RPC Call (Binary)

**Request** (getLots):
```
Hex: 00 00 00 2D 7B 22 72 70 63 49 64 22 3A 31 ...
     └─length─┘ └─JSON payload starts─────────>

Length: 0x0000002D = 45 bytes
JSON: {"rpcId":1,"method":"getLots","args":[]}
```

**Response**:
```
Hex: 00 00 00 A3 7B 22 72 70 63 49 64 22 3A 31 ...
     └─length─┘ └─JSON payload starts─────────>

Length: 0x000000A3 = 163 bytes
JSON: {"rpcId":1,"result":[{"id":"LOT-A",...}],"error":null}
```

### Framing Code

**Python Send**:
```python
import struct
import json

request = {"rpcId": 1, "method": "getLots", "args": []}
payload = json.dumps(request).encode('utf-8')
frame = struct.pack('!I', len(payload)) + payload
conn.sendall(frame)
```

**Python Receive**:
```python
# Read 4-byte length
length_bytes = conn.recv(4)
length = struct.unpack('!I', length_bytes)[0]

# Read payload
payload = b''
while len(payload) < length:
    chunk = conn.recv(length - len(payload))
    payload += chunk

response = json.loads(payload.decode('utf-8'))
```

---

## Performance Characteristics

### Text Protocol
- **Latency**: ~1-5ms (localhost)
- **Throughput**: ~1000 req/s (single client)
- **Concurrency**: Limited by thread overhead

### RPC Protocol
- **Latency**: ~2-10ms (localhost, includes marshalling)
- **Throughput**: ~500-1000 req/s (single client)
- **Concurrency**: Scales with worker threads

### Sensor Updates
- **Throughput**: ~1000 updates/s
- **Processing**: Asynchronous (ACK immediate, processing deferred)
- **Latency**: Variable (depends on worker queue depth)

### Pub/Sub Events
- **Latency**: ~5-20ms from change to subscriber
- **Fan-out**: Supports 100+ concurrent subscribers
- **Back-pressure**: Triggers at max_queue_size events

---

## API Usage Examples

### Complete RPC Client Session

```python
from rpc_client import RPCClient

client = RPCClient(host='127.0.0.1', port=5001, timeout=5.0)

try:
    # Connect
    client.connect()
    
    # List lots
    lots = client.get_lots()
    for lot in lots:
        print(f"{lot['id']}: {lot['free']} free")
    
    # Check availability
    free = client.get_availability("LOT-A")
    print(f"LOT-A has {free} spots")
    
    # Reserve
    success = client.reserve("LOT-A", "ABC123")
    if success:
        print("Reserved!")
    
    # Cancel
    success = client.cancel("LOT-A", "ABC123")
    if success:
        print("Cancelled!")

finally:
    client.close()
```

### Complete Pub/Sub Session

```python
from pubsub_client import PubSubClient

client = PubSubClient(host='127.0.0.1', port=5003)

try:
    client.connect()
    sub_id = client.subscribe("LOT-A")
    print(f"Subscribed with ID {sub_id}")
    
    # Receive events (blocks)
    client.receive_events(duration=30)  # Listen for 30 seconds

finally:
    client.close()
```

### Sensor Simulation

```python
from sensor_simulator import SensorSimulator

simulator = SensorSimulator(host='127.0.0.1', port=5002)

try:
    simulator.connect()
    
    # Send single update
    simulator.send_update("LOT-A", +1)  # Car enters
    simulator.send_update("LOT-A", -1)  # Car exits
    
    # Run continuous simulation
    simulator.simulate_continuous(duration=60, update_rate=2.0)

finally:
    simulator.close()
```

---

## Version History

- **v1.0** (2026-02-19): Initial release
  - Text protocol API
  - RPC API with framing
  - Sensor updates
  - Pub/Sub system

---

## Notes

- All APIs are **synchronous** except sensor updates (async processing)
- **Thread-safe**: All methods can be called concurrently
- **Idempotent**: CANCEL and UPDATE operations are idempotent
- **No authentication**: Academic project (add auth for production)
- **No encryption**: Use TLS wrapper for production deployment

---

For implementation details, see [README.md](README.md).
