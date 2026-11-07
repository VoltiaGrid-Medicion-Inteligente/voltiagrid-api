# Load test of the customer consumption API (US-47)

RNF-04: the customer's consumption must load fast, **p95 ≤ 500 ms** for one month of daily data.

## Run it

1. Start the stack (`make up`, or `docker compose up -d`): the consumption API on 8001 and the inventory API on 8003,
   with the seed loaded. The test reads `DEMO_CUSTOMER_PASSWORD` and `DEMO_INTERNAL_PASSWORD` from `.env`.
2. Run 100 simulated customers for 2 minutes (each logs in once, then asks for its month every 0.5 to 1.5 s):

```powershell
pip install -r requirements-dev.txt
locust -f loadtest/locustfile.py --headless -u 100 -r 20 -t 2m --host http://localhost:8001 `
       --csv loadtest/results/before --only-summary
python -m loadtest.report loadtest/results/before_stats.csv
```

3. After a change, run it again with `--csv loadtest/results/after` and compare:

```powershell
python -m loadtest.report loadtest/results/before_stats.csv loadtest/results/after_stats.csv
```

`loadtest/results/` is git-ignored: copy the lines the report prints into the PR and the performance report.

| Variable | Default | Meaning |
|---|---|---|
| `LOADTEST_MONTH` | `2013-01` | Month every customer asks for |
| `LOADTEST_CUSTOMERS` | `50` | How many customers of the inventory take part |
| `INVENTORY_URL` | `http://localhost:8003` | Where the customer codes come from |

Write down the machine (CPU, RAM) and the number of users with every result: the same API answers faster on a faster
laptop, so numbers only compare on the same machine.

## Precomputed months (T-47.2)

The API computes a month from 1,488 half hours per meter on every request; under load that is what pushes p95 up.
`consumption_daily` stores the answer per customer, day and band (primary key `customer_code, date, band_name`, which
is also the index of the monthly read). Build the months the demo and the load test use:

```powershell
python -m alembic upgrade head
python -m scripts.build_consumption_daily --month 2013-01          # or --from 2012-01 --to 2014-02
```

A built month is one indexed query of about 90 rows; any other month is still computed, with the same response.
Rebuild after a new seed. The inventory lookups (`customer.code` unique, `meter.customer_id` indexed since the first
migration) already had their indexes. Each API worker keeps a connection pool (`DB_POOL_SIZE`, `DB_POOL_OVERFLOW`).
