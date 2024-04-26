Downloads a given GTC 2024 video from the conference catalogue or from the on-demand sessions.

## Usage
### First-time setup
- Ensure you have [Poetry](https://python-poetry.org/) and `ffmpeg` installed.
- Run `poetry install` to install the required dependencies.

### Parameters
- `-d`/`--directory`: The directory to save the video to. Defaults to the current directory.
- `-m`/`--meta`: Save metadata about the video to a JSON file. Stored in the same directory as the video as `{AUTHORS} - {TITLE}.json`.

One of the following is required:
- `-o`/`--ondemand-session-url`: The URL of the on-demand session to be downloaded.
- `-c`/`--conf-session-id`: The session ID of the session from the conference catalogue to be downloaded. This can be found in the URL of the session page. For example, `https://www.nvidia.com/gtc/session-catalog/?#/session/1702594702652001JJhD` has an ID of `1702594702652001JJhD`.
  - `-a`/`--rainforest-auth`: Your Rainforest authentication token - required if downloading from the conference catalogue. See below for instructions.

### Downloading a video from an on-demand session
You can download a video from an on-demand session by providing the URL of the session:
```sh
poetry run python download.py -m -o "$ONDEMAND_SESSION_URL"
```

This will download the video to the current directory with the filename `{AUTHORS} - {TITLE}.mp4`.

### Downloading a video from the conference catalogue
You will need to get an authentication token from Rainforest. You only need to do this if you don't have a token or if your token has expired; otherwise, you can keep using the same token.

1. Go to <https://www.nvidia.com/gtc/session-catalog/?#/> while logged in.
2. Open the developer console (F12 / Ctrl+Shift+I) and go to the "Network" tab, and filter on XHR requests.
3. Reload the page.
4. Look for any POST requests to `events.rainfocus.com` after the `login` request. This will be the last few requests. (e.g. `myData`, `attributes`, `search`, etc)
5. In the headers for the request, look for `rfAuthToken`. Copy the value. It should be a long string of random characters.

You can now download a video given its session ID:
```sh
poetry run python download.py -a "$YOUR_AUTH_TOKEN" -m --conf-session-id $SESSION_ID
```

This will download the video to the current directory with the filename `{AUTHORS} - {TITLE}.mp4`.

## Suggested videos
I downloaded these while testing. You may find them useful as well:

### On-demand sessions
- <https://www.nvidia.com/en-us/on-demand/session/gtc24-s62246/>: JAX Supercharged on GPUs: High Performance LLMs with JAX and OpenXLA (_Chang Lan, Nitin, Qiao Zhang_)

### Conference catalogue
These may no longer work as the conference has ended. You can try to find the corresponding on-demand session instead.

- `1694444293481001kBAn`: Better, Cheaper, Faster LLM Alignment With KTO (_Amanpreet Singh_)
- `1706747368510001RGVh`: Fireside Chat with David Luan and Bryan Catanzaro: The Future of AI and the Path to AGI (_Bryan Catanzaro, David Luan_)
- `1696440824445001lFOk`: Fireside Chat With Kanjun Qiu and Bryan Catanzaro: Building Practical AI Agents that Reason and Code at Scale (_Bryan Catanzaro, Kanjun Qiu_)
- `1694213266066001wkhe`: Beyond Transformers: A New Architecture for Long Context and Linear Performance (_Ce Zhang_)
- `1705548169759001iR7s`: Fireside Chat with Christian Szegedy and Bojan Tunguz: Automated Reasoning for More Advanced Software Synthesis and Verification (_Christian Szegedy,_ Bojan Tunguz)
- `1706123152858001fNnT`: Scaling Grok with JAX and H100 (_Igor Babuschkin_)
- `1702594702652001JJhD`: Transforming AI (_Jensen Huang, Ashish Vaswani, Noam Shazeer, Jakob Uszkoreit, Llion Jones, Aidan Gomez, Lukasz Kaiser, Illia Polosukhin_)
- `1695673049743001rLIc`: A Culture of Open and Reproducible Research, in the Era of Large AI Generative Models (_Joelle Pineau_)
- `1696292994102001l720`: Diffusion Models: A Generative AI Big Bang (_Karsten Kreis, Arash Vahdat_)
- `1705085165951001X0W8`: From Zero to Millions: Scaling Large Language Model Inference With TensorRT-LLM (_Kevin Hu_)
- `1696033648682001S1DC`: CUDA: New Features and Beyond (_Stephen Jones_)
