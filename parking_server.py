#!/usr/bin/env python3
"""
Campus Smart Parking Finder - Main Server
Implements multithreaded TCP server with text protocol, RPC, async updates, and pub/sub.
"""

import socket
import threading
import json
import time
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from queue import Queue, Full, Empty
import struct

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Reservation:
    """Represents a parking spot reservation"""
    def __init__(self, lot_id: str, plate: str, timeout_seconds: int):
        self.lot_id = lot_id
        self.plate = plate
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=timeout_seconds)
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class ParkingLot:
    """Thread-safe parking lot state"""
    def __init__(self, lot_id: str, capacity: int, occupied: int):
        self.id = lot_id
        self.capacity = capacity
        self.occupied = occupied
        self.lock = threading.RLock()
        self.reservations: Dict[str, Reservation] = {}
    
    def get_free(self) -> int:
        """Returns number of free spots (capacity - occupied - active_reservations)"""
        with self.lock:
            self._cleanup_expired_reservations()
            return self.capacity - self.occupied - len(self.reservations)
    
    def _cleanup_expired_reservations(self):
        """Remove expired reservations"""
        expired = [plate for plate, res in self.reservations.items() if res.is_expired()]
        for plate in expired:
            del self.reservations[plate]
            logger.info(json.dumps({
                'event': 'reservation_expired',
                'lot_id': self.id,
                'plate': plate,
                'timestamp': datetime.now().isoformat()
            }))
    
    def reserve(self, plate: str, timeout_seconds: int) -> str:
        """Attempt to reserve a spot. Returns: OK, FULL, or EXISTS"""
        with self.lock:
            self._cleanup_expired_reservations()
            
            if plate in self.reservations:
                return "EXISTS"
            
            if self.get_free() <= 0:
                return "FULL"
            
            self.reservations[plate] = Reservation(self.id, plate, timeout_seconds)
            logger.info(json.dumps({
                'event': 'reservation_created',
                'lot_id': self.id,
                'plate': plate,
                'timestamp': datetime.now().isoformat()
            }))
            return "OK"
    
    def cancel(self, plate: str) -> str:
        """Cancel a reservation. Returns: OK or NOT_FOUND"""
        with self.lock:
            if plate in self.reservations:
                del self.reservations[plate]
                logger.info(json.dumps({
                    'event': 'reservation_cancelled',
                    'lot_id': self.id,
                    'plate': plate,
                    'timestamp': datetime.now().isoformat()
                }))
                return "OK"
            return "NOT_FOUND"
    
    def update_occupancy(self, delta: int) -> int:
        """Update occupancy by delta. Returns new free count."""
        with self.lock:
            old_free = self.get_free()
            self.occupied = max(0, min(self.capacity, self.occupied + delta))
            new_free = self.get_free()
            logger.info(json.dumps({
                'event': 'occupancy_updated',
                'lot_id': self.id,
                'delta': delta,
                'occupied': self.occupied,
                'free': new_free,
                'timestamp': datetime.now().isoformat()
            }))
            return new_free
    
    def to_dict(self) -> dict:
        """Serialize lot state to dictionary"""
        with self.lock:
            return {
                'id': self.id,
                'capacity': self.capacity,
                'occupied': self.occupied,
                'free': self.get_free()
            }


class Subscriber:
    """Represents a pub/sub subscriber"""
    def __init__(self, sub_id: int, lot_id: str, conn: socket.socket, max_queue_size: int):
        self.sub_id = sub_id
        self.lot_id = lot_id
        self.conn = conn
        self.queue = Queue(maxsize=max_queue_size)
        self.active = True


