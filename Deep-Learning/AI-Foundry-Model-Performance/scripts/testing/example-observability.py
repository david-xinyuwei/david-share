#!/usr/bin/env python3
"""
Example script showing how to integrate Application Insights observability
This is a reference implementation for adding observability to existing test scripts
"""

import os
import sys
import time
from pathlib import Path

# Add parent directory to path to import observability module
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

try:
    from utils.observability import init_observability
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    print("Warning: Observability module not available")
    OBSERVABILITY_AVAILABLE = False

def main():
    """Example of using observability in performance testing"""
    
    # Initialize observability (reads APPINSIGHTS_CONNECTION_STRING from environment)
    if OBSERVABILITY_AVAILABLE:
        obs = init_observability()
        correlation_id = obs.get_correlation_id()
        print(f"Observability initialized with correlation ID: {correlation_id}")
    else:
        obs = None
        print("Running without observability")
    
    # Example: Log test start
    if obs:
        obs.log_info("Performance test started", 
                    model="example-model",
                    test_type="stress_test")
    
    # Simulate some work
    print("Running performance test...")
    start_time = time.time()
    
    # Simulate API calls
    for i in range(5):
        request_start = time.time()
        
        # Simulate work
        time.sleep(0.5)
        
        request_duration = (time.time() - request_start) * 1000
        
        # Track the request
        if obs:
            obs.track_request(
                name=f"model_inference_{i}",
                duration_ms=request_duration,
                success=True,
                request_number=i+1,
                model="example-model"
            )
        
        print(f"Request {i+1} completed in {request_duration:.2f}ms")
    
    # Calculate total metrics
    total_duration = time.time() - start_time
    avg_latency = (total_duration / 5) * 1000
    
    # Track custom metrics
    if obs:
        obs.track_metric("total_test_duration", total_duration)
        obs.track_metric("average_latency_ms", avg_latency)
        obs.track_metric("requests_per_second", 5 / total_duration)
        
        obs.log_info("Performance test completed",
                    total_duration=total_duration,
                    avg_latency_ms=avg_latency,
                    total_requests=5)
    
    print(f"\nTest Summary:")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Average Latency: {avg_latency:.2f}ms")
    print(f"Requests/sec: {5/total_duration:.2f}")
    
    if obs:
        print(f"\nCorrelation ID: {correlation_id}")
        print("View logs in Application Insights using this correlation ID")

def example_with_error_handling():
    """Example showing error logging"""
    
    if not OBSERVABILITY_AVAILABLE:
        print("Observability not available, skipping error example")
        return
    
    obs = init_observability()
    
    try:
        obs.log_info("Attempting risky operation")
        
        # Simulate an error
        result = 10 / 0
        
    except Exception as e:
        # Log the exception with full context
        obs.log_exception(
            "Operation failed",
            exception=e,
            operation="division",
            additional_context="example error handling"
        )
        
        print(f"Error logged to Application Insights")
    
    finally:
        obs.log_info("Operation cleanup completed")

if __name__ == "__main__":
    print("=" * 60)
    print("Application Insights Observability Example")
    print("=" * 60)
    print()
    
    # Check if connection string is configured
    connection_string = os.getenv('APPINSIGHTS_CONNECTION_STRING')
    if connection_string:
        print(f"✓ Application Insights configured")
    else:
        print("⚠ APPINSIGHTS_CONNECTION_STRING not set")
        print("  Logs will only appear in console")
    
    print()
    
    # Run examples
    main()
    
    print("\n" + "=" * 60)
    print("Error Handling Example")
    print("=" * 60)
    print()
    
    example_with_error_handling()
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
