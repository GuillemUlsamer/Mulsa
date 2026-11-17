import { Component, inject, OnInit, signal} from '@angular/core';
import { RouterLink, Router} from '@angular/router';
import { Api, Playlist } from '../api';
import { Page } from '../page/page';

declare const gapi: any;
declare const google: any;

@Component({
  imports: [RouterLink, Page],
  selector: 'app-playlists',
  styleUrl: './playlists.scss',
  templateUrl: './playlists.html',
})

export class Playlists implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  playlists = this.api.playlistsCache;
  loading = signal(false);

  ngOnInit() { 
    if (this.playlists().length === 0) this.load();
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
  
  addFromGoogle() {
    this.api.pickerConfig().subscribe(cfg => {
      if (!cfg.token) { this.router.navigateByUrl('/settings'); return; }
      gapi.load('picker', () => {
        const picker = new google.picker.PickerBuilder()
          .setOAuthToken(cfg.token)
          .setDeveloperKey(cfg.api_key)
          .setAppId(cfg.app_id)
          .setOrigin(location.protocol + '//' + location.host)
          .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
          .addView(google.picker.ViewId.SPREADSHEETS)
          .setCallback((data: any) => {
            if (data.action === google.picker.Action.PICKED) this.load();
          })
          .build();
        picker.setVisible(true);
      });
    });
  }
}
