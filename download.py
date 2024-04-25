from __future__ import annotations

from typing import List, Optional
from tqdm import tqdm
from pydantic import BaseModel

import requests
import argparse
import subprocess
import re
import os
import json

RAINFOCUS_WIDGET_ID = "C5aHR3OlA60pUDILVE33Jbn8hagS4Fsw"
RAINFOCUS_API_PROFILE_ID = "hUVpYtzXsLcOoh4rkNjxpSodRKdtJlUs"

BASE_HEADERS = {
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
    session_time_id: str
    length: float
    abstract: str
    participants: List[Participant]
    attributes: dict[str, str]

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
            session_time_id=time["sessionTimeID"],
            length=item["length"],
            abstract=item["abstract"],
            participants=[
                {"name": p["fullName"], "bio": p.get("globalBio")}
                for p in item["participants"]
            ],
            attributes={a["attribute"]: a["value"] for a in item["attributevalues"]},
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

    def fetch(webinar: Webinar) -> KalturaMetadata:
        url = "https://cdnapisec.kaltura.com/api_v3/service/multirequest"

        headers = {**BASE_HEADERS, "Content-Type": "application/json"}

        request = {
            "1": {
                "service": "baseEntry",
                "action": "list",
                "ks": webinar.ks,
                "filter": {"redirectFromEntryId": webinar.entry_id},
                "responseProfile": {"type": 1, "fields": "id"},
            },
            "2": {
                "service": "baseEntry",
                "action": "getPlaybackContext",
                "entryId": "{1:result:objects:0:id}",
                "ks": webinar.ks,
                "contextDataParams": {
                    "objectType": "KalturaContextDataParams",
                    "flavorTags": "all",
                },
            },
            "apiVersion": "3.3.0",
            "format": 1,
            "ks": webinar.ks,
            "clientTag": "html5:v3.17.10",
            "partnerId": webinar.partner_id,
        }

        response = requests.post(url, headers=headers, json=request)
        output = response.json()

        entry_id = output[0]["objects"][0]["id"]
        profiles = output[1]["flavorAssets"]
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

    def fetch_length(self, webinar: Webinar, profile: FlavorProfile) -> float:
        url = self._manifest_url(webinar, profile)
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
        ]
        command.extend(self._headers_args())
        command.append(url)

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        duration = float(result.stdout)
        return duration

    def fetch_video(
        self,
        webinar: Webinar,
        profile: FlavorProfile,
        duration: float,
        output_path: str,
    ):
        url = self._manifest_url(webinar, profile)
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

    def _manifest_url(self, webinar: Webinar, profile: FlavorProfile) -> str:
        return f"https://cdnapisec.kaltura.com/p/{webinar.partner_id}/sp/{webinar.partner_id}00/playManifest/entryId/{self.entry_id}/protocol/https/format/applehttp/flavorIds/{profile.id}/ks/{webinar.ks}/a.m3u8"


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
        "-a", "--rainforest-auth", help="The Rainforest auth token", required=True
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
    parser.add_argument("id", help="The ID of the video to download")
    args = parser.parse_args()

    # --------------------------------------------
    session = Session.fetch_from_conference(args.rainforest_auth, args.id)
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

    # --------------------------------------------
    webinar = Webinar.fetch(args.rainforest_auth, session)

    # --------------------------------------------
    metadata = KalturaMetadata.fetch(webinar)
    profile = max(
        metadata.profiles, key=lambda p: p.width * p.height * p.bitrate * p.frame_rate
    )
    print("selected profile:", profile)

    # --------------------------------------------
    length = metadata.fetch_length(webinar, profile)
    print(f"length: {length} seconds")

    # --------------------------------------------
    return_code = metadata.fetch_video(webinar, profile, length, video_path)
    if return_code == 0:
        print("download: succeeded")
    else:
        print("download: failed")

    # --------------------------------------------
    if args.meta:
        with open(meta_path, "w") as f:
            output_metadata = OutputMetadata.build(session, profile)
            output_metadata_dict = output_metadata.dict()
            f.write(json.dumps(output_metadata_dict, indent=4))
        print("metadata: written")
    exit(return_code)
