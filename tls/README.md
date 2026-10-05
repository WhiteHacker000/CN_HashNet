# TLS / SSL Security Architecture & Certificate Infrastructure

## 📌 Overview
To achieve secure end-to-end HTTPS communication without triggering browser warning prompts or requiring the `-k` (insecure) flag in `curl`, a custom **Local Certificate Authority (CA)** infrastructure was implemented for Team 1.

TLS is terminated at the edge proxy (**Mac 2: 10.7.28.232**) on port `8443`.

---

## 🔐 Certificate Trust Chain & Architecture

```
┌────────────────────────────────────────────────────────┐
│               Team 1 Local Root CA                     │
│           (Self-signed Root Authority)                 │
└──────────────────────────┬─────────────────────────────┘
                           │ Signs
                           ▼
┌────────────────────────────────────────────────────────┐
│           Team 1 Edge Server Certificate               │
│  CN = app.team1.test                                   │
│  Subject Alternative Names (SAN):                      │
│    - DNS.1 = app.team1.test                            │
│    - DNS.2 = api.team1.test                            │
└──────────────────────────┬─────────────────────────────┘
                           │ Presented by Mac 2 on Port 8443
                           ▼
┌────────────────────────────────────────────────────────┐
│              Client macOS Trust Store                  │
│       (System Keychain trusted Root Authority)         │
│          Result: Clean Green Padlock / No -k           │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ OpenSSL Generation Commands (Reproducible Procedure)

### 1. Generate Local Root Certificate Authority (CA)
```bash
# Generate 4096-bit Root CA Private Key (Kept local, never committed)
openssl genrsa -out team1-ca.key 4096

# Create self-signed Root CA Certificate
openssl req -x509 -new -nodes -key team1-ca.key -sha256 -days 365 \
  -out team1-ca.crt \
  -subj "/C=US/ST=State/L=Campus/O=Team1-Networking/OU=Security/CN=Team1-Root-CA"
```

### 2. Generate Server Certificate & CSR with SAN
```bash
# Generate 2048-bit Server Private Key (Kept local on Mac 2)
openssl genrsa -out team1-server.key 2048

# Create OpenSSL configuration for Subject Alternative Names
cat <<EOF > server_san.cnf
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = US
ST = State
L = Campus
O = Team1-Networking
CN = app.team1.test

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = app.team1.test
DNS.2 = api.team1.test
EOF

# Generate Certificate Signing Request (CSR)
openssl req -new -key team1-server.key -out team1-server.csr -config server_san.cnf

# Sign Server Certificate using Team 1 Root CA
openssl x509 -req -in team1-server.csr -CA team1-ca.crt -CAkey team1-ca.key \
  -CAcreateserial -out team1-server.crt -days 365 -sha256 \
  -extfile server_san.cnf -extensions req_ext
```

---

## 💻 Installing Root CA on Client macOS Laptops

To allow macOS browsers (Safari, Chrome) and `curl` to natively trust `https://app.team1.test:8443` without certificate warnings:

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain team1-ca.crt
```

---

## 🔒 Repository Security Notice
In accordance with security best practices:
- **Private keys (`team1-ca.key`, `team1-server.key`) are strictly excluded from this repository via `.gitignore`.**
- Only public certificates and configuration templates are tracked in Git.
