"""Minimal MCP client for the NovaOps knowledge-base server — Stage 1, STDIO.

Starts `python -m mcp_server --role <role>` as a subprocess, opens an MCP
ClientSession over its stdin/stdout, and exercises the whole Stage 1 surface:
tools, resources, capabilities, health, subjects and one question.

    python mcp_client.py --role employee
    python mcp_client.py --role manager --question "How should I run a 1:1?"

Deliberately thin: the server is the source of truth. This client validates no
role, retrieves nothing, filters nothing and classifies no failure — it passes
the role through, prints what the server returns, and surfaces a tool error with
the server's own (already safe) message. It imports nothing from the RAG core or
from mcp_server. `health_check` and `ask_rag` make live AWS calls on the server.
"""
import argparse
import json
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TextIO

import anyio
from mcp import ClientSession, MCPError, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent
SUBJECTS_URI = "rag://subjects"
DEFAULT_QUESTION = "What benefits are available to employees?"


class ToolCallError(RuntimeError):
    """The server answered a tool call with an error; the message is the server's own."""


def server_parameters(role: str, env: dict[str, str] | None = None) -> StdioServerParameters:
    """How to launch the server. `role` is passed through unchecked — the server
    validates it and refuses to start on an unsupported one. `env` is merged over
    the SDK's minimal inherited environment; the server reads its own .env."""
    return StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server", "--role", role], cwd=PROJECT_ROOT, env=env,
    )


@asynccontextmanager
async def connect(role: str, env: dict[str, str] | None = None,
                  errlog: TextIO | None = None) -> AsyncIterator[ClientSession]:
    """An initialized session with a freshly started server; the server stops on exit.
    `errlog` receives the server's stderr (it must be a real file: the SDK hands it
    to the subprocess as its stderr); default: this process's stderr."""
    async with stdio_client(server_parameters(role, env), errlog=errlog or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_tool(session: ClientSession, name: str, arguments: dict | None = None) -> dict:
    result = await session.call_tool(name, arguments or {})
    if result.is_error:
        raise ToolCallError(result.content[0].text if result.content else f"{name} failed")
    return result.structured_content


async def read_json_resource(session: ClientSession, uri: str) -> dict:
    result = await session.read_resource(uri)
    return json.loads(result.contents[0].text)


async def discover(session: ClientSession) -> dict:
    """The static surface: no AWS or OpenSearch call on the server."""
    tools = await session.list_tools()
    resources = await session.list_resources()
    return {
        "tools": sorted(t.name for t in tools.tools),
        "resources": sorted(str(r.uri) for r in resources.resources),
        "capabilities": await call_tool(session, "get_rag_capabilities"),
        "subjects": (await read_json_resource(session, SUBJECTS_URI))["subjects"],
    }


async def run_stage1(session: ClientSession, question: str = DEFAULT_QUESTION) -> dict:
    """Discovery, then the two live calls: health_check and one ask_rag."""
    result = await discover(session)
    result["health"] = await call_tool(session, "health_check")
    result["ask_rag"] = await call_tool(session, "ask_rag", {"question": question})
    return result


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Minimal Stage 1 MCP client (STDIO) for the NovaOps server.")
    parser.add_argument("--role", required=True, help="server role, passed through; the server validates it")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args(argv)

    # The server's stderr is captured rather than inherited: on a Windows console the
    # server runs without a console of its own, so its messages would otherwise be lost.
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as server_log:
        async def run() -> dict | ToolCallError:
            async with connect(args.role, env={"PYTHONIOENCODING": "utf-8"}, errlog=server_log) as session:
                # Caught inside the session: an exception leaving the SDK's task group
                # arrives wrapped in an ExceptionGroup.
                try:
                    return await run_stage1(session, args.question)
                except ToolCallError as exc:
                    return exc

        try:
            result = anyio.run(run)
        except* MCPError as group:
            # The session itself failed — typically the server refused to start (e.g. an
            # unsupported role) and exited before the handshake.
            result = group
            while isinstance(result, BaseExceptionGroup):  # the SDK's task groups nest the error
                result = result.exceptions[0]
        server_log.seek(0)
        server_output = server_log.read()

    if isinstance(result, MCPError):
        parser.exit(1, f"error: {_server_failure(server_output, result)}\n")
    sys.stderr.write(server_output)  # the server's own (sanitized) operational log
    if isinstance(result, ToolCallError):
        parser.exit(1, f"tool error: {result}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _server_failure(server_output: str, error: MCPError) -> str:
    """One line saying why the server went away: its own last error line (argparse's
    "prog: error: " prefix dropped), or the protocol error when it said nothing."""
    lines = [line.strip() for line in server_output.splitlines() if line.strip()]
    if not lines:
        return f"the MCP server closed the connection unexpectedly ({error})"
    # The program name can contain spaces ("python.exe -m mcp_server"), hence the lazy match.
    return "the MCP server failed to start: " + re.sub(r"^.*?: error: ", "", lines[-1], count=1)


if __name__ == "__main__":
    main()
