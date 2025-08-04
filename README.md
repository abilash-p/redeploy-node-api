# redeploy-node-api
A simple Python FastAPI server for automatically redeploying Slurm nodes when a newer image is available on MAAS. The API accepts POST requests to /redeploy, checks the currently deployed image for a given node, and triggers redeployment with the latest image if available.
