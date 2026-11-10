# VR2Windy

VR2Windy is a Windy plugin that displays the latest Virtual Regatta boat
position and lets you compare GPX routes and forecast waypoints. The plugin
uses a local NMEA proxy; it does not send position data to a third-party
service.

The ITYC Dashboard distribution is required to provide the NMEA feed. Its
standard Avalon proxy is not included in this repository. The dashboard sends
a copy of NMEA output to the dedicated Windy proxy on port `8085`.

## Requirements

- ITYC Dashboard installed in Chrome, Edge, or Opera.
- Python 3 for the local NMEA proxy.
- Tkinter for the optional graphical proxy controller (on Linux it may require
  the distribution's `python3-tk` package).
- Node.js and npm to build and serve the plugin.
- OpenSSL to generate a development HTTPS certificate.

## Run locally

1. Start the graphical proxy controller from this repository's root:

   ```sh
   python3 proxy_control.py
   ```

   On Windows, use `py proxy_control.py` if `python3` is not available. Click
   **Démarrer** to start the proxy. The controller also provides **Arrêter**,
   **Redémarrer**, a status indicator, and a log. Closing the controller
   stops the proxy it started, after confirmation. It does not control a proxy
   started separately; stop that process first if port 8085 is already in use.

   Alternatively, run `python3 nmea_windy_proxy.py` in a terminal and stop it
   with `Ctrl+C`. By default, the proxy listens only on `127.0.0.1:8085`.

   On Linux with GNOME, install a per-user application launcher so GNOME can
   associate the window with the proxy icon in the Dash and taskbar:

   ```sh
   python3 scripts/install_proxy_launcher.py
   ```

   Close the controller and start **VR2Windy Proxy** from the applications
   menu. You can then pin it to the Dash. The launcher points to this project
   directory and uses `proxy_icon.png`; rerun the installer if you move the
   project or change your Python installation. It writes
   `vr2windy-proxy.desktop` under `$XDG_DATA_HOME/applications`, or under
   `~/.local/share/applications` when `XDG_DATA_HOME` is unset.

2. Open Virtual Regatta and the ITYC Dashboard. Select a race and enable
   **NMEA output**. Keep the dashboard's normal NMEA port configured for your
   existing client; the dashboard also sends a copy to port `8085` for
   VR2Windy.

3. Install dependencies and start the HTTPS development server:

   ```sh
   npm ci
   npm start
   ```

4. Open [Windy Developer Mode](https://www.windy.com/developer-mode), load
   `https://localhost:9999/plugin.js`, and add VR2Windy. Accept the local
   certificate warning as needed.

5. In VR2Windy, enter the numeric race ID (without the stage number), keep port
   `8085` selected, and click **Follow this race**. The map marker and
   coordinates update as NMEA positions arrive. A vector shows the distance
   traveled in one hour at the current COG/SOG. When available, the plugin
   also shows true wind (IIMWV, reference `T`), apparent wind (IIVWR, including
   port/starboard), true heading (IIHDT), and ITYC sail number and energy
   (IIRPM). Wind speeds are reported in knots. These measurements are kept
   separately for each race and remain at their last received value until
   updated or the proxy restarts.

6. To compare routes, import up to four `.gpx` files. Each route can be
   removed independently. For GPX files with timestamps, the plugin marks
   selected forecast waypoints; click a marker to move Windy's timeline to the
   recorded time.

The plugin selects GFS when it loads. You can choose a different forecast
model in Windy. Model update and reference times are read from Windy's
internal metadata manifest, which is not a documented API and may change.

## Build

```sh
npm ci
npm run build
```

The build writes `dist/plugin.js` and `dist/plugin.min.js`. `plugin.js` can be
loaded in Windy Developer Mode. Build output, `node_modules/`, and the
self-signed development certificate in `.local-ssl/` are generated locally
and are not committed.

## Publish to Windy

The GitHub Actions workflow **Publish plugin to Windy** uploads the built
plugin to Windy's plugin servers. It runs only when started manually from the
repository's **Actions** tab. Add a repository Actions secret named
`WINDY_API_KEY` before running it; the workflow builds the plugin, packages
`dist/`, and sends the archive to Windy's upload API.

The plugin's visibility is controlled by the `private` field in
[`src/pluginConfig.js`](./src/pluginConfig.js). It is currently `true`, so
uploads remain private.

## Network and privacy

The plugin requests loopback access to `localhost`; Chrome may ask for local
network permission. The proxy accepts browser CORS preflights only from
approved Windy origins. If you deliberately bind the proxy to another
interface, restrict access with your firewall and do not expose it directly
to the public Internet.

## License

VR2Windy is distributed under the GNU General Public License, version 3. See
[`LICENSE`](./LICENSE). Third-party components retain their own license
notices.
