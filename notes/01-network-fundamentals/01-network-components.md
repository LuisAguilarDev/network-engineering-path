# 1.1 Network Components

> **Exam objective:** 1.1 Explain the role and function of network components
> **Domain:** 1. Network Fundamentals (20%)
> **Prerequisite:** [0.1 The OSI and TCP/IP Models](../00-base-knowledge/01-osi-and-tcpip-models.md) — explains what "Layer 2" and "Layer 3" mean

## The Big Picture

Every component has one job in moving data from an endpoint to a service and back.

```
                         INTERNET
                            │
                     ┌──────┴──────┐
                     │   Router    │  Connects different networks (L3)
                     └──────┬──────┘
                     ┌──────┴──────┐
                     │ NGFW / IPS  │  Decides what traffic is allowed
                     └──────┬──────┘
                     ┌──────┴──────┐        ┌─────────────────────┐
                     │  L3 Switch  │────────│ WLC / DNA Center    │  Central management
                     └──┬───────┬──┘        └─────────────────────┘
              ┌─────────┘       └─────────┐
        ┌─────┴─────┐               ┌─────┴─────┐
        │ L2 Switch │               │ L2 Switch │  Connect devices in the same LAN
        └─┬───┬───┬─┘               └─┬───────┬─┘
          │   │   │ PoE               │       │
         PC  IP  AP ))) Laptop      Server  Printer
            Phone
```

---

## 1.1.a Routers

**Role:** Connect **different** IP networks and forward packets between them.

- Operate at **Layer 3** (Network) and make decisions using **IP addresses**
- Use a **routing table** to choose the best path. Most specific match wins (longest prefix match)
- **Each router interface is its own broadcast domain**: routers do not forward broadcasts
- Usually the **default gateway** for the hosts in a LAN
- Common extra services: NAT, DHCP, ACLs, VPN, WAN connections

**Analogy:** A post office that reads the city on the envelope (IP network) and sends it to the next post office on the route.

> 🧠 **Quiz:** [Test yourself on 1.1.a](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-a)

---

## 1.1.b Layer 2 and Layer 3 Switches

### Layer 2 switch

**Role:** Connect devices **inside the same LAN/VLAN** and forward frames between them.

- Operates at **Layer 2** (Data Link) and makes decisions using **MAC addresses**
- Builds a **MAC address table** (CAM table) by learning the **source** MAC of each incoming frame
- Forwarding logic:

| Frame destination | Switch action |
|-------------------|---------------|
| Known unicast MAC | **Forward** only out the matching port |
| Unknown unicast MAC | **Flood** out all ports except the incoming one |
| Broadcast (`FFFF.FFFF.FFFF`) | **Flood** out all ports in the VLAN except the incoming one |

- **Each switch port is its own collision domain**
- **All ports in the same VLAN are one broadcast domain**

### Layer 3 switch (multilayer switch)

**Role:** A switch that **can also route**, usually between VLANs.

- Routes between VLANs using **SVIs** (Switched Virtual Interfaces, `interface vlan 10`)
- Can turn a port into a **routed port** (`no switchport`)
- Routing happens in hardware (ASICs), so it is very fast inside the campus
- Typically has fewer WAN/edge features than a dedicated router

| | L2 Switch | L3 Switch | Router |
|---|-----------|-----------|--------|
| Decides with | MAC | MAC + IP | IP |
| Inter-VLAN routing | ❌ | ✅ | ✅ |
| Typical place | Access layer | Distribution / core | Network edge / WAN |

> 🧠 **Quiz:** [Test yourself on 1.1.b](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-b)

---

## 1.1.c Next-Generation Firewalls and IPS

### Firewall

**Role:** Control which traffic may pass between security **zones** (inside, outside, DMZ).

- **Stateful**: tracks active connections, so return traffic for a session opened from inside is allowed automatically
- Default behavior: traffic from a lower-security zone (outside) to a higher one (inside) is **denied unless explicitly permitted**

### IPS (Intrusion Prevention System)

**Role:** Inspect traffic for known attacks and **block them in real time**.

- Sits **inline**: traffic flows through it
- Detects attacks mainly with **signatures** (patterns of known threats)
- **IDS** vs **IPS**: an IDS only receives a **copy** of the traffic and **alerts**; an IPS is inline and can **drop** traffic

### Next-Generation Firewall (NGFW)

A stateful firewall **plus** deeper inspection, all in one device (e.g. Cisco Secure Firewall / Firepower):

- **Application Visibility and Control (AVC)**: identifies apps (e.g. allows Teams but blocks games), not just ports
- **Integrated NGIPS**: IPS that uses context about the network (OS, apps, users) to prioritize threats
- **URL filtering**: blocks website categories
- **Advanced Malware Protection (AMP)**: detects malicious files

> 🧠 **Quiz:** [Test yourself on 1.1.c](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-c)

---

