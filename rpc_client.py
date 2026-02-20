#!/usr/bin/env python3
"""
RPC Client for Campus Smart Parking Finder
Implements client stub with length-prefixed framing and timeout handling.
"""

import socket
import json
import struct
import time
from typing import List, Dict, Optional, Any


class TimeoutError(Exception):
    """Custom exception for RPC timeouts"""
    pass


class RPCClient:
    """RPC Client stub for parking server"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5001, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.next_rpc_id = 1
        self.conn: Optional[socket.socket] = None
    
    def connect(self):
        """Establish connection to RPC server"""
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.settimeout(self.timeout)
        self.conn.connect((self.host, self.port))
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _call_rpc(self, method: str, args: List[Any]) -> Any:
        """
        Internal RPC call method with framing and timeout.
        
        Wire format:
        - Request: 4-byte length (big-endian uint32) + JSON payload
        - JSON payload: {rpcId: uint32, method: str, args: any[]}
        - Response: 4-byte length + JSON payload
        - JSON payload: {rpcId: uint32, result: any, error: str|null}
        """
        if not self.conn:
            self.connect()
        
        # Build request
        rpc_id = self.next_rpc_id
        self.next_rpc_id += 1
        
        request = {
            'rpcId': rpc_id,
            'method': method,
            'args': args
        }
        
        # Serialize and frame request
        request_bytes = json.dumps(request).encode('utf-8')
        request_msg = struct.pack('!I', len(request_bytes)) + request_bytes
        
        # Send request
        start_time = time.time()
        self.conn.sendall(request_msg)
        
        # Receive response with timeout
        try:
            # Read 4-byte length prefix
            length_bytes = self._recv_exactly(4)
            if not length_bytes:
                raise ConnectionError("Connection closed by server")
            
            elapsed = time.time() - start_time
            if elapsed >= self.timeout:
                raise TimeoutError(f"RPC timeout after {elapsed:.2f}s")
            
            msg_length = struct.unpack('!I', length_bytes)[0]
            
            # Read message
            msg_bytes = self._recv_exactly(msg_length)
            if not msg_bytes:
                raise ConnectionError("Connection closed by server")
            
            elapsed = time.time() - start_time
            if elapsed >= self.timeout:
                raise TimeoutError(f"RPC timeout after {elapsed:.2f}s")
            
            # Parse response
            response = json.loads(msg_bytes.decode('utf-8'))
            
            if response['rpcId'] != rpc_id:
                raise ValueError(f"RPC ID mismatch: expected {rpc_id}, got {response['rpcId']}")
            
            if response['error']:
                raise Exception(f"RPC error: {response['error']}")
            
            return response['result']
            
        except socket.timeout:
            raise TimeoutError(f"RPC timeout after {self.timeout}s")
    
    def _recv_exactly(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes from socket"""
        data = b''
        while len(data) < n:
            chunk = self.conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    # ========== RPC Methods ==========
    
    def get_lots(self) -> List[Dict]:
        """Get list of all parking lots"""
        return self._call_rpc('getLots', [])
    
    def get_availability(self, lot_id: str) -> int:
        """Get number of available spots in a lot"""
        return self._call_rpc('getAvailability', [lot_id])
    
    def reserve(self, lot_id: str, plate: str) -> bool:
        """Reserve a spot. Returns True on success, False otherwise."""
        return self._call_rpc('reserve', [lot_id, plate])
    
    def cancel(self, lot_id: str, plate: str) -> bool:
        """Cancel a reservation. Returns True on success, False otherwise."""
        return self._call_rpc('cancel', [lot_id, plate])


class TextProtocolClient:
    """Text protocol client for parking server"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5000):
        self.host = host
        self.port = port
        self.conn: Optional[socket.socket] = None
    
    def connect(self):
        """Connect to server"""
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.host, self.port))
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def send_command(self, command: str) -> str:
        """Send command and receive response"""
        if not self.conn:
            self.connect()
        
        self.conn.sendall((command + '\n').encode('utf-8'))
        
        # Receive response
        buffer = ""
        while '\n' not in buffer:
            data = self.conn.recv(1024).decode('utf-8')
            if not data:
                break
            buffer += data
        
        return buffer.strip()
    
    def ping(self) -> str:
        """Send PING command"""
        return self.send_command("PING")
    
    def get_lots(self) -> List[Dict]:
        """Get all lots"""
        response = self.send_command("LOTS")
        return json.loads(response)
    
    def get_availability(self, lot_id: str) -> int:
        """Get availability for a lot"""
        response = self.send_command(f"AVAIL {lot_id}")
        return int(response)
    
    def reserve(self, lot_id: str, plate: str) -> str:
        """Reserve a spot"""
        return self.send_command(f"RESERVE {lot_id} {plate}")
    
    def cancel(self, lot_id: str, plate: str) -> str:
        """Cancel a reservation"""
        return self.send_command(f"CANCEL {lot_id} {plate}")


def interactive_client():
    """Interactive RPC client for testing"""
    print("Campus Smart Parking Finder - RPC Client")
    print("=" * 50)
    
    client = RPCClient()
    
    try:
        client.connect()
        print(f"Connected to server at {client.host}:{client.port}\n")
        
        while True:
            print("\nCommands:")
            print("  1. List all lots")
            print("  2. Check availability")
            print("  3. Reserve spot")
            print("  4. Cancel reservation")
            print("  5. Exit")
            
            choice = input("\nEnter choice: ").strip()
            
            if choice == '1':
                lots = client.get_lots()
                print("\nParking Lots:")
                for lot in lots:
                    print(f"  {lot['id']}: {lot['free']}/{lot['capacity']} free")
            
            elif choice == '2':
                lot_id = input("Enter lot ID: ").strip()
                try:
                    free = client.get_availability(lot_id)
                    print(f"Available spots: {free}")
                except Exception as e:
                    print(f"Error: {e}")
            
            elif choice == '3':
                lot_id = input("Enter lot ID: ").strip()
                plate = input("Enter license plate: ").strip()
                try:
                    success = client.reserve(lot_id, plate)
                    if success:
                        print("Reservation successful!")
                    else:
                        print("Reservation failed (lot full or already reserved)")
                except Exception as e:
                    print(f"Error: {e}")
            
            elif choice == '4':
                lot_id = input("Enter lot ID: ").strip()
                plate = input("Enter license plate: ").strip()
                try:
                    success = client.cancel(lot_id, plate)
                    if success:
                        print("Cancellation successful!")
                    else:
                        print("Cancellation failed (reservation not found)")
                except Exception as e:
                    print(f"Error: {e}")
            
            elif choice == '5':
                break
            
            else:
                print("Invalid choice")
    
    finally:
        client.close()
        print("\nDisconnected from server")


if __name__ == '__main__':
    interactive_client()
