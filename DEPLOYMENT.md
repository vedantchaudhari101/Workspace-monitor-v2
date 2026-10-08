# Put Workspace Monitor online for free (Oracle Cloud)

This guide takes you from the zip file on your laptop to a public link anyone can open, for example `https://workspace-monitor-yash.duckdns.org`. No prior hosting experience is needed. Copy the commands exactly as written.

**Time:** about 1½–2 hours the first time, most of it waiting.
**Cost:** ₹0. You need a credit card only to verify your identity.

## How it fits together

```
Your laptop                         Oracle Cloud (free server, Ubuntu Linux)
───────────                         ─────────────────────────────────────────
workspace-monitor-v2.zip  ──copy──▶ /home/ubuntu/workspace-monitor/
PowerShell (ssh)          ──type──▶ bash deploy/oracle/setup.sh
                                       │
                                       ├─ Caddy  : the front door on ports 80/443, handles HTTPS
                                       └─ App    : website + API + YOLO video analysis
Visitors' browsers ─────────────────▶ https://your-name.duckdns.org
```

You rent nothing and install nothing on your laptop. The server runs the whole project inside Docker, which the setup script installs for you.

## Before you start

- [ ] A **Visa or Mastercard credit card** with international transactions turned on in your bank app. RuPay, prepaid, virtual cards and most debit cards are rejected. Oracle places a small temporary hold (about ₹100) to verify it and releases it within a few days.
- [ ] Your phone, for SMS verification.
- [ ] The file `workspace-monitor-v2.zip` in your **Downloads** folder.
- [ ] A Windows 10/11 laptop (PowerShell is built in) or a Mac (use Terminal). The commands below are for Windows. Mac differences are noted.
- [ ] VPN switched **off** during signup. Oracle often rejects signups that come through a VPN.

> Oracle's website changes its button labels from time to time. If a label here doesn't match exactly, look for the closest one. The steps stay the same.

---

## Part 1 — Create your Oracle Cloud account

1. Go to **https://www.oracle.com/cloud/free/** and click **Start for free**.
2. Choose **India** as the country, enter your name and email, and verify the email from your inbox.
3. On the account page:
   - **Password:** choose a strong one and save it.
   - **Cloud Account Name:** a short unique name such as `yashcloud`. **Write it down**: you type it every time you sign in.
   - **Home Region:** choose **India Central (Hyderabad)**. Mumbai is also fine, but it often has no free servers left. **This cannot be changed later.**
4. Enter your address and phone number, then complete the card verification.
5. Click **Start my free trial**. Wait for the email titled *"Your Oracle Cloud account is fully provisioned"*. It can take from a few minutes to a few hours.

Ignore the "30-day trial" wording. After 30 days the trial credits expire, but the **Always Free** resources used in this guide stay free.

---

## Part 2 — Create the server

1. Go to **https://cloud.oracle.com**, enter your **Cloud Account Name**, click **Next**, and sign in.
2. Check the region shown at the top right. It must be your home region (for example *India Central (Hyderabad)*).
3. Click the **☰ menu** (top left) → **Compute** → **Instances** → **Create instance**.
4. Fill in the form:

   | Field | What to do |
   |---|---|
   | **Name** | `workspace-monitor` |
   | **Placement** | Leave as is. |
   | **Image and shape** | Click **Edit** (or **Change shape**) first. |
   | → **Shape** | **Virtual machine** → **Ampere** → tick **VM.Standard.A1.Flex**. Set **Number of OCPUs = 2** and **Amount of memory (GB) = 12**. Click **Select shape**. It should show an *Always Free-eligible* label. |
   | → **Image** | Click **Change image** → **Ubuntu** → **Canonical Ubuntu 24.04** (the console automatically picks the ARM version for this shape) → **Select image**. |
   | **Networking** | Leave **Create new virtual cloud network** and **Create new public subnet** selected. Make sure **Automatically assign public IPv4 address** is ticked. |
   | **Add SSH keys** | Choose **Generate a key pair for me** and click **Download private key**. The file looks like `ssh-key-2026-10-08.key`. **Keep it safe: without it you can't log in to the server.** |
   | **Boot volume** | Optional: tick **Specify a custom boot volume size** and enter `100`. The free allowance is 200 GB in total. |

