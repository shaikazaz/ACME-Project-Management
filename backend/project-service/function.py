"""AWS Lambda entry point: translates Lambda events into FastAPI requests."""

import logging

from mangum import Mangum

from app.config import API_BASE_PATH
from app.main import app

logging.getLogger().setLevel(logging.INFO)

# The local proxy removes /api/project-service before calling the Lambda, while
# CloudFront keeps it. Mangum strips the prefix only when it is present, so the
# same routes work in both environments.
handler = Mangum(app, lifespan="off", api_gateway_base_path=API_BASE_PATH)
