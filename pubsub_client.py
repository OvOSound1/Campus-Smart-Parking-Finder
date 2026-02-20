#!/usr/bin/env python3
"""
Pub/Sub Subscriber Client for Campus Smart Parking Finder
Subscribes to parking lot updates and receives real-time events.
"""

import socket
import json
import struct
import argparse
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PubSubClient:
    """Pub/Sub subscriber client"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5003, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.conn: Optional[socket.socket] = None
        self.next_rpc_id = 1
        self.subscription_id: Optional[int] = None
    
    def connect(self):
        """Connect to pub/sub server"""
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.settimeout(self.timeout)
        self.conn.connect((self.host, self.port))
        logger.info(f"Connected to pub/sub server at {self.host}:{self.port}")
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
        logger.info("Disconnected from pub/sub server")
    
    def _send_rpc(self, method: str, args: list) -> dict:
        """Send RPC request and receive response"""
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
        
        # Frame and send
        request_bytes = json.dumps(request).encode('utf-8')
        request_msg = struct.pack('!I', len(request_bytes)) + request_bytes
        self.conn.sendall(request_msg)
        
        # Receive response
        length_bytes = self._recv_exactly(4)
        if not length_bytes:
            raise ConnectionError("Connection closed by server")
        
        msg_length = struct.unpack('!I', length_bytes)[0]
        msg_bytes = self._recv_exactly(msg_length)
        if not msg_bytes:
            raise ConnectionError("Connection closed by server")
        
        response = json.loads(msg_bytes.decode('utf-8'))
        
        if response['error']:
            raise Exception(f"RPC error: {response['error']}")
        
        return response
    
    def _recv_exactly(self, n: int) -> Optional[bytes]:
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def subscribe(self, lot_id: str) -> int:
        """
        Subscribe to updates for a specific lot.
        Returns subscription ID.
        """
        response = self._send_rpc('subscribe', [lot_id])
        self.subscription_id = response['result']
        logger.info(f"Subscribed to {lot_id} with subscription ID {self.subscription_id}")
        return self.subscription_id
    
    def receive_events(self, duration: Optional[int] = None):
        """
        Receive and print events.
        
        Args:
            duration: How long to listen (seconds), None for indefinite
        """
        if not self.conn:
            raise Exception("Not connected")
        
        logger.info("Listening for events... (Press Ctrl+C to stop)")
        
        import time
        start_time = time.time()
        event_count = 0
        
        try:
            # Set longer timeout for event reception
            self.conn.settimeout(30.0)
            
            while True:
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
                
                try:
                    # Receive event (length-prefixed)
                    length_bytes = self._recv_exactly(4)
                    if not length_bytes:
                        logger.warning("Connection closed by server")
                        break
                    
                    msg_length = struct.unpack('!I', length_bytes)[0]
                    msg_bytes = self._recv_exactly(msg_length)
                    if not msg_bytes:
                        logger.warning("Connection closed by server")
                        break
                    
                    event = msg_bytes.decode('utf-8')
                    event_count += 1
                    
                    # Parse and display event
                    parts = event.split()
                    if len(parts) >= 4 and parts[0] == 'EVENT':
                        lot_id = parts[1]
                        free = parts[2]
                        timestamp = parts[3]
                        logger.info(f"[EVENT #{event_count}] {lot_id}: {free} spots free at {timestamp}")
                    else:
                        logger.info(f"[EVENT #{event_count}] {event}")
                
                except socket.timeout:
                    logger.debug("No events received (timeout)")
                    continue
        
        except KeyboardInterrupt:
            logger.info("\nStopped listening for events")
        
        finally:
            elapsed = time.time() - start_time
            logger.info(f"\nEvent summary:")
            logger.info(f"  Duration: {elapsed:.2f}s")
            logger.info(f"  Events received: {event_count}")
            if elapsed > 0:
                logger.info(f"  Average rate: {event_count/elapsed:.2f} events/sec")


def main():
    parser = argparse.ArgumentParser(description='Pub/Sub Subscriber Client')
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=5003, help='Pub/Sub port')
    parser.add_argument('--lot', required=True, help='Lot ID to subscribe to')
    parser.add_argument('--duration', type=int, default=None,
                        help='Listen duration (seconds), omit for indefinite')
    
    args = parser.parse_args()
    
    client = PubSubClient(host=args.host, port=args.port)
    
    try:
        client.connect()
        client.subscribe(args.lot)
        client.receive_events(duration=args.duration)
    
    except Exception as e:
        logger.error(f"Error: {e}")
    
    finally:
        client.close()


if __name__ == '__main__':
    main()
