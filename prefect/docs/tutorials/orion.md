# The components of Orion

Orion is a collection of components and services that form a dedicated _orchestration environment_:

- Orion provides a [**database**](#the-database) for a persistent metadata store that holds flow and task run history, along with [references to data][prefect.orion.schemas.data] produced by tasks and flows.
- The Orion [**webserver**](#the-webserver) serves [a REST API](/api-ref/rest-api/) backed by [FastAPI](https://fastapi.tiangolo.com/) that receives information emitted from workflows and additionally responds with orchestration instructions.
- Orion provides a collection of [**services**](#orion-services) primarily focused on managing deployments.
- The Orion [**Dashboard**](#orion-dashboard) provides a flexible control plane UI for monitoring, configuring, and analyzing your Prefect workflows.

!!! tip "All at once"
    Below we break down each component of Orion individually. To quickly spin up all services simultaneously, you can use the simple `prefect orion start` CLI command, which should produce output similar to this:

    <div class="termy">
    ```
    $ prefect orion start
    Starting Orion API server...
    Starting agent...
    INFO:     Started server process [66610]
    INFO:     Waiting for application startup.
    15:46:09.908 | In-app services have been disabled and will need to be run separately.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://127.0.0.1:4200 (Press CTRL+C to quit)
    Starting agent connected to http://127.0.0.1:4200/api/...
    Agent started! Checking for flow runs...
    ```
    </div>

## The database

The database is the persistent layer that powers many of the features and functionality of Orion.  Currently Orion supports the following databases:

- SQLite: the default in Orion, and our recommendation for lightweight, single-server deployments. SQLite requires essentially no setup.
- PostgreSQL: best for connecting to external databases, but does require additional setup (such as Docker).

When you first install Orion, your database will be located at `~/.prefect/orion.db`. To configure this location, you can specify a connection URL with the `PREFECT_ORION_DATABASE_CONNECTION_URL` environment variable:

```bash
$ export PREFECT_ORION_DATABASE_CONNECTION_URL="sqlite+aiosqlite:////full/path/to/a/location/orion.db"
```

!!! tip "In-memory databases"
    One of the benefits of SQLite is in-memory database support. In-memory databases are only supported in Orion for testing purposes and are not compatible with multiprocessing.  
    
    To use an in-memory SQLite database, set the following environment variable:

    ```bash
    $ export PREFECT_ORION_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///file::memory:?cache=shared&uri=true&check_same_thread=false"
    ```

!!! danger "Migrations"
    Recall that Orion is available as [a technical preview](/faq/#why-is-orion-a-technical-preview). This means many aspects of Orion's schema are still under active development and therefore upgrades should be considered destructive.  As it nears official release, database migration guides and tooling will be available and documented.

If at any point in your testing you'd like to reset your database, run the CLI command:  

```bash
$ prefect orion reset-db
```

This will completely clear all data and reapply the schema.

## The webserver

The Orion webserver can be stood up with a single CLI command:

```bash
$ prefect orion start --no-services
```

There are numerous ways to begin exploring the API:

- Navigate to [http://127.0.0.1:4200/docs](http://127.0.0.1:4200/docs) (or your corresponding API URL) to see the autogenerated Swagger API documentation.
- Navigate to [http://127.0.0.1:4200/redoc](http://127.0.0.1:4200/redoc) (or your corresponding API URL) to see the autogenerated Redoc API documentation.
- Instantiate [an asynchronous `OrionClient`][prefect.client] within Python to send requests to the API.

During normal operation is it not expected that you will need to interact with the API directly, as this is handled automatically for you within the Python client and the UI.  Most users will spin up everything all at once with `prefect orion start`.

## Orion services

Orion also ships with a collection of services that are also run with `prefect orion start`:

- The Orion agent is a lightweight process responsible for submitting both scheduled and manually triggered deployments as sub-processes.
- The Orion scheduler prepares and creates runs for any scheduled deployments.
- The Orion `MarkLateRuns` service which updates late runs by placing them in a `Late` state.

## Orion Dashboard

The Orion Dashboard comes prepackaged with the API when you serve it. By default it can be found at `http://127.0.0.1:4200/`:

<figure markdown=1>
![](/img/tutorials/ui-component.png){: max-width=600px}
</figure>

The dashboard allows you to track and manage your flows, runs, and deployments and additionally allows you to filter by names, tags, and other metadata to quickly find the information you are looking for.

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Orion REST API Specification](/api-ref/rest/)
    - [Deployments](/concepts/deployments/)
