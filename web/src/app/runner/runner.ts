import { Component, OnInit, OnDestroy, ElementRef, afterNextRender, computed, effect, inject, input, signal, viewChild } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Api, LogEvent, PlaylistInfo, Track } from '../api';
import { Page } from '../page/page';

const EASE = 'cubic-bezier(.2,.7,.2,1)';
const WINDOW = 5;

interface Item {
  id: string | null;
  time: string;
  text: string;
  status: string;
  tag: string | null;
}

type Mark = '' | 'busy' | 'done' | 'verify' | 'failed';
type RunState = 'idle' | 'running' | 'finished';

// Dentro del disco (pantalla 3): a la izquierda el libreto con los temas del volumen elegido,
// a la derecha el disco en su bandeja y, al ejecutar, el log en vivo.
@Component({
  imports: [RouterLink, Page],
  selector: 'app-runner',
  styleUrl: './runner.scss',
  templateUrl: './runner.html',
})
export class Runner implements OnInit, OnDestroy {
  api = inject(Api);
  private router = inject(Router);
  private sub?: Subscription;
  private poll?: ReturnType<typeof setInterval>;

  name = input.required<string>();
  info = signal<PlaylistInfo | null>(null);
  items = signal<Item[]>([]);
  runState = signal<RunState>('idle');
  stoppedByUser = false;
  summary = signal('');
  // estado en vivo por tema: clave "volumen|fila"
  marks = signal<Map<string, Mark>>(new Map());
  current = signal<{ vol: string; song: string } | null>(null);
  processed = signal(0);
  // null = seguir al volumen que se esta procesando
  picked = signal<string | null>(null);
  windowStart = signal(0);

  private list = viewChild<ElementRef<HTMLElement>>('list');
  private booklet = viewChild<ElementRef<HTMLElement>>('booklet');
  private tray = viewChild<ElementRef<HTMLElement>>('tray');

  isGoogle = () => this.api.playlistsCache().find(p => p.name === this.name())?.source !== 'xlsx';
  playlist = computed(() => this.api.playlistsCache().find(p => p.name === this.name()));
  volumes = computed(() => this.info()?.volumes ?? []);
  activeVolume = computed(() => {
    const vols = this.volumes();
    const want = this.picked() ?? this.current()?.vol;
    return vols.find(v => v.title === want) ?? vols[0] ?? null;
  });
  activeIndex = computed(() => this.volumes().findIndex(v => v === this.activeVolume()));
  // ventana de 5 volumenes centrada en el activo; "..." a los lados para desplazarla
  visibleVolumes = computed(() => this.volumes().slice(this.windowStart(), this.windowStart() + WINDOW));
  pending = computed(() => { const i = this.info(); return i ? i.marked - i.downloaded : 0; });
  review = computed(() => {
    const out: { kind: Mark; ref: string; text: string }[] = [];
    for (const v of this.volumes()) {
      for (const t of v.tracks) {
        const m = this.mark(v.title, t);
        if (m === 'verify' || m === 'failed') out.push({ kind: m, ref: `${v.title} · ${t.n}`, text: `${t.artist} – ${t.title}` });
      }
    }
    return out;
  });
  counts = computed(() => {
    let done = 0, verify = 0, failed = 0;
    for (const v of this.volumes()) for (const t of v.tracks) {
      const m = this.mark(v.title, t);
      if (m === 'done') done++; else if (m === 'verify') verify++; else if (m === 'failed') failed++;
    }
    return { done, verify, failed };
  });

  constructor() {
    effect(() => {
      this.items();
      queueMicrotask(() => this.list()?.nativeElement.lastElementChild?.scrollIntoView({ block: 'end' }));
    });
    // cuando cambia el volumen activo, la ventana de pestanas se centra en el
    effect(() => {
      const i = this.activeIndex();
      const n = this.volumes().length;
      if (i >= 0) this.windowStart.set(Math.max(0, Math.min(i - Math.floor(WINDOW / 2), n - WINDOW)));
    });
    // viniendo de la caja abierta: las dos mitades crecen hasta las columnas
    afterNextRender(() => { if (history.state?.opened) this.animateEntry(); });
  }

  ngOnInit() {
    // la ficha ya se cargo al seleccionar el disco; se refresca igualmente por si cambio
    const cached = this.api.infoCache.get(this.name());
    if (cached) this.info.set(cached);
    this.api.info(this.name()).subscribe({ next: i => this.info.set(i), error: () => { if (!cached) this.info.set(null); } });
    if (this.api.running()) this.runState.set('running');
    this.sub = this.api.events().subscribe(e => this.apply(e));
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    if (this.poll) clearInterval(this.poll);
  }

  cover() {
    return `/api/playlists/${encodeURIComponent(this.name())}/cover`;
  }

  // marca de un tema: lo que ha pasado en esta ejecucion o, si no, lo que dice la hoja
  mark(vol: string, t: Track): Mark {
    const live = this.marks().get(`${vol}|${t.row}`);
    if (live !== undefined) return live;
    if (!t.marked) return '';
    if (t.status.includes('verify')) return 'verify';
    if (t.status.includes('Downloaded')) return 'done';
    if (t.status.includes('Failed')) return 'failed';
    return '';
  }

