"""Upload sample documents using only Python's standard library."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "examples" / "documents.json"
    for document in json.loads(path.read_text(encoding="utf-8")):
        request = Request(
            args.url.rstrip("/") + "/documents",
            data=json.dumps(document).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                print(response.status, response.read().decode())
        except HTTPError as exc:
            if exc.code != 409:
                detail = exc.read().decode("utf-8", errors="replace")
                print(
                    f"Upload failed for {document['id']}: HTTP {exc.code}: {detail}",
                    file=sys.stderr,
                )
                return 1
            print(f"409 {document['id']}: already loaded")
        except URLError as exc:
            print(
                f"Cannot reach the API at {args.url}: {exc.reason}\n"
                "Start the server in another terminal from the project directory:\n"
                "  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000\n"
                "Wait for 'Application startup complete', then run this script again.\n"
                "If the API uses another address, pass --url http://HOST:PORT.",
                file=sys.stderr,
            )
            return 1
        except TimeoutError:
            print(
                f"Upload timed out for {document['id']}. Check the API logs; "
                "the upload may still be processing.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
