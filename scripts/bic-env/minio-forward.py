"""TCP forwarder: local :9000/:9001 -> orin-tail MinIO (over tailscale).

Managed by scripts/bic-env/mind.sh (real-Mind mode). It replaces the local
bic-minio container so that presigned URLs signed for host
<ORIN_LAB_IP>:9000 resolve to the SAME MinIO from both sides:
  - BE / lab / mock on this bench -> this forwarder -> orin MinIO (tailnet)
  - real Mind on the lab LAN      -> ORIN_LAB_IP = orin itself
SigV4 stays intact because the Host header is identical on both paths.

Stdlib only (asyncio) — no venv needed; started with the system python3.
"""
import asyncio
import os

UPSTREAM_HOST = os.environ.get("ORIN_TS_IP", "100.114.189.44")
PORTS = [int(p) for p in os.environ.get("FWD_PORTS", "9000,9001").split(",")]


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


def make_handler(port: int):
    async def handle(creader, cwriter):
        try:
            ureader, uwriter = await asyncio.wait_for(
                asyncio.open_connection(UPSTREAM_HOST, port), 10
            )
        except Exception:
            cwriter.close()
            return
        await asyncio.gather(pipe(creader, uwriter), pipe(ureader, cwriter))

    return handle


async def main():
    servers = []
    for port in PORTS:
        srv = await asyncio.start_server(make_handler(port), "0.0.0.0", port)
        servers.append(srv)
        print(f"forwarding 0.0.0.0:{port} -> {UPSTREAM_HOST}:{port}", flush=True)
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
