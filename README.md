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
- Import playlists from Discogs
- Import Discogs lists (multi-release) and create volumes automatically
- Keep a Releases catalog sheet with album, year and cover
- Desktop app with playlist cards from your Drive, per-song progress, stop button and a summary of what got downloaded

## Tech Stack
- Python (FastAPI, uvicorn, pywebview, gspread, mutagen)
- Angular (user interface)
- Google Sheets API
- slskd (Soulseek client, REST API)
- FFmpeg
- Google Apps Script

## Prerequisites
1.  **Soulseek account**: username and password. If the user does not exist, it is created with that password the first time it connects.
2. **Google service account**:
    * Enable the Google Sheets and Google Drive APIs in Google Cloud Console.
    * Create a service account and download its JSON key.
    * Save the file as credentials.json anywhere you like; the app asks for its location on first run.
    * **Important**: share your spreadsheet with the service account email (client_email in the JSON) as an editor.

## Installation
1.  Download 'MulsaSetup-x.x.x.exe' from the [Releases](https://github.com/GuillemUlsamer/mulsa/releases) page and run it. It creates a desktop shortcut.
2.  Open Mulsa. The first time, the settings screen shows up:
    *   Soulseek username and password.
    *   Music folder: where playlists are saved (one subfolder per playlist).
    *   Shared folder (optional): what you offer to the Soulseek network. Sharing something makes more users serve you.
    *   Google `credentials.json`.
    *   Soulseek port (leave 50300 if you don't know what it is).

    Fields marked with `*` are required.
3.  Press **Save**. It downloads slskd (the Soulseek client) and configures it; it takes about a minute. Everything lives in `%LOCALAPPDATA%\Mulsa`, outside the music folder.

To update, install the new version on top; settings are kept.

## Spreadsheet Setup
You can set up the sheet by hand or with the included helper.

### Automatic Method (Recommended)
Use the `playlistHelper.gs` script to set up the sheets quickly:
1.  Install the script following the steps in the **Discogs Helper** section (below).
2.  Reload the Google Sheets page.
3.  In the `music_manager` menu at the top, select **Set up**.
4.  Enter the number of volumes (sheets) you want to create.
5.  The script generates the sheets with the right headers and column widths.

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

### Discogs Helper
To make importing music easier:
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
Open Mulsa from the shortcut. Your Google Drive sheets show up as cards with cover and year. Pick one and press **Run**: it downloads the ticked songs into a `PLAYLIST NAME` subfolder of your music folder, showing the state of each song (searching, downloading, converting, done or failed).

**Stop** stops and shuts down slskd. When the run finishes, the list shows the songs worth checking. **Copy log** copies a summary of what got downloaded plus the detailed log to the clipboard, in case you want to look into a failure. **Settings** (on the playlists screen) goes back to the settings screen.

If you untick a song that was already downloaded, the next run deletes it from the folder.

### Status in the sheet
The Status column shows `Downloaded`, `Downloaded (verify)` (check it: odd duration, or found through a search without artist) or `Failed, Do it manually`. Failed songs are retried on every run while they stay ticked.

## Common Problems

### Soulseek cannot connect 
If you are on a network that blocks Soulseek traffic (university wifi, company VPN), slskd cannot connect at all: try from another network.

### The window is blank 
Another program is using port 8765. Close it and open Mulsa again.

### Setting up the project on another computer
No need to redo anything in Google Cloud or share the sheet again.
1. Install from the same installer.
2. Copy credentials.json from the other machine. If you don’t have it at hand, create a new key in the same service account (Credentials > the account > Keys > Add key > JSON). It does not invalidate the other laptop’s key.
3. Fill in the settings.

## Project Structure

*   `main.py`: Starts the backend and opens the app window.
*   `api.py`: HTTP API (FastAPI): playlists, runs, settings and live events for the interface.
*   `web/`: Angular interface (playlists, runner, settings).
*   `manager.py`: Orchestrates a run: starts slskd, reads the sheet, downloads, shuts slskd down.
*   `bootstrap.py`: First run: downloads slskd and generates its configuration.
*   `sheets.py`: Reads and writes the Google sheet; splits songs across threads.
*   `downloader.py`: Search strategy (exact, album, loose, title, artist, queued retry, last resort).
*   `matching.py`: Scores and filters candidates.
*   `slskd_client.py`: slskd API calls, FLAC to MP3 conversion, user memory.
*   `tagging.py`: Filename cleanup and ID3 tags.
*   `log.py`: Event channel between the pipeline and the interface, plus the detailed log.
*   `playlistHelper.gs`: Script for Google Sheets (Google Apps Script).
*   `requirements.txt`: Python dependencies.
*   `Mulsa.spec`, `installer.iss` and `.github/workflows/release.yml`: exe, installer and automatic release.