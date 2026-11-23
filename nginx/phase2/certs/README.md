# Edge certificates (not committed)

Both edges (primary on Mac 2, standby on Mac 4) load their certificate from
this folder, relative to the nginx config:

```
nginx/phase2/certs/team1-server.crt   # server cert, SAN = app.team1.test, api.team1.test
nginx/phase2/certs/team1-server.key   # private key (git-ignored, never commit)
```

Copy the SAME Phase 1 files into this folder on **both** Mac 2 and Mac 4:

```bash
cp /path/to/team1-server.crt /path/to/team1-server.key nginx/phase2/certs/
chmod 600 nginx/phase2/certs/team1-server.key
```

Copy the key to Mac 4 with AirDrop or `scp` — not through GitHub.

Why the same certificate works on both edges: the certificate is issued to the
**name** `app.team1.test` (Subject Alternative Name), not to an IP address.
The client checks the name it typed against the SAN, so after the DNS cutover
the standby edge passes validation without any changes on the client.
