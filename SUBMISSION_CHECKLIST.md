# Assignment 2 Submission Checklist

Use this checklist to ensure your submission is complete before the March 3, 2026 deadline.

## ✅ Code Files (All .py files)

- [ ] `parking_server.py` - Main server implementation
- [ ] `rpc_client.py` - RPC client stub
- [ ] `sensor_simulator.py` - Sensor data simulator
- [ ] `pubsub_client.py` - Pub/sub subscriber client
- [ ] `load_test.py` - Load testing script
- [ ] `test_integration.py` - Integration tests (bonus)

## ✅ Configuration & Dependencies

- [ ] `config.json` - Server configuration
- [ ] `requirements.txt` - Python dependencies (even if empty)
- [ ] Virtual environment setup instructions in README

## ✅ Documentation Files (.md or .txt)

- [ ] `README.md` - Complete with:
  - [ ] Build/run steps
  - [ ] Framing/marshalling spec
  - [ ] Timeout policy
  - [ ] Thread model explanation
  - [ ] Configuration instructions
  - [ ] Pub/sub design explanation
  - [ ] Back-pressure policy documentation
  - [ ] Virtual environment creation steps
  
- [ ] `API.md` - RPC methods and message schemas (optional but recommended)

## ✅ Report (PDF, ≤ 4 pages)

- [ ] `report.pdf` - Technical report including:
  - [ ] Architecture diagrams (can be ASCII art)
  - [ ] Server model explanation
  - [ ] RPC framing description
  - [ ] Async channel design
  - [ ] Pub/sub design
  - [ ] Evaluation methodology
  - [ ] Performance plots (throughput & latency)
  - [ ] Discussion grounded in Ch. 3-4 concepts
  - [ ] Reliability note (sensor disconnects, idempotency)
  - [ ] Pub/sub note (slow subscribers, back-pressure)
  - [ ] Analysis section (200-300 words)

### Report Checklist Details:

**Design Section**:
- [ ] Architecture diagram present
- [ ] Thread model explained (thread-per-connection rationale)
- [ ] RPC framing format documented
- [ ] Marshalling format justified
- [ ] Async channel described
- [ ] Pub/sub architecture explained

**Evaluation Section**:
- [ ] Test methodology described
- [ ] Baseline RPC tests completed (1, 4, 8, 16 workers)
- [ ] Throughput data collected (req/s)
- [ ] Latency data collected (median, P95)
- [ ] Async + pub/sub stress test completed
- [ ] Plots generated and included
- [ ] Results tables formatted

**Analysis Section** (200-300 words):
- [ ] Connection to Ch. 3 (thread scheduling & blocking I/O)
- [ ] Connection to Ch. 4 (sync vs async trade-offs)
- [ ] Connection to pub/sub concepts (fan-out, back-pressure)
- [ ] Specific insights from your results
- [ ] Concrete examples from tests

## ✅ Individual Reflections

Each team member must include:

- [ ] `REFLECTION_[Name1].md` or `.txt` (≤300 words) containing:
  - [ ] What you implemented (specific)
  - [ ] A bug you fixed (with diagnosis)
  - [ ] One design change (with rationale)

- [ ] `REFLECTION_[Name2].md` (if team)
- [ ] `REFLECTION_[Name3].md` (if team)

**Note**: Make sure reflections are:
- Specific (mention file names, function names)
- Technical (show understanding)
- Personal (what YOU did, not the team)

## ✅ Functional Requirements Verification

### A. Multithreaded Server
- [ ] TCP server accepts concurrent clients
- [ ] Thread-per-connection or thread pool implemented
- [ ] Text protocol works: LOTS, AVAIL, RESERVE, CANCEL, PING
- [ ] State kept in memory
- [ ] Shared data protected with locks
- [ ] RESERVE respects capacity under concurrent requests
- [ ] Server organization documented in README

### B. RPC Layer
- [ ] Length-prefixed framing implemented
- [ ] Wire format defined (JSON/TLV/msgpack)
- [ ] Request format: {rpcId, method, args}
- [ ] Reply format: {rpcId, result, error}
- [ ] Client enforces timeouts
- [ ] TimeoutError surfaced clearly
- [ ] Parameter passing documented (endianness, types)
- [ ] RPC path documented in README

### C. Async Messaging
- [ ] Sensors connect on separate TCP port
- [ ] UPDATE command works: `UPDATE <lotId> <delta>`
- [ ] Updates enqueued and processed by workers
- [ ] Subscribers receive notifications
- [ ] Push notifications don't block RPC

### D. Pub/Sub System
- [ ] subscribe(lotId) -> subId implemented
- [ ] unsubscribe(subId) -> bool implemented
- [ ] EVENT format: `EVENT <lotId> <free> <timestamp>`
- [ ] Events published on lot changes
- [ ] Non-blocking with respect to normal RPC
- [ ] Approach chosen and justified (separate connection/multiplexed/thread pool)
- [ ] Back-pressure policy defined and documented
- [ ] Back-pressure policy implemented

## ✅ Non-Functional Requirements

- [ ] Correctness: No overbooking under concurrency
- [ ] Reservations expire after 5 minutes (configurable)
- [ ] Back-pressure: Queuing or rejection with clear error
- [ ] Back-pressure policy documented
- [ ] Logging: Structured logs present (event type, lotId, plate, timestamp)
- [ ] Configuration: Ports, thread pool, lots via JSON/TOML file

