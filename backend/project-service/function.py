"""AWS Lambda entry point: translates Lambda events into FastAPI requests.

Operators can also run tasks by invoking the function directly, which needs AWS
permissions. HTTP requests cannot: AWS builds their events, without a task.
"""

import logging

from mangum import Mangum

from app.config import API_BASE_PATH
from app.main import app
from app.operations import run_task

logging.getLogger().setLevel(logging.INFO)

# The local proxy removes /api/project-service before calling the Lambda, while
# CloudFront keeps it. Mangum strips the prefix only when it is present, so the
# same routes work in both environments.
http_handler = Mangum(app, lifespan="off", api_gateway_base_path=API_BASE_PATH)


def handler(event: dict, context: object) -> dict:
    """Answer one Lambda event.

    Args:
        event: An HTTP request, or a task of an operator.
        context: The Lambda context.

    Returns:
        The HTTP response or the task's result.
    """
    if "task" in event and "requestContext" not in event:
        return run_task(event)
    return http_handler(event, context)
