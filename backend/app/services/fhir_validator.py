import httpx


def validate_resources(resources, hapi_url):
    results = []
    for resource in resources:
        try:
            r = httpx.post(f"{hapi_url.rstrip('/')}/{resource['resourceType']}/$validate", json=resource, timeout=10)
            results.append({"resourceType": resource["resourceType"], "status_code": r.status_code, "valid": r.status_code < 400, "response": r.json() if r.content else {}})
        except Exception as exc:
            results.append({"resourceType": resource["resourceType"], "valid": False, "error": str(exc)})
    return {"hapi_available": any("status_code" in x for x in results), "results": results}
