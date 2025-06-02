#!/usr/bin/env python3
"""
Test script to connect to Infinite Flight and retrieve current aircraft states.
"""

import asyncio
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import InfiniteFlightClient


async def test_get_states():
    """Test retrieving states from Infinite Flight."""
    print("=" * 60)
    print("Infinite Flight State Retrieval Test")
    print("=" * 60)
    print()
    
    # Discover devices
    print("Discovering devices...")
    client = InfiniteFlightClient()
    devices = await client.discover_devices(timeout=5.0)
    
    if not devices:
        print("No devices found!")
        return
    
    device = devices[0]
    print(f"Found: {device.get('deviceName')} - {device.get('aircraft')}")
    
    # Connect
    host = device.get('preferred_ip', device.get('address'))
    port = device.get('port', 10112)
    print(f"\nConnecting to {host}:{port}...")
    
    client = InfiniteFlightClient(host=host, port=port)
    
    if not await client.connect():
        print(f"Connection failed! Error: {client.last_error}")
        return
    
    print("Connected successfully!")
    
    # Get some basic states
    print("\n" + "-" * 40)
    print("BASIC AIRCRAFT STATES")
    print("-" * 40)
    
    basic_states = [
        # Position
        ("aircraft/0/latitude", "Latitude"),
        ("aircraft/0/longitude", "Longitude"),
        ("aircraft/0/altitude_msl", "Altitude MSL"),
        ("aircraft/0/altitude_agl", "Altitude AGL"),
        
        # Attitude
        ("aircraft/0/heading_magnetic", "Heading"),
        ("aircraft/0/pitch", "Pitch"),
        ("aircraft/0/bank", "Bank"),
        
        # Speed
        ("aircraft/0/indicated_airspeed", "IAS"),
        ("aircraft/0/true_airspeed", "TAS"),
        ("aircraft/0/groundspeed", "Ground Speed"),
        ("aircraft/0/vertical_speed", "Vertical Speed"),
        ("aircraft/0/mach", "Mach"),
        
        # Aircraft info
        ("aircraft/0/livery", "Livery"),
        ("aircraft/0/is_on_ground", "On Ground"),
        
        # Systems
        ("aircraft/0/systems/landing_gear/state", "Landing Gear"),
        ("aircraft/0/systems/autopilot/state", "Autopilot"),
    ]
    
    for state_name, display_name in basic_states:
        try:
            value = await client.get_state(state_name)
            
            # Format value based on type
            if isinstance(value, float):
                if "latitude" in state_name or "longitude" in state_name:
                    formatted_value = f"{value:.6f}"
                elif "altitude" in state_name or "speed" in state_name:
                    formatted_value = f"{value:.1f}"
                else:
                    formatted_value = f"{value:.2f}"
            elif isinstance(value, bool):
                formatted_value = "Yes" if value else "No"
            else:
                formatted_value = str(value)
            
            print(f"{display_name:<20} {formatted_value:>15}")
        except Exception as e:
            print(f"{display_name:<20} {'N/A':>15} (Error: {str(e)[:30]})")
    
    # Show available states count
    available_states = client.get_available_states()
    print(f"\nTotal available states: {len(available_states)}")
    
    # Ask if user wants to see all states
    show_all = input("\nShow all available states? (y/n): ").lower().strip() == 'y'
    
    if show_all:
        print("\n" + "-" * 60)
        print("ALL AVAILABLE STATES")
        print("-" * 60)
        
        # Group by category
        categories = {}
        for state in available_states:
            parts = state.split('/')
            category = parts[0] if parts else "other"
            if category not in categories:
                categories[category] = []
            categories[category].append(state)
        
        for category, states in sorted(categories.items()):
            print(f"\n[{category.upper()}] ({len(states)} states)")
            for state in sorted(states)[:10]:  # Show first 10
                print(f"  {state}")
            if len(states) > 10:
                print(f"  ... and {len(states) - 10} more")
    
    # Disconnect
    await client.disconnect()
    print("\nDisconnected.")


async def test_live_monitoring():
    """Test live monitoring of key aircraft states."""
    print("=" * 60)
    print("Infinite Flight Live State Monitor")
    print("=" * 60)
    print()
    
    # Discover and connect
    client = InfiniteFlightClient()
    devices = await client.discover_devices(timeout=5.0)
    
    if not devices:
        print("No devices found!")
        return
    
    device = devices[0]
    print(f"Connecting to {device.get('deviceName')}...")
    
    client = InfiniteFlightClient(
        host=device.get('preferred_ip', device.get('address')),
        port=device.get('port', 10112)
    )
    
    if not await client.connect():
        print(f"Connection failed! Error: {client.last_error}")
        return
    
    print("Connected! Press Ctrl+C to stop monitoring.\n")
    
    # Monitor key states
    monitor_states = [
        ("aircraft/0/altitude_msl", "ALT", "ft"),
        ("aircraft/0/indicated_airspeed", "IAS", "kts"),
        ("aircraft/0/vertical_speed", "VS", "fpm"),
        ("aircraft/0/heading_magnetic", "HDG", "°"),
        ("aircraft/0/pitch", "PITCH", "°"),
        ("aircraft/0/bank", "BANK", "°"),
    ]
    
    try:
        while True:
            # Clear line and print values
            values = []
            for state_name, label, unit in monitor_states:
                try:
                    value = await client.get_state(state_name)
                    if isinstance(value, float):
                        values.append(f"{label}: {value:.1f}{unit}")
                    else:
                        values.append(f"{label}: {value}{unit}")
                except:
                    values.append(f"{label}: N/A")
            
            print(f"\r{' | '.join(values)}", end="", flush=True)
            await asyncio.sleep(0.5)  # Update every 500ms
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
    
    await client.disconnect()


async def main():
    """Main function."""
    print("Select test to run:")
    print("1. Get current aircraft states")
    print("2. Live state monitoring")
    
    try:
        choice = input("\nEnter choice (1-2): ").strip()
        
        if choice == '1':
            await test_get_states()
        elif choice == '2':
            await test_live_monitoring()
        else:
            print("Invalid choice!")
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())