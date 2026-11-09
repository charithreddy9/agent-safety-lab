"""Tiny WSGI API used to check an applied endpoint proposal."""

import json
from http import HTTPStatus


def routes():
    return {("POST", "/reports"): (200, {"resource": "reports"})}


def apply_proposal(current, export_status):
    proposed = current.copy()
    if export_status is not None:
        proposed["POST", "/exports"] = (export_status, {"resource": "exports"})
    return proposed


def make_app(route_table):
    def app(environ, start_response):
        route = environ["REQUEST_METHOD"], environ["PATH_INFO"]
        status, data = route_table.get(route, (404, {"error": "not found"}))
        body = json.dumps(data).encode("utf-8")
        start_response(f"{status} {HTTPStatus(status).phrase}", [
            ("Content-Type", "application/json"), ("Content-Length", str(len(body))),
        ])
        return [body]

    return app
