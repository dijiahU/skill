"""Pod-local package download relay, restricted to this Pod/node and public targets."""
import asyncio
import ipaddress
import os
import re
import socket
from urllib.parse import urlsplit


async def main():
    bind = socket.gethostbyname(socket.gethostname())
    allowed = {bind, os.environ['LOCAL_HOST_IP'], '127.0.0.1'}

    async def serve(reader, writer):
        upstream = None
        try:
            if writer.get_extra_info('peername')[0] not in allowed:
                return
            header = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 15)
            method, target, _ = header.split(b'\r\n', 1)[0].decode('ascii').split(' ', 2)
            if method not in {'GET', 'HEAD', 'CONNECT'}:
                raise ValueError('Download methods only')
            parsed = urlsplit(('//' if method == 'CONNECT' else '') + target)
            host, port = parsed.hostname, parsed.port or (443 if method == 'CONNECT' else 80)
            if port not in {80, 443} or not host:
                raise ValueError('Public web ports only')
            package_domains = ('github.com','githubusercontent.com','pypi.org','pythonhosted.org',
                'astral.sh','debian.org','ubuntu.com','huggingface.co','hf.co','anaconda.org',
                'anaconda.com','prefix.dev','docker.io','docker.com','pytorch.org',
                'alpinelinux.org','rust-lang.org','crates.io','npmjs.org','npmjs.com')
            known_public = any(host == domain or host.endswith('.' + domain) for domain in package_domains)
            # Fixed public package domains are resolved by the upstream proxy; the Pod
            # resolver can disappear or synthesize non-public addresses during SSH reconnect.
            if not known_public:
                addresses = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
                if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                    raise ValueError('Public destinations only: ' + str(host))
            async def connect_upstream():
                for reconnect in range(120):
                    try:
                        return await asyncio.open_connection('127.0.0.1', 17892)
                    except (ConnectionRefusedError, ConnectionResetError):
                        if reconnect == 119:
                            raise
                        await asyncio.sleep(2)
            if method != 'CONNECT':
                header = re.sub(br'(?im)^(?:Proxy-)?Connection:[^\r\n]*\r\n', b'', header)
                header = header[:-2] + b'Connection: close\r\nProxy-Connection: close\r\n\r\n'
            for attempt in range(6):
                remote, upstream = await connect_upstream()
                upstream.write(header)
                await upstream.drain()
                response_header = await asyncio.wait_for(remote.readuntil(b'\r\n\r\n'), 60)
                code = int(response_header.split(b' ', 2)[1])
                if code not in {429, 502, 503, 504} or attempt == 5:
                    break
                upstream.close()
                await upstream.wait_closed()
                print('Retry public download: ' + host + ' status=' + str(code), flush=True)
                await asyncio.sleep(attempt + 1)
            writer.write(response_header)
            await writer.drain()

            async def pipe(source, dest):
                while block := await source.read(65536):
                    dest.write(block)
                    await dest.drain()
            if method != 'CONNECT':
                await pipe(remote, writer)
                return
            pipes = [asyncio.create_task(pipe(reader, upstream)), asyncio.create_task(pipe(remote, writer))]
            done, pending = await asyncio.wait(pipes, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pipes, return_exceptions=True)
        except Exception as exc:
            print(type(exc).__name__ + ': ' + str(exc), flush=True)
        finally:
            writer.close()
            if upstream:
                upstream.close()
    port = int(os.environ.get('TERMINAL_BENCH_PROXY_PORT', '18192'))
    server = await asyncio.start_server(serve, bind, port, limit=65536)
    print('Package relay ready on ' + bind + ':' + str(port), flush=True)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
