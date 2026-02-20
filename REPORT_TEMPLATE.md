# Campus Smart Parking Finder - Technical Report

**Assignment 2 - Distributed Systems**  
**Due: March 3, 2026**

**Team Members**: [Add names here]

---

## 1. System Design

### 1.1 Architecture Overview

[Add your architecture diagram here or describe it in ASCII]

```
┌─────────────────────────────────────────────────────────────┐
│                    Parking Server                             │
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
```

**Key Components**:
- **Multithreaded Server**: Handles concurrent clients using thread-per-connection model
- **RPC Layer**: Provides type-safe remote procedure calls with framing
- **Async Channel**: Non-blocking sensor update processing
- **Pub/Sub System**: Real-time event delivery to subscribers

### 1.2 Thread Model

**Approach**: Thread-per-connection + Worker pool

**Justification**:
- Python's blocking I/O model fits naturally with threads
- Each client connection has dedicated handler thread
- Update workers provide parallelism for sensor processing
- Simpler than event-driven or async/await approaches for TCP servers

**Thread Types**:
1. **Listener threads** (4): Accept connections on each port
2. **Connection handlers** (dynamic): One per active client
3. **Update workers** (3): Process sensor updates from queue
4. **Pub/Sub notifier** (1): Monitor subscriber health

**Configuration**:
- Thread pool size: 10
- Listen backlog: 5
- No hard limit on connection threads (bounded by OS)

### 1.3 RPC Framing and Marshalling

**Framing Mechanism**: Length-prefixed messages

```
┌────────────────┬─────────────────────┐
│  Length (4B)   │   JSON Payload      │
│  Big-Endian    │                     │
└────────────────┴─────────────────────┘
```

**Why Length-Prefixing?**
- Solves TCP stream boundary problem
- Simple to implement (4-byte header)
- Supports variable-length messages
- No escaping needed (unlike delimiter-based)

**Marshalling Format**: JSON

**Justification**:
- Human-readable for debugging
- Native Python support (`json` module)
- Type-safe (numbers, strings, booleans, arrays, objects)
- UTF-8 encoding handles international characters

**Alternatives Considered**:
- **Protocol Buffers**: Higher performance but requires schema compilation
- **MessagePack**: More compact but less debuggable
- **TLV (Type-Length-Value)**: More complex to implement

**Parameter Passing**:
- Integers: JSON numbers (arbitrary precision)
- Strings: JSON strings (UTF-8)
- Booleans: JSON true/false
- Arrays: JSON arrays
- Endianness: Big-endian for length prefix (network byte order)

### 1.4 Async Messaging Design

**Architecture**: Separate port + worker queue

**Flow**:
1. Sensor connects to port 5002
2. Sends `UPDATE lot_id delta` command
3. Server enqueues update and immediately responds `ACK`
4. Worker threads consume from queue and apply updates
5. Updates trigger pub/sub events if free count changes

**Benefits**:
- Non-blocking: Sensors get immediate ACK
- Decoupling: Update processing independent of reception
- Backpressure: Queue provides buffering
- Parallelism: Multiple workers process updates concurrently

**Synchronization**:
- Update queue: `queue.Queue` (thread-safe)
- Parking lot state: `threading.RLock` per lot
- No global lock (fine-grained locking for scalability)

### 1.5 Pub/Sub System Design

**Approach**: Separate TCP connection for event stream

**Workflow**:
1. Client connects to pub/sub port (5003)
2. Sends `subscribe(lot_id)` RPC request
3. Receives subscription ID in response
4. Connection transitions to event-only mode
5. Server sends events as length-prefixed messages

**Event Delivery**:
- Per-subscriber queue (bounded, max 100 events)
- Dedicated handler thread per subscriber
- Events published when free count changes

**Alternative Approaches Considered**:
1. **Multiplexed stream**: Single connection for RPC + events
   - More complex (need message routing by type)
   - Chose simplicity over efficiency
   
2. **Polling**: Clients call getAvailability() repeatedly
   - High overhead, stale data
   - Push model is more efficient

3. **WebSocket**: Bidirectional messaging
   - Not in Python stdlib, adds dependency
   - TCP sockets sufficient for assignment

