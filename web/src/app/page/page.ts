import { Component, input } from '@angular/core';

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
}