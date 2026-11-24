import { Component, OnInit, OnDestroy, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { Api, PlaylistInfo, DiscogsSearchResult } from '../api';
import { Page } from '../page/page';

interface ImportRow {
  vol: string;
  what: string;
  result: string;
  ok: boolean | null;
}

// Lo que hacia el menu music_manager del Apps Script: crear la hoja, importar una lista de
// Discogs, o preparar N volumenes e importar un release en cada uno.
@Component({
  imports: [FormsModule, Page],
  selector: 'app-setup',
  styleUrl: './setup.scss',
  templateUrl: './setup.html',
})
export class Setup implements OnInit, OnDestroy {
  api = inject(Api);
  private sub?: Subscription;

  // sin name: pantalla de crear; con name: setup de una playlist de Google existente
  name = input<string>();
  newName = '';
  listId = '';
  volumeCount = 1;
  searchQuery = '';
  searching = signal(false);
  searchError = signal('');
  searchResults = signal<DiscogsSearchResult[]>([]);
  selectedReleases = signal<DiscogsSearchResult[]>([]);
  releaseIds: Record<string, string> = {};
  info = signal<PlaylistInfo | null>(null);
  volumes = computed(() => this.info()?.volumes ?? []);
  totalTracks = computed(() => this.volumes().reduce((n, v) => n + v.tracks.length, 0));
  sheetUrl = signal('');
  driveFolder = signal('');
  status = signal('');
  error = signal(false);
  busy = signal(false);
  imports = signal<ImportRow[]>([]);
  progress = signal<{ done: number; total: number; pct: number } | null>(null);
  activityTitle = computed(() => {
    const p = this.progress();
    if (p) return `Importing release ${p.done + 1}/${p.total}`;
    if (this.busy()) return 'Importing…';
    return this.imports().length ? 'Recent imports' : 'No imports yet';
  });

  ngOnInit() {
    if (this.name()) {
      this.loadVolumes();
      const auto = history.state?.autoImport;
      if (auto && Array.isArray(auto) && auto.length > 0) {
        this.startImport(this.api.importReleases(this.name()!, auto));
      }
    } else {
      this.api.settings().subscribe(s => this.driveFolder.set(s.drive_folder));
    }
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  loadVolumes() {
    const name = this.name()!;
    this.api.volumes(name).subscribe({ next: r => this.sheetUrl.set(r.url), error: e => this.fail(e) });
    this.api.info(name).subscribe({ next: i => this.info.set(i), error: e => this.fail(e) });
  }

  private fail(e: any) {
    this.busy.set(false);
    this.error.set(true);
    this.status.set(e?.error?.detail ?? 'Error');
  }

  openInDrive() {
    this.api.openUrl(this.sheetUrl()).subscribe();
  }

  create() {
    const name = this.newName.trim();
    if (!name || this.busy()) return;
    this.busy.set(true);
    this.error.set(false);
    this.status.set('Creating...');
    this.api.newPlaylist(name, 1).subscribe({
      next: () => { this.api.playlistsStale.set(true); this.api.go(['/setup', name]); },
      error: e => this.fail(e),
    });
  }

  isSelected(id: number): boolean {
    return this.selectedReleases().some(r => r.id === id);
  }

  searchDiscogs() {
    const q = this.searchQuery.trim();
    if (!q || this.searching() || this.busy()) return;
    this.searching.set(true);
    this.searchError.set('');
    this.api.discogsSearch(q).subscribe({
      next: res => {
        this.searching.set(false);
        this.searchResults.set(res.results ?? []);
        if (!res.results?.length) {
          this.searchError.set('No releases found for this search.');
        }
      },
      error: e => {
        this.searching.set(false);
        this.searchError.set(e?.error?.detail ?? 'Error searching Discogs');
      }
    });
  }

  cleanCompilationTitle(raw: string): string {
    let s = raw.replace(/^(Various|Various Artists)\s*[-–—:]\s*/i, '').trim();
    s = s.replace(/\s*[-–—:]?\s*(Vol(\.|ume)?|Chapter|Part|Pt\.?|#)?\s*([0-9]+|[IVXLCDM]+)$/i, '').trim();
    return s || raw;
  }

  addSelectedRelease(r: DiscogsSearchResult) {
    if (this.isSelected(r.id)) return;
    if (!this.newName.trim()) {
      this.newName = this.cleanCompilationTitle(r.title);
    }
    this.selectedReleases.update(list => [...list, r]);
  }

  removeSelectedRelease(index: number) {
    this.selectedReleases.update(list => list.filter((_, i) => i !== index));
  }

  moveRelease(index: number, delta: number) {
    const list = [...this.selectedReleases()];
    const target = index + delta;
    if (target < 0 || target >= list.length) return;
    const temp = list[index];
    list[index] = list[target];
    list[target] = temp;
    this.selectedReleases.set(list);
  }

  findSeries(r: DiscogsSearchResult) {
    const series = this.cleanCompilationTitle(r.title);
    this.searchQuery = series;
    this.searchDiscogs();
  }

  createWithReleases() {
    const name = this.newName.trim();
    const releases = this.selectedReleases();
    if (!name || releases.length === 0 || this.busy()) return;
    this.busy.set(true);
    this.error.set(false);
    this.status.set('Creating playlist...');
    this.api.newPlaylist(name, releases.length).subscribe({
      next: () => {
        this.api.playlistsStale.set(true);
        this.api.go(['/setup', name], { autoImport: releases.map(r => r.id) });
      },
      error: e => this.fail(e),
    });
  }

  setup() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(false);
    this.status.set('Setting up volumes...');
    this.api.setupPlaylist(this.name()!, this.volumeCount).subscribe({
      next: () => { this.busy.set(false); this.status.set('Volumes ready.'); this.loadVolumes(); },
      error: e => this.fail(e),
    });
  }

  // Acepta el ID suelto o la URL de Discogs; un master no vale (no tiene tracklist propio).
  private parseRelease(raw: string): { id?: string; error?: string } {
    const s = raw.trim();
    if (!s) return {};
    if (/\/master\//.test(s)) return { error: 'This is a master, not a release' };
    const m = s.match(/(\d+)/);
    return m ? { id: m[1] } : { error: 'Not a Discogs ID' };
  }

  importList() {
    const id = this.listId.trim().match(/(\d+)/)?.[1];
    if (!id || this.busy()) return;
    this.imports.set([]);
    this.startImport(this.api.importList(this.name()!, id));
  }

  importRelease(volume: string) {
    const { id, error } = this.parseRelease(this.releaseIds[volume] ?? '');
    if (error) { this.imports.update(r => [{ vol: volume, what: this.releaseIds[volume], result: error, ok: false }, ...r]); return; }
    if (!id || this.busy()) return;
    this.imports.update(r => [{ vol: volume, what: `Release ${id}`, result: 'Importing…', ok: null }, ...r]);
    this.startImport(this.api.importRelease(this.name()!, volume, id));
  }

  // Los imports corren en el backend y avisan por el log; de sus lineas sale la actividad.
  private startImport(request: ReturnType<Api['importList']>) {
    this.busy.set(true);
    this.error.set(false);
    this.status.set('Importing...');
    request.subscribe({ error: e => this.fail(e) });
    this.sub?.unsubscribe();
    this.sub = this.api.events().subscribe(e => {
      if (e.kind !== 'line') return;
      const t = e.text;
      let m: RegExpMatchArray | null;
      if ((m = t.match(/^Importing release (\d+)\/(\d+)/))) {
        const done = +m[1] - 1, total = +m[2];
        this.progress.set({ done, total, pct: Math.round((done / total) * 100) });
      } else if ((m = t.match(/^(V \d+): (.*) · (\d+) tracks$/))) {
        const row = { vol: m[1], what: m[2], result: `${m[3]} tracks`, ok: true };
        this.imports.update(r => r[0]?.vol === m![1] && r[0].ok === null ? [row, ...r.slice(1)] : [row, ...r]);
      } else if (t.startsWith('Import finished') || t.startsWith('Import failed')) {
        if (t.startsWith('Import failed')) {
          this.error.set(true);
          this.imports.update(r => r[0]?.ok === null ? [{ ...r[0], result: t.replace('Import failed: ', ''), ok: false }, ...r.slice(1)] : r);
        }
        this.status.set(t);
        this.progress.set(null);
        this.busy.set(false);
        this.api.playlistsStale.set(true);
        this.loadVolumes();
        this.sub?.unsubscribe();
      }
    });
  }
}
