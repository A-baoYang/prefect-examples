from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.orion.schemas.schedules import CronSchedule
from datetime import timedelta

# note that deployment names are
# stored and referenced as '<flow name>/<deployment name>'
DeploymentSpec(
    flow_location="./hello_world.py",
    name="my-first-deployment",
    parameters={"repos": ["PrefectHQ/Prefect", "PrefectHQ/miter-design"]},
    # schedule=IntervalSchedule(interval=timedelta(minutes=15)),
    schedule=CronSchedule(cron="0 7-22 * * 5"),
)
