# GSLOC-PROXY

`GSLOC-PROXY` is a network-layer location integrity testing proxy for authorized lab environments. It helps mobile app developers, security researchers, and risk-control teams reproduce a specific threat model: the app itself is not hooked, injected, debugged, or using system mock location, but upstream network signals used by system location services are modified inside a controlled test network.

<p><b>English</b> | <a href="docs/README.zh-CN.md">简体中文</a></p>

![GSLOC-PROXY](docs/img/image.png)

This project is not about proving that "location can be changed." Its purpose is to help developers verify whether their own apps over-trust system location results, and whether they have enough multi-signal validation, risk scoring, and anomaly handling.

> This project is intended only for security research, defensive testing, and risk-control robustness validation on devices, apps, accounts, and controlled networks that you own or are authorized to test.
>
> This project is not intended for, and must not be used to bypass, attendance systems, games, financial services, delivery platforms, regional restrictions, anti-cheat systems, platform risk controls, or any third-party application policy.
>
> The maintainers will not provide assistance for unauthorized use, unlawful use, infringement of third-party rights, or use intended to evade third-party policies. Users are responsible for ensuring that their test environment, devices, accounts, network, and target apps are legally authorized and compliant with applicable laws and regulations.

## Purpose

Mobile apps often check for local tampering signals such as jailbreak, debugging, hooks, injected libraries, or system mock location. However, "no local tampering detected" does not mean that the system location result is necessarily trustworthy.

`GSLOC-PROXY` uses a proxy-based approach to simulate network-layer modification of upstream location signals. This lets developers observe how their own apps behave under an authorized experimental threat model.

It is suitable for:

- Location integrity testing.
- Mobile app location risk-control robustness validation.
- Research on system location trust boundaries.
- Defensive testing of multi-source location trust scoring.
- Reproducible lab setups for security reports or internal risk-control exercises.

It is not suitable for, and must not be used as:

- A public proxy service.
- A general-purpose HTTPS MITM proxy.
- A way to bypass any third-party app rule.
- A way to evade platform risk controls, anti-cheat systems, or regional restrictions.
- A tool to collect, store, or analyze other people's device, account, or network data.

## How It Works

On an authorized test device, the user uses their own network routing tool to forward Apple location-related requests to `GSLOC-PROXY` running locally or inside a trusted lab network. The proxy only allows configured location-service hosts and only applies experimental response processing on configured paths.

The current implementation is based on `mitmproxy regular mode`:

- HTTP CONNECT proxy entry point.
- Host allowlist.
- Path allowlist.
- gzip decompression and recompression.
- Experimental signal transformation for recognized location response structures.
- Web console for status, test-location management, and local CA certificate download.

The test chain requires the authorized test device to install and trust the local experimental CA. Without that setup, HTTPS test traffic will not be processed by the proxy.

## Security Boundary

- The proxy entry point listens on `127.0.0.1` by default.
- The management Web/API server listens on `127.0.0.1` by default.
- The management console supports username/password login. Set `GSLOC_MANAGE_PASSWORD` to enable it.
- Non-allowlisted hosts are rejected to avoid becoming a general-purpose proxy.
- Examples are intended only for local or trusted LAN environments with authorized devices.

If you need a phone to access the proxy or console from your computer, temporarily listen on `0.0.0.0` only inside a trusted LAN, and make sure the network, device, and account are all under your control and authorized. Do not expose this service to the public internet.

## Quick Start

### 1. Create a Virtual Environment

Do not install dependencies globally into the system Python. Use the cross-platform setup script:

```bash
cd proxy
python setup-venv.py
```

If `python` points to Python 2 or an older Python version, use `python3 setup-venv.py` or `py -3 setup-venv.py`.

### 2. Prepare Local Config

macOS/Linux:

```bash
cp .env.example .env
cp policy.example.json policy.json
cp state.example.json state.json
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
Copy-Item policy.example.json policy.json
Copy-Item state.example.json state.json
```

Default management console:

```text
http://127.0.0.1:8090/
```

Default proxy endpoint:

```text
127.0.0.1:8082
```

### 3. Start the Proxy

```bash
python run-local.py
```

After startup, the console can generate or download the current mitmproxy CA certificate. The authorized test device must install and trust that CA, otherwise the HTTPS test chain cannot be established.

The copied `state.json` starts with the proxy session and experiment disabled. Configure the test location, install the CA on the authorized test device, and then enable the session and experiment from the console when you are ready to run the test.

