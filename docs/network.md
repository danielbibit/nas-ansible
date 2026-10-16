# Network Access

This NAS setup supports three complementary methods for remote access: DDNS, Cloudflare Tunnel, and Tailscale. They can be used independently or together.

## Overview

```mermaid
graph TD
    Internet -->|Dynamic IP| CF_DNS[Cloudflare DNS]
    NAS -->|Updates IP| DDNS[cloudflare-ddns container]
    DDNS -->|PATCH record| CF_DNS

    Internet -->|HTTPS public traffic| CF_EDGE[Cloudflare Edge]
    CF_EDGE -->|Encrypted tunnel| Cloudflared[cloudflared container]
    Cloudflared -->|https://traefik:443| Traefik
    Traefik --> Services[Internal Services]

    User -->|WireGuard, peer-to-peer| NAS_Host[NAS Host]
    NAS_Host --> Services
```

| Method | Visibility | Firewall ports required | Use case |
|---|---|---|---|
| DDNS | Public | Yes (80/443) | Direct DNS resolution to NAS IP |
| Cloudflare Tunnel | Public | None | Expose services without open ports |
| Tailscale | Private | None | Personal VPN access |

---

## DDNS

**Role:** `roles/cloudflare_ddns/`

Keeps a Cloudflare DNS A record pointing at the NAS's dynamic public IP. The `oznu/cloudflare-ddns` container polls for IP changes and patches the record via the Cloudflare API.

```mermaid
graph LR
    IP[Public IP changes] --> Container[cloudflare-ddns polls]
    Container -->|PATCH A record| CF[Cloudflare DNS]
    CF --> Domain[subdomain.zone resolves to NAS]
```

### Variables

| Variable | Description |
|---|---|
| `cloudflare_ddns_enabled` | Enable the role (default: `false`) |
| `cloudflare_ddns_api_key` | Cloudflare API token with DNS edit permissions |
| `cloudflare_ddns_zone` | DNS zone (e.g. `example.com`) |
| `cloudflare_ddns_subdomain` | Subdomain to keep updated (e.g. `nas`) |
| `cloudflare_ddns_proxy` | Whether to proxy through Cloudflare (`"true"`/`"false"`) |

The container is attached to the `nas` Docker network.

---

## Cloudflare Tunnel

**Role:** `roles/cloudflared/`

Exposes selected services publicly without opening any firewall ports. Traffic flows from the browser through Cloudflare's edge network into the NAS via an outbound-only encrypted tunnel.

### Ansible setup flow

```mermaid
graph TD
    Playbook[cloudflared role] -->|Cloudflare API| CNAME[Create CNAME records\nsubdomain → tunnel-id.cfargotunnel.com]
    Playbook -->|Cloudflare API| SSL[Enforce Always Use HTTPS\n+ SSL mode Full]
    Playbook -->|Cloudflare API| Config[Set remote tunnel config\ningress rules → https://traefik:443]
    Playbook --> Container[Deploy cloudflared container]
```

The tunnel is remotely managed: no config file is written on the NAS. The role pushes the ingress
rules to the Cloudflare API, one rule per public hostname, followed by a catch-all `http_status:404`.
Each rule rewrites the `Host` header to `<subdomain>.<cloudflared_internal_domain>`, so Traefik
matches the request against its usual internal routes.

> **Note:** "Always Use HTTPS" and SSL mode "Full" are zone-wide settings, they apply to every
> record in `cloudflared_cf_zone`, not only to the tunnel hostnames.

When `cloudflared_enabled` is `false`, the role tears down the container and removes the CNAME records.

### Traffic flow

```mermaid
graph LR
    Browser -->|HTTPS| CF_Edge[Cloudflare Edge]
    CF_Edge -->|Encrypted tunnel| cloudflared[cloudflared container]
    cloudflared -->|https://traefik:443| Traefik
    Traefik -->|route by hostname| Service[Internal service]
```

### Variables

| Variable | Description |
|---|---|
| `cloudflared_enabled` | Enable the role (default: `false`) |
| `cloudflared_token` | Tunnel token (base64-encoded JSON, see below) |
| `cloudflared_public_hostnames` | List of subdomains to expose via the tunnel (e.g. `["jellyfin"]`, not FQDNs) |
| `cloudflared_ingress_service` | Backend for tunnel ingress (default: `https://traefik:443`) |
| `cloudflared_no_tls_verify` | Skip TLS verification toward Traefik (default: `true`) |
| `cloudflared_cf_zone` | Cloudflare zone for DNS automation (defaults to `cloudflare_ddns_zone`) |
| `cloudflared_cf_api_token` | Cloudflare API token for DNS automation (defaults to `cloudflare_ddns_api_key`) |
| `cloudflared_internal_domain` | Internal domain used by Traefik (defaults to `traefik_domain`) |

### Token format

`cloudflared_token` is a base64-encoded JSON object containing:

- `.t` — tunnel ID (UUID)
- `.a` — account ID

The token is issued from the Cloudflare Zero Trust dashboard when creating a tunnel.

---

## Tailscale

**Roles:** `roles/tailscale/` (NAS, Docker) and `roles/tailscale_native/` (Proxmox hosts, no Docker)

Provides private WireGuard-based VPN access to the NAS. No services are exposed publicly; access is restricted to devices enrolled in the same Tailscale network.

```mermaid
graph LR
    Device[User device\nTailscale client] -->|WireGuard, peer-to-peer or DERP relay| NAS[NAS host]
    Coord[Tailscale coordination server] -.->|keys and peer discovery| Device
    Coord -.->|keys and peer discovery| NAS
    NAS --> Services[All internal services]
```

Data flows directly between devices over WireGuard; the coordination server only exchanges keys and
endpoints, falling back to a DERP relay when a direct connection is not possible.

### Docker role (NAS)

The container runs with `network_mode: host`, giving it direct access to the NAS network stack. It requires the `NET_ADMIN` and `NET_RAW` capabilities and the `/dev/net/tun` device.

### Variables

| Variable | Description |
|---|---|
| `tailscale_enabled` | Enable the role (default: `false`) |
| `tailscale_authkey` | Tailscale auth key for device registration |
| `tailscale_hostname` | Hostname advertised to the Tailscale network |
| `tailscale_routes` | Subnet routes to advertise (e.g. `192.168.1.0/24`) |
| `tailscale_extra_args` | Additional arguments passed to `tailscale up` |

### Native role (Proxmox hosts)

`roles/tailscale_native/` is used by `playbooks/proxmox.yml` for machines without Docker. It installs
Tailscale from the official apt repository, runs `tailscaled` on the host, and logs in with
`tailscale up` only when the node is not already connected. IP forwarding is enabled automatically
when routes are advertised.

| Variable | Description |
|---|---|
| `tailscale_native_enabled` | Enable the role (default: `true`) |
| `tailscale_native_authkey` | Auth key, only used for the first login |
| `tailscale_native_hostname` | Hostname advertised to the Tailscale network (defaults to the machine hostname) |
| `tailscale_native_advertise_routes` | List of subnets to advertise (e.g. `["192.168.10.0/24"]`) |
| `tailscale_native_accept_routes` | Accept routes advertised by other nodes (default: `false`) |
