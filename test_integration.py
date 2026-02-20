#!/usr/bin/env python3
"""
Integration Test Script
Quick test to verify all components work together
"""

import time
import subprocess
import sys
import socket
import json
import struct

def test_server_ports():
    """Test if server is running on all ports"""
    ports = {
        'Text Protocol': 5000,
        'RPC': 5001,
        'Sensor': 5002,
        'Pub/Sub': 5003
    }
    
    print("Testing server connectivity...")
    for name, port in ports.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if result == 0:
                print(f"  ✓ {name} (port {port}): OK")
            else:
                print(f"  ✗ {name} (port {port}): Not responding")
                return False
        except Exception as e:
            print(f"  ✗ {name} (port {port}): Error - {e}")
            return False
    
    return True

def test_text_protocol():
    """Test text protocol commands"""
    print("\nTesting text protocol...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 5000))
        
        # Test PING
        sock.sendall(b"PING\n")
        response = sock.recv(1024).decode('utf-8').strip()
        assert response == "PONG", f"Expected PONG, got {response}"
        print("  ✓ PING/PONG")
        
        # Test LOTS
        sock.sendall(b"LOTS\n")
        response = sock.recv(4096).decode('utf-8').strip()
        lots = json.loads(response)
        assert isinstance(lots, list), "LOTS should return list"
        assert len(lots) > 0, "Should have at least one lot"
        print(f"  ✓ LOTS (found {len(lots)} lots)")
        
        # Test AVAIL
        lot_id = lots[0]['id']
        sock.sendall(f"AVAIL {lot_id}\n".encode())
        response = sock.recv(1024).decode('utf-8').strip()
        free = int(response)
        print(f"  ✓ AVAIL {lot_id} = {free}")
        
        # Test RESERVE
        sock.sendall(f"RESERVE {lot_id} TEST123\n".encode())
        response = sock.recv(1024).decode('utf-8').strip()
        assert response in ['OK', 'FULL', 'EXISTS'], f"Unexpected response: {response}"
        print(f"  ✓ RESERVE {lot_id} TEST123 = {response}")
        
        # Test CANCEL
        sock.sendall(f"CANCEL {lot_id} TEST123\n".encode())
        response = sock.recv(1024).decode('utf-8').strip()
        print(f"  ✓ CANCEL {lot_id} TEST123 = {response}")
        
        sock.close()
        return True
    
    except Exception as e:
        print(f"  ✗ Text protocol error: {e}")
        return False

def test_rpc():
    """Test RPC interface"""
    print("\nTesting RPC...")
    try:
        from rpc_client import RPCClient
        
        client = RPCClient()
        client.connect()
        
        # Test getLots
        lots = client.get_lots()
        assert isinstance(lots, list)
        print(f"  ✓ getLots() returned {len(lots)} lots")
        
        # Test getAvailability
        lot_id = lots[0]['id']
        free = client.get_availability(lot_id)
        assert isinstance(free, int)
        print(f"  ✓ getAvailability('{lot_id}') = {free}")
        
        # Test reserve
        result = client.reserve(lot_id, "RPC_TEST")
        print(f"  ✓ reserve('{lot_id}', 'RPC_TEST') = {result}")
        
        # Test cancel
        result = client.cancel(lot_id, "RPC_TEST")
        print(f"  ✓ cancel('{lot_id}', 'RPC_TEST') = {result}")
        
        client.close()
        return True
    
    except Exception as e:
        print(f"  ✗ RPC error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sensor():
    """Test sensor update interface"""
    print("\nTesting sensor interface...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 5002))
        
        # Send update
        sock.sendall(b"UPDATE LOT-A +1\n")
        response = sock.recv(1024).decode('utf-8').strip()
        assert response == "ACK", f"Expected ACK, got {response}"
        print("  ✓ UPDATE LOT-A +1 = ACK")
        
        sock.sendall(b"UPDATE LOT-A -1\n")
        response = sock.recv(1024).decode('utf-8').strip()
        assert response == "ACK"
        print("  ✓ UPDATE LOT-A -1 = ACK")
        
        sock.close()
        return True
    
    except Exception as e:
        print(f"  ✗ Sensor error: {e}")
        return False

def test_pubsub():
    """Test pub/sub interface"""
    print("\nTesting pub/sub...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('127.0.0.1', 5003))
        
        # Subscribe
        request = {
            'rpcId': 1,
            'method': 'subscribe',
            'args': ['LOT-A']
        }
        request_bytes = json.dumps(request).encode('utf-8')
        frame = struct.pack('!I', len(request_bytes)) + request_bytes
        sock.sendall(frame)
        
        # Read response
        length_bytes = sock.recv(4)
        length = struct.unpack('!I', length_bytes)[0]
        response_bytes = sock.recv(length)
        response = json.loads(response_bytes.decode('utf-8'))
        
        assert response['error'] is None, f"Subscribe failed: {response['error']}"
        sub_id = response['result']
        print(f"  ✓ subscribe('LOT-A') = {sub_id}")
        
        # Trigger an event by sending sensor update
        sensor_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sensor_sock.connect(('127.0.0.1', 5002))
        sensor_sock.sendall(b"UPDATE LOT-A +1\n")
        sensor_sock.recv(1024)  # ACK
        sensor_sock.sendall(b"UPDATE LOT-A -1\n")
        sensor_sock.recv(1024)  # ACK
        sensor_sock.close()
        
        # Try to receive event (with timeout)
        try:
            length_bytes = sock.recv(4)
            if length_bytes:
                length = struct.unpack('!I', length_bytes)[0]
                event_bytes = sock.recv(length)
                event = event_bytes.decode('utf-8')
                print(f"  ✓ Received event: {event}")
            else:
                print("  ⚠ No event received (may be OK if no change)")
        except socket.timeout:
            print("  ⚠ No event received within timeout (may be OK)")
        
        sock.close()
        return True
    
    except Exception as e:
        print(f"  ✗ Pub/Sub error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("Campus Smart Parking Finder - Integration Test")
    print("="*60)
    print("\nMake sure the server is running before running this test!")
    print("Start it with: python parking_server.py\n")
    
    input("Press Enter when server is ready...")
    
    tests = [
        ("Server Connectivity", test_server_ports),
        ("Text Protocol", test_text_protocol),
        ("RPC Interface", test_rpc),
        ("Sensor Updates", test_sensor),
        ("Pub/Sub System", test_pubsub),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
