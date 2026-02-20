# Individual Reflection - [Your Name]

**Project**: Campus Smart Parking Finder  
**Date**: [Date]

---

## What I Implemented

[Describe the specific components/features you were responsible for implementing. Be specific about which files, functions, or subsystems you worked on. Maximum 150 words.]

**Example**:
"I implemented the RPC layer including the client stub (`rpc_client.py`) and server skeleton in `parking_server.py`. This involved designing the length-prefixed framing mechanism using struct.pack/unpack for network byte order, implementing the JSON marshalling for requests/responses, and adding timeout handling with proper error propagation. I also created the TimeoutError exception class and ensured that the client properly handles connection failures. Additionally, I implemented the `_recv_exactly()` helper function to handle partial receives from TCP sockets, which was crucial for reliably reading framed messages."

**Your implementation** (150 words max):

[Write your description here]

---

## A Bug I Fixed

[Describe a specific bug you encountered and debugged. Explain: (1) what the symptom was, (2) how you diagnosed it, (3) what the root cause was, and (4) how you fixed it. Maximum 100 words.]

**Example**:
"Initially, the server would deadlock under high load. I added debug logging and discovered that `ParkingLot.get_free()` was calling `_cleanup_expired_reservations()`, which also needed the lock. Since both used `threading.Lock()`, the same thread couldn't acquire the lock twice. I changed `threading.Lock()` to `threading.RLock()` (reentrant lock), which allows the same thread to acquire the lock multiple times. This fixed the deadlock while maintaining thread safety for concurrent access from different threads."

**Your bug** (100 words max):

[Write your description here]

---

## One Design Change

[Describe a design decision you made or changed during development. Explain what the original approach was, why you changed it, and what the impact was. Maximum 50 words.]

**Example**:
"Originally, pub/sub used a single global event queue with subscriber IDs. I changed it to per-subscriber queues, which simplified back-pressure handling (each subscriber has independent capacity) and improved fairness (slow subscribers don't block fast ones)."

**Your design change** (50 words max):

[Write your description here]

---

**Total Word Count**: ~300 words

---

**Instructions**:
1. Replace [Your Name] with your actual name
2. Fill in each section, staying within word limits
3. Be specific and technical (not generic)
4. Use concrete examples (file names, function names, line numbers if relevant)
5. Save as `REFLECTION_[YourName].md` or `.txt`

**Grading Focus**:
- Specificity (not "I worked on the server" but "I implemented X function in Y file")
- Technical depth (show understanding of what you built)
- Problem-solving (the bug section should demonstrate debugging skills)
- Reflection (the design change should show learning/iteration)
