from prefect import flow, task
from typing import List
import httpx
from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import CronSchedule


@task(retries=3)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")


@flow(name="Github Stars")
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)


# deployment names are stored and referenced as '<flow name>/<deployment name>'
DeploymentSpec(
    flow=github_stars,
    name="my-first-deployment",
    parameters={"repos": ["PrefectHQ/Prefect", "PrefectHQ/miter-design"]},
    schedule=CronSchedule(cron="0 7-22 * * 5"),
)