### 4. Set Up an Authorized iPhone

If the iPhone needs to access the Web console from your computer, make the proxy and management endpoints reachable only on a trusted LAN, and set a strong `GSLOC_MANAGE_PASSWORD` before doing so.

On the authorized iPhone:

1. Open the Web console in Safari.
2. Tap the CA certificate download button and allow iOS to download the configuration profile.
3. Go to Settings > General > VPN & Device Management, then install the downloaded `GSLOC-PROXY` certificate profile.
4. Go to Settings > General > About > Certificate Trust Settings, then fully trust the `GSLOC-PROXY` certificate.
5. Return to the Web console, configure the test location and signal transformation mode, then enable the proxy session and experiment.

For later tests on the same device, you can usually skip the certificate installation and trust steps unless the proxy CA was regenerated or the device profile was removed.

### 5. Configure Client Routing

Use a network tool you control, such as sing-box, ClashMi, Surge, Stash, Quantumult X, Loon, or an equivalent lab router, to forward only the configured Apple location-service hosts to the `GSLOC-PROXY` proxy endpoint.

For sing-box, start from the example file:

```text
docs/example/sing-box-1.13.json
```

Adjust the example before use:

- set `outbounds[].server` to the address of the machine running `GSLOC-PROXY`;
- set `outbounds[].server_port` to the proxy port, which defaults to `8082`;
- keep the route rules aligned with `policy.json`;
- keep unrelated traffic direct or otherwise restricted by your lab policy.

After the routing tool is active, go to Settings > Privacy & Security > Location Services on the authorized iPhone, turn Location Services off, and turn it back on so the device refreshes its location-service state.

## Docker Compose

Docker deployment files live in `docker/`. There is one Compose file per deployment path:

- `docker/compose.build.yml`: build and deploy from source.
- `docker/compose.develop.yml`: deploy the `develop` image from GHCR.
- `docker/compose.yml`: deploy a pinned release image from GHCR.

Source build from a full repository checkout:

```bash
docker compose -f docker/compose.build.yml up --build -d
```

This builds `docker/Dockerfile` and runs the local image `gsloc-proxy:local`.

For a pinned release image, edit `docker/compose.yml` and set the image tag you want:

```yaml
image: ghcr.io/inp146/gsloc-proxy:0.1.0
```

Then run this from the `docker/` directory:

```bash
cd docker
docker compose pull
docker compose up -d
```

Git tag `v0.1.0` publishes GHCR image tags such as `0.1.0` and `0.1`.

Default endpoints:

```text
Management console: http://127.0.0.1:8090/
Proxy endpoint:      127.0.0.1:8082
```

The Compose setup publishes both ports to `127.0.0.1` on the host by default and stores runtime state, logs, and the mitmproxy CA in the `gsloc-proxy-data` Docker volume. On first start, the image seeds missing `/config/policy.json` and `/data/state.json` from the source `policy.example.json` and `state.example.json`, matching the local copy-based setup. Existing files in the Docker volume are preserved.

The container image listens on `0.0.0.0` inside the container so Compose port bindings can control host exposure. If you run the image without these Compose files, bind published ports to `127.0.0.1` unless you are on a trusted LAN and have set a strong `GSLOC_MANAGE_PASSWORD`.

Ports default to local-only access:

```yaml
ports:
  - "127.0.0.1:8082:8082"
  - "127.0.0.1:8090:8090"
```

For trusted LAN access, change `127.0.0.1` to `0.0.0.0` and set a strong `GSLOC_MANAGE_PASSWORD`. Do not publish the service to the public internet.

To use a private policy file, add this bind mount to the selected Compose file:

```yaml
volumes:
  - type: bind
    source: ./policy.json
    target: /config/policy.json
    read_only: true
    bind:
      create_host_path: false
  - gsloc-proxy-data:/data
```

Edit the selected Compose file directly for ports, management password, image version, or policy file.

## Configuration

### `.env`

Controls process startup parameters such as proxy port, management Web/API listen address, console login, policy path, runtime state path, mitmproxy config directory, restart flag file, and log settings.

The default management username is `admin`. When `GSLOC_MANAGE_PASSWORD` is empty, login is disabled, which is only appropriate for default local-only access on `127.0.0.1`. If you set `GSLOC_MANAGE_HOST` to `0.0.0.0` for trusted LAN access, set a strong password:

