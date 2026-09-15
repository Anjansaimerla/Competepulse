#!/usr/bin/env python3
"""Competepulse Web Dashboard Entry Point: starts the local web interface."""

import os
import socket
import sys
from competepulse.web import run_server


def find_available_port(start_port: int = 8080) -> int:
    for p in range(start_port, start_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    return start_port


if __name__ == "__main__":
    if "PORT" in os.environ and os.environ["PORT"].isdigit():
        port = int(os.environ["PORT"])
    elif len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    else:
        port = find_available_port(8080)

    print(f"\n============================================================")
    print(f"🚀 Competepulse Web Dashboard Running!")
    print(f"👉 Port: {port}")
    print(f"============================================================\n")
    run_server(host="0.0.0.0", port=port)