5. Click **Create**. After a minute or two the status turns green: **RUNNING**.
6. On the instance page, find **Public IP address** (under *Instance access* or *Instance information*) and copy it. It looks like `140.238.12.34`. This guide calls it **YOUR_IP**.

### If you see "Out of capacity for shape VM.Standard.A1.Flex"

This means Oracle has no free ARM servers left in your region at the moment. It is common and not your fault.

- If an **Availability domain** dropdown appears under *Placement*, try a different one.
- Try again at another time of day. Late night and early morning work best. People often succeed after a few days of retrying.
- Try **1 OCPU / 6 GB**. You can resize the server to 2 / 12 later from the instance page (**More actions → Edit**).
- Upgrading to Pay As You Go (Part 9) is reported to help with capacity.

---

## Part 3 — Open the website ports

Oracle blocks web traffic until you allow it.

1. On your instance page, open **Primary VNIC** (or the *Networking* tab) and click the **Subnet** link (for example `subnet-2026...`).
2. Open **Security** (or **Security Lists**) and click **Default Security List for vcn-...**.
3. Open **Security rules** (or **Ingress Rules**) and click **Add Ingress Rules**.
4. Fill in one rule:
   - **Source Type:** CIDR
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** TCP
   - **Destination Port Range:** `80`
   - **Description:** `website http`
5. Click **+ Another Ingress Rule** and add the same again with **Destination Port Range** `443` and description `website https`.
6. Click **Add Ingress Rules**.

Port 22, which you use to log in, is already open by default.

---

## Part 4 — Log in to the server from your laptop

### Windows

1. Press **Start**, type **PowerShell**, and open **Windows PowerShell**.
2. Move the key into a safe place and lock it down. Paste these lines one at a time and press Enter after each:

   ```powershell
   mkdir $HOME\.ssh -Force
   Move-Item $HOME\Downloads\ssh-key-*.key $HOME\.ssh\oracle.key
   icacls $HOME\.ssh\oracle.key /inheritance:r
   icacls $HOME\.ssh\oracle.key /grant:r "$($env:USERNAME):(R)"
   ```

3. Connect. Replace `YOUR_IP` with your server's IP:

   ```powershell
   ssh -i $HOME\.ssh\oracle.key ubuntu@YOUR_IP
   ```

4. The first time it asks *"Are you sure you want to continue connecting?"*. Type `yes` and press Enter.
5. You're in when the prompt changes to something like `ubuntu@workspace-monitor:~$`. Every command you type in this window now runs **on the server**, not on your laptop.

### Mac

```bash
mkdir -p ~/.ssh && mv ~/Downloads/ssh-key-*.key ~/.ssh/oracle.key && chmod 400 ~/.ssh/oracle.key
ssh -i ~/.ssh/oracle.key ubuntu@YOUR_IP
```

To leave the server, type `exit`. To come back, run the same `ssh ...` command again.

---

## Part 5 — Copy the project to the server

**Easiest: get it straight from GitHub.** In the **SSH window** (the server), run:

```bash
git clone https://github.com/vedantchaudhari101/Workspace-monitor-v2.git workspace-monitor
cd workspace-monitor
ls
```

Then skip to Part 6. If you'd rather upload the zip from your laptop, follow the steps below instead.

1. Open a **second** PowerShell window on your laptop and leave the SSH window open. Run:

   ```powershell
   scp -i $HOME\.ssh\oracle.key $HOME\Downloads\workspace-monitor-v2.zip ubuntu@YOUR_IP:~/
   ```

   You'll see a progress bar. The zip is small, so this takes seconds.
   On a Mac: `scp -i ~/.ssh/oracle.key ~/Downloads/workspace-monitor-v2.zip ubuntu@YOUR_IP:~/`

2. Back in the **SSH window** (the server), unpack it:

   ```bash
   sudo apt-get update && sudo apt-get install -y unzip
   unzip workspace-monitor-v2.zip
   cd workspace-monitor
   ls
   ```

   You should see `backend`, `frontend`, `deploy`, `Dockerfile`, `README.md` and the other project files. The project now lives at **`/home/ubuntu/workspace-monitor`** on the server.

---

## Part 6 — Get a free web address (recommended)

Without this step your link is `http://YOUR_IP`. It works, but it has no HTTPS padlock and is hard to remember. DuckDNS gives you a free name with HTTPS.

