import { Component, ElementRef, afterNextRender, inject, input } from '@angular/core';

@Component({
  selector: 'app-page',
  imports: [],
  templateUrl: './page.html',
  styleUrl: './page.scss',
})
export class Page {
  heading = input.required<string>();
  // fondo gris en el contenido, para separarlo de cabecera y pie (lo usa la estanteria)
  shade = input(false);
  // solo la linea de separacion con cabecera y pie, sin cambiar el fondo
  divided = input(false);
  // logo a la izquierda del titulo (Playlists)
  logo = input(false);

  // cada pantalla entra con un fundido; la salida la hace Api.go() antes de navegar
  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef);
    afterNextRender(() => host.nativeElement.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 120, easing: 'linear' }));
  }
}