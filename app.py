#!/usr/bin/env python3
"""
Flask web application for Infinite Flight client with WebSocket support.
"""

import asyncio
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
from typing import Optional

from src import InfiniteFlightClient

app = Flask(__name__)
import os  # Added for environment variables

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "pyfinite-flight-secret")

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global client instance
current_client: Optional[InfiniteFlightClient] = None
discovery_task: Optional[asyncio.Task] = None
event_loop: Optional[asyncio.AbstractEventLoop] = None
location_update_task: Optional[threading.Thread] = None
location_update_active = False


def run_async(coro):
    """Run an async coroutine in a thread-safe way."""
    global event_loop
    if event_loop is None:
        event_loop = asyncio.new_event_loop()
        threading.Thread(target=event_loop.run_forever, daemon=True).start()

    future = asyncio.run_coroutine_threadsafe(coro, event_loop)
    return future.result()


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    """Handle client connection."""
    print("Client connected")
    emit("connected", {"status": "Connected to server"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection."""
    print("Client disconnected")
    # Stop location updates
    stop_location_updates()
    # Disconnect from Infinite Flight if connected
    global current_client
    if current_client and current_client.is_connected:
        run_async(current_client.disconnect())
        current_client = None


@socketio.on("start_discovery")
def handle_start_discovery():
    """Start device discovery."""
    print("Starting device discovery...")
    emit("discovery_started", {"message": "Scanning for Infinite Flight devices..."})

    async def discover():
        client = InfiniteFlightClient()
        devices = await client.discover_devices(timeout=5.0)
        return devices

    try:
        devices = run_async(discover())

        # Emit each device as it's found
        for i, device in enumerate(devices):
            device_info = {
                "id": i,
                "deviceName": device.get("deviceName", "Unknown"),
                "deviceId": device.get("deviceId", "Unknown"),
                "state": device.get("state", "Unknown"),
                "aircraft": device.get("aircraft", "N/A"),
                "livery": device.get("livery", "N/A"),
                "version": device.get("version", "Unknown"),
                "address": device.get("address", "Unknown"),
                "preferredIp": device.get(
                    "preferred_ip", device.get("address", "Unknown")
                ),
                "port": device.get("port", 10112),
                "addresses": device.get("addresses", []),
            }
            socketio.emit("device_found", device_info)

        # Emit discovery complete
        socketio.emit(
            "discovery_complete",
            {
                "message": f"Discovery complete. Found {len(devices)} device(s).",
                "count": len(devices),
            },
        )

    except Exception as e:
        socketio.emit("discovery_error", {"error": str(e)})


@socketio.on("connect_to_device")
def handle_connect_to_device(data):
    """Connect to a specific device."""
    global current_client

    host = data.get("host")
    port = data.get("port", 10112)

    print(f"Attempting to connect to {host}:{port}...")
    emit(
        "connection_status",
        {"status": "connecting", "message": f"Connecting to {host}:{port}..."},
    )

    try:
        # Disconnect existing client if any
        if current_client and current_client.is_connected:
            run_async(current_client.disconnect())

        # Create new client
        current_client = InfiniteFlightClient(host=host, port=port)

        # Connect
        connected = run_async(current_client.connect())

        if connected:
            # Get some basic info
            available_states = current_client.get_available_states()

            emit(
                "connection_status",
                {
                    "status": "connected",
                    "message": f"Successfully connected to Infinite Flight!",
                    "host": host,
                    "port": port,
                    "availableStates": len(available_states),
                },
            )

            # Send initial state data
            emit(
                "manifest_loaded",
                {
                    "stateCount": len(available_states),
                    "categories": _categorize_states(available_states),
                },
            )

            # Start location updates
            start_location_updates()
        else:
            error_msg = current_client.last_error or "Connection failed"
            emit(
                "connection_status",
                {"status": "failed", "message": f"Connection failed: {error_msg}"},
            )
            current_client = None

    except Exception as e:
        emit("connection_status", {"status": "error", "message": f"Error: {str(e)}"})
        current_client = None


@socketio.on("disconnect_from_device")
def handle_disconnect_from_device():
    """Disconnect from the current device."""
    global current_client

    # Stop location updates
    stop_location_updates()

    if current_client and current_client.is_connected:
        try:
            run_async(current_client.disconnect())
            emit(
                "connection_status",
                {
                    "status": "disconnected",
                    "message": "Disconnected from Infinite Flight",
                },
            )
        except Exception as e:
            emit(
                "connection_status",
                {"status": "error", "message": f"Error disconnecting: {str(e)}"},
            )
        finally:
            current_client = None
    else:
        emit(
            "connection_status", {"status": "disconnected", "message": "Not connected"}
        )


@socketio.on("get_connection_status")
def handle_get_connection_status():
    """Get current connection status."""
    global current_client

    if current_client and current_client.is_connected:
        emit(
            "connection_status",
            {
                "status": "connected",
                "host": current_client.host,
                "port": current_client.port,
            },
        )
    else:
        emit("connection_status", {"status": "disconnected"})


@socketio.on("debug_states")
def handle_debug_states():
    """Debug endpoint to check specific states."""
    global current_client

    if not current_client or not current_client.is_connected:
        emit("debug_response", {"error": "Not connected"})
        return

    debug_states = [
        "aircraft/0/heading_true",
        "aircraft/0/heading_magnetic",
        "aircraft/0/heading",
        "aircraft/0/indicated_airspeed",
        "aircraft/0/airspeed_indicated",
        "aircraft/0/ias",
        "aircraft/0/calibrated_airspeed",
        "aircraft/0/true_airspeed",
        "aircraft/0/groundspeed",
        "aircraft/0/mach",
        "aircraft/0/airspeed",
    ]

    results = {}
    for state_name in debug_states:
        try:
            value = run_async(current_client.get_state(state_name))
            # Get the raw value and data type
            state_id = current_client._state_map.get(state_name)
            if state_id:
                data_type = current_client._manifest[state_id][1]
                results[state_name] = {
                    "value": str(value),
                    "raw": value,
                    "type": data_type.name,
                }
            else:
                results[state_name] = str(value)
        except Exception as e:
            results[state_name] = f"NOT FOUND: {str(e)}"

    emit("debug_response", {"states": results})


@socketio.on("get_category_states")
def handle_get_category_states(data):
    """Get all states for a specific category."""
    global current_client

    if not current_client or not current_client.is_connected:
        emit("category_states_error", {"error": "Not connected to Infinite Flight"})
        return

    category = data.get("category")
    if not category:
        emit("category_states_error", {"error": "No category specified"})
        return

    try:
        # Get all states for this category
        all_states = current_client.get_available_states()
        category_states = []

        for state_name in all_states:
            if state_name.startswith(f"{category}/"):
                # Try to get the current value
                try:
                    value = run_async(current_client.get_state(state_name))
                    formatted_value = _format_state_value(value, state_name)
                    state_type = _get_state_type(state_name)
                except Exception as e:
                    formatted_value = "N/A"
                    state_type = "Unknown"

                category_states.append(
                    {
                        "name": state_name,
                        "displayName": state_name.replace(f"{category}/", "").replace(
                            "/", " > "
                        ),
                        "value": formatted_value,
                        "type": state_type,
                        "category": category,
                    }
                )

        # Sort states by name
        category_states.sort(key=lambda x: x["name"])

        emit(
            "category_states",
            {
                "category": category,
                "states": category_states,
                "count": len(category_states),
            },
        )

    except Exception as e:
        emit("category_states_error", {"error": str(e)})


@socketio.on("set_aircraft_state")
def handle_set_aircraft_state(data):
    """Set a specific aircraft state."""
    global current_client

    if not current_client or not current_client.is_connected:
        emit(
            "set_state_response",
            {"success": False, "error": "Not connected to Infinite Flight"},
        )
        return

    state_name = data.get("state_name")
    value = data.get("value")

    if not state_name:
        emit(
            "set_state_response", {"success": False, "error": "state_name not provided"}
        )
        return

    # Value can be None for some types (e.g. if we were to allow setting booleans to false explicitly)
    # but for now, we expect a value.
    if value is None:
        emit("set_state_response", {"success": False, "error": "value not provided"})
        return

    try:
        print(f"Attempting to set state: {state_name} to {value}")
        # The client's set_state method is async, so we use run_async
        run_async(current_client.set_state(state_name, value))
        emit(
            "set_state_response",
            {"success": True, "state_name": state_name, "value": value},
        )
        print(f"Successfully set state: {state_name} to {value}")

        # Optionally, re-fetch the state to confirm and send update
        # current_value = run_async(current_client.get_state(state_name))
        # emit("state_update", {"state_name": state_name, "value": current_value})

    except ValueError as ve:  # Catch specific errors from client.set_state
        print(f"ValueError setting state {state_name}: {ve}")
        emit("set_state_response", {"success": False, "error": str(ve)})
    except (
        NotImplementedError
    ) as nie:  # Catch specific errors from client._send_request
        print(f"NotImplementedError setting state {state_name}: {nie}")
        emit("set_state_response", {"success": False, "error": str(nie)})
    except Exception as e:
        print(f"Error setting state {state_name}: {e}")
        emit("set_state_response", {"success": False, "error": str(e)})


def _categorize_states(states):
    """Categorize states by their prefix."""
    categories = {}
    for state in states:
        parts = state.split("/")
        category = parts[0] if parts else "other"
        if category not in categories:
            categories[category] = 0
        categories[category] += 1
    return categories


def _format_state_value(value, state_name):
    """Format a state value for display."""
    if value is None:
        return "N/A"

    # Boolean values
    if isinstance(value, bool):
        return "Yes" if value else "No"

    # Float values - format based on state name
    if isinstance(value, float):
        if "latitude" in state_name or "longitude" in state_name:
            return f"{value:.6f}"
        elif "altitude" in state_name or "speed" in state_name:
            return f"{value:.1f}"
        elif "heading" in state_name or "pitch" in state_name or "bank" in state_name:
            return f"{value:.1f}°"
        else:
            return f"{value:.2f}"

    # String values
    if isinstance(value, str):
        return value if value else "(empty)"

    # Default
    return str(value)


def _get_state_type(state_name):
    """Get a display type for a state based on its name."""
    if "latitude" in state_name or "longitude" in state_name:
        return "Position"
    elif "altitude" in state_name:
        return "Altitude"
    elif "speed" in state_name:
        return "Speed"
    elif "heading" in state_name or "pitch" in state_name or "bank" in state_name:
        return "Angle"
    elif "state" in state_name:
        return "Status"
    else:
        return "Value"


def start_location_updates():
    """Start sending location updates to all connected clients."""
    global location_update_task, location_update_active

    if location_update_active:
        return  # Already running

    location_update_active = True
    location_update_task = threading.Thread(target=_location_update_loop, daemon=True)
    location_update_task.start()
    print("Started location updates")


def stop_location_updates():
    """Stop sending location updates."""
    global location_update_active

    location_update_active = False
    print("Stopped location updates")


def _location_update_loop():
    """Background thread that sends location updates."""
    global current_client, location_update_active

    while location_update_active:
        if current_client and current_client.is_connected:
            try:
                # Get location data
                location_data = {}

                # Position
                try:
                    lat = run_async(current_client.get_state("aircraft/0/latitude"))
                    location_data["latitude"] = f"{lat:.6f}"
                except:
                    location_data["latitude"] = "N/A"

                try:
                    lon = run_async(current_client.get_state("aircraft/0/longitude"))
                    location_data["longitude"] = f"{lon:.6f}"
                except:
                    location_data["longitude"] = "N/A"

                # Altitude
                try:
                    alt_msl = run_async(
                        current_client.get_state("aircraft/0/altitude_msl")
                    )
                    location_data["altitude_msl"] = f"{alt_msl:,.0f} ft"
                except:
                    location_data["altitude_msl"] = "N/A"

                try:
                    alt_agl = run_async(
                        current_client.get_state("aircraft/0/altitude_agl")
                    )
                    location_data["altitude_agl"] = f"{alt_agl:,.0f} ft"
                except:
                    location_data["altitude_agl"] = "N/A"

                # Heading - try true heading first, then magnetic
                heading_found = False
                try:
                    heading = run_async(
                        current_client.get_state("aircraft/0/heading_true")
                    )
                    if heading is not None:
                        # Convert from radians to degrees
                        heading = heading * 180 / 3.14159265359
                        location_data["heading"] = f"{heading:.0f}°T"
                        heading_found = True
                except:
                    pass

                if not heading_found:
                    try:
                        heading = run_async(
                            current_client.get_state("aircraft/0/heading_magnetic")
                        )
                        if heading is not None:
                            # Convert from radians to degrees
                            heading = heading * 180 / 3.14159265359
                            location_data["heading"] = f"{heading:.0f}°M"
                    except:
                        location_data["heading"] = "N/A"

                # Speed - use indicated_airspeed and convert from m/s to knots
                try:
                    speed = run_async(
                        current_client.get_state("aircraft/0/indicated_airspeed")
                    )
                    if speed is not None:
                        # Convert from m/s to knots
                        speed_knots = speed * 1.94384
                        location_data["speed"] = f"{speed_knots:.0f} kts IAS"
                    else:
                        # Fallback to groundspeed
                        try:
                            speed = run_async(
                                current_client.get_state("aircraft/0/groundspeed")
                            )
                            if speed is not None:
                                # Also in m/s
                                speed_knots = speed * 1.94384
                                location_data["speed"] = f"{speed_knots:.0f} kts GS"
                            else:
                                location_data["speed"] = "N/A"
                        except:
                            location_data["speed"] = "N/A"
                except Exception as e:
                    location_data["speed"] = "N/A"

                # Emit location update to all connected clients
                socketio.emit("location_update", location_data)

            except Exception as e:
                print(f"Error getting location data: {e}")

        # Wait before next update (2 Hz update rate)
        threading.Event().wait(0.5)


if __name__ == "__main__":
    print("Starting Infinite Flight Web Interface...")
    print("Open http://localhost:5000 in your browser")
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
