Downloads a given GTC 2024 video.

## Usage
### First-time setup
- Ensure you have [Poetry](https://python-poetry.org/) and `ffmpeg` (including `ffprobe`) installed.
- Run `poetry install` to install the required dependencies.

### Authenticating
You only have to do this if you don't have an authentication token or your token has expired.

1. Go to <https://www.nvidia.com/gtc/session-catalog/?#/> while logged in.
2. Open the developer console (F12 / Ctrl+Shift+I) and go to the "Network" tab, and filter on XHR requests.
3. Reload the page.
4. Look for any POST requests to `events.rainfocus.com` after the `login` request. This will be the last few requests. (e.g. `myData`, `attributes`, `search`, etc)
5. In the headers for the request, look for `rfAuthToken`. Copy the value. It should be a long string of random characters.

### Downloading a video
You can now download a video given its session ID:
```sh
poetry run python download.py -a "$YOUR_AUTH_TOKEN" $SESSION_ID
```

This will download the video to the current directory with the filename `{AUTHORS} - {TITLE}.mp4`.

Parameters:
- `-a`/`--rainforest-auth` (required): Your Rainforest authentication token.
- `-d`/`--directory`: The directory to save the video to. Defaults to the current directory.
- `-m`/`--meta`: Save metadata about the video to a JSON file. Stored in the same directory as the video as `{AUTHORS} - {TITLE}.json`.
- `id` (required): The session ID of the video to be downloaded. This can be found in the URL of the session page. For example, `https://www.nvidia.com/gtc/session-catalog/?#/session/1702594702652001JJhD` has an ID of `1702594702652001JJhD`.

## Suggested videos
I downloaded these while testing. You may find them useful as well:

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
- `1696033648682001S1DC`: CUDA: New Features and Beyond (_Stephen Jones (_SW)_)
