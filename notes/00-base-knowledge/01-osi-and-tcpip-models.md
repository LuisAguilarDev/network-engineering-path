# 0.1 The OSI and TCP/IP Models (Layers)

> **Why this note exists:** Every CCNA topic says things like "Layer 2 switch", "Layer 3 routing" or "Layer 4 port".
> Those numbers come from the **OSI model**. Learn this first and the rest of the notes make sense.
> **Exam relevance:** Not a numbered objective, but it is used in almost every question.

## The Big Picture

```
 Layer  Name           What it does (one line)                 Unit (PDU)   Address / ID     Example
 ─────  ─────────────  ──────────────────────────────────────  ───────────  ───────────────  ─────────────────
   7    Application    Protocols that apps use to talk          Data         —                HTTP, DNS, SSH
   6    Presentation   Format, encrypt, compress the data       Data         —                UTF-8, JPEG, TLS
   5    Session        Open, keep, and close conversations      Data         —                RPC, NetBIOS
   4    Transport      Deliver to the right app (process)       Segment      Port number      TCP, UDP
   3    Network        Deliver across different networks        Packet       IP address       IPv4, IPv6
   2    Data Link      Deliver to the next device on the LAN    Frame        MAC address      Ethernet, Wi-Fi
   1    Physical       Move bits as signals over a medium       Bits         —                Cables, radio
```

Think of it as **a team of 7 specialists**. Each one does one job and trusts the others to do theirs.
When you send something, the data goes **down** the layers on your computer, travels as bits, and goes **up** the layers on the other computer.

```
   Your PC                                          Server
 ┌───────────┐                                   ┌───────────┐
 │ 7 App     │  ── each layer "talks" to the ──► │ 7 App     │
 │ 6 Pres    │     same layer on the other side  │ 6 Pres    │
 │ 5 Session │                                   │ 5 Session │
 │ 4 Trans   │                                   │ 4 Trans   │
 │ 3 Network │                                   │ 3 Network │
 │ 2 Link    │                                   │ 2 Link    │
 │ 1 Phys    │ ═════════ bits on the wire ══════ │ 1 Phys    │
 └───────────┘                                   └───────────┘
   data goes DOWN                                   data goes UP
```

Mnemonics to remember the order:

- **1 → 7:** **P**lease **D**o **N**ot **T**hrow **S**ausage **P**izza **A**way (Physical, Data Link, Network, Transport, Session, Presentation, Application)
- **7 → 1:** **A**ll **P**eople **S**eem **T**o **N**eed **D**ata **P**rocessing

---

## 0.1.a Why Networks Use Layered Models

**Problem:** Sending data between two computers involves many unrelated problems: cables, addressing, routing, reliability, encryption, the app format. Solving all of that in one piece of software would be a mess.

**Solution:** Split the work into **layers**. Each layer:

- Has **one job**
- Gives a **service** to the layer above and uses the layer below
- Can change without breaking the others (you can switch from copper to Wi-Fi without changing your web browser)

Benefits:

- **Standards:** vendors (Cisco, Juniper, Microsoft…) build products that work together
- **Troubleshooting:** you can check one layer at a time ("Is the cable OK? Layer 1. Do I have an IP? Layer 3.")
- **Shared language:** "Is it a Layer 2 or a Layer 3 problem?" tells another engineer exactly where to look

**Analogy:** Building a house. The electrician, the plumber, and the painter each do their own job. The painter doesn't need to know how the wiring works, only that the walls are ready.

> 🧠 **Quiz:** [Test yourself on 0.1.a](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-a)

---

## 0.1.b Layer 1: Physical

**Job:** Move **bits** (1s and 0s) from one device to the next as physical **signals**.

- It does not understand addresses or data, only "1" and "0"
- Signal types:
  - **Electrical** pulses over **copper** (Ethernet UTP cable, RJ45 connector)
  - **Light** pulses over **fiber optic** cable
  - **Radio** waves over the air (Wi-Fi)
