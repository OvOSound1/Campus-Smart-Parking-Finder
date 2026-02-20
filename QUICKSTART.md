# Quick Start Guide

This guide will get you running the Campus Smart Parking Finder in under 5 minutes.

## Prerequisites

- Python 3.7 or higher
- Terminal/Command Prompt

## Setup (One-Time)

### macOS/Linux:
```bash
# Run the setup script
chmod +x setup.sh
./setup.sh
```

### Windows:
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the System

### Terminal 1: Start the Server
```bash
python parking_server.py
```

You should see:
```
INFO - Parking server initialized with 4 lots
INFO - All server components started
INFO - Text protocol server listening on port 5000
INFO - RPC server listening on port 5001
```

### Terminal 2: Try the Interactive Client
```bash
python rpc_client.py
```

Try these commands:
1. List all lots (option 1)
2. Check availability for LOT-A (option 2)
3. Reserve a spot (option 3)

### Terminal 3: Watch Live Events
```bash
python pubsub_client.py --lot LOT-A
```

### Terminal 4: Simulate Sensors
```bash
python sensor_simulator.py --duration 30 --rate 2.0
```

Now watch Terminal 3 - you'll see live events as parking occupancy changes!

## Run Load Tests

```bash
# Quick test (4 workers, 30 seconds)
python load_test.py --workers 4 --duration 30

# Full baseline suite (takes ~6 minutes)
python load_test.py --baseline
```

Results saved to `load_test_results.json`

## Common Issues

**"Connection refused"**
- Make sure server is running (Terminal 1)
- Check no other process is using ports 5000-5003

**"Module not found"**
- Activate virtual environment: `source .venv/bin/activate`

**"Address already in use"**
- Kill existing server: `pkill -f parking_server.py`
- Or change ports in `config.json`

## Next Steps

1. Read [README.md](README.md) for full documentation
2. Check [API.md](API.md) for API reference
3. Edit `config.json` to customize lot capacities
4. Fill out `REPORT_TEMPLATE.md` with your test results

## Testing Checklist

- [ ] Server starts without errors
- [ ] RPC client can list lots
- [ ] Can reserve and cancel spots
- [ ] Pub/sub receives events
- [ ] Sensors can send updates
- [ ] Load test completes successfully

## File Overview

| File | Purpose |
|------|---------|
| `parking_server.py` | Main server (start this first) |
| `rpc_client.py` | Interactive RPC client |
| `pubsub_client.py` | Subscribe to lot updates |
| `sensor_simulator.py` | Generate parking events |
| `load_test.py` | Performance testing |
| `config.json` | Server configuration |

## Video Demo Script

Want to record a demo? Follow this:

1. **Start server** (show terminal output)
2. **Open RPC client**, list lots
3. **Start subscriber** for LOT-A in another terminal
4. **Reserve a spot** via RPC client
5. **Watch event** appear in subscriber terminal
6. **Start sensor simulator** 
7. **Watch events** stream to subscriber
8. **Run quick load test**
9. **Show results** in load_test_result.json

Total demo time: ~3 minutes

---

**Need help?** Check the full [README.md](README.md) or [API.md](API.md)
