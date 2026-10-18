# VoltiaGrid API collection (Bruno)

Happy and error cases for every endpoint of the three APIs (US-12, T-12.3).
Bruno stores each request as a plain `.bru` file, so the collection is versioned
and reviewed like code.

## Environments

| File                     | Use                                                                       |
| ------------------------ | ------------------------------------------------------------------------- |
| `environments/local.bru` | APIs running on your machine (ports 8001, 8002, 8003)                     |
| `environments/aws.bru`   | APIs behind the ALB; replace `REPLACE-WITH-ALB-DNS` when the stack exists |

The `00-auth` folder runs first: it logs in with `POST /auth/token` and stores
`customerToken` and `internalToken` for the rest of the requests. The passwords are
secret variables (`customerPassword`, `internalPassword`): they are never committed.
Use the same values as `DEMO_CUSTOMER_PASSWORD` and `DEMO_INTERNAL_PASSWORD` in your `.env`.

## Run it

1. Start the three APIs (one terminal each):

   ```bash
   python -m uvicorn app.api.customer_consumption.main:app --port 8001
   python -m uvicorn app.api.control_center.main:app --port 8002
   python -m uvicorn app.api.network_inventory.main:app --port 8003
   ```

2. Run the whole collection from this folder (needs Node.js 18+):

   ```bash
   cd collections/voltiagrid
   npx --yes --package=@usebruno/cli@2.15.1 bru run --env local --env-var customerPassword=<DEMO_CUSTOMER_PASSWORD> --env-var internalPassword=<DEMO_INTERNAL_PASSWORD>
   ```

   Every request must pass. To explore it visually, open this folder in the Bruno app
   (_Open Collection_), pick the `local` environment and type the two passwords in
   its secret variables.

## Adding a request

Copy a `.bru` file of the same folder, change `meta.name`, `seq`, the URL and the `assert` block.
Every new endpoint needs at least one happy case and one error case.
