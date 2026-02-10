P2P FUSE Distributed Storage

A lightweight, decentralized storage solution that allows devices on the same network to discover each other and share disk space securely.
✨ Features

    🔍 Auto-Discovery: Clients use UDP broadcasting to find available storage servers on the network automatically.

    📂 FUSE Integration: Mount remote storage as a local folder. Use standard commands like ls, cp, mv, and rm just like a local disk.

    🔐 Encrypted Transfer: All file data is encrypted/decrypted on-the-fly using an XOR Cipher with a unique persistent key.

    ⚡ Multi-Threaded Server: The server can handle multiple client requests by spinning up dedicated service threads on dynamic ports.

    🛡️ Path Sanity: Server-side checks prevent "Path Traversal" attacks to ensure clients only access their designated storage folders.

🏗️ Architecture

The system consists of two primary components:
1. The Client (c.py)

    Broadcasts a UDP request for storage.

    Mounts a FUSE filesystem once a server is found.

    Intercepts system calls (read, write, mkdir) and forwards them to the server via TCP.

    Handles encryption/decryption locally so the server never sees raw data.

2. The Server (s.py)

    Listens for UDP broadcasts on port 4444.

    Checks disk availability against client requirements.

    Isolated Storage: Creates a unique directory client_storage_[IP] for every connecting client.

    Persistent Execution: Designed to run as a background service.

🚀 Getting Started
Prerequisites

    Linux (FUSE support is native).

    Python 3.x

    fusepy library: pip install fusepy

Server Setup

    Open port 4444 for discovery:
    Bash

    sudo ufw allow 4444/udp

    Run the server:
    Bash

    python3 s.py

Client Setup

    Create a mount point (if not created automatically):
    Bash

    mkdir ~/p2p_storage

    Run the client:
    Bash

    python3 c.py

    Navigate to p2p_storage to start using remote disk space!

🛠️ Configuration & Commands
Protocol Details
Protocol	Port	Function
UDP	4444	Server Discovery & Handshake
TCP	Dynamic	File Data Transfer (Assigned by Server)
Deployment (Background)

To run the services in the background and log output:

Server:
Bash

nohup python3 s.py > server_log.log 2>&1 &

Client:
Bash

nohup python3 c.py > client_log.log 2>&1 &

🔒 Security Note

This project uses an XOR Cipher for demonstration. While it prevents casual snooping of the files on the server's disk, it is not a replacement for industry-standard encryption like AES for production environments.
📜 Roadmap

    [ ] Support for AES-256 encryption.

    [ ] Implementation of file caching for faster getattr calls.

    [ ] User authentication (Username/Password) during handshake.

    [ ] Support for Windows via WinFsp.
