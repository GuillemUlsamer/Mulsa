import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Api, Playlist } from '../api';
import { Page } from '../page/page';

@Component({
  imports: [RouterLink, Page],
  selector: 'app-playlists',
  styleUrl: './playlists.scss',
  templateUrl: './playlists.html',
})

export class Playlists implements OnInit, OnDestroy {
  private api = inject(Api);
  playlists = this.api.playlistsCache;
  loading = signal(false);
  private sub?: Subscription;

  ngOnInit() { 
    if (this.playlists().length === 0) this.load();
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  load() {
    this.loading.set(true);
    this.api.playlists().subscribe({
      next: p => { this.playlists.set(p); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
  
  importXlsx() {
    this.api.importXlsx().subscribe(r => { if (r.name) this.load(); });
  }

  cover(name_playlist: string) {
    return `/api/playlists/${encodeURIComponent( name_playlist )}/cover`;
  }
  
  // El selector se abre en el navegador del sistema; nos enteramos de que ha acabado por el log.
  addFromGoogle() {
    this.api.openPicker(location.origin).subscribe();
    this.sub?.unsubscribe();
    this.sub = this.api.events().subscribe(e => {
      if (e.kind !== 'line' || !e.text.startsWith('Google playlists')) return;
      this.load();
      this.sub?.unsubscribe();
    });
  }
}
