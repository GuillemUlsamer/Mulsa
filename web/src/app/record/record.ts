import { Component, ElementRef, HostListener, afterNextRender, computed, effect, inject, input, output, signal, untracked, viewChild } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { Api, Playlist, PlaylistInfo } from '../api';

const EASE = 'cubic-bezier(.2,.7,.2,1)';

// Disco seleccionado (pantalla 2): sale de la estanteria al centro con su ficha al lado.
// La apertura y el cierre son "FLIP": se mide donde estaba el disco en la balda y donde
// acaba en el centro, y se anima la diferencia con la Web Animations API.
@Component({
  imports: [NgTemplateOutlet],
  selector: 'app-record',
  styleUrl: './record.scss',
  templateUrl: './record.html',
})
export class SelectedRecord {
  playlists = input.required<Playlist[]>();
  start = input.required<number>();
  originEl = input<HTMLElement | null>(null);
  // true al volver del runner: la caja empieza abierta con la bisagra en el centro y se cierra
  reverse = input(false);
  close = output<void>();
  open = output<Playlist>();
  setup = output<Playlist>();

  private api = inject(Api);
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private stage = viewChild.required<ElementRef<HTMLElement>>('stage');
  private big = viewChild.required<ElementRef<HTMLElement>>('big');
  private scrim = viewChild.required<ElementRef<HTMLElement>>('scrim');
  private panel = viewChild.required<ElementRef<HTMLElement>>('panel');

  current = signal(0);
  flipped = signal(false);
  opening = signal(false);
  info = signal<PlaylistInfo | null>(null);
  playlist = computed(() => this.playlists()[this.current()]);
  private closing = false;

  constructor() {
    // el indice inicial llega como input; a partir de ahi lo manejamos aqui (prev/next)
    effect(() => this.current.set(this.start()));
    // cada vez que cambia el disco, se pide su ficha
    effect(() => {
      const p = this.playlist();
      untracked(() => this.load(p));
    });
    afterNextRender(() => this.reverse() ? this.animateReverse() : this.animateOpen());
  }

  private load(p: Playlist | undefined) {
    this.info.set(null);
    if (p) this.api.info(p.name).subscribe({ next: i => { this.info.set(i); this.api.infoCache.set(p.name, i); }, error: () => this.info.set(null) });
  }

  cover(name: string) {
    return `/api/playlists/${encodeURIComponent(name)}/cover`;
  }

  backCover(name: string) {
    return `/api/playlists/${encodeURIComponent(name)}/back-cover`;
  }

  progress() {
    const i = this.info();
    return i && i.marked ? Math.round((i.downloaded / i.marked) * 100) : 0;
  }

  // desplazamiento y escala entre el disco de la balda y el escenario del centro
  private delta(from: HTMLElement) {
    const a = from.getBoundingClientRect();
    const b = this.stage().nativeElement.getBoundingClientRect();
    return {
      s: a.width / b.width,
      dx: a.left + a.width / 2 - (b.left + b.width / 2),
      dy: a.top + a.height / 2 - (b.top + b.height / 2),
    };
  }

  private shelfRecord(name: string) {
    return document.querySelector<HTMLElement>(`app-shelf .record[data-name="${CSS.escape(name)}"]`);
  }

