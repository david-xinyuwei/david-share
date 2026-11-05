#!/usr/bin/env python3
"""Verify native cross-host GPU transfer before reloading a model pool."""
import argparse
import hashlib
import json
import socket
import time

import torch
from mooncake.engine import TransferEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("receiver", "sender"))
    parser.add_argument("--host", required=True)
    parser.add_argument("--peer")
    parser.add_argument("--port", type=int, default=19868)
    parser.add_argument("--protocol", choices=("rdma", "tcp"), required=True)
    args = parser.parse_args()
    torch.cuda.set_device(0)
    length = 1024 * 1024
    expected = (torch.arange(length, device="cuda", dtype=torch.int32) % 251).to(torch.uint8)
    buffer = expected.clone() if args.role == "sender" else torch.zeros_like(expected)
    torch.cuda.synchronize()
    engine = TransferEngine()
    assert engine.initialize(args.host, "P2PHANDSHAKE", args.protocol, "") == 0
    assert engine.register_memory(buffer.data_ptr(), length) == 0
    try:
        if args.role == "receiver":
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.settimeout(120)
                listener.bind((args.host, args.port))
                listener.listen(1)
                print(json.dumps({"status": "READY", "role": args.role, "protocol": args.protocol}), flush=True)
                connection, _ = listener.accept()
            with connection:
                connection.settimeout(120)
                reader = connection.makefile("rb")
                offer = {"target": f"{args.host}:{engine.get_rpc_port()}", "address": buffer.data_ptr(), "length": length}
                connection.sendall((json.dumps(offer) + "\n").encode())
                receipt = json.loads(reader.readline(4096))
                torch.cuda.synchronize()
                matches = receipt["return_code"] == 0 and torch.equal(buffer, expected)
                digest = hashlib.sha256(buffer.cpu().numpy().tobytes()).hexdigest()
                result = {"status": "PASS" if matches else "FAIL", "role": args.role,
                          "protocol": args.protocol, "bytes": length, "matches": matches, "sha256": digest}
                connection.sendall((json.dumps(result) + "\n").encode())
                print(json.dumps(result), flush=True)
                assert matches, "Native cross-host GPU bytes differ"
        else:
            if not args.peer:
                parser.error("sender requires --peer")
            with socket.create_connection((args.peer, args.port), timeout=120) as connection:
                connection.settimeout(120)
                reader = connection.makefile("rb")
                offer = json.loads(reader.readline(4096))
                assert offer["length"] == length
                started = time.monotonic()
                result = engine.batch_transfer_sync_write(offer["target"], [buffer.data_ptr()], [offer["address"]], [length])
                connection.sendall((json.dumps({"return_code": result}) + "\n").encode())
                receipt = json.loads(reader.readline(4096))
                print(json.dumps({"status": receipt["status"], "role": args.role, "protocol": args.protocol,
                                  "bytes": length, "return_code": result, "receiver_matches": receipt["matches"],
                                  "elapsed_s": time.monotonic() - started}), flush=True)
                assert result == 0 and receipt["matches"], "Native cross-host GPU transfer failed"
    finally:
        engine.unregister_memory(buffer.data_ptr())


if __name__ == "__main__":
    main()