import asyncio
from base64 import b64encode
from decimal import Decimal
from os import environ
from pathlib import Path
import uvicorn
from arrow import now
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from toggl_track_earnings.__version__ import __version__
from toggl_track_earnings.http import HttpClient
from toggl_track_earnings.toggl_track import TogglTrackClient
from .websockets import ConnectionManager

api_token = b64encode(f"{environ['TOGGL_TRACK_USER']}:{environ['TOGGL_TRACK_PASS']}".encode()).decode("ascii")

http_client = HttpClient(f"toggl-track-earnings v{__version__}")
toggl_track_client = TogglTrackClient(api_token=api_token, http_client=http_client)

manager = ConnectionManager()
last_earnings: str | None = None

app = FastAPI()
app_port = int(environ.get("TOGGL_TRACK_PORT", 8000))
templates = Jinja2Templates(directory=Path(__file__).parent / "web")


def get_earnings() -> Decimal:
    today = now()
    first_day_of_month = today.replace(day=1)
    last_day_of_month = today.shift(months=1).replace(day=1).shift(days=-1)

    earnings = Decimal(0)

    for entry in toggl_track_client.time_entries(_from=first_day_of_month, to=last_day_of_month):
        if not entry.billable:
            continue

        rate = (entry.project.rate if entry.project else None) or entry.workspace.default_hourly_rate

        earned = (rate / Decimal(60)) * (entry.duration / Decimal(60))

        earnings += earned

    return earnings


async def fetch_earnings() -> None:
    global last_earnings

    loop = asyncio.get_event_loop()

    while True:
        earnings = str(await loop.run_in_executor(None, get_earnings))

        if earnings != last_earnings:
            await manager.broadcast({"month": earnings})
            last_earnings = earnings


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(fetch_earnings())


app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "web" / "assets"), name="static")


@app.get("/")
async def get(request: Request, response_class=HTMLResponse):  # noqa
    return templates.TemplateResponse(
        "index.html", {"request": request, "websocket_url": f"ws://127.0.0.1:{app_port}/ws"}
    )


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json({"month": last_earnings})

        while True:
            msg = await websocket.receive_text()

            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def main() -> None:
    uvicorn.run(
        "toggl_track_earnings.toggl_track_earnings:app",
        port=app_port,
        log_level="info",
        ws="websockets",
        reload=False,
    )


if __name__ == "__main__":
    main()