  private animateOpen() {
    const from = this.originEl();
    if (!from) return;
    const { s, dx, dy } = this.delta(from);
    this.stage().nativeElement.animate(
      [{ transform: `translate(${dx}px, ${dy}px) scale(${s})` }, { transform: 'none' }],
      { duration: 380, easing: EASE });
    this.scrim().nativeElement.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: 'linear' });
    this.panel().nativeElement.animate(
      [{ opacity: 0, transform: 'translateX(12px)' }, { opacity: 1, transform: 'none' }],
      { duration: 200, delay: 180, easing: EASE, fill: 'backwards' });
  }

  // Abrir la caja: la ficha se va, la caja se endereza y se desplaza hasta que su bisagra
  // (borde izquierdo) queda en el centro, y la tapa gira 180 grados. A los 620 ms el runner
  // toma el relevo con las dos mitades planas (ver runner.ts).
  openCase() {
    if (this.closing || this.opening()) return;
    const p = this.playlist();
    this.flipped.set(false);
    this.opening.set(true);
    const stage = this.stage().nativeElement;
    const rect = stage.getBoundingClientRect();
    const dx = window.innerWidth / 2 - rect.left;
    const dy = window.innerHeight / 2 - (rect.top + rect.height / 2);
    stage.animate([{ transform: 'none' }, { transform: `translate(${dx}px, ${dy}px)` }],
      { duration: 800, easing: 'cubic-bezier(.65,0,.35,1)', fill: 'forwards' });
    this.panel().nativeElement.animate([{ opacity: 1 }, { opacity: 0, transform: 'translateX(12px)' }], { duration: 250, fill: 'forwards' });
    this.closing = true;
    // tapa abierta a los ~1100 ms; luego fundido a blanco y el runner entra con su propio fade
    setTimeout(() => this.host.nativeElement.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 350, fill: 'forwards' }), 2000);
    setTimeout(() => this.open.emit(p), 2050);
  }

  private animateReverse() {
    const stage = this.stage().nativeElement;
    const big = this.big().nativeElement;
    const rect = stage.getBoundingClientRect();
    const dx = window.innerWidth / 2 - rect.left;
    const dy = window.innerHeight / 2 - (rect.top + rect.height / 2);
    // estado inicial: abierta y centrada en la bisagra, sin transiciones
    big.classList.add('no-anim', 'is-opening');
    stage.style.transform = `translate(${dx}px, ${dy}px)`;
    this.panel().nativeElement.style.opacity = '0';
    this.scrim().nativeElement.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 250, easing: 'linear' });
    // en el siguiente frame se quita el estado abierto y las transiciones de CSS cierran la tapa
    requestAnimationFrame(() => requestAnimationFrame(() => {
      big.classList.remove('no-anim');
      big.classList.remove('is-opening');
      stage.style.transform = '';
      stage.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }],
        { duration: 1000, delay: 300, easing: 'cubic-bezier(.65,0,.35,1)', fill: 'backwards' });
      this.panel().nativeElement.animate([{ opacity: 0, transform: 'translateX(12px)' }, { opacity: 1, transform: 'none' }],
        { duration: 250, delay: 1200, easing: EASE, fill: 'forwards' });
    }));
  }

  doClose() {
    if (this.closing) return;
    this.closing = true;
    const target = this.playlist() ? this.shelfRecord(this.playlist().name) : null;
    if (!target) { this.close.emit(); return; }
    const { s, dx, dy } = this.delta(target);
    this.stage().nativeElement.animate(
      [{ transform: 'none' }, { transform: `translate(${dx}px, ${dy}px) scale(${s})` }],
      { duration: 260, easing: EASE, fill: 'forwards' });
    this.panel().nativeElement.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 120, fill: 'forwards' });
    this.scrim().nativeElement.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, fill: 'forwards' })
      .onfinish = () => this.close.emit();
  }

  step(d: number) {
    const n = this.playlists().length;
    if (!n) return;
    // la vuelta al frente no se anima: se quita la transicion un instante
    const big = this.big().nativeElement;
    big.style.transition = 'none';
    this.flipped.set(false);
    void big.offsetWidth;
    big.style.transition = '';
    this.current.set((this.current() + d + n) % n);
    this.stage().nativeElement.animate(
      [{ opacity: 0, transform: `translateX(${d * 24}px)` }, { opacity: 1, transform: 'none' }],
      { duration: 240, easing: EASE });
  }

  @HostListener('document:keydown', ['$event'])
  onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') this.doClose();
    else if (e.key === 'ArrowLeft') this.step(-1);
    else if (e.key === 'ArrowRight') this.step(1);
  }
}
