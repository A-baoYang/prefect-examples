from prefect import flow


@flow
def hello_world(name="world"):
    print(f"Hello {name}!")


raise RuntimeError("This flow shall not load!")
