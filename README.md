# redeploy-node-api
A simple Python FastAPI server for automatically redeploying Slurm nodes when a newer image is available on MAAS. The API accepts POST requests to /redeploy, where it checks the currently deployed image for a given node, and triggers redeployment with the latest image if available. This implementation assumes a image name of <`prefix`>-vX.Y.Z (e.g Noble-Prod-v2.0.0), but this logic can be modified for other naming schemes.

This application expects a .env file with the following values:
```
MAAS_HOST=http://<MAAS-IP>/MAAS
API_KEY=<MAAS API KEY> #Should be 3 values seperated by ":". Can be found in the MAAS GUI
API_TOKEN=supersecrettoken #token for slurm endpoints to use 
USER_DATA = <base64 encoded cloud-init user data>
```

Run the application with
```
AUTHLIB_INSECURE_TRANSPORT=1 uvicorn redeploy-node-api:app --host 0.0.0.0 --port 8080
```

Or use systemd:
```
[Unit]
Description=Redeploy Node API FastAPI service
After=snap.maas.pebble.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/redeploy-node-api/src

EnvironmentFile=/home/ubuntu/redeploy-node-api/src/.env

Environment=AUTHLIB_INSECURE_TRANSPORT=1

ExecStart=/home/ubuntu/redeploy-node-api/.venv/bin/uvicorn redeploy-node-api:app --host 0.0.0.0 --port 8080

Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target

```

This application should be called by the RebootProgram defined in slurm.