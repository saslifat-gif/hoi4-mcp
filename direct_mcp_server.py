"""Named game-side MCP requests; input simulation is absent."""
import argparse
from mcp.server.fastmcp import FastMCP
from transport import BridgeClient


def create_server(client):
    server = FastMCP('hoi4-game-side-commands', instructions=(
        'File/mod controller for an authorized single-player test campaign. '
        'No keyboard, mouse, screen coordinates, screenshots or input fallback. '
        'Supports scripted queued construction, new base land-equipment production lines and state snapshots. '
        'Use a unique 32-character lowercase hexadecimal request_id per intended action; keep it after a timeout. '
        'Repeat the same ID only to reconcile; publication is not retried automatically. '
        'Poll hoi4_receipt. Engine acknowledgment means the script branch ran, not that the requested gameplay outcome is verified. '
        'Daily hooks require an unpaused game. Research/focus selection, pause/speed, diplomacy, event choices and unit orders remain unsupported. '
        'Normal-player command equivalence and complete gameplay coverage are unverified.'))

    @server.tool()
    def hoi4_status() -> dict:
        """Read session handshake, pending IDs, supported operations and production allowlist."""
        return client.call('/status', {})

    @server.tool()
    def hoi4_arm(enabled: bool) -> dict:
        """Arm/disarm an already authorized test campaign after its native startup handshake."""
        return client.call('/arm', {'enabled': enabled})

    @server.tool()
    def hoi4_snapshot(request_id: str) -> dict:
        """Queue a native daily-hook state snapshot. Paused simulation leaves it pending."""
        return client.call('/submit', {'request_id': request_id, 'command': {'kind': 'snapshot'}})

    @server.tool()
    def hoi4_construct(request_id: str, state_id: int, building: str, levels: int = 1) -> dict:
        """Request construction with instant_build=no; native ownership/free-slot guards apply.
        building: industrial_complex, arms_factory or dockyard. levels: 1..5 when the native queued-capacity backend is installed; otherwise 1. Capacity is rechecked on the game thread before insertion.
        This is a game-script request. Queue insertion and normal-player eligibility equivalence need live verification.
        """
        return client.call('/submit', {'request_id': request_id, 'command': {'kind': 'construct',
            'state_id': state_id, 'building': building, 'levels': levels}})

    @server.tool()
    def hoi4_produce(request_id: str, equipment: str, factories: int = 1) -> dict:
        """Request a new base land-equipment line with available factories and unlock-tech guards.
        Use an ID from hoi4_status's allowlist; factories: 1..15. No stockpile grant or progress override.
        Existing-line edits, DLC/mod overlays, exact allocation and normal-player eligibility equivalence are unverified.
        """
        return client.call('/submit', {'request_id': request_id, 'command': {'kind': 'produce',
            'equipment': equipment, 'factories': factories}})

    @server.tool()
    def hoi4_receipt(command_id: str) -> dict:
        """Read pending/rejected/acknowledged delivery. This does not refresh or republish mod files."""
        return client.call('/receipt', {'command_id': command_id})

    @server.tool()
    def hoi4_deliver(command_id: str) -> dict:
        """Explicitly refresh an unresolved request's effect and caller using its original ID.
        Inspect its receipt first after uncertainty. Native done flags prevent repeating its script branch.
        Never assigns a fresh ID or creates another gameplay request.
        """
        return client.call('/deliver', {'command_id': command_id})
    return server


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:18768')
    p.add_argument('--token-file',required=True);args=p.parse_args()
    create_server(BridgeClient(args.url,token_file=args.token_file)).run(transport='stdio')


if __name__ == '__main__':
    main()
