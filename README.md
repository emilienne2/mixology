# Chez Émilienne 🥃

This personal project is a full-stack, containerized cocktail recipe book and AI mixology assistant.

## 🏗️ Architecture & Stack

**Frontend** HTML5, Vanilla JavaScript, CSS (Served via Nginx)

**Backend** Python (FastAPI), packaged with Poetry

**Database** SQLite

**AI Assistant** Gemini 3.5 Flash-Lite on Google's free tier. The backend calls it over HTTPS.

**Deployment** Containerized with Docker Compose, designed for local hosting on a mini-computer via Cloudflare Tunnels.

## 🚀 Local Development Setup

### Prerequisites

- Docker Desktop
- Git

### Running the App

To spin up the frontend (Nginx) and the backend locally:

`docker compose up`

Frontend accessible at: `http://localhost:8080` 

Backend API is accessible at: `http://localhost:8000`

### Using the AI Assistant via the Get Creative chat

Get Creative asks Gemini 3.5 Flash-Lite how to change the recipe on the page. The FastAPI container sends the saved recipe, the portion count, the measurement system, and the question to Google, and shows the reply. The reply is not saved.

This is a short suggestion about one drink, so the free tier is enough. Google runs the model. The containers stay nginx, the API, and SQLite. Google may use these free-tier requests to improve its models.

Create a key in [Google AI Studio](https://aistudio.google.com/apikey) and choose **Default Gemini Project**. The project name and project number stay with that key.

Put the key in a `.env` file next to `docker-compose.yml`:

```
GEMINI_API_KEY=your-key
```

`.env` is gitignored. Restart the backend after saving it:

```
docker compose up -d backend
```

### Recipes database

Recipe files in `database/recipes/` are the committed copy. `database/mixology.db` is built from them and is not committed. Build that database before starting the app. The backend mounts the file read-only, and the pages read it through the API.

Build the full database from all committed recipe files:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/build_database.py
```

Add a new recipe to the existing database:

```
docker run --rm -v "$PWD":/work -w /work python:3 python database/add_recipe.py database/recipes/earl-grey-martini.json
```

### Testing

Three checks cover loader rules that building the database does not: the recipe path, a conflicting cup weight, and a spirit family inferred from the name.

```
docker run --rm -v "$PWD":/work -w /work python:3 python -m unittest database/test_recipe_rules.py
```

## Deployment

### Setting up a dedicated mini-computer to run the web app

A mini-computer will be set up to run headless. However, for initial set up,
a keyboard, mouse, monitor, and ethernet connection will be essential.

#### Flash Ubuntu onto a USB stick
1. Download the latest stable release of Ubuntu (live server version) and the associated `SHA256SUMS` file from https://releases.ubuntu.com/.
2. Verify the downloaded `.iso` file. 
   - **On Linux/Windows:** Run `sha256sum -c SHA256SUMS --ignore-missing` in the directory where Ubuntu was downloaded.
   - **On macOS:** Run `shasum -a 256 -c SHA256SUMS --ignore-missing` instead.
3. Flash the Ubuntu image onto a USB stick. If using a MacBook, Raspberry Pi Imager is a recommended and convenient app for flashing the image.

#### Set the mini-computer to boot upon power
1. To set up the computer to boot upon power, press the Delete key while powering on.
2. Within BIOS, navigate to **Chipset > PCH-IO Configuration** and set **State after G3** to **S0**.
3. Press **F4** to save and exit.

#### Install Ubuntu
1. Plug the USB into the mini-computer, and then press **F7** while powering it on. Select the USB as boot device and choose "Try or Install Ubuntu Server".
2. Use most default settings during install. Select "Install OpenSSH server".
3. Once installation completes, reboot. You can now disconnect the keyboard, mouse, and monitor, and perform the remaining steps via SSH over your local ethernet connection.

#### Basic computer set-up
1. Connect to the mini-computer via SSH, install network manager, and connect to Wi-Fi:
```bash
sudo apt update && sudo apt install -y network-manager
sudo nmtui  # Select "Activate a connection", choose your network, and enter your password, then Back > Quit
```
Verify Wi-Fi connection by running `ip -br addr` and confirming you now see an active `wlo1` connection. You can now disconnect the ethernet cable if desired.

2. Install mDNS service to enable SSH via hostname.
```
sudo apt install -y avahi-daemon
sudo systemctl enable --now avahi-daemon
```
While using Avahi Daemon, be sure to restrict incoming traffic via firewall (see the next step) and only use Avahi Daemon on a trusted local network. Also, keep packages updated by regularly running `sudo apt update && sudo apt upgrade`.
You can now ssh into the mini-computer via `ssh username@hostname.local`.

3. Update system packages, install Docker, standard admin CLI tools, and configure a basic firewall:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git curl htop ufw
sudo usermod -aG docker $USER  # exit the SSH session and reconnect after this step for change to take effect

sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5353/udp comment 'mDNS'
sudo ufw allow 8080/tcp
sudo ufw enable
sudo ufw status verbose  # verify firewall is active
```

4. Safely power down the mini-computer to remove from set-up station.
`sudo shutdown -h now`

### Setting up the app

1. On the mini-computer, clone the repo and build the database:
```
mkdir src
cd src
git clone https://github.com/emilienne2/mixology.git
cd mixology
docker run --rm -v "$PWD":/work -w /work python:3 python database/build_database.py
```

2. Create a .env file using the GEMINI_API_KEY, as set up on the laptop.

3. Start running the site.
```
docker compose up -d --build
```
Verify the the mini-computer is running the site by going to http://<hostname>.local:8080. You may need to try an incognito browser window to block the upgrade to https.

4. Make the site reachable from outside this network with a Cloudflare Tunnel. The tunnel is Cloudflare's `cloudflared` program. It runs on the mini-computer and connects out to Cloudflare, so no inbound port has to be opened. Point it at `http://localhost:8080`. Nginx on that port already forwards `/api/` to the API.

The domain's DNS must be hosted at Cloudflare. A free Cloudflare plan is enough. Register the name before logging the tunnel in. At https://dash.cloudflare.com, open **Domain Registration** and register the domain. A name bought there already uses Cloudflare DNS. Use that exact name as `<domain-name>` below. `www.<domain-name>` is a separate name, and the route command does not create it.

On the mini-computer, install `cloudflared`:

```
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install -y cloudflared
```

Log in, then create a named tunnel. `cloudflared tunnel login` prints a URL.
Open that URL on a computer with a browser, choose the domain, and authorize the tunnel. That writes `~/.cloudflared/cert.pem`.
If the file is there, login succeeded, and you can create the tunnel:  `cloudflared tunnel create chez-emilienne`

The create command prints a tunnel ID and writes `~/.cloudflared/<tunnel-id>.json`. Create `~/.cloudflared/config.yaml`, using that ID and a hostname on your domain:

```yaml
tunnel: <tunnel-id>
credentials-file: /home/<username>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: <domain-name>.com
    service: http://localhost:8080
  - service: http_status:404
```

Create the DNS record, then run the tunnel once in the foreground to confirm the hostname loads:

```
cloudflared tunnel route dns chez-emilienne <domain-name.com>
cloudflared tunnel run chez-emilienne
```

Leave that running and open `https://<domain-name>.com` from off the network. Stop it with Ctrl-C when the page loads, then install it as a service so it starts on boot:

```
sudo cloudflared --config /home/<username>/.cloudflared/config.yaml service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```
