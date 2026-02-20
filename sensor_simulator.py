#!/usr/bin/env python3
"""
Sensor Simulator for Campus Smart Parking Finder
Simulates parking sensors sending occupancy updates to the server.
"""

import socket
import time
import random
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SensorSimulator:
    """Simulates parking sensors sending updates"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5002,
                 lot_ids: list = None, update_rate: float = 1.0):
        self.host = host
        self.port = port
        self.lot_ids = lot_ids or ['LOT-A', 'LOT-B', 'LOT-C', 'LOT-D']
        self.update_rate = update_rate  # updates per second per lot
        self.conn: socket.socket = None
        self.running = False
    
    def connect(self):
        """Connect to sensor server"""
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.host, self.port))
        logger.info(f"Connected to sensor server at {self.host}:{self.port}")
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
        logger.info("Disconnected from sensor server")
    
    def send_update(self, lot_id: str, delta: int):
        """Send an UPDATE command"""
        if not self.conn:
            self.connect()
        
        command = f"UPDATE {lot_id} {delta}\n"
        self.conn.sendall(command.encode('utf-8'))
        
        # Wait for ACK
        response = self.conn.recv(1024).decode('utf-8').strip()
        if response != 'ACK':
            logger.warning(f"Unexpected response: {response}")
    
    def simulate_continuous(self, duration: int = 60):
        """
        Simulate continuous sensor updates.
        
        Args:
            duration: How long to run the simulation (seconds)
        """
        self.running = True
        start_time = time.time()
        update_count = 0
        
        logger.info(f"Starting sensor simulation for {duration} seconds")
        logger.info(f"Update rate: {self.update_rate} updates/sec/lot")
        
        try:
            while self.running and (time.time() - start_time) < duration:
                # For each lot, decide if we should send an update this iteration
                for lot_id in self.lot_ids:
                    # Randomly decide to send update based on rate
                    if random.random() < self.update_rate / 10:  # Check 10 times per second
                        # Random delta: +1 (car enters) or -1 (car exits)
                        delta = random.choice([-1, 1])
                        
                        try:
                            self.send_update(lot_id, delta)
                            update_count += 1
                            logger.debug(f"Sent: UPDATE {lot_id} {delta}")
                        except Exception as e:
                            logger.error(f"Error sending update: {e}")
                            raise
                
                # Sleep briefly
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        
        finally:
            elapsed = time.time() - start_time
            logger.info(f"\nSimulation complete:")
            logger.info(f"  Duration: {elapsed:.2f}s")
            logger.info(f"  Total updates: {update_count}")
            logger.info(f"  Average rate: {update_count/elapsed:.2f} updates/sec")
    
    def simulate_burst(self, lot_id: str, num_updates: int, delay: float = 0.1):
        """
        Send a burst of updates to a specific lot.
        
        Args:
            lot_id: Target lot
            num_updates: Number of updates to send
            delay: Delay between updates (seconds)
        """
        logger.info(f"Sending {num_updates} updates to {lot_id} (delay={delay}s)")
        
        for i in range(num_updates):
            delta = random.choice([-1, 1])
            try:
                self.send_update(lot_id, delta)
                logger.info(f"[{i+1}/{num_updates}] UPDATE {lot_id} {delta}")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Error sending update: {e}")
                break


def main():
    parser = argparse.ArgumentParser(description='Parking Sensor Simulator')
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=5002, help='Sensor port')
    parser.add_argument('--duration', type=int, default=60, 
                        help='Simulation duration (seconds)')
    parser.add_argument('--rate', type=float, default=1.0,
                        help='Updates per second per lot')
    parser.add_argument('--lots', nargs='+', default=['LOT-A', 'LOT-B', 'LOT-C', 'LOT-D'],
                        help='Lot IDs to simulate')
    parser.add_argument('--mode', choices=['continuous', 'burst'], default='continuous',
                        help='Simulation mode')
    parser.add_argument('--burst-lot', default='LOT-A', help='Lot for burst mode')
    parser.add_argument('--burst-count', type=int, default=10, help='Updates in burst mode')
    
    args = parser.parse_args()
    
    simulator = SensorSimulator(
        host=args.host,
        port=args.port,
        lot_ids=args.lots,
        update_rate=args.rate
    )
    
    try:
        simulator.connect()
        
        if args.mode == 'continuous':
            simulator.simulate_continuous(args.duration)
        elif args.mode == 'burst':
            simulator.simulate_burst(args.burst_lot, args.burst_count)
    
    finally:
        simulator.close()


if __name__ == '__main__':
    main()
