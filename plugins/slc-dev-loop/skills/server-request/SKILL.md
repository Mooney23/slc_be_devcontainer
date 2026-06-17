---
name: server-request
description: Make HTTP requests to the local Flask development server. Use this skill whenever the user wants to call an API endpoint, test a route, hit an endpoint, make a request, send data to the server, check an API response, or interact with the Flask backend in any way. Also trigger when the user mentions specific API paths, HTTP methods (GET, POST, PUT, PATCH, DELETE), or says things like "call the devices endpoint", "fetch alarms", "create a device", "update firmware", or any natural language that implies invoking a REST API on the local server.
---

Make HTTP requests to the local Flask development server on the user's behalf, using the Swagger spec to discover available endpoints and help construct valid requests.

## Step 1: Ensure the server is running

Before making any request, check if the Flask server is up:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/swagger.json --max-time 3
```

- If you get `200`, the server is running — proceed.
- If the request fails or times out, the server is not running. Use the **server-start** skill to start it, then wait for it to be ready before continuing.

## Step 2: Fetch the Swagger spec

If you haven't already fetched the Swagger spec in this conversation, retrieve it:

```bash
curl -s http://127.0.0.1:5000/swagger.json
```

This gives you the full OpenAPI spec with all registered endpoints, their methods, parameters, and expected request/response schemas. Cache this in your context — you don't need to fetch it again for the rest of the conversation.

Use the spec to:
- Resolve what endpoint the user is referring to (even from vague natural language)
- Know which HTTP method(s) an endpoint supports
- Identify required and optional query parameters
- Identify the expected request body schema for POST/PUT/PATCH

## Step 3: Translate the user's intent into a request

When the user describes what they want in natural language (e.g., "get all devices for org acme", "create an alarm"), match their intent to the closest endpoint in the Swagger spec.

### Building query parameters

If the endpoint accepts query parameters, check which are required and which are optional. Ask the user for any required values you don't already know. For optional parameters, only include them if the user mentioned them or if they're clearly relevant.

### Building a request body

If the endpoint expects a JSON body (POST, PUT, PATCH), use the Swagger spec's schema definition to construct it. Walk the user through any required fields they haven't provided. Present the draft body and let them adjust it before sending.

## Step 4: Confirm before sending

This is important — always show the user exactly what you're about to send and get their approval before executing. Present it clearly:

```
Method:  POST
URL:     http://127.0.0.1:5000/deviceservice/api/v1/acme/devices
Headers: Content-Type: application/json
Body:
{
  "device_name": "sensor-01",
  "device_type": "temperature"
}
```

Wait for the user to confirm. If they want changes, adjust and show again.

## Step 5: Execute the request

Use `curl` to make the request. Always include `-s` (silent) and `-w` to capture the status code, and `-D -` to capture response headers.

```bash
curl -s -D /tmp/resp_headers.txt -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"device_name": "sensor-01", "device_type": "temperature"}' \
  "http://127.0.0.1:5000/deviceservice/api/v1/acme/devices"
```

For GET requests with query parameters, URL-encode them properly.

## Step 6: Present the response

Always show:
1. **Status code** — with a brief human-readable meaning (e.g., `200 OK`, `404 Not Found`, `422 Unprocessable Entity`)
2. **Response headers** — read from `/tmp/resp_headers.txt` and display them
3. **Response body** — if the JSON response is longer than 500 lines when pretty-printed, show the first 50 lines and let the user know the full response is available if they want to see more. For shorter responses, show the full body pretty-printed.

If the request failed (4xx/5xx), read the error message from the response body and help the user understand what went wrong — cross-reference with the Swagger spec if the issue is a missing field or wrong format.