```bash
GSLOC_MANAGE_USER=admin
GSLOC_MANAGE_PASSWORD=change-this-to-a-long-random-password
```

### `policy.json`

Defines the hosts and paths that the proxy is allowed to process.

### `state.json`

Stores runtime experiment state, including whether the experiment is enabled, the simulated upstream location, signal transformation mode, and scale.

## Web Console

The Web console provides:

- Proxy and experiment status.
- Proxy session and experiment enable/disable controls.
- Simulated upstream location for the current integrity test.
- Signal transformation mode switching.
- Latest test result.
- Allowlist policy view.
- Local mitmproxy CA generation and download.
- Runtime logs.

The console is an experimental helper interface and must not be exposed to the public internet. For remote access, add your own access controls, such as reverse-proxy authentication, internal network restrictions, or other authorization mechanisms.

## Client Routing

This project does not provide a general-purpose proxy service and does not take over global device traffic. Authorized test devices should use a network tool controlled by the user to forward only the required location-service requests to `GSLOC-PROXY`.

`GSLOC-PROXY` itself is an HTTP CONNECT proxy endpoint. It does not run a TUN/VPN interface. Tools such as sing-box, mihomo, Surge, Quantumult X, or an equivalent lab router can sit in front of it and perform the client-side routing:

- capture traffic from the authorized test device or lab network;
- match only the configured Apple location-service hostnames, such as the hosts in `policy.json`;
- forward those matched requests to the `GSLOC-PROXY` HTTP proxy endpoint;
- leave unrelated traffic direct or blocked according to your lab policy.

The repository includes `docs/example/sing-box-1.13.json` as a local experiment routing example. In that file:

- `outbounds[].server` should be the address of the machine running `GSLOC-PROXY` as seen from the routing tool;
- `outbounds[].server_port` should match `GSLOC_PROXY_PORT`, which defaults to `8082`;
- the route rule domains should stay aligned with the allowed hosts in `policy.json`;
- the final route should remain direct or otherwise restricted so the setup does not become a general-purpose proxy.

If the routing tool and `GSLOC-PROXY` run on the same machine, the proxy address can usually be `127.0.0.1:8082`. If an iPhone reaches the proxy through a trusted LAN, bind the proxy to a reachable LAN interface, use that LAN address in the routing tool, and set a strong `GSLOC_MANAGE_PASSWORD` before exposing the management console to the LAN.

The authorized test device still needs to install and trust the local mitmproxy CA. Client routing alone is not enough for HTTPS response processing.

## Defensive Guidance

Apps should not treat location as trustworthy merely because jailbreak, hooks, debugging, or system mock location were not detected. A more robust approach is to treat location trust as part of server-side risk scoring and combine it with multiple signals.

Potential detection and mitigation directions include:

- Consistency between system location, IP geolocation, ASN, and network environment.
- Trajectory continuity, speed, acceleration, direction, altitude, accuracy, and timestamp anomalies.
- Impossible travel.
- Multiple accounts or devices repeatedly using the same location.
- Large-scale account activity from the same proxy exit or suspicious network environment.
- Multi-source risk scoring across Wi-Fi, cellular, motion sensors, and business context.
- Step-up verification for high-risk location-sensitive actions.
- Treating jailbreak, mock location, and hooking checks as one layer rather than sufficient proof.

Core idea:

> No single signal can prove that a mobile device's reported location is real. Location trust should be scored from the consistency of device, network, behavior, and historical trajectory signals.

## Development

Backend:

```bash
cd proxy
python setup-venv.py
python run-local.py
```

On Windows, if `python` is not Python 3.11 or newer, use:

```powershell
py -3 setup-venv.py
py -3 run-local.py
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Build frontend static files:

```bash
cd web
npm run build
```

The build output is written to `proxy/gsloc_proxy/static/`, which is not tracked by default.

Docker image builds are checked by GitHub Actions on pull requests to `develop`. Pushes to `develop` and version tags such as `v0.1.0` publish multi-arch `linux/amd64` and `linux/arm64` images to GitHub Container Registry as `ghcr.io/<owner>/<repo>`.

## License

This project is released under the MIT License.

The MIT License describes software copyright permissions only. It does not imply that the maintainers approve of unauthorized, unlawful, or third-party-infringing use. Users are responsible for ensuring that their test environment, devices, accounts, network, and target apps are legally authorized and compliant with applicable laws and regulations.
