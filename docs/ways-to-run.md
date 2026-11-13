# Three ways to run it, and getting a brief every day

## Three ways to run it

1. **Local (your computer, your key).** The command line from the [README quickstart](../README.md#try-it-without-installing). Briefs land in `briefs/`.
2. **Static demo (no key, no server).** `docs/demo/` replays the recorded brief in a window onto
   Composer's own screen: the compose sentence, the sources being read, the sand-and-words
   animation through each step, the weave, then the finished edition, where each card opens to
   show which of its words each article backs. `docs/demo/brief.html` is the same brief as a plain
   page. Host the `docs/` folder on any static host (GitHub Pages works), open
   `docs/demo/index.html` from disk, or serve it on your own computer and open
   http://127.0.0.1:8000/ :

   ```sh
   python3 -m http.server 8000 --bind 127.0.0.1 --directory docs/demo
   ```

   On a laptop the phone stands in the middle of the page, with what you are looking at beside
   it; on a phone it fills the screen. It makes no outside request and calls no model; with
   reduced motion it shows the finished edition. Rebuild the folder with:

   ```sh
   composer demo --site docs/demo
   ```

3. **The app, always on (your key, your machine or server).** `composer up` (after `./setup.sh`, see [install the app](install-the-app.md)) runs the
   full app on 127.0.0.1:8765 with its engine, optional narration and the daily brief. The 0.1 `composer serve`
   below still works: it shows the latest
   brief as a plain page (the one `docs/demo/brief.html` shows, not the phone replay) and a form
   to compose a new one. It listens on 127.0.0.1:8765 by default; open http://127.0.0.1:8765/ .
   Without a key it still shows the recorded brief, and Compose says that a key is needed.
   Other web sites open in your browser cannot use it: it answers only requests addressed to
   127.0.0.1 or localhost, and only its own page can start a brief.

   ```sh
   composer serve
   ```

   To let other machines reach it, set `COMPOSER_SERVER_PASS` to a long phrase first and start
   it with `--host 0.0.0.0`; it refuses to listen beyond this machine without one, because
   anyone who can compose spends your API credit. Put a TLS proxy in front of it. One brief runs
   at a time.

   To run it on a server with HTTPS and a login, use the container image with Docker Compose and Caddy:
   [docs/deploy-vps.md](deploy-vps.md) walks through it step by step, with a trial on your own computer first.

## To get this every day

Pick one of three:

1. **Your laptop.** Turn on the daily brief (`./setup.sh` asks; later, `composer setup --reconfigure schedule`). It
   runs only while `composer up` runs and that computer is awake, and you read it on that computer.
2. **Your own server with a domain.** Always on, and you can read it from anywhere, on any device. The container
   image, Caddy for HTTPS and one login: [docs/deploy-vps.md](deploy-vps.md).
3. **No setup (coming soon).** A daily brief by email from [lensmith.ai](https://lensmith.ai), with nothing to install. It is not live yet.