  markedIn(tracks: Track[]) {
    return tracks.filter(t => t.marked).length;
  }

  pick(title: string) {
    this.picked.set(title);
  }

  shiftWindow(d: number) {
    const n = this.volumes().length;
    this.windowStart.update(s => Math.max(0, Math.min(s + d * WINDOW, n - WINDOW)));
  }

  run() {
    this.items.set([]);
    this.marks.set(new Map());
    this.processed.set(0);
    this.summary.set('');
    this.stoppedByUser = false;
    this.picked.set(null);
    this.api.run(this.name()).subscribe(() => {
      this.api.running.set(true);
      this.runState.set('running');
    });
  }

  stop() {
    this.stoppedByUser = true;
    this.api.stop().subscribe();
    // el backend tarda en parar; cuando /status diga que no corre, pasamos a terminado
    this.poll = setInterval(() => this.api.status().subscribe(s => {
      if (!s.running) { clearInterval(this.poll); this.finish(); }
    }), 1000);
  }

  copyLog() {
    this.api.log().subscribe(log => navigator.clipboard.writeText(log));
  }

  // fundido de la pagina y vuelta a la estanteria con este disco seleccionado
  back() {
    const page = document.querySelector('app-page');
    const anim = page?.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 250, easing: 'linear', fill: 'forwards' });
    const go = () => this.router.navigate(['/'], { state: { selected: this.name() } });
    if (anim) anim.onfinish = go; else go();
  }

  remove() {
    const what = this.isGoogle() ? 'Send the sheet to the Drive trash?' : 'Remove the imported xlsx from Mulsa?';
    if (!confirm(`${what}\nDownloaded music is kept.`)) return;
    this.api.deletePlaylist(this.name()).subscribe({
      next: () => { this.api.playlistsCache.set([]); this.router.navigateByUrl('/'); },
      error: e => alert(e.error?.detail ?? 'Could not delete'),
    });
  }

  private finish() {
    if (this.runState() !== 'running') return;
    this.api.running.set(false);
    this.runState.set('finished');
    this.current.set(null);
    this.api.summary().subscribe(t => this.summary.set(t));
    // la hoja ya tiene los estados nuevos: refrescamos contadores y la lista de playlists
    this.api.info(this.name()).subscribe(i => this.info.set(i));
    this.api.playlistsCache.set([]);
  }

  private apply(e: LogEvent) {
    const id = JSON.stringify(e.song_id);
    const time = new Date().toLocaleTimeString('en-GB');
    if (e.kind === 'song' && e.song_id) {
      const [vol, row] = e.song_id;
      this.current.set({ vol, song: e.text.replace(/^\[[^\]]*\]\s*/, '') });
      this.setMark(vol, row, 'busy');
      this.items.update(i => [...i, { id, time, text: e.text, status: '', tag: null }]);
    } else if (e.kind === 'status' && e.song_id) {
      const [vol, row] = e.song_id;
      if (e.tag === 'done') { this.setMark(vol, row, e.text.includes('verify') ? 'verify' : 'done'); this.processed.update(n => n + 1); }
      else if (e.tag === 'failed' || e.tag === 'error') { this.setMark(vol, row, 'failed'); this.processed.update(n => n + 1); }
      this.items.update(i => i.map(item => item.id === id ? { ...item, status: e.text, tag: e.tag } : item));
    } else if (e.kind === 'line') {
      this.items.update(i => [...i, { id: null, time, text: e.text, status: '', tag: e.tag }]);
      if (e.text.startsWith('Finished') || e.text.startsWith('Stopped')) this.finish();
    }
  }

  private setMark(vol: string, row: number, m: Mark) {
    this.marks.update(map => { const next = new Map(map); next.set(`${vol}|${row}`, m); return next; });
  }

  // FLIP: el libreto arranca donde estaba la tapa abierta (a la izquierda del centro) y la
  // bandeja donde estaba la caja (a la derecha); cada uno crece hasta su sitio definitivo.
  private animateEntry() {
    const W = window.innerWidth, H = window.innerHeight;
    const from = (el: HTMLElement | undefined, left: number) => {
      if (!el) return;
      const r = el.getBoundingClientRect();
      const s = 420 / r.width, sy = 420 / r.height;
      const dx = left - r.left, dy = (H / 2 - 210) - r.top;
      el.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${s}, ${sy})` }, { transform: 'none' }],
        { duration: 450, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'backwards' });
    };
    from(this.booklet()?.nativeElement, W / 2 - 420);
    from(this.tray()?.nativeElement, W / 2);
    document.querySelector('app-page')?.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, easing: 'linear' });
    for (const sel of ['app-page .top', 'app-page .bottom', '.col-right .info'])
      document.querySelector(sel)?.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 450, easing: 'linear' });
  }
}
