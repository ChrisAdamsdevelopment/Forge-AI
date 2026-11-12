# Protected local MCP tunnel — recovery and verification

This is a **read-only** check for an existing ngrok tunnel to a protected local MCP HTTP server. It does **not** install ngrok, launch a server, register tools in ChatGPT, or replace an existing launcher.

## Canonical boundaries

- Keep the current protected MCP process and ngrok terminal running. Do not launch a competing tunnel on the same domain.
- Use an explicitly selected, version-checked ngrok executable. Do not rely on a bare ngrok command when Chocolatey and WinGet shims coexist on Windows.
- The MCP process should bind to 127.0.0.1, require authentication, and enforce narrow filesystem roots. Do not expose Forge's unauthenticated tool server directly through ngrok.
- An anonymous HTTP 401 response is **expected**. It is a useful protection check, **not** proof that an AI client's authenticated MCP tools are registered.
- Never paste MCP bearer tokens, authentication headers, .env, or ngrok auth tokens into public issues or the repository.

## Run on Windows

From a Forge-AI checkout, with the protected server and ngrok already running:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-McpTunnel.ps1 -NgrokExe 'D:\GrowthEngineeringVenture\Tools\ngrok\ngrok.exe' -PublicUrl 'https://YOUR-RESERVED-DOMAIN.ngrok-free.dev' -LocalPort 8766
~~~

The script verifies, in order:

1. The named ngrok executable exists and reports a version of at least 3.29.0.
2. The local listener is loopback-only, owned by the expected process (command line contains the default marker `local-workspace-mcp`). Customize `-ServerCommandMarker` if the actual known server uses a different executable or entrypoint.
3. Local http://127.0.0.1:8766/mcp rejects **both anonymous GET and read-only MCP initialize POST** with HTTP 401; redirects are not followed.
4. The local ngrok inspector at http://127.0.0.1:4040/api/tunnels reports one tunnel for the specified origin, forwarding to loopback port 8766.
5. Public https://YOUR-RESERVED-DOMAIN.ngrok-free.dev/mcp rejects those same anonymous GET and initialize POST requests with 401.
6. The inspector mapping remains unchanged after the public probe.

Success ends with '[PASS] Read-only transport/authentication probes completed.' Failure reports the layer and returns nonzero exit status. These probes do not authenticate an MCP tool client or prove that authorized tool execution works.

## Failure patterns

| Symptom | Likely failure | Next action |
| --- | --- | --- |
| Missing Chocolatey ngrok.exe | Broken Chocolatey shim | Supply the verified absolute executable path |
| ERR_NGROK_121; agent 3.3.1 | Outdated ngrok binary | Verify the selected binary's actual version |
| Unknown flag --url | Mismatched agent and launcher | Inspect the selected executable's ngrok http --help output |
| Local /mcp cannot connect | Existing MCP listener stopped | Inspect existing server logs, do not launch a competing server |
| Local /mcp responds 200 anonymously | Authentication failure | Stop public exposure and investigate immediately |
| Inspector shows different port | Wrong forwarding or process | Inspect current tunnel; do not start another on the same domain |
| Public /mcp responds 401 | Expected anonymous protection | Proceed to separate client-registration checks |
| GitHub works but local filesystem tools fail | Different integration layers | GitHub access alone does not imply desktop filesystem access |

## AI client registration is separate

A public ngrok endpoint does not register tools automatically inside an AI conversation. Determine whether the client/account supports custom MCP connections; configure credentials in the client's secure settings; then perform an authenticated read-only MCP tool listing. Never commit or paste tokens.

The historical Poweruser_Local_MCP_Toolchain repository is archived and states that authentication is not required by default. It must not be treated as the configuration of the newer protected port-8766 service.