1. Go to **https://www.duckdns.org** and sign in with Google or GitHub.
2. In the **sub domain** box, type a name, for example `workspace-monitor-yash`, and click **add domain**.
3. In the row that appears, paste **YOUR_IP** into **current ip** and click **update ip**.
4. Your address is now `workspace-monitor-yash.duckdns.org`. To check it, run this in PowerShell on your laptop:

   ```powershell
   nslookup workspace-monitor-yash.duckdns.org
   ```

   The **Address** in the answer should be YOUR_IP. It can take a minute to update.

Your server's IP doesn't change, so you only do this once.

---

## Part 7 — Run the setup (one command)

In the **SSH window**, inside `~/workspace-monitor`:

1. Start a *tmux* session. This keeps the setup running even if your laptop's connection drops:

   ```bash
   tmux new -s setup
   ```

   If it says `tmux: command not found`, run `sudo apt-get install -y tmux` first.

2. Run the setup:

   ```bash
   bash deploy/oracle/setup.sh
   ```

3. Answer the questions:

   | Question | Suggested answer |
   |---|---|
   | Domain | `workspace-monitor-yash.duckdns.org` (from Part 6). Leave it empty to use `http://YOUR_IP`. |
   | Admin email | Press Enter to keep `admin@workspace.dev`, or type your own. |
   | Admin password | Type one (at least 8 characters: letters, numbers, `@ # % _ . -`), or press Enter to generate one. |
   | Include the example building with demo data? | `Y`. It gives visitors something to explore straight away, and it's always labelled as demo data in the app. |
   | Show demo login button? | `N` if you'll share the password yourself. `Y` if anyone with the link should be able to sign in with one click. |

4. Wait. The first build downloads and installs everything, including PyTorch and the YOLO models, and takes **10–20 minutes**. When it finishes, it prints:

   ```
   ==> Done
   Open:      https://workspace-monitor-yash.duckdns.org
   Sign in:   admin@workspace.dev
   Password:  ...
   ```

If your connection drops during the build, log in again (Part 4) and run `tmux attach -t setup` to see it continue. When you're done, press `Ctrl+B`, then `D`, to leave tmux without stopping anything.

---

## Part 8 — Check that it works

1. Open your link in a browser. The first HTTPS visit can take up to a minute while the certificate is issued.
2. Sign in with the email and password from Part 7.
3. On the **Live** page, click **Try the sample video**, or **Choose video** to upload your own.
4. You should see *Analyzing workspace* while it finds the seats (about a minute on this server), then the video with green and red seat boxes.

**Your public link is live.** Put it in your README, résumé and LinkedIn.

> For a convincing demo, record your own 30–60 second clip with people's permission: a fixed camera placed high, chairs visible and empty at the start, then people sitting down and leaving. The bundled sample clip rarely registers occupancy, because its chairs are hidden behind the people.

---

## Part 9 — Keep it running for the long term

Oracle can take back free servers that look unused, and can close accounts that are never signed into. Do these once:

1. **Upgrade to Pay As You Go.** Go to **☰ → Billing & Cost Management → Upgrade and Manage Payment → Upgrade your account → Pay As You Go**.
   - You still pay nothing while you stay within the *Always Free* limits. This guide only uses Always Free resources.
   - Users report that upgraded accounts are not reclaimed for being idle. Oracle's documentation doesn't promise this, but it is the most reliable protection available.
   - Oracle may place another temporary card hold, which is released in 3–5 days.
2. **Set a spending alert** so nothing is ever charged by surprise. Go to **☰ → Billing & Cost Management → Budgets → Create Budget**:
   - **Name:** `zero-spend`
   - **Budget amount:** `1` (USD)
   - **Alert:** *Actual spend*, threshold **1** (percentage of budget), with your email.

   If you ever get this email, something non-free was created. Delete it.
3. **Sign in to the Oracle console at least once a month.** Oracle may treat accounts unused for 30 days as abandoned. Set a monthly phone reminder.
4. **Never create other resources** (databases, load balancers, extra servers) unless they show *Always Free-eligible*.
5. **Keep a backup** of the data now and then (Part 10).

Oracle reduced its free limits once in 2026 without notice. If it happens again, the project folder plus `deploy/oracle/.env` is everything you need to set up again anywhere, on Oracle or any Linux server.

---