class ParkingServer:
    """Main parking server with text protocol, RPC, async updates, and pub/sub"""
    
    def __init__(self, config_path: str = 'config.json'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize parking lots
        self.lots: Dict[str, ParkingLot] = {}
        for lot_config in self.config['lots']:
            lot = ParkingLot(
                lot_config['id'],
                lot_config['capacity'],
                lot_config['occupied']
            )
            self.lots[lot_config['id']] = lot
        
        # Server state
        self.running = False
        self.update_queue = Queue()
        
        # Pub/Sub state
        self.subscribers: Dict[int, Subscriber] = {}
        self.subscriber_lock = threading.Lock()
        self.next_sub_id = 1
        
        logger.info(f"Parking server initialized with {len(self.lots)} lots")
    
    def start(self):
        """Start all server components"""
        self.running = True
        
        # Start worker threads for async updates
        for i in range(3):
            thread = threading.Thread(target=self._update_worker, daemon=True)
            thread.start()
        
        # Start pub/sub notifier thread
        notifier = threading.Thread(target=self._pubsub_notifier, daemon=True)
        notifier.start()
        
        # Start servers on different threads
        servers = [
            threading.Thread(target=self._run_text_protocol_server, daemon=True),
            threading.Thread(target=self._run_rpc_server, daemon=True),
            threading.Thread(target=self._run_sensor_server, daemon=True),
            threading.Thread(target=self._run_pubsub_server, daemon=True),
        ]
        
        for server in servers:
            server.start()
        
        logger.info("All server components started")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down server...")
            self.running = False
    
    # ========== TEXT PROTOCOL SERVER ==========
    
    def _run_text_protocol_server(self):
        """Run text protocol server (thread-per-connection model)"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((
            self.config['server']['host'],
            self.config['server']['text_protocol_port']
        ))
        server_sock.listen(self.config['server']['backlog'])
        
        logger.info(f"Text protocol server listening on port {self.config['server']['text_protocol_port']}")
        
        while self.running:
            try:
                server_sock.settimeout(1.0)
                conn, addr = server_sock.accept()
                thread = threading.Thread(
                    target=self._handle_text_protocol_client,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Text protocol server error: {e}")
    
    def _handle_text_protocol_client(self, conn: socket.socket, addr):
        """Handle text protocol client connection"""
        logger.info(f"Text protocol client connected: {addr}")
        
        try:
            buffer = ""
            while self.running:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        response = self._process_text_command(line)
                        conn.sendall((response + '\n').encode('utf-8'))
        except Exception as e:
            logger.error(f"Text protocol client error: {e}")
        finally:
            conn.close()
            logger.info(f"Text protocol client disconnected: {addr}")
    
    def _process_text_command(self, command: str) -> str:
        """Process text protocol command"""
        parts = command.split()
        if not parts:
            return "ERROR: Empty command"
        
        cmd = parts[0].upper()
        
        if cmd == "PING":
            return "PONG"
        
        elif cmd == "LOTS":
            lots_data = [lot.to_dict() for lot in self.lots.values()]
            return json.dumps(lots_data)
        
        elif cmd == "AVAIL":
            if len(parts) != 2:
                return "ERROR: AVAIL requires lot_id"
            lot_id = parts[1]
            if lot_id not in self.lots:
                return "ERROR: Unknown lot"
            return str(self.lots[lot_id].get_free())
        
        elif cmd == "RESERVE":
            if len(parts) != 3:
                return "ERROR: RESERVE requires lot_id and plate"
            lot_id, plate = parts[1], parts[2]
            if lot_id not in self.lots:
                return "ERROR: Unknown lot"
            result = self.lots[lot_id].reserve(
                plate,
                self.config['server']['reservation_timeout_seconds']
            )
            return result
        
        elif cmd == "CANCEL":
            if len(parts) != 3:
                return "ERROR: CANCEL requires lot_id and plate"
            lot_id, plate = parts[1], parts[2]
            if lot_id not in self.lots:
                return "ERROR: Unknown lot"
            return self.lots[lot_id].cancel(plate)
        
        else:
            return f"ERROR: Unknown command: {cmd}"
    
    # ========== RPC SERVER ==========
    
    def _run_rpc_server(self):
        """Run RPC server with thread pool"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((
            self.config['server']['host'],
            self.config['server']['rpc_port']
        ))
        server_sock.listen(self.config['server']['backlog'])
        
        logger.info(f"RPC server listening on port {self.config['server']['rpc_port']}")
        
        while self.running:
            try:
                server_sock.settimeout(1.0)
                conn, addr = server_sock.accept()
                thread = threading.Thread(
                    target=self._handle_rpc_client,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"RPC server error: {e}")
    
    def _handle_rpc_client(self, conn: socket.socket, addr):
        """Handle RPC client with length-prefixed framing"""
        logger.info(f"RPC client connected: {addr}")
        
        try:
            while self.running:
                # Read 4-byte length prefix
                length_bytes = self._recv_exactly(conn, 4)
                if not length_bytes:
                    break
                
                msg_length = struct.unpack('!I', length_bytes)[0]
                
                # Read message
                msg_bytes = self._recv_exactly(conn, msg_length)
                if not msg_bytes:
                    break
                
                # Process RPC request
                request = json.loads(msg_bytes.decode('utf-8'))
                response = self._process_rpc_request(request)
                
                # Send response with length prefix
                response_bytes = json.dumps(response).encode('utf-8')
                response_msg = struct.pack('!I', len(response_bytes)) + response_bytes
                conn.sendall(response_msg)
                
        except Exception as e:
            logger.error(f"RPC client error: {e}")
        finally:
            conn.close()
            logger.info(f"RPC client disconnected: {addr}")
    
    def _recv_exactly(self, conn: socket.socket, n: int) -> Optional[bytes]:
        """Receive exactly n bytes from socket"""
        data = b''
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def _process_rpc_request(self, request: dict) -> dict:
        """Process RPC request and return response"""
        rpc_id = request.get('rpcId', 0)
        method = request.get('method', '')
        args = request.get('args', [])
        
        try:
            if method == 'getLots':
                result = [lot.to_dict() for lot in self.lots.values()]
                return {'rpcId': rpc_id, 'result': result, 'error': None}
            
            elif method == 'getAvailability':
                if len(args) < 1:
                    raise ValueError("Missing lot_id argument")
                lot_id = args[0]
                if lot_id not in self.lots:
                    raise ValueError(f"Unknown lot: {lot_id}")
                result = self.lots[lot_id].get_free()
                return {'rpcId': rpc_id, 'result': result, 'error': None}
            
            elif method == 'reserve':
                if len(args) < 2:
                    raise ValueError("Missing arguments")
                lot_id, plate = args[0], args[1]
                if lot_id not in self.lots:
                    raise ValueError(f"Unknown lot: {lot_id}")
                result_str = self.lots[lot_id].reserve(
                    plate,
                    self.config['server']['reservation_timeout_seconds']
                )
                result = (result_str == "OK")
                return {'rpcId': rpc_id, 'result': result, 'error': None}
            
            elif method == 'cancel':
                if len(args) < 2:
                    raise ValueError("Missing arguments")
                lot_id, plate = args[0], args[1]
                if lot_id not in self.lots:
                    raise ValueError(f"Unknown lot: {lot_id}")
                result_str = self.lots[lot_id].cancel(plate)
                result = (result_str == "OK")
                return {'rpcId': rpc_id, 'result': result, 'error': None}
            
            elif method == 'subscribe':
                # This is handled separately in pub/sub server
                raise ValueError("Use pub/sub connection for subscribe")
            
            elif method == 'unsubscribe':
                # This is handled separately in pub/sub server
                raise ValueError("Use pub/sub connection for unsubscribe")
            
            else:
                raise ValueError(f"Unknown method: {method}")
                
        except Exception as e:
            return {'rpcId': rpc_id, 'result': None, 'error': str(e)}
    
    # ========== SENSOR UPDATE SERVER ==========
    
    def _run_sensor_server(self):
        """Run sensor update server"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((
            self.config['server']['host'],
            self.config['server']['sensor_port']
        ))
        server_sock.listen(self.config['server']['backlog'])
        
        logger.info(f"Sensor server listening on port {self.config['server']['sensor_port']}")
        
        while self.running:
            try:
                server_sock.settimeout(1.0)
                conn, addr = server_sock.accept()
                thread = threading.Thread(
                    target=self._handle_sensor_client,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Sensor server error: {e}")
    
    def _handle_sensor_client(self, conn: socket.socket, addr):
        """Handle sensor client connection"""
        logger.info(f"Sensor client connected: {addr}")
        
        try:
            buffer = ""
            while self.running:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        # Enqueue update for async processing
                        self.update_queue.put(line)
                        conn.sendall("ACK\n".encode('utf-8'))
        except Exception as e:
            logger.error(f"Sensor client error: {e}")
        finally:
            conn.close()
            logger.info(f"Sensor client disconnected: {addr}")
    
    def _update_worker(self):
        """Worker thread to process sensor updates"""
        while self.running:
            try:
                update_cmd = self.update_queue.get(timeout=1.0)
                parts = update_cmd.split()
                
                if len(parts) == 3 and parts[0].upper() == 'UPDATE':
                    lot_id = parts[1]
                    delta = int(parts[2])
                    
                    if lot_id in self.lots:
                        old_free = self.lots[lot_id].get_free()
                        new_free = self.lots[lot_id].update_occupancy(delta)
                        
                        # Publish event if free count changed
                        if old_free != new_free:
                            self._publish_event(lot_id, new_free)
                    else:
                        logger.warning(f"Update for unknown lot: {lot_id}")
                        
            except Empty:
                # Normal timeout, continue
                continue
            except Exception as e:
                logger.error(f"Update worker error: {e}")
    
    # ========== PUB/SUB SERVER ==========
    
    def _run_pubsub_server(self):
        """Run pub/sub server for subscriptions"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((
            self.config['server']['host'],
            self.config['server']['pubsub_port']
        ))
        server_sock.listen(self.config['server']['backlog'])
        
        logger.info(f"Pub/Sub server listening on port {self.config['server']['pubsub_port']}")
        
        while self.running:
            try:
                server_sock.settimeout(1.0)
                conn, addr = server_sock.accept()
                thread = threading.Thread(
                    target=self._handle_pubsub_client,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Pub/Sub server error: {e}")
    
    def _handle_pubsub_client(self, conn: socket.socket, addr):
        """Handle pub/sub client connection"""
        logger.info(f"Pub/Sub client connected: {addr}")
        
        try:
            while self.running:
                # Read length-prefixed RPC request
                length_bytes = self._recv_exactly(conn, 4)
                if not length_bytes:
                    break
                
                msg_length = struct.unpack('!I', length_bytes)[0]
                msg_bytes = self._recv_exactly(conn, msg_length)
                if not msg_bytes:
                    break
                
                request = json.loads(msg_bytes.decode('utf-8'))
                response = self._process_pubsub_request(request, conn)
                
                # Send response
                response_bytes = json.dumps(response).encode('utf-8')
                response_msg = struct.pack('!I', len(response_bytes)) + response_bytes
                conn.sendall(response_msg)
                
                # If this was a subscribe request, keep connection open for events
                if request.get('method') == 'subscribe' and response.get('error') is None:
                    # Connection will be kept alive for event delivery
                    self._handle_subscription_events(response['result'], conn)
                    break
                    
        except Exception as e:
            logger.error(f"Pub/Sub client error: {e}")
        finally:
            conn.close()
            logger.info(f"Pub/Sub client disconnected: {addr}")
    
    def _process_pubsub_request(self, request: dict, conn: socket.socket) -> dict:
        """Process pub/sub RPC request"""
        rpc_id = request.get('rpcId', 0)
        method = request.get('method', '')
        args = request.get('args', [])
        
        try:
            if method == 'subscribe':
                if len(args) < 1:
                    raise ValueError("Missing lot_id argument")
                lot_id = args[0]
                if lot_id not in self.lots:
                    raise ValueError(f"Unknown lot: {lot_id}")
                
                # Create subscriber
                with self.subscriber_lock:
                    sub_id = self.next_sub_id
                    self.next_sub_id += 1
                    
                    max_queue = self.config['pubsub']['max_queue_size']
                    subscriber = Subscriber(sub_id, lot_id, conn, max_queue)
                    self.subscribers[sub_id] = subscriber
                
                logger.info(f"Created subscription {sub_id} for lot {lot_id}")
                return {'rpcId': rpc_id, 'result': sub_id, 'error': None}
            
            elif method == 'unsubscribe':
                if len(args) < 1:
                    raise ValueError("Missing sub_id argument")
                sub_id = args[0]
                
                with self.subscriber_lock:
                    if sub_id in self.subscribers:
                        self.subscribers[sub_id].active = False
                        del self.subscribers[sub_id]
                        logger.info(f"Unsubscribed {sub_id}")
                        return {'rpcId': rpc_id, 'result': True, 'error': None}
                    else:
                        return {'rpcId': rpc_id, 'result': False, 'error': 'Unknown subscription'}
            
            else:
                raise ValueError(f"Unknown method: {method}")
                
        except Exception as e:
            return {'rpcId': rpc_id, 'result': None, 'error': str(e)}
    
    def _handle_subscription_events(self, sub_id: int, conn: socket.socket):
        """Handle event delivery for a subscription"""
        try:
            subscriber = self.subscribers.get(sub_id)
            if not subscriber:
                return
            
            while self.running and subscriber.active:
                try:
                    # Get event from subscriber's queue (blocking)
                    event = subscriber.queue.get(timeout=1.0)
                    
                    # Send event with length prefix
                    event_bytes = event.encode('utf-8')
                    event_msg = struct.pack('!I', len(event_bytes)) + event_bytes
                    conn.sendall(event_msg)
                    
                except Exception as e:
                    if "Empty" not in str(type(e).__name__):
                        logger.error(f"Event delivery error for sub {sub_id}: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Subscription handler error: {e}")
        finally:
            # Clean up subscriber
            with self.subscriber_lock:
                if sub_id in self.subscribers:
                    self.subscribers[sub_id].active = False
                    del self.subscribers[sub_id]
    
    def _publish_event(self, lot_id: str, free: int):
        """Publish event to subscribers of this lot"""
        event_msg = f"EVENT {lot_id} {free} {datetime.now().isoformat()}"
        
        with self.subscriber_lock:
            for sub_id, subscriber in list(self.subscribers.items()):
                if subscriber.lot_id == lot_id and subscriber.active:
                    try:
                        # Try to enqueue event
                        if self.config['pubsub']['back_pressure_policy'] == 'drop_oldest':
                            # Drop oldest if queue is full
                            try:
                                subscriber.queue.put_nowait(event_msg)
                            except Full:
                                # Remove oldest and add new
                                try:
                                    subscriber.queue.get_nowait()
                                    subscriber.queue.put_nowait(event_msg)
                                    logger.warning(f"Dropped oldest event for subscriber {sub_id}")
                                except:
                                    pass
                        else:
                            # Default: block (could also disconnect)
                            subscriber.queue.put_nowait(event_msg)
                            
                    except Exception as e:
                        logger.error(f"Failed to queue event for subscriber {sub_id}: {e}")
    
    def _pubsub_notifier(self):
        """Background thread to handle pub/sub notifications"""
        # This thread monitors for changes and fan-out events
        # Most work is done in _publish_event called from update workers
        while self.running:
            time.sleep(1)
            # Could add periodic health checks here


if __name__ == '__main__':
    server = ParkingServer('config.json')
    server.start()
