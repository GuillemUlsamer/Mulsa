# Mulsa

This project keeps a local music folder in sync with your Google Sheets.

If you tick a song in your spreadsheet, Mulsa searches for it on Soulseek (through slskd), downloads it, converts it to MP3, writes the metadata (artist, title, album, year, track number and cover art) and reports the status back to the sheet. If you untick a song, it deletes it.

It includes a Google Apps Script (playlistHelper.gs) to import tracklists from Discogs into the sheet.

## Features
- Sync music library with Google Sheets
- Download tracks from Soulseek automatically (strives for best bitrate)
- Up to 5 downloads at once, spread across users; remembers which users serve well
- Convert to MP3
- Add metadata: artist, title, album (compilation + volume), year, track number and cover art
- Flag songs worth checking (verify) when the duration looks off or the match came from a search without artist
- Create playlists in your Google Drive from the app: import a Discogs release or a whole Discogs list (one volume per release), with a Releases catalog sheet (album, year and cover)
- Import playlists from an xlsx file
- Desktop app with playlist cards, per-song progress, stop button and a summary of what got downloaded
- Sign in with Google: Mulsa only sees the sheets you pick or creates

## Tech Stack
- Python (FastAPI, uvicorn, pywebview, gspread, mutagen)
- Angular (user interface)
- Google Sheets API
- slskd (Soulseek client, REST API)
- FFmpeg
- Google Apps Script

## Prerequisites
1.  **Soulseek account**: username and password. If the user does not exist, it is created with that password the first time it connects.
2.  **Google account**, to keep the playlists in Google Sheets. You sign in from the app.