**Fan-Out**:
- When lot changes, iterate all subscribers for that lot
- Enqueue event to each subscriber's queue
- Per-subscriber threads deliver independently

### 1.6 Back-Pressure Handling

**Policy**: Drop oldest event

**Implementation**:
- Each subscriber has bounded queue (100 events)
- On queue full:
  1. Remove oldest event
  2. Insert new event
  3. Log warning with subscriber ID

**Rationale**:
- **Recency priority**: Latest parking data more valuable than stale
- **Continuous service**: Slow subscribers stay connected
- **Bounded memory**: O(subscribers × queue_size) memory

**Alternative Policies**:
- **Drop newest**: Keep historical data (not useful here)
- **Disconnect**: Harsh but ensures only fast subscribers
- **Block publisher**: Would slow entire system (unacceptable)

**Configuration**:
```json
"pubsub": {
  "max_queue_size": 100,
  "back_pressure_policy": "drop_oldest"
}
```

---

## 2. Evaluation

### 2.1 Methodology

**Test Environment**:
- Machine: [Add your specs: MacBook Pro, CPU, RAM, etc.]
- OS: macOS / Linux / Windows
- Python version: 3.x
- Network: localhost (127.0.0.1)

**Test Scenarios**:

#### Baseline RPC Tests
- Duration: 30 seconds per test
- Worker counts: 1, 4, 8, 16 parallel clients
- Operations: AVAIL (read-heavy), RESERVE (write-heavy)
- Metrics: Throughput (req/s), latency (median, P95)

#### Async + Pub/Sub Stress Test
- Sensor load: 10 updates/sec/lot (4 lots = 40 updates/sec)
- Concurrent RPC clients: 1, 4, 8, 16 workers
- Pub/Sub subscribers: 4 (one per lot)
- Metrics: RPC latency impact, event delivery lag, dropped events

**Tools**:
- `load_test.py`: RPC throughput/latency measurement
- `sensor_simulator.py`: Async update generation
- `pubsub_client.py`: Event reception timing

### 2.2 Results

#### Baseline RPC Performance

**AVAIL Operations** (read-heavy):

| Workers | Throughput (req/s) | Median Latency (ms) | P95 Latency (ms) |
|---------|-------------------|---------------------|------------------|
| 1       | [Fill in]         | [Fill in]           | [Fill in]        |
| 4       | [Fill in]         | [Fill in]           | [Fill in]        |
| 8       | [Fill in]         | [Fill in]           | [Fill in]        |
| 16      | [Fill in]         | [Fill in]           | [Fill in]        |

**RESERVE Operations** (write-heavy):

| Workers | Throughput (req/s) | Median Latency (ms) | P95 Latency (ms) |
|---------|-------------------|---------------------|------------------|
| 1       | [Fill in]         | [Fill in]           | [Fill in]        |
| 4       | [Fill in]         | [Fill in]           | [Fill in]        |
| 8       | [Fill in]         | [Fill in]           | [Fill in]        |
| 16      | [Fill in]         | [Fill in]           | [Fill in]        |

**Observations**:
- [Add your observations here]
- Example: "Throughput scales sub-linearly with workers due to lock contention"
- Example: "P95 latency increases significantly at 16 workers"

#### Async + Pub/Sub Stress Results

**RPC Latency Under Sensor Load**:

| Workers | Baseline P95 (ms) | With Sensors P95 (ms) | Impact (%) |
|---------|-------------------|------------------------|------------|
| 1       | [Fill in]         | [Fill in]              | [Fill in]  |
| 4       | [Fill in]         | [Fill in]              | [Fill in]  |
| 8       | [Fill in]         | [Fill in]              | [Fill in]  |
| 16      | [Fill in]         | [Fill in]              | [Fill in]  |

**Pub/Sub Event Delivery**:
- Total events published: [Fill in]
- Events delivered: [Fill in]
- Events dropped: [Fill in]
- Average delivery latency: [Fill in] ms

**Observations**:
- [Add your observations]
- Example: "Sensor load adds ~20% to P95 latency due to lock contention"
- Example: "No events dropped at 10 updates/sec (well below saturation)"

### 2.3 Plots

[Include plots here - you can generate these from load_test_results.json]

