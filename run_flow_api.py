from prefect.client import OrionClient

async with OrionClient() as client:
    deployment = await client.read_deployment_by_name(
        "Addition Machine/my-first-deployment"
    )
    flow_run = await client.create_flow_run_from_deployment(deployment)
