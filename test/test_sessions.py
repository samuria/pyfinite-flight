#!/usr/bin/env python3
"""
Test script to monitor active Infinite Flight sessions and their status.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import InfiniteFlightClient


async def monitor_sessions(duration: int = 30):
    """Monitor Infinite Flight sessions for a specified duration."""
    print("=" * 60)
    print("Infinite Flight Session Monitor")
    print("=" * 60)
    print(f"Monitoring for {duration} seconds...")
    print()
    
    # Track discovered sessions
    sessions = {}
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < duration:
        # Create client for discovery
        client = InfiniteFlightClient()
        
        # Discover devices (short timeout for continuous monitoring)
        devices = await client.discover_devices(timeout=1.0)
        
        # Update session information
        for device in devices:
            device_id = device.get('deviceId')
            if device_id:
                # Track when we first saw this session
                if device_id not in sessions:
                    sessions[device_id] = {
                        'first_seen': datetime.now(),
                        'last_seen': datetime.now(),
                        'device': device
                    }
                else:
                    sessions[device_id]['last_seen'] = datetime.now()
                    sessions[device_id]['device'] = device  # Update with latest info
        
        # Clear screen and display current sessions
        print("\033[2J\033[H")  # Clear screen and move cursor to top
        print("=" * 60)
        print(f"Active Infinite Flight Sessions - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        print()
        
        if not sessions:
            print("No active sessions found.")
        else:
            for session_id, session_data in sessions.items():
                device = session_data['device']
                duration_sec = (session_data['last_seen'] - session_data['first_seen']).total_seconds()
                
                print(f"Session: {device.get('deviceName', 'Unknown')}")
                print(f"  State:     {device.get('state', 'Unknown')}")
                print(f"  Aircraft:  {device.get('aircraft', 'N/A')}")
                print(f"  Duration:  {int(duration_sec)}s")
                print(f"  Device ID: {session_id[:8]}...")
                print()
        
        # Small delay before next scan
        await asyncio.sleep(1)
    
    print("\nMonitoring complete.")
    print(f"Total unique sessions detected: {len(sessions)}")


async def test_connection_stability():
    """Test connection stability with multiple connect/disconnect cycles."""
    print("=" * 60)
    print("Connection Stability Test")
    print("=" * 60)
    print()
    
    # First discover a device
    client = InfiniteFlightClient()
    devices = await client.discover_devices(timeout=5.0)
    
    if not devices:
        print("No devices found for testing!")
        return
    
    device = devices[0]
    print(f"Testing with: {device.get('deviceName')} - {device.get('aircraft')}")
    print()
    
    # Test multiple connections
    test_count = 5
    successful = 0
    
    for i in range(test_count):
        print(f"Connection test {i+1}/{test_count}...", end="", flush=True)
        
        test_client = InfiniteFlightClient(
            host=device.get('preferred_ip', device.get('address')),
            port=device.get('port', 10112)
        )
        
        if await test_client.connect():
            successful += 1
            print(" ✓ Connected", end="", flush=True)
            
            # Small delay to simulate some work
            await asyncio.sleep(0.5)
            
            await test_client.disconnect()
            print(" → Disconnected")
        else:
            print(" ✗ Failed")
        
        # Small delay between tests
        await asyncio.sleep(0.5)
    
    print()
    print(f"Results: {successful}/{test_count} successful connections")
    print(f"Success rate: {(successful/test_count)*100:.1f}%")


async def main():
    """Main function."""
    print("Select test to run:")
    print("1. Monitor active sessions (30 seconds)")
    print("2. Test connection stability")
    print("3. Run both tests")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            await monitor_sessions()
        elif choice == '2':
            await test_connection_stability()
        elif choice == '3':
            await monitor_sessions()
            print("\n" + "="*60 + "\n")
            await test_connection_stability()
        else:
            print("Invalid choice!")
            
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())