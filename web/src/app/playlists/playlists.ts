import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Api, Playlist } from '../api';
import { Page } from '../page/page';
import { Shelf } from '../shelf/shelf';
import { SelectedRecord } from '../record/record';

@Component({
  imports: [RouterLink, Page, Shelf, SelectedRecord],
  selector: 'app-playlists',
  styleUrl: './playlists.scss',
  templateUrl: './playlists.html',
})

export class Playlists implements OnInit, OnDestroy {
  private api = inject(Api);
  private router = inject(Router);
  playlists = this.api.playlistsCache;
  loading = signal(false);
  private sub?: Subscription;
  selected = signal<{ p: Playlist; el: HTMLElement | null } | null>(null);

  ngOnInit() { 
    if (this.playlists().length === 0 || this.api.playlistsStale()) this.load();
    // al volver del runner, el disco que estaba abierto vuelve a estar seleccionado
    const back = history.state?.selected as string | undefined;
    if (back) {
      const p = this.playlists().find(x => x.name === back);
      if (p) this.selected.set({ p, el: null });
    }
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  // Dos fases: la lista de nombres llega rapido y la estanteria se pinta; luego cada disco pide
  // su portada, ano y volumenes y se va completando segun llegan.
  load() {
    this.loading.set(true);
    this.api.playlistsQuick().subscribe({
      next: list => {
        // conservar lo que ya sabiamos de cada una mientras llega lo nuevo
        const known = new Map(this.playlists().map(p => [p.name, p]));
        this.playlists.set(list.map(p => known.get(p.name) ? { ...known.get(p.name)!, source: p.source } : p));
        this.api.playlistsStale.set(false);
        let left = list.length;
        if (!left) this.loading.set(false);
        for (const p of list) {
          this.api.header(p.name).subscribe({
            next: h => {
              this.playlists.update(all => all.map(x => x.name === p.name ? { ...x, ...h } : x));
              if (--left === 0) this.loading.set(false);
            },
            error: () => { if (--left === 0) this.loading.set(false); },
          });
        }
      },
      error: () => this.loading.set(false),
    });
  }
  
  importXlsx() {
    this.api.importXlsx().subscribe(r => { if (r.name) this.load(); });
  }

  open(p: Playlist) {
    this.router.navigate(['/run', p.name], { state: { opened: true } });
  }

  setup(p: Playlist) {
    this.router.navigate(['/setup', p.name]);
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
