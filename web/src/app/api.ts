import { Injectable, inject, Service, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Playlist { 
    name: string;
    cover_url: string | null;
    year: string;
    volumes: number;
    source: 'google' | 'xlsx';
}

export interface Track {
    n: string;
    row: number;
    artist: string;
    title: string;
    marked: boolean;
    status: string;
}

export interface PlaylistInfo {
    volumes: { title: string; album: string; tracks: Track[] }[];
    marked: number;
    downloaded: number;
    back_cover: boolean;
}

export interface Settings {
    configured: boolean;
    soulseek_username: string;
    music_dir: string;
    share_dir: string;
    listen_port: number;
    // discogs_token: string;
    credentials_file: string;
    drive_folder: string;
}

export interface LogEvent {
    kind: 'song' | 'status' | 'line';
    song_id: [string, number] | null;
    text: string;
    tag: string | null;
}

@Injectable({ providedIn: 'root' })
export class Api {
    private http = inject(HttpClient);
    private base = '/api';
    playlistsCache = signal<Playlist[]>([]);
    // true: la lista cambio (run, setup...); Playlists la recarga por detras sin vaciarla
    playlistsStale = signal(false);
    running = signal(false);
    // ficha ya cargada en la pantalla 2, para que el runner abra con los datos listos
    infoCache = new Map<string, PlaylistInfo>();

    playlists(){
        return this.http.get<Playlist[]>(`${this.base}/playlists`);
    }
    settings(){
        return this.http.get<Settings>(`${this.base}/settings`);
    }
    summary(){
        return this.http.get(`${this.base}/summary`, { responseType: 'text' });
    }
    log(){
        return this.http.get(`${this.base}/log`, { responseType: 'text' });
    }
    saveSettings(body: Omit<Settings, 'configured' | 'drive_folder'> & {soulseek_password: string}) {
        return this.http.post(`${this.base}/settings`, body);
    }
    run(name: string){
        return this.http.post(`${this.base}/run/${encodeURIComponent(name)}`, null);
    }
    stop(){
        return this.http.post(`${this.base}/stop`, null);
    }
    status(){
        return this.http.get<{running: boolean}>(`${this.base}/status`);
    }
    pickFolder(){
        return this.http.post<{path: string}>(`${this.base}/pick-folder`, null);
    }
    pickFile(){
        return this.http.post<{path: string}>(`${this.base}/pick-file`, null);
    }
    importXlsx(){ 
        return this.http.post<{name: string | null}>(`${this.base}/playlists/import`, {});
    }
    googleStatus(){ 
        return this.http.get<{connected: boolean}>(`${this.base}/auth/google`); 
    }
    info(name: string) {
        return this.http.get<PlaylistInfo>(`${this.base}/playlists/${encodeURIComponent(name)}/info`);
    }
    deletePlaylist(name: string) {
        return this.http.delete(`${this.base}/playlists/${encodeURIComponent(name)}`);
    }
    volumes(name: string) {
        return this.http.get<{url: string, volumes: string[]}>(`${this.base}/playlists/${encodeURIComponent(name)}/volumes`);
    }
    newPlaylist(name: string, volumes: number) {
        return this.http.post<{name: string}>(`${this.base}/playlists/new`, { name, volumes });
    }
    setupPlaylist(name: string, volumes: number) {
        return this.http.post(`${this.base}/playlists/${encodeURIComponent(name)}/setup`, { volumes });
    }
    importList(name: string, list_id: string) {
        return this.http.post(`${this.base}/playlists/${encodeURIComponent(name)}/import-list`, { list_id });
    }
    importRelease(name: string, volume: string, release_id: string) {
        return this.http.post(`${this.base}/playlists/${encodeURIComponent(name)}/import-release`, { volume, release_id });
    }
    openUrl(url: string) {
        return this.http.post(`${this.base}/open-url`, { url });
    }
    openPicker(origin: string) {
        return this.http.post(`${this.base}/picker/open`, { origin });
    }
    googleLogin(){ 
        return this.http.post(`${this.base}/auth/google`, {}); 
    }
    googleLogout(){ 
        return this.http.delete(`${this.base}/auth/google`); 
    }
    events(): Observable<LogEvent> {
        return new Observable(subscriber => {
            const source = new EventSource(`${this.base}/events`);
            source.onmessage = e => {
                subscriber.next(JSON.parse(e.data));
            };
            source.onerror = () => {
                // EventSource reconecta solo (p. ej. tras un reinicio de uvicorn); no cerramos el stream
                console.warn('events stream reconnecting...');
            };
            return () => source.close();
        });
    }
}