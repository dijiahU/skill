"""Targeted dependency repairs; preserve task files and verifier assertions."""
import re


def adapt(source, *, repair_uv=True):
    changes = []
    uv = re.compile(r"^RUN curl -LsSf https://astral\.sh/uv/(0\.9\.7)/install\.sh \| sh$", re.M)
    def install_uv(match):
        changes.append("uv-binary")
        version = match[1]
        return ("RUN mkdir -p /root/.local/bin && "
                "curl -fL --retry 5 --retry-all-errors --connect-timeout 30 "
                f"https://github.com/astral-sh/uv/releases/download/{version}/uv-x86_64-unknown-linux-gnu.tar.gz "
                "-o /tmp/terminal-bench-uv.tar.gz && "
                "tar -xzf /tmp/terminal-bench-uv.tar.gz -C /root/.local/bin --strip-components=1 "
                "uv-x86_64-unknown-linux-gnu/uv uv-x86_64-unknown-linux-gnu/uvx && "
                f"/root/.local/bin/uv --version | grep -F 'uv {version}'")
    if repair_uv:
        source = uv.sub(install_uv, source)
    install = "RUN pip install --no-cache-dir 'gnucleus-freecad-validator[render]==0.1.3'"
    if install in source:
        changes.append("vtk-compatible")
        source = source.replace(install, install + " 'pyvista==0.46.4' 'vtk==9.2.6'")
    return source, changes
