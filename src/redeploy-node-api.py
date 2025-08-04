from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, validator
from authlib.integrations.httpx_client import AsyncOAuth1Client
from dotenv import load_dotenv
import logging
import asyncio
import httpx
import os
import re
from packaging.version import Version, InvalidVersion

# === Load Environment ===
load_dotenv()

MAAS_HOST = os.getenv("MAAS_HOST")
API_KEY = os.getenv("API_KEY")
CONSUMER_KEY, CONSUMER_TOKEN, SECRET = API_KEY.split(":")
API_TOKEN = os.getenv("API_TOKEN") 

MAAS_READY_STATE = "Ready"

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redeploy-node-api")

# === FastAPI App ===
app = FastAPI()
maas_client: AsyncOAuth1Client = None

class RedeployRequest(BaseModel):
    system_id: str

    @validator("system_id")
    def must_not_be_empty(cls, v):
        if not v.strip(): 
            raise ValueError("system_id cannot be empty")
        return v

async def check_auth(api_token: str = Header(...)):
    if api_token != API_TOKEN:
        logger.warning("Unauthorized attempt with token: %s", api_token)
        raise HTTPException(status_code=401, detail="Invalid API key.")

# === MAAS API Logic ===

# Get machine details by system_id and returns the json response
async def get_machine(system_id: str):
    url = f"{MAAS_HOST}/api/2.0/machines/{system_id}/"
    resp = await maas_client.get(url)
    resp.raise_for_status()
    return resp.json()

# Gets the latest image version available in MAAS for the given current image name (I am following the naming convention of "prefix-vX.Y.Z")
# This function returns the latest image name with the highest version number.
# This function uses regex to extract the prefix and version from the current image name.
# Packaging.version is used handle version comparison.
async def get_latest_image_version(current_image: str):
    match = re.match(r"^(?P<prefix>.+)-v(?P<version>[\d\.]+)$", current_image)
    if not match:
        logger.warning(f"Unexpected image format: {current_image}")
        return current_image
    
    prefix = match.group("prefix")
    current_version = match.group("version")


    url = f"{MAAS_HOST}/api/2.0/boot-resources/"
    resp = await maas_client.get(url)
    resp.raise_for_status()
    images = resp.json()

    latest = Version(current_version)
    latest_image = current_image

    for image in images:
        image_name = image.get("name")
        
        if not image.get("name").startswith(prefix):
            print(f"{image_name} -skipping")
            continue
        try:
            print(f"{image_name} -parsing")
            version = image_name.replace(prefix, "")
            version = version.lstrip("-v")
            parsed_version = Version(version)
            if parsed_version > latest:
                latest = parsed_version
                latest_image = image_name
        except InvalidVersion:
            continue  # skip bad versions
    
    return latest_image

async def wait_for_ready(system_id: str, timeout=100, interval=5):
    elapsed = 0
    while elapsed < timeout:
        print(f"Checking if machine {system_id} is ready... {elapsed} seconds")
        resp = await maas_client.get(f"{MAAS_HOST}/api/2.0/machines/{system_id}/")
        resp.raise_for_status()
        machine = resp.json()
        if machine.get("status_name") == MAAS_READY_STATE:
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Machine {system_id} did not become ready within {timeout} seconds")

async def release_and_redeploy(system_id: str, latest_image: str):
    print(f"Releasing {system_id} with image {latest_image}")
    release = await maas_client.post(
        f"{MAAS_HOST}/api/2.0/machines/{system_id}/op-release",
        data={
            "comment": "Release by redeploy-node-api",
        }
    )

    release.raise_for_status()
    print(f"Released {system_id}, waiting for it to become ready...")
    await wait_for_ready(system_id)
    print(f"{system_id} is ready, proceeding with redeploy...")
    dep = await maas_client.post(
        f"{MAAS_HOST}/api/2.0/machines/{system_id}/op-deploy",
        data={
            "distro_series": latest_image,
        }
    )
    dep.raise_for_status()

    return {"status": "redeploying"}

# This function handles the redeploy logic for a given system_id.
async def handle_redeploy(system_id: str):
    machine = await get_machine(system_id)
    ossystem = machine.get("osystem")
    current_image = machine.get("distro_series")
    logger.info(f"{system_id} is running image: {ossystem}/{current_image}")

    latest_image = await get_latest_image_version(current_image)
    logger.info(f"Latest available image: {latest_image}")

    latest_image_full_name = f"{ossystem}/{latest_image}"

    if latest_image == current_image:
        logger.info(f"No new image available for {system_id}. Skipping redeploy.")
        return {"status": "no_update_needed"}
    else:
        logger.info(f"Redeploying {system_id} with new image: {latest_image}")
        redeploy_result = await release_and_redeploy(system_id, latest_image_full_name)
        return redeploy_result

@app.post("/redeploy")
async def redeploy(req: RedeployRequest, x_api_key: str = Header(...)):
    await check_auth(x_api_key)
    try:
        result = await handle_redeploy(req.system_id)
        return result
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    global maas_client
    logger.info("Initializing MAAS OAuth1 client...")
    maas_client = AsyncOAuth1Client(
        client_id=CONSUMER_KEY,
        token_secret=SECRET,
        token=CONSUMER_TOKEN,
        signature_method="PLAINTEXT",
    )
    maas_client.timeout = httpx.Timeout(30.0, connect=5.0)
    logger.info("MAAS client ready.")



