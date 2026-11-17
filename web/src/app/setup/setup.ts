import { Component, OnInit, OnDestroy, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { Api } from '../api';
import { Page } from '../page/page';

// Lo que hacia el menu music_manager del Apps Script: crear la hoja, importar una lista de
// Discogs, o preparar N volumenes e importar un release en cada uno.
@Component({
  imports: [RouterLink, FormsModule, Page],
  selector: 'app-setup',
  styleUrl: './setup.scss',
  templateUrl: './setup.html',
})
export class Setup implements OnInit, OnDestroy {
  private api = inject(Api);
  private router = inject(Router);
  private sub?: Subscription;

  // sin name: pantalla de crear; con name: setup de una playlist de Google existente
  name = input<string>();
  newName = '';
  listId = '';
  volumeCount = 1;
  releaseIds: Record<string, string> = {};
  volumes = signal<string[]>([]);
  sheetUrl = signal('');
  driveFolder = signal('');
  status = signal('');
  busy = signal(false);

  ngOnInit() {
    if (this.name()) this.loadVolumes();
    else this.api.settings().subscribe(s => this.driveFolder.set(s.drive_folder));
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  loadVolumes() {
    this.api.volumes(this.name()!).subscribe({
      next: r => { this.volumes.set(r.volumes); this.sheetUrl.set(r.url); this.volumeCount = r.volumes.length || 1; },
      error: e => this.status.set(e.error?.detail ?? 'Error'),
    });
  }

  openInDrive() {
    this.api.openUrl(this.sheetUrl()).subscribe();
  }

  create() {
    const name = this.newName.trim();
    if (!name) return;
    this.busy.set(true);
    this.status.set('Creating...');
    this.api.newPlaylist(name, 1).subscribe({
      next: () => { this.api.playlistsCache.set([]); this.router.navigate(['/setup', name]); },
      error: e => { this.busy.set(false); this.status.set(e.error?.detail ?? 'Error'); },
    });
  }

  setup() {
    this.busy.set(true);
    this.status.set('Setting up volumes...');
    this.api.setupPlaylist(this.name()!, this.volumeCount).subscribe({
      next: () => { this.busy.set(false); this.status.set('Volumes ready.'); this.loadVolumes(); },
      error: e => { this.busy.set(false); this.status.set(e.error?.detail ?? 'Error'); },
    });
  }

  importList() {
    if (!this.listId.trim()) return;
    this.startImport(this.api.importList(this.name()!, this.listId.trim()));
  }

  importRelease(volume: string) {
    const id = (this.releaseIds[volume] ?? '').trim();
    if (!id) return;
    this.startImport(this.api.importRelease(this.name()!, volume, id));
  }

  // Los imports corren en el backend y avisan por el log; seguimos sus lineas hasta el final.
  private startImport(request: ReturnType<Api['importList']>) {
    this.busy.set(true);
    this.status.set('Importing...');
    request.subscribe({ error: e => { this.busy.set(false); this.status.set(e.error?.detail ?? 'Error'); } });
    this.sub?.unsubscribe();
    this.sub = this.api.events().subscribe(e => {
      if (e.kind !== 'line') return;
      this.status.set(e.text);
      if (e.text.startsWith('Import finished') || e.text.startsWith('Import failed')) {
        this.busy.set(false);
        this.api.playlistsCache.set([]);
        this.loadVolumes();
        this.sub?.unsubscribe();
      }
    });
  }
}