## Part 10 — Everyday commands

Log in to the server (Part 4), then:

```bash
cd ~/workspace-monitor
```

| To… | Run |
|---|---|
| See if it's running | `sudo docker compose -f deploy/oracle/docker-compose.yml ps` |
| Watch the app's log (Ctrl+C to stop watching) | `sudo docker compose -f deploy/oracle/docker-compose.yml logs -f app` |
| Restart | `sudo docker compose -f deploy/oracle/docker-compose.yml restart` |
| Stop (data is kept) | `sudo docker compose -f deploy/oracle/docker-compose.yml down` |
| Start again | `sudo docker compose -f deploy/oracle/docker-compose.yml up -d` |
| Change the password, domain or demo button | `bash deploy/oracle/setup.sh`, answer **n** to "Keep these settings?" |
| See the saved settings and password | `cat deploy/oracle/.env` |
| Back up the database to the home folder | `sudo docker compose -f deploy/oracle/docker-compose.yml cp app:/data/workspace_monitor.db ~/backup-$(date +%F).db` |
| Install security updates (monthly) | `sudo apt-get update && sudo apt-get upgrade -y`, then `sudo reboot`. Everything restarts on its own. |

To copy a backup to your laptop, run this from PowerShell on your laptop:
`scp -i $HOME\.ssh\oracle.key ubuntu@YOUR_IP:~/backup-*.db $HOME\Downloads\`

The demo data option only applies the first time the app starts with an empty database.

---

## Part 11 — Update to a new version later

**From a zip:**

1. Copy the new zip to the server as in Part 5.
2. On the server:

   ```bash
   cd ~
   mv workspace-monitor workspace-monitor-old
   unzip workspace-monitor-v3.zip                       # use the new zip's name
   cp workspace-monitor-old/deploy/oracle/.env workspace-monitor/deploy/oracle/.env
   cd workspace-monitor
   bash deploy/oracle/setup.sh                          # answer Y to keep settings
   ```

**From GitHub** (if you used `git clone` in Part 5):

```bash
cd ~/workspace-monitor && git pull && bash deploy/oracle/setup.sh
```

Your data lives in Docker storage, not in the project folder, so it survives updates. When the new version works, you can delete the old folder: `rm -rf ~/workspace-monitor-old`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **Out of capacity** when creating the server | See the end of Part 2. Keep retrying. |
| `WARNING: UNPROTECTED PRIVATE KEY FILE!` | Run the two `icacls` lines from Part 4 again. On a Mac: `chmod 400 ~/.ssh/oracle.key`. |
| `Permission denied (publickey)` | Check the username is `ubuntu`, and that `-i` points at the `.key` file you downloaded for this server. |
| `Connection timed out` when using ssh | Check the instance is **RUNNING** and the IP is correct. |
| The site doesn't open at all | Check both ingress rules from Part 3 exist. On the server, run the "See if it's running" command. Both `app` and `caddy` should say *running*. |
| `http://YOUR_IP` works but `https://name.duckdns.org` doesn't | Check `nslookup` shows YOUR_IP (Part 6) and that port 443 is open (Part 3). See the HTTPS log with `sudo docker compose -f deploy/oracle/docker-compose.yml logs caddy`. |
| Setup stopped with an error during the build | Run `bash deploy/oracle/setup.sh` again. It continues where it can. If it fails again, copy the last 30 lines of output and ask for help. |
| `no space left on device` | Run `sudo docker system prune -af`, then run setup again. If it still fails, increase the boot volume in the Oracle console. |
| Forgot the password | `cat deploy/oracle/.env` |
| Upload fails | Videos are limited to 200 MB. Trim the clip or lower its resolution. |
| The site was fine but now doesn't load | Log in to the server and run the "See if it's running" command. If the server itself is gone, Oracle reclaimed it. Recreate it (Parts 2–7) and restore a backup. |

---

## Other ways to host

- **Any Linux server or VPS:** the same `deploy/oracle/setup.sh` works on any Ubuntu 22.04/24.04 machine with 4 GB of RAM or more, on x86 or ARM.
- **With PostgreSQL instead of SQLite:** `docker compose up -d --build` from the project root (see `docker-compose.yml`).
- **Hugging Face Spaces:** since mid-2026, Docker Spaces need a paid PRO plan, so it is no longer a free option for this project.
