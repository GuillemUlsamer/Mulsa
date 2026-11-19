import { Component, ElementRef, OnDestroy, afterNextRender, computed, inject, input, output, signal } from '@angular/core';
import { Playlist } from '../api';

// Medidas del diseno (design_handoff_mulsa_shelf/README.md): portada 176, aire arriba 40,
// base del disco B = 216, fila 310. Todo en px y relativo al borde superior de la fila.
const COVER = 176;
const PAD = 40;
const B = PAD + COVER;
const ROW_H = 310;
const GAP = 34;
// padding lateral del host (shelf.scss): no cuenta como ancho util
const SIDE = 24;
// baldas que se ven siempre, aunque esten vacias
const MIN_ROWS = 4;

interface Slot {
  p: Playlist | null;
  w: number;
  originX: number;
  left: number;
  tagLeft: number;
  tagW: number;
}

// Una playlist es un disco de pie en una balda, con su etiqueta de supermercado debajo.
// El 3D es CSS puro: cada hueco tiene su propia perspectiva, pero todas apuntan al mismo
// punto (encima del centro de la balda), asi que los discos de la izquierda ensenan el
// canto derecho y al reves, como si los miraras desde un solo sitio.
@Component({
  selector: 'app-shelf',
  styleUrl: './shelf.scss',
  templateUrl: './shelf.html',
})
export class Shelf implements OnDestroy {
  playlists = input.required<Playlist[]>();
  select = output<{ p: Playlist; el: HTMLElement }>();

  readonly COVER = COVER;
  readonly B = B;
  readonly ROW_H = ROW_H;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private width = signal(0);
  private observer?: ResizeObserver;

  constructor() {
    // El ancho real solo existe cuando el elemento esta pintado; ResizeObserver lo sigue despues.
    afterNextRender(() => {
      this.width.set(this.host.nativeElement.clientWidth - SIDE * 2);
      this.observer = new ResizeObserver(() => this.width.set(this.host.nativeElement.clientWidth - SIDE * 2));
      this.observer.observe(this.host.nativeElement);
    });
  }

  ngOnDestroy() {
    this.observer?.disconnect();
  }

  // Reparte las playlists en filas de tantos huecos como quepan (minimo 4) segun el ancho; se recalcula sola
  // cuando cambian las playlists o el ancho (computed).
  rows = computed<Slot[][]>(() => {
    const W = Math.max(COVER + GAP, this.width() || 600); // 600 solo antes del primer render
    const per = Math.max(1, Math.floor(W / (COVER + GAP)));
    const slotW = W / per;
    const tagW = Math.min(slotW - 20, COVER - 16);
    const list = this.playlists();
    const rows: Slot[][] = [];
    const count = Math.max(MIN_ROWS, Math.ceil(list.length / per));
    for (let r = 0; r < count; r++) {
      const slots: Slot[] = [];
      for (let j = 0; j < per; j++) {
        const off = W / 2 - slotW * (j + 0.5);
        slots.push({
          p: list[r * per + j] ?? null,
          w: slotW,
          originX: slotW / 2 + off,
          left: (slotW - COVER) / 2,
          tagLeft: (slotW - tagW) / 2,
          tagW,
        });
      }
      rows.push(slots);
    }
    return rows;
  });

  cover(name: string) {
    return `/api/playlists/${encodeURIComponent(name)}/cover`;
  }

  vols(n: number) {
    return n === 1 ? '1 vol.' : `${n} vols.`;
  }
}
