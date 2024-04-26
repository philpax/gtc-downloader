from __future__ import annotations

from typing import List, Optional
from tqdm import tqdm
from pydantic import BaseModel
from bs4 import BeautifulSoup

import requests
import argparse
import subprocess
import re
import os
import json

RAINFOCUS_WIDGET_ID = "C5aHR3OlA60pUDILVE33Jbn8hagS4Fsw"
RAINFOCUS_API_PROFILE_ID = "hUVpYtzXsLcOoh4rkNjxpSodRKdtJlUs"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Referer": "https://www.nvidia.com/",
    "Origin": "https://www.nvidia.com",
}


def get_rainfocus_headers(auth_token: str):
    return {
        **BASE_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "rfWidgetId": RAINFOCUS_WIDGET_ID,
        "rfApiProfileId": RAINFOCUS_API_PROFILE_ID,
        "rfAuthToken": auth_token,
    }


class Participant(BaseModel):
    name: str
    bio: Optional[str] = None


class Session(BaseModel):
    session_id: str
    title: str
    time: str
    length: float
    abstract: str
    participants: List[Participant]
    attributes: dict[str, str]

    # Present on Rainforest sessions
    session_time_id: Optional[str]
    # Present on on-demand sessions
    kaltura_id: Optional[str]

    def fetch_from_conference(auth_token: str, id: str) -> Session:
        url = "https://events.rainfocus.com/api/session"

        headers = get_rainfocus_headers(auth_token)
        request = {
            "id": id,
        }

        response = requests.post(url, headers=headers, data=request)
        json = response.json()

        item = json["items"][0]
        time = item["times"][0]

        return Session(
            session_id=item["sessionID"],
            title=item["title"].strip(),
            time=time["utcStartTime"],
            length=item["length"],
            abstract=item["abstract"],
            participants=[
                {"name": p["fullName"], "bio": p.get("globalBio")}
                for p in item["participants"]
            ],
            attributes={a["attribute"]: a["value"] for a in item["attributevalues"]},
            session_time_id=time["sessionTimeID"],
            kaltura_id=None,
        )

    def fetch_from_ondemand(id: str) -> Session:
        url = f"https://api-prod.nvidia.com/services/nod/api/v1/session?id={id}"

        response = requests.get(url, headers=BASE_HEADERS)
        json = response.json()

        data = json["sessionData"]

        return Session(
            session_id=data["sessionID"],
            title=data["sTitle"].strip(),
            time=data["sDate"],
            length=data["sLength"],
            abstract=data["sAbstract"],
            participants=[
                {
                    "name": f"{p.get('firstName')} {p.get('lastName')}",
                    "bio": p.get("bio"),
                }
                for p in data["speakerList"]
            ],
            attributes={a["attribute"]: a["value"] for a in data["attributes"]},
            session_time_id=None,
            kaltura_id=data["assets"][0]["url"].split(":")[-1],
        )


class Webinar(BaseModel):
    partner_id: str
    entry_id: str
    user_id: str
    ks: str

    def fetch(auth_token: str, session: Session) -> Webinar:
        url = "https://events.rainfocus.com/api/rainfocus/v2/webinar"

        headers = get_rainfocus_headers(auth_token)
        request = {
            "sessionTimeId": session.session_time_id,
        }

        response = requests.post(url, headers=headers, data=request)
        json = response.json()

        raw_data = json["data"]
        data = {
            "partner_id": raw_data["partnerId"],
            "entry_id": raw_data["entryId"],
            "user_id": raw_data["userId"],
            "ks": raw_data["ks"],
        }

        webinar_model = Webinar(**data)
        return webinar_model


class FlavorProfile(BaseModel):
    width: int
    height: int
    bitrate: float
    frame_rate: float
    id: str