- Defines: cables, connectors, pin-outs, voltages, speeds (100 Mbps, 1 Gbps…), and maximum cable length
- **Devices:** cables, connectors, **hubs**, **repeaters**, the physical port of a NIC
- A **hub** just repeats the bits out of every port. All its ports share one collision domain (that's why switches replaced hubs)

**Typical Layer 1 problems:** unplugged or broken cable, bad connector, cable too long, interference, port shut down.

**Analogy:** The road. It doesn't care what the trucks carry or where they go, it just has to be there and be in good shape.

> 🧠 **Quiz:** [Test yourself on 0.1.b](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-b)

---

## 0.1.c Layer 2: Data Link

**Job:** Deliver data to the **next device on the same local network** (LAN). One hop at a time.

- Uses **MAC addresses**: 48-bit physical addresses burned into every network card
  - Written in hex, e.g. `AAAA.BBBB.0001` (Cisco format) or `AA-AA-BB-BB-00-01` (Windows format)
  - Broadcast MAC: `FFFF.FFFF.FFFF` = "everyone on this LAN"
- Unit of data: **frame**

```
 ┌──────────────┬─────────────┬──────┬───────────────────────┬─────┐
 │ Dest MAC     │ Source MAC  │ Type │ Payload (the packet)  │ FCS │
 └──────────────┴─────────────┴──────┴───────────────────────┴─────┘
      header ───────────────────────►                          trailer
```

- **FCS** (Frame Check Sequence): a checksum. If the frame arrives corrupted, the receiver **drops it** (Layer 2 detects errors, it does not resend)
- Protocols: **Ethernet** (IEEE 802.3, wired) and **Wi-Fi** (IEEE 802.11, wireless)
- **Devices:** **switches**, access points (bridge wireless and wired), NICs
- MAC addresses are only **local**: they are used to reach the next device and are replaced at every router

**Analogy:** The delivery truck inside one neighborhood. It knows the exact house (MAC), but it never leaves the neighborhood.

> 🧠 **Quiz:** [Test yourself on 0.1.c](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-c)

---

## 0.1.d Layer 3: Network

**Job:** Deliver data **end to end**, from the source host to the destination host, **across different networks**.

- Uses **IP addresses** (IPv4 like `192.168.1.10`, or IPv6): **logical** addresses that you configure and that show which network a host belongs to
- Unit of data: **packet**
- **Routing:** choosing the path from one network to another, hop by hop, using a **routing table**
- The IP header carries **source IP**, **destination IP**, and **TTL** (Time To Live: reduced by 1 at each router so packets can't loop forever)
- Protocols: **IPv4**, **IPv6**, **ICMP** (`ping`, `traceroute`), routing protocols like **OSPF**
- **Devices:** **routers** and **Layer 3 switches**

### MAC vs IP: the key idea

When a packet crosses routers, the **IP addresses stay the same** from start to end, but the **MAC addresses change at every hop**:

```
  PC ──── Router A ──── Router B ──── Server

  IP:  PC  → Server   (same on every link)
  MAC: PC  → A        A → B        B → Server   (new frame on each link)
```

**Analogy:** IP = the full postal address on the envelope (city, street). MAC = the name of the next truck driver. The envelope keeps the same address the whole trip, but it changes trucks many times.

> 🧠 **Quiz:** [Test yourself on 0.1.d](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-d)

---

## 0.1.e Layer 4: Transport

**Job:** Deliver data to the **right application (process)** on the host, and decide **how** to deliver it (reliable or fast).

- Layer 3 gets the packet to the right **computer**; Layer 4 gets it to the right **program** on that computer
- Uses **port numbers** (0–65535) to identify applications:

| Port | Protocol | Used for |
| ---- | -------- | -------- |
| 22   | TCP      | SSH      |
| 53   | UDP/TCP  | DNS      |
| 80   | TCP      | HTTP     |
| 443  | TCP      | HTTPS    |

- **Socket** = IP address + port (e.g. `192.168.1.10:51000` → `203.0.113.5:443`)
- **Segmentation:** splits big data into smaller pieces and numbers them so they can be put back together
- Two main protocols:

|                              | TCP                                      | UDP                             |
| ---------------------------- | ---------------------------------------- | ------------------------------- |
| Connection                   | Yes (3-way handshake: SYN, SYN-ACK, ACK) | No                              |
| Reliable (resends lost data) | ✅                                       | ❌                              |
| Keeps order                  | ✅                                       | ❌                              |
| Overhead / speed             | More / slower                            | Less / faster                   |
| Unit name                    | **Segment**                              | **Datagram**                    |
| Typical use                  | Web, email, SSH, file transfer           | Voice, video, DNS queries, DHCP |

**Analogy:** The receptionist of a building. The address got the letter to the building (Layer 3); the receptionist reads the apartment number (port) and gives it to the right person. TCP = registered mail with delivery confirmation. UDP = a normal postcard.

> 🧠 **Quiz:** [Test yourself on 0.1.e](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-e)

---

## 0.1.f Layer 5: Session

**Job:** **Open, manage, and close** the conversations (sessions) between two applications.

- Keeps different conversations separate (e.g. two browser tabs to the same site)
- Can add **checkpoints** so a long transfer can resume from the last checkpoint instead of starting again
- Examples: **RPC** (Remote Procedure Call), **NetBIOS**
- In real networks this job is usually done by the application itself or by TCP, so you rarely configure anything "at Layer 5"

**Analogy:** A phone call. Dialing, talking, and hanging up are managing the session.

> 🧠 **Quiz:** [Test yourself on 0.1.f](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-f)

---

## 0.1.g Layer 6: Presentation

**Job:** Make sure the data is in a **format both sides understand**. It's the translator.

- **Formatting / encoding:** text (ASCII, UTF-8), images (JPEG, PNG), video (MPEG)
- **Encryption / decryption:** e.g. **TLS/SSL** is often placed here (it's what puts the "S" in HTTPS)
- **Compression:** making data smaller before sending it
- Like Layer 5, in practice this is done inside the application or its libraries

**Analogy:** A translator who also puts the letter in a locked box (encryption) and folds it smaller (compression).

> 🧠 **Quiz:** [Test yourself on 0.1.g](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-g)

---

## 0.1.h Layer 7: Application

**Job:** Provide the **network protocols that applications use** to talk to each other.

- This is the layer the user's software interacts with
- ⚠️ Layer 7 is the **protocol**, not the program: **Chrome** is not Layer 7; **HTTP** (what Chrome uses) is
- Examples:

| Protocol     | What it does                                          |
| ------------ | ----------------------------------------------------- |
| HTTP / HTTPS | Web pages                                             |
| DNS          | Turns names (`example.com`) into IP addresses         |
| DHCP         | Gives IP addresses to hosts automatically             |
| SMTP / IMAP  | Send / read email                                     |
| SSH / Telnet | Remote command line (SSH is encrypted, Telnet is not) |
| FTP / TFTP   | File transfer                                         |
| SNMP         | Monitor network devices                               |

**Analogy:** The language and rules of a letter: "Dear…", the request, "Sincerely…". Both sides must follow the same format to understand each other.

> 🧠 **Quiz:** [Test yourself on 0.1.h](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-h)

---

## 0.1.i The TCP/IP Model

OSI is the **reference model** (used for teaching and talking). **TCP/IP** is the model the **real internet is built on**. They map like this:

```
        OSI (7)                   TCP/IP (4)            TCP/IP updated (5)
  ┌──────────────────┐       ┌──────────────────┐     ┌──────────────────┐
  │ 7 Application    │       │                  │     │                  │
  │ 6 Presentation   │  ──►  │   Application    │     │ 5 Application    │
  │ 5 Session        │       │                  │     │                  │
  ├──────────────────┤       ├──────────────────┤     ├──────────────────┤
  │ 4 Transport      │  ──►  │   Transport      │     │ 4 Transport      │
  ├──────────────────┤       ├──────────────────┤     ├──────────────────┤
  │ 3 Network        │  ──►  │   Internetwork   │     │ 3 Network        │
  ├──────────────────┤       ├──────────────────┤     ├──────────────────┤
  │ 2 Data Link      │  ──►  │   Network        │     │ 2 Data Link      │
  │ 1 Physical       │       │ (Network Access) │     │ 1 Physical       │
  └──────────────────┘       └──────────────────┘     └──────────────────┘
```

- TCP/IP merges OSI layers **5, 6, and 7** into a single **Application** layer
- The original TCP/IP model merges layers **1 and 2** into **Link** (also called Network Access); Cisco material often uses a 5-layer version that keeps them separate
- Engineers still use the **OSI numbers** when talking: "Layer 2 switch", "Layer 3 routing", "Layer 4 firewall rule", "Layer 7 inspection"

> 🧠 **Quiz:** [Test yourself on 0.1.i](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-i)

---

## 0.1.j Encapsulation and Decapsulation

When you send data, **each layer adds its own header** (and Layer 2 also a trailer) to what it got from the layer above. This is **encapsulation**. The receiver removes them in reverse order: **decapsulation**.

```
 Layer 7-5                          [        DATA        ]                    → Data
 Layer 4               [TCP/UDP hdr][        DATA        ]                    → Segment
 Layer 3       [IP hdr][TCP/UDP hdr][        DATA        ]                    → Packet
 Layer 2 [Eth hdr][IP hdr][TCP/UDP hdr][     DATA        ][FCS]               → Frame
 Layer 1  1011000101110101001010101110100010101011101010101...                → Bits
```

PDU names, top to bottom: **Data → Segment → Packet → Frame → Bits**
(memorize: "**D**o **S**ome **P**eople **F**ear **B**irthdays?")

### Example: you open `https://example.com`

1. **L7:** The browser builds an **HTTP** request (after **DNS** found the server's IP)
2. **L6:** **TLS** encrypts it
3. **L5:** The session to that server is kept open for the next requests
4. **L4:** **TCP** adds source port (random, e.g. 51000) and destination port **443**
5. **L3:** **IP** adds your IP as source and the server's IP as destination
6. **L2:** **Ethernet** adds your MAC as source and your **default gateway's MAC** as destination (the server is in another network, so the frame only goes to the router)
7. **L1:** The NIC sends the frame as electrical signals on the cable
8. Each router removes the frame, reads the IP, chooses the next hop, and builds a **new frame**
9. The server decapsulates from L1 up to L7 and reads the HTTP request

### The full flow, including devices in the middle

Data always goes **down** the layers on the sender and **up** on the receiver. When the server replies, the roles swap: the server goes down 7→1 and your PC goes up 1→7.

Devices in the path only go **up to the layer they need** to make their decision, then go back down:

```
   PC         Switch       Router       Switch       Server
  (sender)                                          (receiver)
   7 ↓                                                 ↑ 7
   6 ↓                                                 ↑ 6
   5 ↓                                                 ↑ 5
   4 ↓                                                 ↑ 4
   3 ↓                     ↑ 3 ↓                       ↑ 3
   2 ↓        ↑ 2 ↓        ↑ 2 ↓        ↑ 2 ↓          ↑ 2
   1 ↓ ══════ ↑ 1 ↓ ══════ ↑ 1 ↓ ══════ ↑ 1 ↓ ════════ ↑ 1
```

- **Switch:** opens up to L2, reads the destination **MAC**, sends the same frame out the right port
- **Router:** opens up to L3, reads the destination **IP**, throws away the old frame and builds a **new frame** for the next link
- **Endpoints** (PC and server) are the only ones that use all 7 layers

"Each layer talks to the same layer on the other side" is a **logical** conversation: TCP on the PC reads nothing but the header that TCP on the server wrote. The only thing that physically travels is **bits** at Layer 1.

> 🧠 **Quiz:** [Test yourself on 0.1.j](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-j)

---

## 0.1.k Which Layer Each Device Works At

A device "works at Layer N" when it makes its decisions using information from that layer.

| Device                | Highest layer it uses | Decides with                  |
| --------------------- | --------------------- | ----------------------------- |
| Cable, hub, repeater  | L1                    | Nothing, just repeats signals |
| Switch (L2)           | L2                    | MAC addresses                 |
| Access point          | L2                    | Bridges 802.11 ⇄ Ethernet     |
| Router                | L3                    | IP addresses                  |
| Layer 3 switch        | L3                    | MAC + IP                      |
| Traditional firewall  | L4                    | IP + ports                    |
| NGFW                  | L7                    | IP + ports + application      |
| Endpoints and servers | L7                    | Use all 7 layers              |

Now go back to [1.1 Network Components](../01-network-fundamentals/01-network-components.md): every "Layer 2" or "Layer 3" there refers to this table.

> 🧠 **Quiz:** [Test yourself on 0.1.k](https://luisaguilardev.github.io/network-engineering-path/notes/00-base-knowledge/quizzes/01-osi-and-tcpip-models.html#q-0-1-k)

---

## Key Takeaways

- **7 layers**, bottom to top: Physical, Data Link, Network, Transport, Session, Presentation, Application
- **L1** bits and signals · **L2** MAC + frames, local delivery · **L3** IP + packets, between networks · **L4** ports + TCP/UDP, to the right app
- **L5–L7** are usually handled by the application; TCP/IP merges them into one Application layer
- **Encapsulation:** each layer adds a header going down; decapsulation removes them going up
- **IP stays the same end to end; MAC changes at every router hop**

## Exam Traps

- ⚠️ PDU names: **Segment** (L4), **Packet** (L3), **Frame** (L2), **Bits** (L1). Don't mix packet and frame
- ⚠️ **Switch = L2 (MAC)**, **Router = L3 (IP)**, **Hub = L1**
- ⚠️ MAC addresses are **physical/local**; IP addresses are **logical** and routable
- ⚠️ **TCP** = reliable, connection-oriented. **UDP** = no connection, no resend, faster
- ⚠️ Layer 7 means the **protocol** (HTTP, DNS), not the app (Chrome, Outlook)
- ⚠️ TCP/IP **Application** layer = OSI **5 + 6 + 7**
