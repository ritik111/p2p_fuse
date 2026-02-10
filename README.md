P2P FUSE Distributed Storage

A lightweight, decentralized storage solution that allows devices on the same network to discover each other and share disk space securely.
 Features

     Auto-Discovery: Clients use UDP broadcasting to find available storage servers on the network automatically.

     FUSE Integration: Mount remote storage as a local folder. Use standard commands like ls, cp, mv, and rm just like a local disk.

     Encrypted Transfer: All file data is encrypted/decrypted on-the-fly using an XOR Cipher with a unique persistent key.

     Multi-Threaded Server: The server can handle multiple client requests by spinning up dedicated service threads on dynamic ports.

     Metadata Caching: High-performance client-side caching to minimize network latency during directory traversal.

     Path Sanity: Server-side checks prevent "Path Traversal" attacks to ensure clients only access their designated storage folders.

 Architecture

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

 Getting Started
Prerequisites

    Linux (FUSE support is native).

    Python 3.x

    fusepy library: pip install fusepy (optional, there is a fuse.py file in the client directory)

Server Setup

    cd server
    python3 s.py
    
Client Setup
    cd client
    python3 c.py

 Configuration & Commands
Protocol Details
Protocol	Port	Function
UDP	4444	Server Discovery & Handshake
TCP	Dynamic	File Data Transfer (Assigned by Server)
Deployment (Background)

To run the services in the background and log output:

Server:
Bash

    chmod +x ./server_install.sh
    ./server_install.sh

Client:
Bash

    chmod +x ./client_install.sh
    ./client_install.sh

Security & Encryption

The system uses a Rolling XOR Cipher.

    Key Generation: A unique 5-digit key is generated for every new server connection and saved to a _key.txt file.

    Offset-Aware: To support random access (seeking) within a file, the XOR cipher uses the file offset to align the key correctly:
    CipherByte=DataByte⊕Key[(i+offset)(modKeyLength)]

 Roadmap

    [ ] Support for AES-256 encryption.

    [ ] Implementation of file caching for faster getattr calls.

    [ ] User authentication (Username/Password) during handshake.

    [ ] Support for Windows via WinFsp.