class KalturaMetadata(BaseModel):
    # different to webinar entry_id; possibly redirected to from the original webinar entry_id
    entry_id: str
    profiles: List[FlavorProfile]

    def fetch_from_params(
        partner_id: str, entry_id: str, ks: Optional[str]
    ) -> KalturaMetadata:
        url = "https://cdnapisec.kaltura.com/api_v3/service/multirequest"
        headers = {**BASE_HEADERS, "Content-Type": "application/json"}

        # Set up the base request
        request = {
            "apiVersion": "3.3.0",
            "format": 1,
            "ks": ks if ks else "",
            "clientTag": "html5:v3.17.10",
            "partnerId": partner_id,
        }

        # Add a first step to start a widget session if ks is not provided
        # and use its result for ks in the next steps
        first_step = 1 if ks is not None else 2
        second_step = first_step + 1
        if ks is None:
            request["1"] = {
                "action": "startWidgetSession",
                "service": "session",
                "widgetId": f"_{partner_id}",
            }
            ks = "{1:result:ks}"

        request[str(first_step)] = {
            "service": "baseEntry",
            "action": "list",
            "ks": ks,
            "filter": {"redirectFromEntryId": entry_id},
            "responseProfile": {"type": 1, "fields": "id"},
        }
        request[str(second_step)] = {
            "service": "baseEntry",
            "action": "getPlaybackContext",
            "entryId": f"{{{first_step}:result:objects:0:id}}",
            "ks": ks,
            "contextDataParams": {
                "objectType": "KalturaContextDataParams",
                "flavorTags": "all",
            },
        }

        response = requests.post(url, headers=headers, json=request)
        output = response.json()

        entry_id = output[first_step - 1]["objects"][0]["id"]
        profiles = output[second_step - 1]["flavorAssets"]
        return KalturaMetadata(
            entry_id=entry_id,
            profiles=[
                FlavorProfile(
                    width=a["width"],
                    height=a["height"],
                    bitrate=a["bitrate"],
                    frame_rate=a["frameRate"],
                    id=a["id"],
                )
                for a in profiles
            ],
        )

    def fetch_video(
        self,
        partner_id: str,
        ks: Optional[str],
        profile: FlavorProfile,
        duration: float,
        output_path: str,
    ):
        url = self._manifest_url(partner_id, ks, profile)
        command = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
        ]
        command.extend(self._headers_args())
        command.extend(["-i", url, "-codec", "copy", output_path])

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            # stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
        )

        pattern = re.compile(r"out_time_ms=(\d+)")
        # Calculate the total steps as duration in seconds (for tqdm progress bar)
        total_steps = int(duration)

        with tqdm(total=total_steps, unit="s", desc="download") as pbar:
            last_time = 0
            while True:
                line = process.stdout.readline()
                if not line:
                    break

                match = pattern.search(line)
                if match:
                    elapsed_time_ms = int(match.group(1))
                    elapsed_time_s = int(elapsed_time_ms / 1000000)
                    progress_step = elapsed_time_s - last_time
                    if progress_step > 0:
                        pbar.update(progress_step)
                        last_time = elapsed_time_s

        process.wait()
        return process.returncode

    def _headers_args(self) -> list[str]:
        # manually specify the order of the headers because God is dead and the Kaltura server will 404 if the order is wrong
        headers = [
            ("Accept", "*/*"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Origin", "https://www.nvidia.com"),
            ("Connection", "keep-alive"),
            ("Referer", "https://www.nvidia.com/"),
        ]

        output = []
        for kv in headers:
            output.append("-headers")
            output.append(f"{kv[0]}: {kv[1]}")
        return output

    def _manifest_url(
        self, partner_id: str, ks: Optional[str], profile: FlavorProfile
    ) -> str:
        output = f"https://cdnapisec.kaltura.com/p/{partner_id}/sp/{partner_id}00/playManifest/entryId/{self.entry_id}/protocol/https/format/applehttp/flavorIds/{profile.id}"
        if ks is not None:
            output += f"/ks/{ks}"
        output += "/a.m3u8"
        return output


class OutputMetadata(BaseModel):
    url: str
    session_id: str
    title: str
    time: str
    length: float
    abstract: str
    participants: List[Participant]
    attributes: dict[str, str]
    width: int
    height: int
    bitrate: float
    frame_rate: float

    def build(session: Session, profile: FlavorProfile):
        return OutputMetadata(
            url=f"https://www.nvidia.com/gtc/session-catalog/?#/session/{session.session_id}",
            session_id=session.session_id,
            title=session.title,
            time=session.time,
            length=session.length,
            abstract=session.abstract,
            participants=session.participants,
            attributes=session.attributes,
            width=profile.width,
            height=profile.height,
            bitrate=profile.bitrate,
            frame_rate=profile.frame_rate,
        )


def sanitize_filename(filename):
    disallowed_chars = '/\\:*?"<>|'
    for char in disallowed_chars:
        filename = filename.replace(char, "_")
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download a video from the NVIDIA GTC event"
    )
    parser.add_argument(
        "-a",
        "--rainforest-auth",
        help="The Rainforest auth token, required only for conference sessions",
    )
    parser.add_argument(
        "-d", "--directory", help="The directory to save the video to", default=""
    )
    parser.add_argument(
        "-m",
        "--meta",
        help="Write metadata to a file",
        action="store_true",
    )
    parser.add_argument(
        "-c",
        "--conf-session-id",
        help="The ID of the video to download from the conference",
    )
    parser.add_argument(
        "-o",
        "--ondemand-session-url",
        help="The URL of the video to download from on-demand",
    )
    args = parser.parse_args()

    # Get the session from the provided ID or URL
    partner_id = None

    if args.conf_session_id:
        if args.rainforest_auth is None:
            raise ValueError(
                "Rainforest auth token is required for conference sessions"
            )

        session = Session.fetch_from_conference(
            args.rainforest_auth, args.conf_session_id
        )
    elif args.ondemand_session_url:
        response = requests.get(args.ondemand_session_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # get partner id from image url
        image = soup.find("meta", attrs={"property": "og:image"}).get("content")
        partner_id = image.split("/")[4]
        session_id = soup.find("meta", attrs={"property": "event_sessionId"}).get(
            "content"
        )

        session = Session.fetch_from_ondemand(session_id)

    else:
        raise ValueError("No session ID provided")

    # Prepare the paths
    print(f"title: {session.title}")
    print(f"abstract: {session.abstract}")
    print(f"presenters: {', '.join(p.name for p in session.participants)}")

    base_filename = (
        f"{', '.join(p.name for p in session.participants)} - {session.title}"
    )
    base_filename = sanitize_filename(base_filename)
    video_path = os.path.join(args.directory, f"{base_filename}.mp4")
    print(f"video path: {video_path}")
    if os.path.exists(video_path):
        os.remove(video_path)
    meta_path = None

    if args.meta:
        meta_path = os.path.join(args.directory, f"{base_filename}.json")
        if os.path.exists(meta_path):
            os.remove(meta_path)
        print(f"metadata path: {meta_path}")

    # Get the metadata and select our profile
    entry_id = None
    ks = None
    if args.conf_session_id:
        webinar = Webinar.fetch(args.rainforest_auth, session)
        partner_id = webinar.partner_id
        entry_id = webinar.entry_id
        ks = webinar.ks
    else:
        entry_id = session.kaltura_id

    metadata = KalturaMetadata.fetch_from_params(partner_id, entry_id, ks)

    profile = max(
        metadata.profiles, key=lambda p: p.width * p.height * p.bitrate * p.frame_rate
    )
    print("selected profile:", profile)

    # Download the video
    return_code = metadata.fetch_video(
        partner_id, ks, profile, session.length, video_path
    )
    if return_code == 0:
        print("download: succeeded")
    else:
        print("download: failed")

    # Write metadata
    if args.meta:
        with open(meta_path, "w") as f:
            output_metadata = OutputMetadata.build(session, profile)
            output_metadata_dict = output_metadata.dict()
            f.write(json.dumps(output_metadata_dict, indent=4))
        print("metadata: written")

    # Exit
    exit(return_code)
