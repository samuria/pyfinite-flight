#!/usr/bin/env python3
"""
Test script to discover Infinite Flight devices and display current session information.
"""

import asyncio
import json
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import InfiniteFlightClient


async def test_discovery():
    """Test device discovery and display session information."""
    print("=" * 60)
    print("Infinite Flight Device Discovery Test")
    print("=" * 60)
    print()
    
    # Create client
    client = InfiniteFlightClient()
    
    # Discover devices
    print("Scanning for Infinite Flight devices (5 seconds)...")
    print("-" * 40)
    
    devices = await client.discover_devices(timeout=5.0)
    
    if not devices:
        print("No devices found!")
        print("\nMake sure:")
        print("- Infinite Flight is running")
        print("- Connect API is enabled in IF settings")
        print("- Both devices are on the same network")
        return
    
    print(f"\nFound {len(devices)} device(s):\n")
    
    # Display information for each device
    for i, device in enumerate(devices, 1):
        print(f"Device #{i}")
        print("-" * 40)
        print(f"Device Name:    {device.get('deviceName', 'Unknown')}")
        print(f"Device ID:      {device.get('deviceId', 'Unknown')}")
        print(f"State:          {device.get('state', 'Unknown')}")
        print(f"Aircraft:       {device.get('aircraft', 'N/A')}")
        print(f"Livery:         {device.get('livery', 'N/A')}")
        print(f"Version:        {device.get('version', 'Unknown')}")
        print(f"IP Address:     {device.get('address', 'Unknown')}")
        print(f"Preferred IP:   {device.get('preferred_ip', device.get('address', 'Unknown'))}")
        print(f"Port:           {device.get('port', 'Unknown')}")
        
        # Show all available IPs
        if 'addresses' in device and device['addresses']:
            print(f"All IPs:        {', '.join(device['addresses'])}")
        
        print()
        
        # Test connection to first device
        if i == 1:
            print("Testing connection to first device...")
            host = device.get('preferred_ip', device.get('address'))
            port = device.get('port', 10112)
            print(f"Attempting connection to {host}:{port}")
            
            test_client = InfiniteFlightClient(host=host, port=port)
            
            if await test_client.connect():
                print("✓ Connection successful!")
                await test_client.disconnect()
                print("✓ Disconnected")
            else:
                print("✗ Connection failed!")
                if hasattr(test_client, 'last_error') and test_client.last_error:
                    print(f"  Error: {test_client.last_error}")
                print("  Make sure Infinite Flight Connect API is enabled")
                print("  and both devices are on the same network")
            print()
    
    # Save discovery data to file
    save_data = input("Save discovery data to JSON file? (y/n): ").lower().strip() == 'y'
    if save_data:
        filename = "discovered_devices.json"
        with open(filename, 'w') as f:
            json.dump(devices, f, indent=2)
        print(f"\nDiscovery data saved to {filename}")


async def main():
    """Main function."""
    try:
        await test_discovery()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())