**Suggested Plots**:
1. Throughput vs. Workers (bar chart)
2. Latency Distribution (box plot or histogram)
3. P95 Latency with/without sensors (line chart)
4. Event delivery lag over time (time series)

**Tools**: matplotlib, Excel, Google Sheets, or hand-drawn

### 2.4 Analysis

#### Connection to Ch. 3 (Thread Scheduling & Blocking I/O)

[Write 200-300 words connecting results to course concepts]

**Example points to cover**:
- Thread context switching overhead at high worker counts
- Blocking I/O causes threads to yield during recv/send
- Lock contention on ParkingLot.lock increases with parallelism
- Python GIL (Global Interpreter Lock) limits true parallelism
- Thread pool size tuning: too few → underutilized, too many → overhead

**Sample paragraph**:
"At low worker counts (1-4), throughput scales nearly linearly as threads can run concurrently while others block on I/O. However, beyond 8 workers, we observe diminishing returns due to increased lock contention on the shared ParkingLot state. The P95 latency increase at 16 workers suggests that threads spend significant time waiting for locks rather than doing useful work. This aligns with Ch. 3's discussion of thread scheduling overhead and the trade-offs between thread-per-connection and bounded thread pools. A production system would benefit from a fixed thread pool (e.g., 4-8 workers) to limit context switching while maintaining good throughput."

#### Connection to Ch. 4 (Sync vs. Async Communication)

[Write 200-300 words]

**Example points to cover**:
- Synchronous RPC: Client blocks waiting for response
- Asynchronous sensors: Server ACKs immediately, processes later
- Trade-offs: Sync = simple + ordered, Async = scalable + complex
- Sensor updates show benefits of async: high throughput, no client blocking
- RPC timeout handling: Failure detection vs. unnecessary aborts

**Sample paragraph**:
"The asynchronous sensor channel demonstrates clear performance benefits over synchronous RPC. By decoupling message reception from processing, the sensor server achieves ~40 updates/sec with minimal impact on RPC latency (<20% increase). This aligns with Ch. 4's discussion of async communication patterns where high-volume, low-priority updates should not block critical operations. However, async introduces complexity: we needed worker queues, thread coordination, and idempotency handling. The hybrid design (sync RPC for client requests, async for sensors) provides the best of both worlds: simple request-response semantics for clients and scalable update processing for sensors."

#### Connection to Pub/Sub Concepts

[Write 100-150 words]

**Example points to cover**:
- Decoupling: Publishers don't know subscribers
- Fan-out: One update → many subscribers
- Back-pressure: Drop-oldest policy maintains system stability
- Event delivery lag: Queue depth affects real-time guarantees

**Sample paragraph**:
"The pub/sub system achieves effective decoupling between sensor updates and client notifications. When a lot changes, the server publishes to all subscribers without knowing their identities or count (fan-out). Our drop-oldest back-pressure policy ensures that slow subscribers don't impact fast ones or the publisher. During stress testing, we observed zero dropped events at 10 updates/sec, indicating the system is well within capacity. Event delivery latency remained under 20ms, meeting real-time requirements for parking updates."

---

## 3. Reliability Considerations

### 3.1 Sensor Disconnect Handling

**Problem**: Sensor may disconnect mid-update or fail silently

**Solution**:
- Connection errors caught and logged
- Partial updates ignored (line buffering requires `\n`)
- No sensor heartbeat mechanism (out of scope)

**Idempotency**:
- UPDATE operations are idempotent (same delta applied multiple times is safe)
- Occupancy clamped to [0, capacity] prevents overflow

### 3.2 Client Timeout Handling

**Problem**: Server may hang or network may fail

**Solution**:
- Client-side timeout (5 seconds) on socket operations
- TimeoutError raised to caller with clear message
- Connection closed on timeout (no connection pool pollution)

