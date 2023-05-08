# toggl-track-earnings

Gratuitously display your monthly earnings as reported by [Toggl Track](https://toggl.com/) in your web browser.

<img src=".github/readme/Screencast%20from%202023-05-08%2014-41-54.gif" width="50%" height="50%" alt="Demo"/>

## Quick Start

```bash
# Install
pip install 'toggl_track_earnings @ git+https://github.com/logram-llc/toggl-track-earnings'

# Run
TOGGL_TRACK_USER='nicholas@logram.io' TOGGL_TRACK_PASS='xyz' TOGGL_TRACK_PORT='8000' toggl-track-earnings
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

The program start might take some time, but subsequent pulls from the API should be much faster. Toggl Track's API has a strict ratelimit (~1 req/sec).
