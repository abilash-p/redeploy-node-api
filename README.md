# redeploy-node-api
A simple Python FastAPI server for automatically redeploying Slurm nodes when a newer image is available on MAAS. The API accepts POST requests to /redeploy, checks the currently deployed image for a given node, and triggers redeployment with the latest image if available.


This application expects a .env file with the following values:
```
MAAS_HOST=http://<MAAS-IP>/MAAS
API_KEY=<MAAS API KEY> #Should be 3 values seperated by ":". Can be found in the MAAS GUI
API_TOKEN=supersecrettoken #token for slurm endpoints to use 

```

Run the application with
```
AUTHLIB_INSECURE_TRANSPORT=1 uvicorn redeploy-node-api:app --host 0.0.0.0 --port 8080
```