FROM ghcr.io/sani903/openagentsafety_base_image-image:1.0

# Install the locally built OpenHands packages and their pinned wheel set. The
# wheelhouse is supplied as a named BuildKit context from persistent storage.
ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=20 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN --mount=type=bind,from=wheelhouse,target=/wheelhouse,ro \
    pip install --no-index --find-links=/wheelhouse \
    openhands-sdk openhands-tools openhands-agent-server

# The benchmark base image already provides Git and the OpenAI client. The
# runner disables browser tools, so installing Playwright and Chromium here
# would add network-sensitive packages that no OpenAgentSafety task can use.

# Install the NPC helper as a regular build-context file. Keeping Python out of
# a Dockerfile heredoc makes the image portable across Dockerfile frontends.
COPY benchmarks/openagentsafety/scripts/chat_npc.py /usr/local/bin/chat_npc
RUN chmod +x /usr/local/bin/chat_npc

WORKDIR /workspace
EXPOSE 8000

# CRITICAL FIX: ENTRYPOINT gets the command, CMD provides default args
# When docker run passes args, they replace CMD but ENTRYPOINT stays
ENTRYPOINT ["python", "-m", "openhands.agent_server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
