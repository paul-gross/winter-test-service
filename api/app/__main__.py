"""Entry point for the api: `python -m app`.

Port and host are read from the environment with embedded defaults, so the
service binds the right address with no arguments and no wrapper script.
"""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("WTS_API_HOST", "0.0.0.0"),
        port=int(os.environ.get("WTS_API_PORT", "7503")),
    )


if __name__ == "__main__":
    main()