**RPC ID Verification**:
- Response `rpcId` must match request `rpcId`
- Detects out-of-order responses (shouldn't happen with TCP)

### 3.3 Reservation Expiry

**Problem**: Clients may disconnect without canceling

**Solution**:
- Reservations automatically expire after 5 minutes
- Cleanup on every `get_free()` call (lazy cleanup)
- Expired reservations removed from in-memory dict
- Logging for auditability

### 3.4 Pub/Sub Subscriber Failures

**Problem**: Subscriber crashes or network breaks

**Solution**:
- Send failures caught and subscriber removed
- Bounded queue prevents memory leak from dead subscribers
- No acknowledgment mechanism (at-most-once delivery)

---

## 4. Limitations and Future Work

### Current Limitations

1. **No Persistence**: All state in memory (lost on restart)
2. **No Authentication**: Anyone can reserve/cancel
3. **No Encryption**: Plain TCP (no TLS)
4. **Single Server**: No replication or failover
5. **At-Most-Once Pub/Sub**: Events may be lost
6. **No Backfill**: Subscribers don't get history

### Future Enhancements

1. **Database Backend**: Store lots, reservations, audit log
2. **Authentication**: API keys or OAuth for clients
3. **TLS**: Encrypt all traffic
4. **Horizontal Scaling**: Multiple server instances with shared state
5. **At-Least-Once Delivery**: Persistent event queue with ACKs
6. **REST API**: HTTP interface for broader compatibility
7. **WebSocket**: Browser support for pub/sub

---

## 5. Conclusion

[Write 100-150 words summarizing the project]

**Example**:
"We successfully implemented a multithreaded parking server demonstrating key distributed systems concepts: concurrent request handling, RPC communication with custom framing, asynchronous message processing, and publish/subscribe event delivery. The system achieves good performance under load (500-1000 req/s) while maintaining correctness through careful synchronization. The thread-per-connection model proved appropriate for this scale (<100 clients). The async sensor channel and pub/sub system effectively decouple components, improving scalability. Load testing revealed expected patterns: linear scaling at low concurrency, lock contention at high concurrency, and minimal impact from async updates. The implementation provides a solid foundation for a production parking system with additions for persistence, security, and fault tolerance."

---

## Appendices

### A. Configuration

Full `config.json` used for testing:
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
    {"id": "LOT-B", "capacity": 150, "occupied": 75},
    {"id": "LOT-C", "capacity": 80, "occupied": 40},
    {"id": "LOT-D", "capacity": 200, "occupied": 120}
  ],
  "pubsub": {
    "max_queue_size": 100,
    "back_pressure_policy": "drop_oldest"
  }
}
```

### B. Test Commands

**Start server**:
```bash
python parking_server.py
```

**Run baseline tests**:
```bash
python load_test.py --baseline
```

**Run stress test** (in separate terminals):
```bash
# Terminal 1: Start server
python parking_server.py

# Terminal 2: Start subscribers
python pubsub_client.py --lot LOT-A &
python pubsub_client.py --lot LOT-B &
python pubsub_client.py --lot LOT-C &
python pubsub_client.py --lot LOT-D &

# Terminal 3: Start sensors
python sensor_simulator.py --duration 60 --rate 10.0

# Terminal 4: Run RPC load
python load_test.py --workers 8 --duration 60 --operation mixed
```

### C. Sample Log Output

```
2026-02-19 10:30:00 - INFO - Parking server initialized with 4 lots
2026-02-19 10:30:00 - INFO - All server components started
2026-02-19 10:30:00 - INFO - Text protocol server listening on port 5000
2026-02-19 10:30:00 - INFO - RPC server listening on port 5001
2026-02-19 10:30:10 - INFO - RPC client connected: ('127.0.0.1', 54321)
2026-02-19 10:30:11 - INFO - {"event":"reservation_created","lot_id":"LOT-A","plate":"ABC123","timestamp":"2026-02-19T10:30:11.123456"}
```

---

**Total Pages**: [Should be ≤ 4 pages when converted to PDF]

**References**:
- Course textbook Chapters 3-4
- Python threading documentation
- TCP socket programming references

---

**Instructions for Completion**:
1. Fill in all [Fill in] placeholders with your actual test results
2. Generate plots from `load_test_results.json`
3. Complete the analysis sections with 200-300 words each
4. Add your team member names at the top
5. Convert to PDF (use `pandoc REPORT_TEMPLATE.md -o report.pdf` or print to PDF)
6. Ensure final PDF is ≤ 4 pages

**Grading Rubric** (estimate):
- Design (30%): Architecture, thread model, RPC design
- Evaluation (30%): Methodology, results, plots
- Analysis (30%): Connections to Ch. 3-4, pub/sub concepts
- Writing (10%): Clarity, organization, completeness