## 1.1.d Access Points (APs)

**Role:** Connect wireless clients (802.11 / Wi-Fi) to the wired network.

- Acts as a **bridge** between the wireless and the wired (Ethernet) network
- Advertises one or more **SSIDs** (wireless network names)
- Usually powered by **PoE** from the switch
- Deployment modes:

| Mode | Managed by | Notes |
|------|------------|-------|
| **Autonomous** | Itself | Each AP configured one by one. Fine for small networks |
| **Lightweight** | **WLC** | Tunnels traffic to the WLC using **CAPWAP** |
| **Cloud-based** | Cloud dashboard | e.g. Cisco Meraki |

> 🧠 **Quiz:** [Test yourself on 1.1.d](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-d)

---

## 1.1.e Controllers (Cisco DNA Center and WLC)

### WLC (Wireless LAN Controller)

**Role:** Centrally manage many **lightweight APs**.

- Handles configuration, RF management (channels, power), authentication, and roaming
- **Split-MAC architecture**: the AP handles real-time tasks (sending frames, beacons); the WLC handles management tasks
- APs and WLC talk through a **CAPWAP** tunnel:
  - UDP **5246**: control (encrypted with DTLS)
  - UDP **5247**: data

### Cisco DNA Center

**Role:** An **SDN controller** that manages the whole enterprise network (wired and wireless) from one place.

- Basis of Cisco's **intent-based networking**: you define *what* you want and it configures the devices
- **Northbound API** (REST): apps and scripts talk **to** DNA Center
- **Southbound** protocols (SSH, NETCONF, SNMP): DNA Center talks **to** the devices
- Provides automation, monitoring, and analytics (Assurance)

> Cisco renamed DNA Center to **Catalyst Center** in 2023. The exam blueprint still says DNA Center.

> 🧠 **Quiz:** [Test yourself on 1.1.e](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-e)

---

## 1.1.f Endpoints

**Role:** The devices at the **edge** of the network that **create or consume data**. They are where communication starts and ends.

- Examples: PCs, laptops, smartphones, IP phones, printers, IP cameras, IoT sensors
- Need an IP address, subnet mask, default gateway, and DNS server to communicate outside their LAN

> 🧠 **Quiz:** [Test yourself on 1.1.f](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-f)

---

## 1.1.g Servers

**Role:** Devices (or software) that **provide services** to clients.

- Examples: web, email, file, DNS, DHCP, database servers
- **Client-server model**: clients request, servers respond
- "Server" describes a **role**, not specific hardware: a laptop running a web service is a server for that service
- Often run as **virtual machines** or containers in a data center or the cloud

> 🧠 **Quiz:** [Test yourself on 1.1.g](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-g)

---

## 1.1.h PoE (Power over Ethernet)

**Role:** Deliver **electrical power and data over the same Ethernet cable**.

- **PSE** (Power Sourcing Equipment): provides power, usually the switch
- **PD** (Powered Device): receives power, e.g. AP, IP phone, IP camera
- Benefit: no power outlet needed where the device is mounted (ceilings, walls)
- The PSE first **detects** that a PoE device is connected before sending power, so non-PoE devices are safe
- A switch has a total **power budget**; it can't power every port at max at the same time

| Standard | Name | Power at PSE (switch port) |
|----------|------|----------------------------|
| 802.3af | PoE | 15.4 W |
| 802.3at | PoE+ | 30 W |
| 802.3bt Type 3 | UPoE | 60 W |
| 802.3bt Type 4 | UPoE+ | 90 W |

> 🧠 **Quiz:** [Test yourself on 1.1.h](https://luisaguilardev.github.io/network-engineering-path/notes/01-network-fundamentals/quizzes/01-network-components.html#q-1-1-h)

---

## Key Takeaways

- **Router** = connects different networks using IP. **Switch** = connects devices in a LAN using MAC
- **L3 switch** = switch + routing, ideal for inter-VLAN routing in the campus
- **NGFW** = stateful firewall + application awareness + IPS + URL filtering + malware protection
- **Lightweight APs** need a **WLC** and talk to it via **CAPWAP**
- **DNA Center** = SDN controller: REST northbound, SSH/NETCONF/SNMP southbound
- **PoE** lets a switch (PSE) power APs, phones, and cameras (PDs)

## Exam Traps

- ⚠️ Switches learn the **source** MAC but forward based on the **destination** MAC
- ⚠️ Routers **break** broadcast domains; switches **break** collision domains (but not broadcast domains)
- ⚠️ **IDS** = passive copy, alerts only. **IPS** = inline, can block
- ⚠️ Northbound = controller ⇄ **apps**. Southbound = controller ⇄ **devices**
- ⚠️ PoE values to memorize: **15.4 W** (af), **30 W** (at), **60 W** / **90 W** (bt)
- ⚠️ CAPWAP control is **5246**, data is **5247**, both UDP
