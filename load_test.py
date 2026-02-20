#!/usr/bin/env python3
"""
Load Testing Script for Campus Smart Parking Finder
Tests RPC throughput and latency under various loads.
"""

import time
import threading
import statistics
import argparse
import json
from typing import List, Dict
from rpc_client import RPCClient, TimeoutError


class LoadTestResults:
    """Container for load test results"""
    def __init__(self):
        self.latencies: List[float] = []
        self.successes = 0
        self.failures = 0
        self.timeouts = 0
        self.start_time = None
        self.end_time = None
        self.lock = threading.Lock()
    
    def record_success(self, latency: float):
        with self.lock:
            self.latencies.append(latency)
            self.successes += 1
    
    def record_failure(self):
        with self.lock:
            self.failures += 1
    
    def record_timeout(self):
        with self.lock:
            self.timeouts += 1
    
    def get_summary(self) -> Dict:
        """Calculate summary statistics"""
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        total_requests = self.successes + self.failures + self.timeouts
        
        summary = {
            'duration_seconds': duration,
            'total_requests': total_requests,
            'successful_requests': self.successes,
            'failed_requests': self.failures,
            'timeout_requests': self.timeouts,
            'throughput_req_per_sec': total_requests / duration if duration > 0 else 0,
        }
        
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            summary.update({
                'latency_min_ms': min(self.latencies) * 1000,
                'latency_max_ms': max(self.latencies) * 1000,
                'latency_mean_ms': statistics.mean(self.latencies) * 1000,
                'latency_median_ms': statistics.median(self.latencies) * 1000,
                'latency_p95_ms': sorted_latencies[int(len(sorted_latencies) * 0.95)] * 1000 if len(sorted_latencies) > 0 else 0,
                'latency_p99_ms': sorted_latencies[int(len(sorted_latencies) * 0.99)] * 1000 if len(sorted_latencies) > 0 else 0,
            })
        
        return summary


class LoadTester:
    """Load tester for parking server"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5001, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.lot_ids = ['LOT-A', 'LOT-B', 'LOT-C', 'LOT-D']
    
    def worker_thread(self, worker_id: int, duration: int, operation: str, results: LoadTestResults):
        """Worker thread that executes operations"""
        client = RPCClient(host=self.host, port=self.port, timeout=self.timeout)
        
        try:
            client.connect()
            end_time = time.time() + duration
            request_count = 0
            
            while time.time() < end_time:
                try:
                    start = time.time()
                    
                    if operation == 'avail':
                        # Random availability check
                        import random
                        lot_id = random.choice(self.lot_ids)
                        client.get_availability(lot_id)
                    
                    elif operation == 'reserve':
                        # Reserve with unique plate
                        import random
                        lot_id = random.choice(self.lot_ids)
                        plate = f"W{worker_id}-{request_count}"
                        client.reserve(lot_id, plate)
                    
                    elif operation == 'mixed':
                        # Mix of operations
                        import random
                        op = random.choice(['avail', 'reserve', 'list'])
                        
                        if op == 'avail':
                            lot_id = random.choice(self.lot_ids)
                            client.get_availability(lot_id)
                        elif op == 'reserve':
                            lot_id = random.choice(self.lot_ids)
                            plate = f"W{worker_id}-{request_count}"
                            success = client.reserve(lot_id, plate)
                            # Cancel if successful to keep state clean
                            if success:
                                client.cancel(lot_id, plate)
                        else:  # list
                            client.get_lots()
                    
                    latency = time.time() - start
                    results.record_success(latency)
                    request_count += 1
                
                except TimeoutError:
                    results.record_timeout()
                except Exception as e:
                    results.record_failure()
                    print(f"Worker {worker_id} error: {e}")
        
        finally:
            client.close()
    
    def run_load_test(self, num_workers: int, duration: int, operation: str = 'avail') -> LoadTestResults:
        """
        Run load test with specified parameters.
        
        Args:
            num_workers: Number of concurrent worker threads
            duration: Test duration in seconds
            operation: Type of operation ('avail', 'reserve', 'mixed')
        
        Returns:
            LoadTestResults object
        """
        print(f"\n{'='*60}")
        print(f"Load Test: {num_workers} workers, {duration}s duration, operation={operation}")
        print(f"{'='*60}")
        
        results = LoadTestResults()
        results.start_time = time.time()
        
        # Start worker threads
        workers = []
        for i in range(num_workers):
            worker = threading.Thread(
                target=self.worker_thread,
                args=(i, duration, operation, results),
                daemon=True
            )
            workers.append(worker)
            worker.start()
        
        # Wait for all workers to complete
        for worker in workers:
            worker.join()
        
        results.end_time = time.time()
        
        return results
    
    def run_baseline_tests(self):
        """Run baseline RPC tests with different worker counts"""
        print("\n" + "="*60)
        print("BASELINE RPC TESTS")
        print("="*60)
        
        worker_counts = [1, 4, 8, 16]
        duration = 30
        
        all_results = {}
        
        # Test AVAIL operations
        print("\n--- Testing AVAIL operations ---")
        for num_workers in worker_counts:
            results = self.run_load_test(num_workers, duration, 'avail')
            summary = results.get_summary()
            all_results[f'avail_{num_workers}w'] = summary
            self.print_summary(summary)
            time.sleep(2)  # Brief pause between tests
        
        # Test RESERVE operations
        print("\n--- Testing RESERVE operations ---")
        for num_workers in worker_counts:
            results = self.run_load_test(num_workers, duration, 'reserve')
            summary = results.get_summary()
            all_results[f'reserve_{num_workers}w'] = summary
            self.print_summary(summary)
            time.sleep(2)
        
        # Save results
        with open('load_test_results.json', 'w') as f:
            json.dump(all_results, f, indent=2)
        
        print(f"\nResults saved to load_test_results.json")
        
        return all_results
    
    def print_summary(self, summary: Dict):
        """Print test summary"""
        print(f"\nResults:")
        print(f"  Duration: {summary['duration_seconds']:.2f}s")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Successful: {summary['successful_requests']}")
        print(f"  Failed: {summary['failed_requests']}")
        print(f"  Timeouts: {summary['timeout_requests']}")
        print(f"  Throughput: {summary['throughput_req_per_sec']:.2f} req/s")
        
        if 'latency_median_ms' in summary:
            print(f"\nLatency:")
            print(f"  Min: {summary['latency_min_ms']:.2f}ms")
            print(f"  Median: {summary['latency_median_ms']:.2f}ms")
            print(f"  Mean: {summary['latency_mean_ms']:.2f}ms")
            print(f"  P95: {summary['latency_p95_ms']:.2f}ms")
            print(f"  P99: {summary['latency_p99_ms']:.2f}ms")
            print(f"  Max: {summary['latency_max_ms']:.2f}ms")


def main():
    parser = argparse.ArgumentParser(description='Load Testing for Parking Server')
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=5001, help='RPC port')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--duration', type=int, default=30, help='Test duration (seconds)')
    parser.add_argument('--operation', choices=['avail', 'reserve', 'mixed'], default='avail',
                        help='Type of operation to test')
    parser.add_argument('--baseline', action='store_true',
                        help='Run full baseline test suite')
    
    args = parser.parse_args()
    
    tester = LoadTester(host=args.host, port=args.port)
    
    if args.baseline:
        tester.run_baseline_tests()
    else:
        results = tester.run_load_test(args.workers, args.duration, args.operation)
        summary = results.get_summary()
        tester.print_summary(summary)
        
        # Save single test result
        with open('load_test_result.json', 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to load_test_result.json")


if __name__ == '__main__':
    main()
