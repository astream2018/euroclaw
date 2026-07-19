"""``python -m euroclaw`` -> launch the API with uvicorn."""

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "euroclaw.app:app",
        host=os.getenv("HOST", "0.0.0.0"),  # nosec B104 - container entrypoint
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("EUROCLAW_RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    main()