## ✅ Evaluation & Experiments

### Baseline RPC Tests (30 seconds each):
- [ ] 1 worker: throughput + latency measured
- [ ] 4 workers: throughput + latency measured
- [ ] 8 workers: throughput + latency measured
- [ ] 16 workers: throughput + latency measured
- [ ] Tests run for both AVAIL and RESERVE
- [ ] Results saved (load_test_results.json)

### Async + Pub/Sub Stress Test:
- [ ] Sensors sending 10 updates/sec/lot
- [ ] Same client loads (1/4/8/16 workers)
- [ ] RPC tail latency measured
- [ ] Pub/sub delivery measured
- [ ] Back-pressure behavior observed

### Analysis:
- [ ] Results connected to thread scheduling (Ch. 3)
- [ ] Results connected to blocking I/O (Ch. 3)
- [ ] Sync vs async trade-offs discussed (Ch. 4)
- [ ] Pub/sub fan-out discussed
- [ ] Back-pressure impact analyzed
- [ ] 200-300 words written

## ✅ Testing Before Submission

- [ ] Server starts without errors
- [ ] All four ports listening (5000-5003)
- [ ] Text protocol client works
- [ ] RPC client works
- [ ] Sensor simulator works
- [ ] Pub/sub client works
- [ ] Load tests complete successfully
- [ ] Integration test passes (`python test_integration.py`)
- [ ] No crashes under load
- [ ] Logs show expected behavior

## ✅ Code Quality

- [ ] No syntax errors
- [ ] No runtime errors during normal operation
- [ ] Proper error handling (try/except where appropriate)
- [ ] Locks used correctly (no deadlocks)
- [ ] Thread-safe operations
- [ ] Clean code (readable, commented where needed)
- [ ] Follows Python conventions

## ✅ Documentation Quality

- [ ] README has clear setup instructions
- [ ] README explains design choices
- [ ] All commands tested and work
- [ ] No broken links in markdown files
- [ ] Technical terms used correctly
- [ ] No spelling/grammar errors

## ✅ Canvas Submission Format

**Create a ZIP file containing**:
- [ ] All .py files
- [ ] All .md or .txt documentation files
- [ ] requirements.txt
- [ ] config.json
- [ ] report.pdf
- [ ] All individual reflection files

**File naming**:
- [ ] ZIP file named: `Assignment2_[TeamName].zip`
- [ ] PDF named: `report.pdf` or `Report_[TeamName].pdf`
- [ ] Reflections named: `REFLECTION_[YourName].md`

**Verify ZIP contents**:
```bash
# Create submission
zip -r Assignment2_Team.zip *.py *.md *.txt *.json report.pdf

# Verify contents
unzip -l Assignment2_Team.zip

# Test extraction
unzip Assignment2_Team.zip -d /tmp/test
```

## ✅ Final Checks

- [ ] All team member names in report.pdf
- [ ] Date on report is current
- [ ] Virtual environment instructions in README
- [ ] File size reasonable (<10MB)
- [ ] No unnecessary files (no __pycache__, .pyc, .venv)
- [ ] Submitted before deadline (March 3, 2026 11:59pm)

## 🎯 Optional Enhancements (Extra Credit)

- [ ] Comprehensive unit tests
- [ ] Integration test suite
- [ ] Performance visualization scripts
- [ ] Advanced back-pressure policies
- [ ] Connection pooling
- [ ] Graceful shutdown handling
- [ ] Health check endpoints
- [ ] Metrics/monitoring
- [ ] Docker containerization
- [ ] Demo video

## 📊 Expected File Structure

```
Assignment2_Team.zip
├── parking_server.py
├── rpc_client.py
├── sensor_simulator.py
├── pubsub_client.py
├── load_test.py
├── test_integration.py
├── config.json
├── requirements.txt
├── README.md
├── API.md
├── report.pdf
├── REFLECTION_Alice.md
├── REFLECTION_Bob.md
└── setup.sh (optional)
```

## 🚨 Common Mistakes to Avoid

- [ ] Forgetting requirements.txt (even if empty)
- [ ] Missing virtual environment setup in README
- [ ] No back-pressure policy documentation
- [ ] Analysis section too short (<200 words)
- [ ] Report exceeds 4 pages
- [ ] No connection to Ch. 3-4 concepts
- [ ] Missing individual reflections
- [ ] Plots not included in report
- [ ] Thread model not explained
- [ ] RPC framing not documented

## ✅ Post-Submission

- [ ] Keep a backup of your submission
- [ ] Verify ZIP uploaded successfully to Canvas
- [ ] Check submission timestamp
- [ ] Confirm all team members listed

---

**Need Help?**

- Review [README.md](README.md) for documentation
- Check [API.md](API.md) for interface details
- See [REPORT_TEMPLATE.md](REPORT_TEMPLATE.md) for report structure
- Run `python test_integration.py` to verify everything works

**Estimated Time to Complete**:
- Code implementation: 12-20 hours
- Load testing: 2-3 hours
- Report writing: 3-4 hours
- Documentation: 2-3 hours
- Testing & debugging: 2-4 hours
- **Total: 20-35 hours**

**Good luck!** 🚀
