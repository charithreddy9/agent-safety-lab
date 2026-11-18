"""Settlement-day pilot. Python 3.10+, standard library only."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

POLICY = """Each row represents one settled sale and at most one partial or full refund.
All amounts are integer cents in one currency. Credit the sale on sale_day and
subtract the refund on refund_day. Return one (day, net_cents) row per day
with at least one event, including zero-net days. Ignore ordering. A refund
may settle on or after the sale day. Without a refund, refund_day is NULL
and refund_cents is zero. Both day fields use ISO YYYY-MM-DD."""
SCHEMA = "CREATE TABLE sales(id INTEGER PRIMARY KEY, sale_day TEXT, sale_cents INTEGER, refund_day TEXT, refund_cents INTEGER)"
AUTHOR = POLICY + "\n" + SCHEMA + "\nWrite one SQLite SELECT (WITH allowed). Return JSON with a single string field sql."
REVIEW = """Design one small test for this report. Return JSON with fields rows and expected.
Use 1 to 6 sales rows, each [id,sale_day,sale_cents,refund_day,refund_cents].
expected is the complete collection of [day,net_cents] pairs. Use positive
integer IDs and sale amounts. Only return the JSON object."""
GOOD = """SELECT day, SUM(amount) FROM (
SELECT sale_day AS day, sale_cents AS amount FROM sales UNION ALL
SELECT refund_day, -refund_cents FROM sales WHERE refund_day IS NOT NULL)
GROUP BY day"""
FAULT = GOOD.replace("SELECT refund_day,", "SELECT sale_day,")
FIXTURES = [
    [[1,"2026-06-01",10000,"2026-06-02",2000]],
    [[1,"2026-06-01",10000,"2026-06-01",2000]],
    [[1,"2026-06-01",10000,None,0]],
    [[1,"2026-06-01",10000,"2026-06-02",10000],[2,"2026-06-02",10000,None,0]]
]

def day(value):
    return date.fromisoformat(value).isoformat() == value

def oracle(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
        raise ValueError("row count")
    ids, totals = set(), Counter()
    for ident, sold, price, refunded, amount in rows:
        if type(ident) is not int or ident <= 0 or ident in ids or not day(sold):
            raise ValueError("invalid sale")
        if type(price) is not int or price <= 0 or type(amount) is not int:
            raise ValueError("invalid cents")
        ids.add(ident)
        totals[sold] += price
        if refunded is None and amount == 0:
            continue
        if not day(refunded) or refunded < sold or not 0 < amount <= price:
            raise ValueError("invalid refund")
        totals[refunded] -= amount
    return sorted(totals.items())

def execute(sql, rows):
    db = sqlite3.connect(":memory:")
    try:
        db.execute(SCHEMA)
        db.executemany("INSERT INTO sales VALUES (?,?,?,?,?)",rows)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
        db.set_authorizer(lambda op,*args: sqlite3.SQLITE_OK if op in allowed else sqlite3.SQLITE_DENY)
        db.set_progress_handler(lambda: 1, 100000)
        result = db.execute(sql).fetchmany(100)
        if len(result) == 100 or any(len(r)!=2 or type(r[0]) is not str or type(r[1]) is not int for r in result):
            raise ValueError("invalid report output")
        return sorted(result)
    finally:
        db.close()

def score(sql, test):
    truth = oracle(test["rows"])
    expected = test["expected"]
    correct = (isinstance(expected,list) and all(isinstance(pair,list) and len(pair)==2
               and type(pair[0]) is str and type(pair[1]) is int for pair in expected)
               and sorted(expected)==[list(pair) for pair in truth])
    actual = execute(sql,test["rows"])
    differs = actual != truth
    balanced = sum(v for _,v in actual)==sum(v for _,v in truth)
    return dict(valid_rows=True, correct_expected=correct, distinguishes=differs,
                balanced=balanced, detects_balanced_error=correct and differs and balanced)

def post(route, payload):
    req = Request("http://127.0.0.1:11434/api/"+route, data=json.dumps(payload).encode(),
                  headers={"Content-Type":"application/json"})
    with urlopen(req,timeout=600) as response:
        return json.load(response)

def trial(model,seed,path):
    def log(item):
        with path.open("a",encoding="utf-8") as handle:
            handle.write(json.dumps(item)+"\n")
    def ask(messages):
        request=dict(model=model,messages=messages,stream=False,format="json",
                     options=dict(seed=seed,temperature=0.3,num_predict=1200))
        response=post("chat",request)
        log(dict(request=request,response=response))
        return response["message"]["content"]
    with path.open("x",encoding="utf-8") as handle:
        handle.write(json.dumps(dict(model=model,seed=seed,sqlite=sqlite3.sqlite_version))+"\n")
    author=[dict(role="user",content=AUTHOR)]
    raw=ask(author)
    try:
        sql=json.loads(raw)["sql"]
        controls=[score(sql,dict(rows=r,expected=[list(p) for p in oracle(r)])) for r in FIXTURES]
        log(dict(author_controls=controls))
    except (KeyError,ValueError,TypeError,sqlite3.Error,OverflowError) as exc:
        log(dict(author_error=str(exc)))
        return
    for arm,history in [("self",author+[dict(role="assistant",content=raw)]),("independent",[])]:
        content = POLICY+"\n"+SCHEMA+"\n"+REVIEW
        raw_test=ask(history+[dict(role="user",content=content)])
        try:
            result=score(sql,json.loads(raw_test))
        except (ValueError,TypeError,KeyError,sqlite3.Error,OverflowError) as exc:
            result=dict(error=str(exc),detects_balanced_error=False)
        log(dict(arm=arm,result=result))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--seed",type=int,default=1)
    parser.add_argument("--out",type=Path,default=Path("trial.jsonl"))
    args=parser.parse_args()
    if args.model:
        trial(args.model,args.seed,args.out)
    else:
        checks=[]
        for rows in FIXTURES:
            expected=[list(p) for p in oracle(rows)]
            test=dict(rows=rows,expected=expected)
            assert execute(GOOD,rows)==oracle(rows)
            checks.append(score(FAULT,test)["detects_balanced_error"])
            assert not score(GOOD,test)["detects_balanced_error"]
        assert checks==[True,False,False,True]
        assert not score(FAULT,dict(rows=FIXTURES[0],expected=[["2026-06-01",8000]]))["detects_balanced_error"]
        print("Reference matched 4/4 fixtures. Seeded fault exposed on 2/4. Wrong expectation rejected.")
