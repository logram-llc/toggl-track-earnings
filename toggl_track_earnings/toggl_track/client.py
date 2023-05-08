from typing import Any, Protocol
from collections.abc import Generator
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from arrow import Arrow
from arrow import get as arrow_get
from arrow import now
from .consts import TOGGL_TRACK_API_BASE_URL


class IHttpClientResponse(Protocol):
    def json(self) -> Any:
        ...

    def raise_for_status(self) -> None:
        ...

    @property
    def status_code(self) -> int:
        ...


class IHttpClient(Protocol):
    def get(
        self,
        *args,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        **kwargs,
    ) -> IHttpClientResponse:
        ...


@dataclass(frozen=True, kw_only=True)
class Workspace:
    id: int
    default_hourly_rate: Decimal


@dataclass(frozen=True, kw_only=True)
class Client:
    id: int
    name: str
    archived: bool


@dataclass(frozen=True, kw_only=True)
class Project:
    id: int
    rate: Decimal | None
    client: Client


@dataclass(frozen=True, kw_only=True)
class TimeEntry:
    id: int
    billable: bool
    description: str
    start: Arrow
    end: Arrow | None
    user_id: int
    duration: int
    is_deleted: bool
    is_ongoing: bool
    workspace: Workspace
    project: Project | None


class TogglTrackClient:
    def __init__(self, api_token: str, http_client: IHttpClient):
        self.api_token = api_token

        self.session = http_client

    @cache
    def client(self, id: int, workspace_id: int) -> Client | None:
        res = self.session.get(
            url=f"{TOGGL_TRACK_API_BASE_URL}workspaces/{workspace_id}/clients/{id}",
            timeout=10,
            headers={
                "Authorization": f"Basic {self.api_token}",
            },
        )

        if res.status_code == 403:
            return None

        res.raise_for_status()

        json = res.json()

        return Client(id=json["id"], name=json["name"], archived=json["archived"])

    @cache
    def project(self, id: int, workspace_id: int) -> Project | None:
        res = self.session.get(
            url=f"{TOGGL_TRACK_API_BASE_URL}workspaces/{workspace_id}/projects/{id}",
            timeout=10,
            headers={
                "Authorization": f"Basic {self.api_token}",
            },
        )

        if res.status_code == 403:
            return None

        res.raise_for_status()

        json = res.json()

        client = self.client(id=json["client_id"], workspace_id=workspace_id)
        if client is None:
            raise ValueError(f"Project {id} does not have a client assigned to it.")

        return Project(
            id=json["id"],
            rate=Decimal(json["rate"]) if json.get("rate") else None,
            client=client,
        )

    @cache
    def workspace(self, id: int) -> Workspace | None:
        res = self.session.get(
            url=f"{TOGGL_TRACK_API_BASE_URL}workspaces/{id}",
            timeout=10,
            headers={
                "Authorization": f"Basic {self.api_token}",
            },
        )

        if res.status_code == 403:
            return None

        res.raise_for_status()

        json = res.json()

        return Workspace(id=json["id"], default_hourly_rate=Decimal(json["default_hourly_rate"]))

    def time_entries(self, _from: Arrow, to: Arrow) -> Generator[TimeEntry, None, None]:
        params = {
            "start_date": _from.format("YYYY-MM-DD"),
            "end_date": to.format("YYYY-MM-DD"),
        }

        res = self.session.get(
            url=f"{TOGGL_TRACK_API_BASE_URL}me/time_entries",
            params=params,
            timeout=10,
            headers={
                "Authorization": f"Basic {self.api_token}",
            },
        )

        res.raise_for_status()

        for entry in res.json():
            workspace = self.workspace(entry["workspace_id"])
            if workspace is None:
                raise ValueError(f"Unable to fetch workspace for time entry {entry['id']}")

            project = (
                self.project(workspace_id=entry["workspace_id"], id=entry["project_id"])
                if entry.get("project_id")
                else None
            )

            start = arrow_get(entry["start"])
            duration = entry["duration"]

            # NOTE: Ongoing/running/not stopped time entries will have a
            # negative duration. Set it to now - start.
            if duration < 0:
                duration = int(now().timestamp() - start.timestamp())

            yield TimeEntry(
                id=entry["id"],
                billable=entry["billable"],
                description=entry["description"],
                start=start,
                end=arrow_get(entry["stop"]) if entry.get("stop") else None,
                duration=duration,
                is_deleted=entry["server_deleted_at"] is not None,
                is_ongoing=entry["duration"] < 0,
                user_id=entry["user_id"],
                workspace=workspace,
                project=project,
            )
