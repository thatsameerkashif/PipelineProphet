import os
from dotenv import load_dotenv

load_dotenv()

# IBM Cloudant
CLOUDANT_URL: str = os.getenv("CLOUDANT_URL", "")
CLOUDANT_APIKEY: str = os.getenv("CLOUDANT_APIKEY", "")
CLOUDANT_DB_PREFIX: str = os.getenv("CLOUDANT_DB_PREFIX", "pp_")

# IBM watsonx.ai
WATSONX_API_KEY: str = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")

# GitHub
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
