"""The p95 report of the load test (US-47, T-47.1)."""

import pytest

from loadtest.report import endpoint_stats, line, main

HEADER = ("Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,"
          "Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,"
          "99.99%,100%")


def stats_file(tmp_path, name, p95):
    path = tmp_path / name
    path.write_text("\n".join([
        HEADER,
        "POST,/auth/token,20,0,12,13,9,40,500,0.2,0,12,13,14,15,20,25,30,40,40,40,40",
        f"GET,/me/consumption/daily,1200,0,300,320,90,2100,9000,10.1,0,300,330,350,380,450,{p95},700,900,2100,2100,2100",
        ",Aggregated,1220,0,300,318,9,2100,8900,10.3,0,300,330,350,380,450,600,700,900,2100,2100,2100",
    ]) + "\n", encoding="utf-8")
    return str(path)


def test_reads_the_consumption_endpoint_row(tmp_path):
    s = endpoint_stats(stats_file(tmp_path, "a.csv", 610))
    assert (s["requests"], s["failures"], s["median"], s["p95"], s["p99"], s["rps"]) == (1200, 0, 300, 610, 900, 10.1)


def test_verdict_against_500_ms():
    assert "MISSES RNF-04" in line("before", {"requests": 1, "failures": 0, "rps": 1, "median": 1, "p95": 501, "p99": 1})
    assert "meets RNF-04" in line("after", {"requests": 1, "failures": 0, "rps": 1, "median": 1, "p95": 500, "p99": 1})


def test_before_and_after(tmp_path, capsys):
    main([stats_file(tmp_path, "b.csv", 2000), stats_file(tmp_path, "c.csv", 80)])
    out = capsys.readouterr().out
    assert "p95 2000 -> 80 ms (-96%)" in out


def test_unknown_file_layout_fails(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text(HEADER + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        endpoint_stats(str(path))