## Installation
1.  Download `MulsaSetup-x.x.x.exe` from the [Releases](https://github.com/GuillemUlsamer/Mulsa/releases) page and run it. It creates a desktop shortcut.
2.  Open Mulsa. The first time, the settings screen shows up:
    *   Soulseek username and password.
    *   Music folder: where playlists are saved (one subfolder per playlist).
    *   Shared folder (optional): what you offer to the Soulseek network. Sharing something makes more users serve you.
    *   Soulseek port (leave 50300 if you don't know what it is).
    *   **Sign in with Google**: opens your browser; accept and come back. Mulsa asks only for access to the files you pick or it creates.

    Fields marked with `*` are required.
3.  Press **Save**. It downloads slskd (the Soulseek client) and configures it; it takes about a minute. Everything lives in `%LOCALAPPDATA%\Mulsa`, outside the music folder.

To update, install the new version on top; settings are kept.

Advanced: instead of signing in you can use a Google service account (`credentials.json`) with the sheets shared to it. That is how older versions worked and it still does.

## Spreadsheet Setup
Mulsa creates and fills the sheets for you (see **Usage**). This section is for sheets made by hand, and for the optional Apps Script helper that lets you import from Discogs inside Google Sheets, for example from your phone.

### Column Layout (Manual)
If you prefer to do it by hand, the spreadsheet must have the following columns (starting at column A):

| Column | Suggested Name | Description |
| :--- | :--- | :--- |
| A | Position | Track number |
| B | Artist | Artist name |
| C | Title | Song name |
| D | Duration | Track length (mm:ss or h:mm:ss) |
| E | Cumulative | (Optional) |
| F | Download | **Checkbox** (TRUE to download, FALSE to delete) |
| G | Status | Written by the app |
| H | Notes | (Optional) |

### Discogs Helper (optional)
Same as the app's setup and imports, but as a menu inside Google Sheets, usable from your phone. Needs your own Discogs token (discogs.com/settings/developers) in the script:
1.  Open your spreadsheet in Google Sheets.
2.  Go to Extensions > Apps Script.
3.  Add the library: 1efgoS3Xk_cBVN14eYvrbJngBN8EuUARaOQsqbWSH-eFU6SWdwZR4Tv9N
4.  Paste this into the editor:
   
function onOpen() { General_music_manager.onOpen(); }

function showImportDialog() { General_music_manager.showImportDialog(); }

function showListImportDialog() { General_music_manager.showListImportDialog(); }

function showSetupDialog() { General_music_manager.showSetupDialog(); }

function setupSheet(sheetFileName, volNum) { General_music_manager.setupSheet(sheetFileName, volNum); }

function importDiscogsRelease(sheetName, releaseId) { General_music_manager.importDiscogsRelease(sheetName, releaseId); }

function importDiscogsList (listId) { General_music_manager.importDiscogsList(); }

function getOrCreateReleasesSheet(spreadsheet) { General_music_manager.getOrCreateReleasesSheet(spreadsheet); }

function initializeReleasesSheetHeaders(releasesSheet) { General_music_manager.initializeReleasesSheetHeaders(releasesSheet); }

function appendReleaseToCatalog(albumName, releaseYear, coverUrl) { General_music_manager(albumName, releaseYear, coverUrl); }

function durationToSeconds(duration) { General_music_manager.durationToSeconds(duration); }

function secondsToSheetsDuration(seconds) { General_music_manager.secondsToSheetsDuration(seconds); }

5.  Reload the sheet. A custom menu appears to import Discogs releases by ID.

Besides importing by Release ID, the menu also includes:
- **Import Discogs List**: imports a whole list and creates one volume per release.
- **Releases** sheet: keeps a catalog of imported albums (name, year and cover).

## Usage
Open Mulsa from the shortcut. Your playlists show up as cards with cover and year. Ways to get them there:
- **New playlist** creates a Google Sheet in your Drive (in the folder you picked with Add from Google, or the Drive root) and opens its setup page. There you either **Import list** (a Discogs list ID: one volume per release, filled in) or **Set up** N empty volumes and **Import** a Discogs release ID into each one. **Open in Drive** shows the sheet while it fills. The first time a sheet shows a cover, Google asks you to allow `IMAGE()` to load external URLs: click **Allow access** once.
- **Add from Google** opens a Google Drive picker in your browser. Pick the sheets you want (several at once with Shift); Mulsa only sees the sheets you pick there or creates itself, so a sheet you make by hand in Drive has to be picked once. Picking a folder saves it as the place where New playlist creates sheets.
- **Import xlsx** loads a spreadsheet exported from Google Sheets (File > Download > xlsx) with the same column layout. Mulsa keeps a copy and writes the status there.

Tick the songs you want in the sheet (from any device), then pick the playlist and press **Run**: it downloads the ticked songs into a `PLAYLIST NAME` subfolder of your music folder, showing the state of each song (searching, downloading, converting, done or failed).

**Stop** stops and shuts down slskd. When the run finishes, the list shows the songs worth checking. **Copy log** copies a summary of what got downloaded plus the detailed log to the clipboard, in case you want to look into a failure. **Setup** goes back to the playlist's setup page, and **Delete** sends the sheet to the Drive trash (or removes the imported xlsx); downloaded music is kept. **Settings** (on the playlists screen) goes back to the settings screen.

If you untick a song that was already downloaded, the next run deletes it from the folder.

### Status in the sheet
The Status column shows `Downloaded`, `Downloaded (verify)` (check it: odd duration, or found through a search without artist) or `Failed, Do it manually`. Failed songs are retried on every run while they stay ticked.

## Common Problems

### Soulseek cannot connect 
If you are on a network that blocks Soulseek traffic (university wifi, company VPN), slskd cannot connect at all: try from another network.

### Setting up the project on another computer
Install from the same installer, fill in the settings and sign in with Google again. Playlists you picked or created are already authorized for Mulsa, so they show up right away.

## Development

```
git clone https://github.com/GuillemUlsamer/Mulsa.git
cd Mulsa
pip install -r requirements.txt
cd web && npm ci && cd ..
```

Google sign-in and Discogs covers need two files that are not in the repo, both under `assets/`: `google_client.json` (an OAuth desktop client from Google Cloud, with the `drive.file` scope) and `discogs_client.json` (`{"key": ..., "secret": ...}` from a Discogs application). Without them the app still runs, without Google and without covers. The release workflow writes them from the `GOOGLE_CLIENT_JSON` and `DISCOGS_CLIENT_JSON` repository secrets.

While developing, two terminals:

```
python -m uvicorn api:app --reload --port 8765     # backend, restarts when a .py changes
cd web; ng serve                                   # frontend at http://localhost:4200, reloads on its own
```

The native file dialogs only work inside the app window: `cd web; ng build; cd ..; python main.py`.

To build the exe and the installer (needs [Inno Setup 6](https://jrsoftware.org/isdl.php)):

```
cd web; ng build; cd ..
python -m pip install pyinstaller
python -m PyInstaller --noconfirm Mulsa.spec
& "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Releases are published by pushing a `vX.Y.Z` tag: GitHub Actions builds the installer and uploads it to Releases.

## Project Structure

*   `main.py`: Starts the backend and opens the app window.
*   `api.py`: HTTP API (FastAPI): playlists, runs, settings and live events for the interface.
*   `web/`: Angular interface (playlists, runner, setup, settings). `web/public/picker.html` is the Google Drive picker, opened in the system browser.
*   `manager.py`: Orchestrates a run: starts slskd, reads the sheet, downloads, shuts slskd down.
*   `bootstrap.py`: First run: downloads slskd and generates its configuration.
*   `sheets.py`: Playlist sources (Google sheet or imported xlsx), creating and filling sheets, listing playlists; splits songs across threads.
*   `gauth.py`: Google sign-in (OAuth) and token storage.
*   `discogs.py`: Discogs API calls.
*   `downloader.py`: Search strategy (exact, album, loose, title, artist, queued retry, last resort).
*   `matching.py`: Scores and filters candidates.
*   `slskd_client.py`: slskd API calls, FLAC to MP3 conversion, user memory.
*   `tagging.py`: Filename cleanup and ID3 tags.
*   `log.py`: Event channel between the pipeline and the interface, plus the detailed log.
*   `playlistHelper.gs`: Optional Apps Script with the same setup and Discogs imports inside Google Sheets.
*   `requirements.txt`: Python dependencies.
*   `Mulsa.spec`, `installer.iss` and `.github/workflows/release.yml`: exe, installer and automatic release.