import asyncio
import json
import socket
import struct
from typing import Dict, List, Optional, Any, Tuple
from enum import IntEnum


class DataType(IntEnum):
    """Data types used in the Connect API v2."""

    BOOLEAN = 0
    INTEGER = 1
    FLOAT = 2
    DOUBLE = 3
    STRING = 4
    LONG = 5


class InfiniteFlightClient:
    """Minimal client for discovering and connecting to Infinite Flight sessions."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """Initialize the client.

        Args:
            host: IP address of Infinite Flight device.
            port: TCP port for connection (default: 10112 for API v2).
        """
        self.host = host
        self.port = port or 10112  # Default to API v2 port
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self.last_error: Optional[str] = None
        self._manifest: Dict[int, Tuple[str, DataType]] = {}  # id -> (name, type)
        self._state_map: Dict[str, int] = {}  # name -> id

    async def discover_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Listen for Infinite Flight UDP broadcasts on port 15000.

        Returns device information including:
        - State (e.g., "Playing")
        - Port (TCP port for connection)
        - DeviceID
        - Aircraft type
        - Version
        - DeviceName
        - IP Addresses
        - Livery

        Args:
            timeout: How long to listen for broadcasts in seconds

        Returns:
            List of discovered devices with their connection info
        """
        devices = []

        # Create UDP socket for listening to broadcasts
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 15000))
        sock.settimeout(timeout)

        start_time = asyncio.get_event_loop().time()

        while True:
            try:
                data, addr = sock.recvfrom(4096)

                # Parse JSON data
                device_info = json.loads(data.decode("utf-8"))
                device_info["address"] = addr[0]

                # Extract preferred IP if available
                # Filter out localhost and IPv6 addresses to find the best IP
                if "addresses" in device_info and device_info["addresses"]:
                    valid_ips = []
                    source_ip = addr[0]  # The IP that sent the broadcast

                    for ip in device_info["addresses"]:
                        # Skip localhost, IPv6, and link-local addresses
                        if (
                            not ip.startswith("127.")
                            and not ":" in ip
                            and not ip.startswith("169.254.")
                        ):
                            valid_ips.append(ip)

                    # Prefer IPs in the same subnet as the source
                    # The source IP is likely the correct one to use
                    if source_ip in valid_ips:
                        device_info["preferred_ip"] = source_ip
                    elif valid_ips:
                        # Try to find an IP in the same subnet
                        source_prefix = ".".join(source_ip.split(".")[:3])
                        for ip in valid_ips:
                            if ip.startswith(source_prefix):
                                device_info["preferred_ip"] = ip
                                break
                        else:
                            # Just use the first valid IP
                            device_info["preferred_ip"] = valid_ips[0]
                    else:
                        device_info["preferred_ip"] = addr[0]
                else:
                    device_info["preferred_ip"] = addr[0]

                # Avoid duplicates
                if not any(
                    d.get("deviceId") == device_info.get("deviceId") for d in devices
                ):
                    devices.append(device_info)

            except socket.timeout:
                break
            except Exception:
                # Ignore parse errors
                pass

            # Check if we've exceeded timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                break

        sock.close()
        return devices

    async def connect(self) -> bool:
        """Connect to Infinite Flight via TCP socket.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.host or not self.port:
            raise ValueError("Host and port must be set before connecting")

        try:
            # Create TCP socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)

            # Connect
            self._socket.connect((self.host, self.port))
            self._connected = True

            # Get manifest after connecting
            await self.get_manifest()

            return True

        except socket.timeout:
            self._connected = False
            if self._socket:
                self._socket.close()
                self._socket = None
            self.last_error = "Connection timed out"
            return False
        except ConnectionRefusedError:
            self._connected = False
            if self._socket:
                self._socket.close()
                self._socket = None
            self.last_error = "Connection refused - Check if Connect API is enabled"
            return False
        except Exception as e:
            self._connected = False
            if self._socket:
                self._socket.close()
                self._socket = None
            self.last_error = str(e)
            return False

    async def disconnect(self):
        """Disconnect from Infinite Flight."""
        if self._socket:
            self._socket.close()
            self._socket = None
        self._connected = False
        self._manifest.clear()
        self._state_map.clear()

    @property
    def is_connected(self) -> bool:
        """Check if connected to Infinite Flight."""
        return self._connected

    def _send_request(
        self, state_id: int, is_set: bool = False, value: Optional[Any] = None
    ):
        """Send a request to the API.

        Args:
            state_id: The numeric ID of the state/command
            is_set: Whether this is a set request (True) or get request (False)
            value: The value to set (only used if is_set is True)
        """
        if not self._connected or not self._socket:
            raise RuntimeError("Not connected to Infinite Flight")

        # Pack the state ID as little-endian 32-bit integer
        data = struct.pack("<i", state_id)

        # Add the boolean flag
        data += struct.pack("?", is_set)

        # If setting a value, add it (not implemented in this minimal version)
        if is_set and value is not None:
            # Determine data type from manifest
            if state_id not in self._manifest:
                raise ValueError(
                    f"State ID {state_id} not found in manifest. Cannot determine type for setting."
                )

            _, state_type = self._manifest[state_id]

            if state_type == DataType.BOOLEAN:
                data += struct.pack("?", bool(value))
            elif state_type == DataType.INTEGER:
                data += struct.pack("<i", int(value))
            elif state_type == DataType.FLOAT:
                data += struct.pack("<f", float(value))
            elif state_type == DataType.DOUBLE:
                data += struct.pack("<d", float(value))
            elif state_type == DataType.STRING:
                str_value = str(value).encode("utf-8")
                data += struct.pack("<i", len(str_value))  # Length of string
                data += str_value  # String data
            elif state_type == DataType.LONG:
                data += struct.pack("<q", int(value))
            else:
                raise NotImplementedError(
                    f"Setting values for data type {state_type} is not implemented"
                )

        # Send the request
        self._socket.send(data)

    def _receive_data(self, expected_length: int) -> bytes:
        """Receive a specific amount of data from the socket.

        Args:
            expected_length: Number of bytes to receive

        Returns:
            The received data
        """
        data = b""
        # Temporarily increase timeout for large data transfers
        old_timeout = self._socket.gettimeout()
        self._socket.settimeout(30.0)  # 30 seconds for manifest

        try:
            while len(data) < expected_length:
                chunk = self._socket.recv(expected_length - len(data))
                if not chunk:
                    raise RuntimeError("Connection closed while reading data")
                data += chunk
        finally:
            # Restore original timeout
            self._socket.settimeout(old_timeout)

        return data

    async def get_manifest(self) -> Dict[str, Any]:
        """Get the manifest from Infinite Flight.

        Returns:
            Dictionary mapping state names to their info
        """
        if not self._connected:
            raise RuntimeError("Not connected to Infinite Flight")

        # Send manifest request (-1)
        self._send_request(-1, False)

        # Receive response header
        header = self._receive_data(
            12
        )  # 4 bytes ID + 4 bytes total length + 4 bytes string length

        # Parse header
        response_id, total_length, string_length = struct.unpack("<iii", header)

        if response_id != -1:
            raise RuntimeError(f"Unexpected response ID: {response_id}")

        # Receive the manifest string
        manifest_data = self._receive_data(string_length)
        manifest_str = manifest_data.decode("utf-8")

        # Parse manifest
        self._manifest.clear()
        self._state_map.clear()

        for line in manifest_str.strip().split("\n"):
            if not line:
                continue

            parts = line.split(",", 2)
            if len(parts) != 3:
                continue

            try:
                state_id = int(parts[0])
                data_type = int(parts[1])
                name = parts[2]

                # Skip commands (they have data_type = -1)
                if data_type == -1:
                    continue

                self._manifest[state_id] = (name, DataType(data_type))
                self._state_map[name] = state_id
            except (ValueError, KeyError):
                continue

        return {
            name: {"id": state_id, "type": data_type.name}
            for state_id, (name, data_type) in self._manifest.items()
        }

    async def get_state(self, state_name: str) -> Any:
        """Get a state value from Infinite Flight.

        Args:
            state_name: The name of the state (e.g., "aircraft/0/altitude_msl")

        Returns:
            The state value
        """
        if not self._connected:
            raise RuntimeError("Not connected to Infinite Flight")

        if state_name not in self._state_map:
            raise ValueError(f"Unknown state: {state_name}")

        state_id = self._state_map[state_name]
        state_type = self._manifest[state_id][1]

        # Send get request
        self._send_request(state_id, False)

        # Receive response header (8 bytes: 4 for ID, 4 for data length)
        header = self._receive_data(8)
        response_id, data_length = struct.unpack("<ii", header)

        if response_id != state_id:
            raise RuntimeError(
                f"Unexpected response ID: {response_id}, expected {state_id}"
            )

        # Receive the actual data
        data = self._receive_data(data_length)

        # Parse based on data type
        if state_type == DataType.BOOLEAN:
            return struct.unpack("?", data)[0]
        elif state_type == DataType.INTEGER:
            return struct.unpack("<i", data)[0]
        elif state_type == DataType.FLOAT:
            return struct.unpack("<f", data)[0]
        elif state_type == DataType.DOUBLE:
            return struct.unpack("<d", data)[0]
        elif state_type == DataType.STRING:
            # String format: 4 bytes length + string data
            str_length = struct.unpack("<i", data[:4])[0]
            return data[4 : 4 + str_length].decode("utf-8")
        elif state_type == DataType.LONG:
            return struct.unpack("<q", data)[0]
        else:
            raise ValueError(f"Unknown data type: {state_type}")

    def get_available_states(self) -> List[str]:
        """Get a list of all available state names.

        Returns:
            List of state names
        """
        return sorted(self._state_map.keys())

    async def set_state(self, state_name: str, value: Any):
        """Set a state value in Infinite Flight.

        Args:
            state_name: The name of the state (e.g., "aircraft/0/systems/flaps/state")
            value: The value to set for the state

        Raises:
            RuntimeError: If not connected
            ValueError: If state_name is unknown or data type is unsupported for setting
        """
        if not self._connected:
            raise RuntimeError("Not connected to Infinite Flight")

        if state_name not in self._state_map:
            raise ValueError(f"Unknown state: {state_name}")

        state_id = self._state_map[state_name]
        # The _send_request method will use self._manifest[state_id][1] to get the type

        # Send set request
        self._send_request(state_id, True, value)
        # As per docs, API does not send a confirmation for SetState

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
